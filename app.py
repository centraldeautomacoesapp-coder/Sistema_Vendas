import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import json
import google.generativeai as genai

# Configuração de tela limpa e direta
st.set_page_config(page_title="Delly's Inteligência IA", layout="centered")

# --- 🤖 CONFIGURAÇÃO DA IA GEMINI ---
CHAVE_API_GEMINI = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=CHAVE_API_GEMINI)

# --- OTIMIZAÇÃO VISUAL MOBILE ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span { font-size: 16px !important; }
    h3 { font-size: 20px !important; font-weight: bold !important; }
    h4 { font-size: 18px !important; }
    div.stButton > button {
        width: 100% !important; height: 46px !important; font-size: 13px !important;
        font-weight: bold !important; margin: 0 !important; border-radius: 8px !important;
    }
    code { font-size: 14px !important; line-height: 1.6 !important; white-space: pre-wrap !important; }
    </style>
""", unsafe_allow_html=True)

# 📅 CONTROLE DE TEMPO E DATAS (BRASÍLIA)
data_atual_sistema = pd.Timestamp.now(tz='America/Sao_Paulo').tz_localize(None).normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m')

# --- 📁 SISTEMA DE PERSISTÊNCIA ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIVO_PROGRESSO):
        try:
            with open(ARQUIVO_PROGRESSO, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

def salvar_progresso_atual():
    dados = {
        "data_ultimo_acesso": data_hoje_str,
        "envios_hoje": st.session_state.get("envios_hoje", 0),
        "fila_ofertas_dia": st.session_state.get("fila_ofertas_dia", None),
        "fila_ofertas_relampago": st.session_state.get("fila_ofertas_relampago", None),
        "memoria_ofertas_cruas_dia": st.session_state.get("memoria_ofertas_cruas_dia", []),
        "memoria_ofertas_cruas_rel": st.session_state.get("memoria_ofertas_cruas_rel", []),
        "excluidos_ofertas_dia": list(st.session_state.get("excluidos_ofertas_dia", set())),
        "excluidos_ofertas_relampago": list(st.session_state.get("excluidos_ofertas_relampago", set())),
        "excluidos_permanente": list(st.session_state.get("excluidos_permanente", set())),
        "meta_pos_f2": st.session_state.get("meta_pos_f2", 0),
        "meta_pos_f6": st.session_state.get("meta_pos_f6", 0),
        "meta_pos_marcas": st.session_state.get("meta_pos_marcas", 0),
        "meta_rob_f2": st.session_state.get("meta_rob_f2", 0.0),
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f: json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")

if 'envios_hoje' not in st.session_state:
    if ultimo_acesso == data_hoje_str:
        st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
        st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
        st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
        st.session_state.memoria_ofertas_cruas_dia = progresso_backup.get("memoria_ofertas_cruas_dia", [])
        st.session_state.memoria_ofertas_cruas_rel = progresso_backup.get("memoria_ofertas_cruas_rel", [])
        st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
        st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))
    else:
        st.session_state.envios_hoje = 0
        st.session_state.fila_ofertas_dia = None
        st.session_state.fila_ofertas_relampago = None
        st.session_state.memoria_ofertas_cruas_dia = []
        st.session_state.memoria_ofertas_cruas_rel = []
        st.session_state.excluidos_ofertas_dia = set()
        st.session_state.excluidos_ofertas_relampago = set()

if 'excluidos_permanente' not in st.session_state: st.session_state.excluidos_permanente = set(progresso_backup.get("excluidos_permanente", []))
if 'meta_pos_f2' not in st.session_state: st.session_state.meta_pos_f2 = progresso_backup.get("meta_pos_f2", 0)
if 'meta_pos_f6' not in st.session_state: st.session_state.meta_pos_f6 = progresso_backup.get("meta_pos_f6", 0)
if 'meta_pos_marcas' not in st.session_state: st.session_state.meta_pos_marcas = progresso_backup.get("meta_pos_marcas", 0)
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False
if 'cache_ia_gemini' not in st.session_state: st.session_state.cache_ia_gemini = {}

def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def identificar_nicho_cliente(nome_cliente, nome_fantasia=""):
    texto = limpar_texto(nome_cliente) + " " + limpar_texto(nome_fantasia)
    if any(k in texto for k in ['pizza', 'pizzaria', 'massa']): return 'pizzaria'
    if any(k in texto for k in ['burger', 'hamburguer', 'lanche', 'burguer', 'snack', 'sub']): return 'hamburgueria'
    if any(k in texto for k in ['padaria', 'confeitaria', 'pao', 'panificadora', 'doceria']): return 'padaria'
    if any(k in texto for k in ['restaurante', 'buffet', 'comida', 'churrascaria', 'grill', 'cozinha', 'marmita']): return 'restaurante'
    return 'geral'

# --- 🧠 CONEXÃO EXPANDIDA E ROBUSTA DE BANCO DE DADOS ---
@st.cache_data(ttl=600)
def carregar_dados_vendas():
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_atual, "planilhas_drive")
    if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
    try: gdown.download_folder("https://drive.google.com/drive/folders/1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF", output=pasta_destino, quiet=True)
    except: pass
    
    arquivos_excel = glob.glob(os.path.join(pasta_destino, "**", "*.xlsx"), recursive=True)
    lista_dfs = []
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            
            # Mapeamento ultra flexível de colunas para evitar quebras por pequenas variações de nome
            c_dt = next((c for c in df.columns if any(k in str(c).lower() for k in ["dt", "data", "delivery", "faturamento"])), None)
            c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "raz" in str(c).lower()), None)
            c_prod = next((c for c in df.columns if "produto" in str(c).lower() or "desc" in str(c).lower()), None)
            c_fat = next((c for c in df.columns if "faturamento" in str(c).lower() or "brut" in str(c).lower() or "valor" in str(c).lower()), None)
            c_fil = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower()), None)
            
            if c_dt and c_cli and c_prod and c_fat:
                sub = df[[c_dt, c_cli, c_prod, c_fat]].copy()
                sub.columns = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                if c_fil:
                    sub['Filial'] = df[c_fil].astype(str).str.strip()
                else:
                    sub['Filial'] = "1"
                    
                if sub['Faturamento Brut'].dtype == 'object':
                    sub['Faturamento Brut'] = sub['Faturamento Brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['Faturamento Brut'] = pd.to_numeric(sub['Faturamento Brut'], errors='coerce')
                lista_dfs.append(sub)
        except: continue
        
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cliente'].notna()]
        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
        unificado['Cliente_Busca'] = unificado['Cliente'].apply(limpar_texto)
        return unificado
    return pd.DataFrame()

@st.cache_data(ttl=600)
def carregar_base_clientes_cadastro():
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_clientes = os.path.join(diretorio_atual, "planilhas_clientes")
    if not os.path.exists(pasta_clientes): os.makedirs(pasta_clientes)
    try: gdown.download_folder("https://drive.google.com/drive/folders/1f_miT6ZGR6cxUeD2IlZ4BduIivzUVEdu", output=pasta_clientes, quiet=True)
    except: pass
    
    arquivos_excel = glob.glob(os.path.join(pasta_clientes, "**", "*.xlsx"), recursive=True)
    lista_dfs_cli = []
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "raz" in str(c).lower()), None)
            c_fant = next((c for c in df.columns if "fantasia" in str(c).lower() or "nome" in str(c).lower()), None)
            c_cid = next((c for c in df.columns if "cidade" in str(c).lower() or "munic" in str(c).lower() or "bairro" in str(c).lower()), None)
            
            if c_cli:
                sub = pd.DataFrame()
                sub['Cliente'] = df[c_cli].astype(str).str.strip()
                sub['Nome_Fantasia'] = df[c_fant].astype(str).str.strip() if c_fant else ""
                sub['Cidade'] = df[c_cid].astype(str).str.strip() if c_cid else "Não Informada"
                sub['Cliente_Busca'] = sub['Cliente'].apply(limpar_texto)
                lista_dfs_cli.append(sub)
        except: continue
        
    if lista_dfs_cli:
        return pd.concat(lista_dfs_cli, ignore_index=True).drop_duplicates(subset=['Cliente_Busca'])
    return pd.DataFrame()

with st.spinner("Sincronizando bancos de dados da Delly's..."):
    df_total = carregar_dados_vendas()
    df_clientes = carregar_base_clientes_cadastro()

# Alinhamento automático inteligente de mês para evitar telas zeradas
mes_exibicao = mes_atual_referencia
if not df_total.empty:
    meses_com_dados = df_total['Ano_Mes'].dropna().unique()
    if mes_atual_referencia not in meses_com_dados and len(meses_com_dados) > 0:
        mes_exibicao = max(meses_com_dados)
        st.sidebar.warning(f"Exibindo dados de {mes_exibicao} (Planilha sem registros de {mes_atual_referencia}).")

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_exibicao] if not df_total.empty else pd.DataFrame()

# Lógica das Marcas Exclusivas
termo_marcas = "lebon|seara|doriana|frangosul"
if not df_mes_atual.empty:
    mask_marcas_mes = df_mes_atual['Produto_Busca'].str.contains(termo_marcas, na=False)
    clientes_marcas_positivados = set(df_mes_atual[mask_marcas_mes]['Cliente'].unique())
else:
    clientes_marcas_positivados = set()

mapa_cadastro_clientes = {}
if not df_clientes.empty:
    for _, r in df_clientes.iterrows():
        mapa_cadastro_clientes[r['Cliente_Busca']] = {
            "Nome": r['Cliente'], "Fantasia": r['Nome_Fantasia'], "Cidade": r['Cidade']
        }

def obter_info_cliente(nome_vendas):
    vendas_limpo = limpar_texto(nome_vendas)
    if b := mapa_cadastro_clientes.get(vendas_limpo): return b
    return {"Nome": nome_vendas, "Fantasia": "", "Cidade": "Não Localizada"}

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    if df.empty: return mapa
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    for cli in df['Cliente'].unique():
        tags = []
        dt_ult = ultimas_compras.get(cli, data_hoje)
        dias_sem_compra = (data_hoje - dt_ult).days
        vendas_mes = df_mes[df_mes['Cliente'] == cli] if not df_mes.empty else pd.DataFrame()
        
        if not vendas_mes.empty:
            tags.append("POSITIVADO")
            filiais = vendas_mes['Filial'].astype(str).str.strip().unique()
            if any(f in filiais for f in ['2', '02', '2.0']): tags.append("FILIAL 2")
            if any(f in filiais for f in ['6', '06', '6.0']): tags.append("FILIAL 6")
        else:
            tags.append("NÃO POSITIVADO")
        if dias_sem_compra > 30: tags.append("SUMIDO")
        mapa[cli] = {"tags": tags, "dias": dias_sem_compra}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

def obter_badges_html(cliente_nome):
    html = ""
    if cliente_nome in clientes_marcas_positivados:
        html += '<span style="background-color:#E3FCEF; color:#006644; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">MARCAS EXCLUSIVAS</span>'
    info = dict_carteira.get(cliente_nome, {"tags": []})
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
    return html

# --- 🎯 CABEÇALHO DO SISTEMA ---
st.markdown("# 🟢 Delly's Inteligência IA")
st.write("---")

col_tit_meta, col_btn_meta = st.columns([4, 2])
with col_tit_meta: st.markdown("### 📊 Indicadores Gerais")
with col_btn_meta:
    if st.session_state.modo_edicao_metas:
        if st.button("💾 Salvar Metas", key="m_save"):
            st.session_state.modo_edicao_metas = False; salvar_progresso_atual(); st.rerun()
    else:
        if st.button("📝 Editar Metas", key="m_edit"): st.session_state.modo_edicao_metas = True; st.rerun()

mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0']) if not df_mes_atual.empty else pd.Series()
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0']) if not df_mes_atual.empty else pd.Series()

real_pos_f2 = df_mes_atual[mask_f2]['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_f6 = df_mes_atual[mask_f6]['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_geral = df_mes_atual['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_marcas = len(clientes_marcas_positivados)

meta_pos_f2, meta_pos_f6 = int(st.session_state.meta_pos_f2), int(st.session_state.meta_pos_f6)
meta_pos_marcas = int(st.session_state.meta_pos_marcas)
meta_pos_geral = meta_pos_f2 + meta_pos_f6

real_rob_f2 = df_mes_atual[mask_f2]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_f6 = df_mes_atual[mask_f6]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_geral = real_rob_f2 + real_rob_f6

meta_rob_f2, meta_rob_f6 = float(st.session_state.meta_rob_f2), float(st.session_state.meta_rob_f6)
meta_rob_geral = meta_rob_f2 + meta_rob_f6

if st.session_state.modo_edicao_metas:
    c_ed1, c_ed2 = st.columns(2)
    with c_ed1:
        st.session_state.meta_pos_f2 = st.number_input("Meta Pos. F2", value=meta_pos_f2, step=1)
        st.session_state.meta_pos_f6 = st.number_input("Meta Pos. F6", value=meta_pos_f6, step=1)
        st.session_state.meta_pos_marcas = st.number_input("Meta Pos. Marcas Excl.", value=meta_pos_marcas, step=1)
    with c_ed2:
        st.session_state.meta_rob_f2 = st.number_input("Meta ROB F2 (R$)", value=meta_rob_f2, step=1000.0)
        st.session_state.meta_rob_f6 = st.number_input("Meta ROB F6 (R$)", value=meta_rob_f6, step=1000.0)
else:
    df_indicadores = pd.DataFrame([
        {"Métrica": "🎯 Positivação Geral", "Alvo": meta_pos_geral, "Realizado": f"{real_pos_geral} clis", "Atingimento": f"{(real_pos_geral/meta_pos_geral*100) if meta_pos_geral>0 else 0:.1f}%"},
        {"Métrica": "⭐ Marcas Exclusivas (Lebon/Seara)", "Alvo": meta_pos_marcas, "Realizado": f"{real_pos_marcas} clis", "Atingimento": f"{(real_pos_marcas/meta_pos_marcas*100) if meta_pos_marcas>0 else 0:.1f}%"},
        {"Métrica": "◽ Filial 2", "Alvo": meta_pos_f2, "Realizado": f"{real_pos_f2} clis", "Atingimento": f"{(real_pos_f2/meta_pos_f2*100) if meta_pos_f2>0 else 0:.1f}%"},
        {"Métrica": "◽ Filial 6", "Alvo": meta_pos_f6, "Realizado": f"{real_pos_f6} clis", "Atingimento": f"{(real_pos_f6/meta_pos_f6*100) if meta_pos_f6>0 else 0:.1f}%"},
        {"Métrica": "💰 Faturamento Geral", "Alvo": f"R$ {meta_rob_geral:,.2f}", "Realizado": f"R$ {real_rob_geral:,.2f}", "Atingimento": f"{(real_rob_geral/meta_rob_geral*100) if meta_rob_geral>0 else 0:.1f}%"}
    ])
    st.table(df_indicadores)

st.write("---")

# --- NAVEGAÇÃO COMPLETA RESTAURADA ---
c_nav1, c_nav2 = st.columns(2)
with c_nav1:
    if st.button("🟢 Painel Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"): st.session_state.aba_atual = "🟢 Ofertas"; st.rerun()
with c_nav2:
    if st.button("🚨 Alertas Radar", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"): st.session_state.aba_atual = "🚨 Alertas"; st.rerun()

c_nav3, c_nav4 = st.columns(2)
with c_nav3:
    if st.button("🔍 Consulta Cliente", type="primary" if st.session_state.aba_atual == "🔍 Cliente" else "secondary"): st.session_state.aba_atual = "🔍 Cliente"; st.rerun()
with c_nav4:
    if st.button("📦 Consulta Produto", type="primary" if st.session_state.aba_atual == "📦 Produto" else "secondary"): st.session_state.aba_atual = "📦 Produto"; st.rerun()

c_nav5, c_nav6 = st.columns(2)
with c_nav5:
    if st.button("🧠 Assistente IA", type="primary" if st.session_state.aba_atual == "🧠 Assistente" else "secondary"): st.session_state.aba_atual = "🧠 Assistente"; st.rerun()
with c_nav6:
    if st.button("🏷️ Marcas Exclusivas", type="primary" if st.session_state.aba_atual == "🏷️ Marcas" else "secondary"): st.session_state.aba_atual = "🏷️ Marcas"; st.rerun()

st.write("---")

# --- ENGINE AUXILIAR DA IA ---
def executar_analise_inteligente_gemini(cliente, info_c, produtos_usuario, deixou_de_comprar, bloco_ofertas, tipo_canal="dia"):
    chave_cache = f"{cliente}_{len(bloco_ofertas)}_{tipo_canal}_v3"
    if chave_cache in st.session_state.cache_ia_gemini: return st.session_state.cache_ia_gemini[chave_cache]
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Gere uma mensagem comercial curta para o cliente {cliente} focando em cross-selling de produtos alimentícios com base em seu histórico: {produtos_usuario[:15]}."
        res = model.generate_content(prompt).text
        dados = {"mensagem_transmissao": res, "caixa_historico_ofertas": "Ofertas sugeridas", "caixa_venda_cruzada": "Cross selling"}
        st.session_state.cache_ia_gemini[chave_cache] = dados
        return dados
    except:
        return {"mensagem_transmissao": "Olá! Verifique nossas ofertas exclusivas do dia.", "caixa_historico_ofertas": "", "caixa_venda_cruzada": ""}

# --- ABAS DE INTERFACE ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    if df_total.empty:
        st.info("Aguardando carregamento correto das planilhas do Drive para povoar a fila.")
    else:
        tipo_lista = st.radio("Canal Ativo:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
        id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
        id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
        id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
        
        with st.expander("📝 Inserir Novas Ofertas"):
            texto_ofertas_colado = st.text_area("Lista de Produtos (Um por linha):", value="\n".join(st.session_state.get(id_memoria, [])), height=120)
            if st.button("🚀 Atualizar Fila"):
                linhas = [l.strip() for l in texto_ofertas_colado.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas
                st.session_state[id_fila] = {c: linhas for c in df_total['Cliente'].dropna().unique() if c not in st.session_state[id_excluidos]}
                salvar_progresso_atual(); st.rerun()

        fila_ativa = st.session_state.get(id_fila)
        if fila_ativa:
            cli_corrente = list(fila_ativa.keys())[0]
            inf = obter_info_cliente(cli_corrente)
            st.markdown(f"### 🏢 {cli_corrente}")
            st.markdown(obter_badges_html(cli_corrente), unsafe_allow_html=True)
            
            res_ia = executar_analise_inteligente_gemini(cli_corrente, inf, [], [], st.session_state[id_memoria])
            st.code(res_ia["mensagem_transmissao"])
            
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                if st.button("✅ Confirmar Envio"):
                    st.session_state.envios_hoje += 1; st.session_state[id_excluidos].add(cli_corrente)
                    del st.session_state[id_fila][cli_corrente]; salvar_progresso_atual(); st.rerun()
            with c_a2:
                if st.button("❌ Pular"): del st.session_state[id_fila][cli_corrente]; st.rerun()

elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Ocultos / Churn")
    alertas = [{"Cliente": c, "Dias Sem Compra": d["dias"]} for c, d in dict_carteira.items() if d["dias"] > 30]
    if alertas: st.dataframe(pd.DataFrame(alertas).sort_values(by="Dias Sem Compra", ascending=False))
    else: st.success("Nenhum cliente sumido da carteira!")

elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Central de Atendimento ao Cliente")
    if not df_total.empty:
        c_sel = st.selectbox("Escolha o Cliente:", [""] + sorted(list(df_total['Cliente'].unique())))
        if c_sel:
            inf = obter_info_cliente(c_sel)
            st.markdown(f"### 🏢 {inf['Nome']} (Fantasia: {inf['Fantasia']})")
            st.markdown(f"📍 **Cidade:** {inf['Cidade']}")
            st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
            
            prods = df_total[df_total['Cliente'] == c_sel]['Produto'].dropna().unique()
            st.markdown("#### Histórico Comercial")
            st.write(", ".join(list(prods)[:30]))

elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Consulta por Produto")
    if not df_total.empty:
        p_sel = st.selectbox("Selecione o Produto:", [""] + sorted(list(df_total['Produto'].dropna().unique())))
        if p_sel:
            df_p = df_total[df_total['Produto'] == p_sel]
            st.metric("Total Faturado", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
            st.dataframe(df_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10))

elif st.session_state.aba_atual == "🧠 Assistente":
    st.subheader("🧠 Consultor Ágil de Vendas")
    p_user = st.text_input("Faça uma pergunta sobre metas ou produtos:")
    if p_user:
        model_flash = genai.GenerativeModel("gemini-1.5-flash")
        st.info(model_flash.generate_content(f"Responda comercialmente: {p_user}").text)

# --- 🏷️ NOVA ABA: CONTROLE DE MARCAS EXCLUSIVAS COMPLETO ---
elif st.session_state.aba_atual == "🏷️ Marcas":
    st.subheader("🏷️ Painel de Positivação: Lebon, Seara, Doriana e Frangosul")
    
    if df_total.empty:
        st.info("Carregue a planilha de histórico para liberar o cruzamento de Marcas.")
    else:
        # Encontra clientes que compraram historicamente mas não no mês de análise
        mask_marcas_total = df_total['Produto_Busca'].str.contains(termo_marcas, na=False)
        clientes_historico_marcas = set(df_total[mask_marcas_total]['Cliente'].unique())
        clientes_churn_marcas = clientes_historico_marcas - clientes_marcas_positivados
        
        # Encontra clientes da planilha cadastral que nunca compraram as marcas exclusivas
        todos_clientes_cadastro = set(df_clientes['Cliente'].unique()) if not df_clientes.empty else set(df_total['Cliente'].unique())
        clientes_nunca_marcas = todos_clientes_cadastro - clientes_historico_marcas
        
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            st.metric("⚠️ Churn no Mês (Já comprou, zerado agora)", len(clientes_churn_marcas))
        with c_m2:
            st.metric("🎯 Potenciais (Nunca compraram as Marcas)", len(clientes_nunca_marcas))
            
        st.write("---")
        st.markdown("### 🚨 Churn de Marcas (Recuperar Urgente)")
        if clientes_churn_marcas:
            df_recuperar = pd.DataFrame([obter_info_cliente(c) for c in clientes_churn_marcas])
            st.dataframe(df_recuperar[['Nome', 'Fantasia', 'Cidade']].drop_duplicates(), use_container_width=True)
        else:
            st.success("Nenhum cliente de marcas exclusivas em Churn no mês.")
            
        st.write("---")
        st.markdown("### 🚀 Clientes Disponíveis para Primeira Positivação")
        if clientes_nunca_marcas:
            df_potenciais = pd.DataFrame([obter_info_cliente(c) for c in clientes_nunca_marcas])
            st.dataframe(df_potenciais[['Nome', 'Fantasia', 'Cidade']].drop_duplicates(), use_container_width=True)
        else:
            st.info("Todos os clientes cadastrados já compraram marcas exclusivas em algum momento.")
