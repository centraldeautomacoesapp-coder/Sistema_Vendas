import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import random
import json
import google.generativeai as genai

# Configuração de tela
st.set_page_config(page_title="Delly's Inteligência IA", layout="centered")

# --- 🤖 CONFIGURAÇÃO INTEGRADA DA IA GEMINI (SEGURA VIA SECRETS) ---
CHAVE_API_GEMINI = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=CHAVE_API_GEMINI)

# --- OTIMIZAÇÃO VISUAL PARA CELULAR ---
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

# 📅 CONTROLE DE DATA AJUSTADO PARA O HORÁRIO DE BRASÍLIA
MAPA_DIAS_ING_PORT = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}
data_atual_sistema = pd.Timestamp.now(tz='America/Sao_Paulo').tz_localize(None).normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7]

# --- 📁 SISTEMA DE PERSISTÊNCIA COMPLETO ---
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
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False
if 'cache_ia_gemini' not in st.session_state: st.session_state.cache_ia_gemini = {}

def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def extrair_palavras_produto(linha):
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(linha))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc']
    return [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 2 and p not in ignorar]

def identificar_nicho_cliente(nome_cliente, nome_fantasia=""):
    texto = limpar_texto(nome_cliente) + " " + limpar_texto(nome_fantasia)
    if any(k in texto for k in ['pizza', 'pizzaria', 'massa']): return 'pizzaria'
    if any(k in texto for k in ['burger', 'hamburguer', 'lanche', 'burguer', 'snack', 'sub']): return 'hamburgueria'
    if any(k in texto for k in ['padaria', 'confeitaria', 'pao', 'panificadora', 'doceria']): return 'padaria'
    if any(k in texto for k in ['restaurante', 'buffet', 'comida', 'churrascaria', 'grill', 'cozinha', 'marmita']): return 'restaurante'
    return 'geral'

# --- 🧠 ENGINE DE INTELIGÊNCIA ARTIFICIAL DE BACKGROUND (GEMINI PRO VIA API) ---
def executar_analise_inteligente_gemini(cliente, info_c, produtos_usuario, deixou_de_comprar, bloco_ofertas, tipo_canal="dia"):
    chave_cache = f"{cliente}_{len(bloco_ofertas)}_{tipo_canal}_v2"
    if chave_cache in st.session_state.cache_ia_gemini:
        return st.session_state.cache_ia_gemini[chave_cache]

    nicho = identificar_nicho_cliente(cliente, info_c.get('Fantasia', ''))
    
    prompt = f"""
    Você é o Motor de Inteligência Comercial (Gemini Pro) da distribuidora Delly's.
    Sua função é fazer associações lógicas e comerciais flexíveis entre a lista de ofertas do dia e o histórico do cliente.
    
    NÃO use correspondência exata de nomes. Use inteligência de mercado: se o cliente compra laticínios ou farinhas e há itens similares em oferta, associe-os! Extrapole para garantir ótimas sugestões de venda cruzada para o nicho do cliente.

    REGRAS CRÍTICAS:
    1. PROIBIDO MENCIONAR SABORES NO TEXTO: Omitir completamente palavras de sabores (Ex: Calabresa, Quatro Queijos, Chocolate, Frango, etc). Mantenha apenas o NOME BASE DO PRODUTO, o TAMANHO/EMBALAGEM (ex: UN, KG, CX) e o VALOR (R$).
    2. ZERO REPETIÇÃO: Um produto não pode aparecer em mais de uma lista.
    3. FORMATO WHATSAPP ESPAÇADO: Use quebras de linhas duplas (\\n\\n) entre parágrafos e itens.

    Dados do Cliente:
    - Razão Social: {cliente}
    - Nome Fantasia: {info_c.get('Fantasia', 'Não Definido')}
    - Nicho Comercial: {nicho}

    Histórico Comercial do Cliente (O que ele compra/comprava):
    {", ".join(produtos_usuario[:30])}

    PRODUTOS QUE ELE DEIXOU DE COMPRAR RECENTEMENTE (CHURN):
    {", ".join(deixou_de_comprar[:15])}

    TODAS AS OFERTAS DISPONÍVEIS HOJE NO SISTEMA:
    {" | ".join(bloco_ofertas)}

    Retorne estritamente um JSON válido (sem markdown, sem ```json):
    {{
      "mensagem_transmissao": "Mensagem de abordagem comercial personalizada para o WhatsApp. Deve saudar o cliente pelo nome fantasia (se houver), destacar de 3 a 5 ofertas de hoje que tenham relação lógica com o histórico dele ou itens que ele deixou de comprar, e adicionar sugestões agressivas de venda cruzada ideias para o nicho {nicho}.",
      "caixa_historico_ofertas": "📢 *OPORTUNIDADES DO SEU HISTÓRICO DE COMPRAS:*\\n\\nListe aqui (com ✅) as ofertas de hoje compatíveis com o que ele já conhece ou costumava comprar. Espaçamento duplo \\n\\n.",
      "caixa_venda_cruzada": "🔥 *SUGESTÕES EXCLUSIVAS PARA SEU NICHO DO DIA:*\\n\\nListe aqui (com ✨) as ofertas de hoje que ele NUNCA comprou, mas que são perfeitas para uma {nicho}. Seja generoso nas sugestões baseando-se na lista de ofertas brutas."
    }}
    """
    
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        resposta = model.generate_content(prompt)
        texto_puro = resposta.text.strip()
        
        if texto_puro.startswith("```"):
            texto_puro = texto_puro.split("```")[1]
            if texto_puro.startswith("json"):
                texto_puro = texto_puro[4:]
        
        dados_finais = json.loads(texto_puro.strip())
        st.session_state.cache_ia_gemini[chave_cache] = dados_finais
        return dados_finais
    except Exception as e:
        return {
            "mensagem_transmissao": f"Olá! Separamos ótimas ofertas personalizadas para o seu negócio hoje:\n\n" + "\n\n".join([f"👉 {l}" for l in bloco_ofertas[:4]]),
            "caixa_historico_ofertas": "📢 *OPORTUNIDADES DO SEU HISTÓRICO:*\n\n" + "\n\n".join([f"✅ {l}" for l in bloco_ofertas[:3]]),
            "caixa_venda_cruzada": "🔥 *SUGESTÕES DE VENDA CRUZADA VIA IA:*\n\n" + "\n\n".join([f"✨ {l}" for l in bloco_ofertas[-3:]])
        }

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=600)
def carregar_dados_nuvem():
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_atual, "planilhas_drive")
    if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
    try: gdown.download_folder("[https://drive.google.com/drive/folders/1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF](https://drive.google.com/drive/folders/1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF)", output=pasta_destino, quiet=True)
    except: pass
    
    arquivos_excel = glob.glob(os.path.join(pasta_destino, "**", "*.xlsx"), recursive=True)
    lista_dfs = []
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            c_dt = next((c for c in df.columns if "dt" in str(c).lower() and "entrega" in str(c).lower()), None)
            c_cli = next((c for c in df.columns if "cliente" in str(c).lower()), None)
            c_prod = next((c for c in df.columns if "produto" in str(c).lower()), None)
            c_fat = next((c for c in df.columns if "faturamento" in str(c).lower() and "brut" in str(c).lower()), None)
            c_fil = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower()), None)
            
            if c_dt and c_cli and c_prod and c_fat:
                sel = [c_dt, c_cli, c_prod, c_fat]
                heads = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                if c_fil:
                    sel.append(c_fil); heads.append('Filial')
                sub = df[sel].copy(); sub.columns = heads
                if sub['Faturamento Brut'].dtype == 'object':
                    sub['Faturamento Brut'] = sub['Faturamento Brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['Faturamento Brut'] = pd.to_numeric(sub['Faturamento Brut'], errors='coerce')
                lista_dfs.append(sub)
        except: continue
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cliente'].notna()]
        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], dayfirst=True, errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
        unificado['Cliente_Busca'] = unificado['Cliente'].apply(limpar_texto)
        if 'Filial' not in unificado.columns: unificado['Filial'] = "1"
        return unificado
    
    return pd.DataFrame(columns=['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut', 'Filial', 'Data_Datetime', 'Ano_Mes', 'Produto_Busca', 'Cliente_Busca'])

@st.cache_data(ttl=600)
def carregar_base_clientes_cadastro():
    url = "[https://docs.google.com/spreadsheets/d/1QNiwKklXLpBrc_g21p1GRFs4dfFMze6v/export?format=xlsx](https://docs.google.com/spreadsheets/d/1QNiwKklXLpBrc_g21p1GRFs4dfFMze6v/export?format=xlsx)"
    try:
        df = pd.read_excel(url)
        df.columns = df.columns.str.strip()
        c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "razao" in str(c).lower()), df.columns[0])
        c_fant = next((c for c in df.columns if "fantasia" in str(c).lower() or "nicho" in str(c).lower()), c_cli)
        c_cid = next((c for c in df.columns if "cidade" in str(c).lower() or "munic" in str(c).lower()), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        
        df_reordenado = pd.DataFrame()
        df_reordenado['Cliente'] = df[c_cli].astype(str).str.strip()
        df_reordenado['Nome_Fantasia'] = df[c_fant].astype(str).str.strip() if c_fant in df.columns else ""
        df_reordenado['Cidade'] = df[c_cid].astype(str).str.strip() if c_cid in df.columns else "Não Informada"
        df_reordenado['Cliente_Busca'] = df_reordenado['Cliente'].apply(limpar_texto)
        return df_reordenado
    except:
        return pd.DataFrame(columns=['Cliente', 'Nome_Fantasia', 'Cidade', 'Cliente_Busca'])

with st.spinner("Sincronizando bases de dados e inteligência artificial..."):
    df_total = carregar_dados_nuvem()
    df_clientes = carregar_base_clientes_cadastro()

mapa_cadastro_clientes = {}
if not df_clientes.empty:
    for _, r in df_clientes.iterrows():
        cli_nome = str(r['Cliente']).strip()
        fantasia = str(r['Nome_Fantasia']).strip()
        cidade = str(r['Cidade']).strip()
        info_dict = {
            "Nome": cli_nome, 
            "Fantasia": fantasia if fantasia.lower() != "nan" else "", 
            "Cidade": cidade if cidade.lower() != "nan" else "Não Informada"
        }
        mapa_cadastro_clientes[limpar_texto(cli_nome)] = info_dict

def obter_info_cliente(nome_vendas):
    vendas_limpo = limpar_texto(nome_vendas)
    if Bureau := mapa_cadastro_clientes.get(vendas_limpo): return Bureau
    return {"Nome": nome_vendas, "Fantasia": "Não Localizado", "Cidade": "Não Localizada"}

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

if not df_mes_atual.empty:
    mask_lebon_g = df_mes_atual['Produto_Busca'].str.contains("lebon|seara|doriana|frangosul", na=False)
    clientes_grupo_lebon = set(df_mes_atual[mask_lebon_g]['Cliente'].unique())
else:
    clientes_grupo_lebon = set()

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    if df.empty: return mapa
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    for cli in df['Cliente'].unique():
        if pd.isna(cli) or not str(cli).strip(): continue
        tags = []
        dt_ult = ultimas_compras.get(cli, data_hoje)
        dias_sem_compra = (data_hoje - dt_ult).days
        vendas_mes = df_mes[df_mes['Cliente'] == cli]
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
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = ""
    if cliente_nome in clientes_grupo_lebon:
        html += '<span style="background-color:#E3FCEF; color:#006644; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">LEBON</span>'
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 6</span>'
    return html

# --- HEADER E METAS (CORRIGIDO LINK DE MARCDOWN DENTRO DA STRING) ---
st.image("[https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg](https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg)", use_container_width=True)
st.write("---")

col_tit_meta, col_btn_meta = st.columns([4, 2])
with col_tit_meta: st.markdown("### 📊 Indicadores Gerais")
with col_btn_meta:
    if st.session_state.modo_edicao_metas:
        if st.button("💾 Salvar Metas", key="m_save"):
            st.session_state.modo_edicao_metas = False; salvar_progresso_atual(); st.rerun()
    else:
        if st.button("📝 Editar Metas", key="m_edit"): st.session_state.modo_edicao_metas = True; st.rerun()

mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0'])
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0'])

real_pos_f2 = df_mes_atual[mask_f2]['Cliente'].nunique()
real_pos_f6 = df_mes_atual[mask_f6]['Cliente'].nunique()
real_pos_geral = df_mes_atual[mask_f2 | mask_f6]['Cliente'].nunique()

meta_pos_f2, meta_pos_f6 = int(st.session_state.meta_pos_f2), int(st.session_state.meta_pos_f6)
meta_pos_geral = meta_pos_f2 + meta_pos_f6

real_rob_f2, real_rob_f6 = df_mes_atual[mask_f2]['Faturamento Brut'].sum(), df_mes_atual[mask_f6]['Faturamento Brut'].sum()
real_rob_geral = real_rob_f2 + real_rob_f6

meta_rob_f2, meta_rob_f6 = float(st.session_state.meta_rob_f2), float(st.session_state.meta_rob_f6)
meta_rob_geral = meta_rob_f2 + meta_rob_f6

if st.session_state.modo_edicao_metas:
    c_ed1, c_ed2 = st.columns(2)
    with c_ed1:
        st.session_state.meta_pos_f2 = st.number_input("Meta Pos. F2", value=meta_pos_f2, step=1)
        st.session_state.meta_pos_f6 = st.number_input("Meta Pos. F6", value=meta_pos_f6, step=1)
    with c_ed2:
        st.session_state.meta_rob_f2 = st.number_input("Meta ROB F2 (R$)", value=meta_rob_f2, step=1000.0)
        st.session_state.meta_rob_f6 = st.number_input("Meta ROB F6 (R$)", value=meta_rob_f6, step=1000.0)
else:
    df_indicadores = pd.DataFrame([
        {"Métrica": "🎯 Positivação Geral", "Alvo": meta_pos_geral, "Realizado": f"{real_pos_geral} clis", "Atingimento": f"{(real_pos_geral/meta_pos_geral*100) if meta_pos_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ Filial 2", "Alvo": meta_pos_f2, "Realizado": f"{real_pos_f2} clis", "Atingimento": f"{(real_pos_f2/meta_pos_f2*100) if meta_pos_f2>0 else 0:.1f}%"},
        {"Métrica": "◽ Filial 6", "Alvo": meta_pos_f6, "Realizado": f"{real_pos_f6} clis", "Atingimento": f"{(real_pos_f6/meta_pos_f6*100) if meta_pos_f6>0 else 0:.1f}%"},
        {"Métrica": "💰 Faturamento Geral", "Alvo": f"R$ {meta_rob_geral:,.2f}", "Realizado": f"R$ {real_rob_geral:,.2f}", "Atingimento": f"{(real_rob_geral/meta_rob_geral*100) if meta_rob_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ F2", "Alvo": f"R$ {meta_rob_f2:,.2f}", "Realizado": f"R$ {real_rob_f2:,.2f}", "Atingimento": f"{(real_rob_f2/meta_rob_f2*100) if meta_rob_f2>0 else 0:.1f}%"},
        {"Métrica": "◽ F6", "Alvo": f"R$ {meta_rob_f6:,.2f}", "Realizado": f"R$ {real_rob_f6:,.2f}", "Atingimento": f"{(real_rob_f6/meta_rob_f6*100) if meta_rob_f6>0 else 0:.1f}%"}
    ])
    st.table(df_indicadores)

st.write("---")

# --- NAVEGAÇÃO ---
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

c_nav5, _ = st.columns([1, 1])
with c_nav5:
    if st.button("🧠 Assistente IA", type="primary" if st.session_state.aba_atual == "🧠 Assistente" else "secondary"): st.session_state.aba_atual = "🧠 Assistente"; st.rerun()

st.write("---")

# --- ABA 1: PAINEL DE OFERTAS (CONVERTIDO DE OCR PARA CAMPO DE TEXTO COLADO) ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    tipo_lista = st.radio("Canal Ativo:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    
    # Substituído file_uploader por text_area tradicional para digitação estável e direta
    with st.expander("📝 Inserir / Atualizar Bloco de Ofertas (Colar Texto)", expanded=False):
        st.markdown("**Cole aqui o texto ou lista das novas ofertas (uma por linha):**")
        texto_ofertas_colado = st.text_area("Lista de Produtos:", value="\n".join(st.session_state.get(id_memoria, [])), height=180, label_visibility="collapsed")
        
        if st.button("🚀 Processar e Atualizar Fila"):
            if texto_ofertas_colado.strip():
                linhas_limpas = [l.strip() for l in texto_ofertas_colado.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas_limpas
                
                nova_fila = {}
                todos_clientes_validos = sorted(list(df_total['Cliente'].dropna().unique()))
                
                for cli in todos_clientes_validos:
                    if cli in st.session_state.excluidos_permanente or cli in st.session_state[id_excluidos]: continue
                    nova_fila[cli] = linhas_limpas
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.success(f"Sucesso! {len(linhas_limpas)} itens salvos. Fila de transmissão atualizada.")
                st.rerun()
            else:
                st.warning("Insira algum texto antes de atualizar.")

    fila_ativa = st.session_state.get(id_fila)
    if not fila_ativa:
        st.info("Nenhum cliente na fila de transmissão para as ofertas atuais.")
    else:
        clis_lista = list(fila_ativa.keys())
        st.markdown(f"🎯 Clientes em Potencial na Fila: **{len(clis_lista)}**")
        cli_corrente = clis_lista[0]
        
        info_c = obter_info_cliente(cli_corrente)
        
        produtos_usuario = df_total[df_total['Cliente'] == cli_corrente]['Produto'].dropna().unique().tolist()
        produtos_mes_atual = df_mes_atual[df_mes_atual['Cliente'] == cli_corrente]['Produto'].dropna().unique().tolist()
        deixou_de_comprar = list(set(produtos_usuario) - set(produtos_mes_atual))
        
        bloco_total_ofertas = st.session_state.get(id_memoria, [])
        
        with st.spinner("O Gemini Pro está avaliando o melhor mix de ofertas..."):
            resultado_ia = executar_analise_inteligente_gemini(
                cli_corrente, info_c, produtos_usuario, deixou_de_comprar, bloco_total_ofertas, "relampago" if "⚡" in tipo_lista else "dia"
            )
        
        st.markdown(f"### 🏢 {cli_corrente}")
        st.markdown(obter_badges_html(cli_corrente), unsafe_allow_html=True)
        st.write("")
        
        st.markdown("**Mensagem Comercial Integrada (IA Pro):**")
        st.code(resultado_ia.get("mensagem_transmissao", ""), language=None)
        
        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("✅ Confirmar Envio"):
                st.session_state.envios_hoje += 1; st.session_state[id_excluidos].add(cli_corrente)
                del st.session_state[id_fila][cli_corrente]; salvar_progresso_atual(); st.rerun()
        with c_act2:
            if st.button("❌ Pular Cliente"):
                del st.session_state[id_fila][cli_corrente]; st.rerun()

# --- ABA 2: ALERTAS RADAR ---
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Ocultos / Churn")
    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if dados["dias"] > 30:
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"]})
    if not lista_alertas:
        st.success("Excelente! Nenhum cliente em zona crítica de sumiço.")
    else:
        df_al = pd.DataFrame(lista_alertas).sort_values(by="Dias", ascending=False)
        for idx, row in df_al.iterrows():
            st.warning(f"⚠️ {row['Cliente']} - Sem comprar há {row['Dias']} dias.")

# --- ABA 3: CONSULTA CLIENTE ---
elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Central de Atendimento ao Cliente")
    lista_clis = sorted(list(df_total['Cliente'].dropna().unique()))
    c_sel = st.selectbox("Escolha o Cliente para analisar:", [""] + lista_clis)
    
    if c_sel:
        inf = obter_info_cliente(c_sel)
        st.markdown(f"### 🏢 {c_sel}")
        if inf['Fantasia']: st.markdown(f"⭐ **Fantasia:** {inf['Fantasia']}")
        st.markdown(f"📍 **Cidade:** {inf['Cidade']} | Nicho: `{identificar_nicho_cliente(c_sel, inf.get('Fantasia',''))}`")
        st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
        
        produtos_usuario = df_total[df_total['Cliente'] == c_sel]['Produto'].dropna().unique().tolist()
        produtos_mes_atual = df_mes_atual[df_mes_atual['Cliente'] == c_sel]['Produto'].dropna().unique().tolist()
        deixou_de_comprar = list(set(produtos_usuario) - set(produtos_mes_atual))
        
        st.write("---")
        st.markdown("#### 🛒 Histórico Comercial (O que ele já compra)")
        st.write(", ".join(produtos_usuario[:20]) if produtos_usuario else "Nenhum histórico mapeado.")
        
        st.write("---")
        st.markdown("#### 🛑 Produtos que DEIXOU DE COMPRAR neste mês")
        if deixou_de_comprar:
            for item in deixou_de_comprar[:10]:
                st.markdown(f"• ` {item} `")
        else:
            st.success("Cliente manteve o portfólio ativo este mês.")
            
        ofertas_dia = st.session_state.get("memoria_ofertas_cruas_dia", [])
        ofertas_rel = st.session_state.get("memoria_ofertas_cruas_rel", [])
        bloco_total_ofertas = ofertas_dia + ofertas_rel
        
        if bloco_total_ofertas:
            with st.spinner("Conectando ao banco de dados para analisar ofertas e cross-selling..."):
                resultado_ia = executar_analise_inteligente_gemini(c_sel, inf, produtos_usuario, deixou_de_comprar, bloco_total_ofertas, "dia")
            
            st.write("---")
            st.markdown("#### ☀️ Oportunidades Baseadas no Histórico + Churn")
            st.code(resultado_ia.get("caixa_historico_ofertas", ""), language=None)
            
            st.write("")
            st.markdown("#### ✨ Vendas Cruzadas Inteligentes Sugeridas")
            st.code(resultado_ia.get("caixa_venda_cruzada", ""), language=None)

# --- ABA 4: CONSULTA PRODUTO ---
elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Consulta por Produto")
    p_sel = st.selectbox("Selecione o Produto:", [""] + sorted(list(df_total['Produto'].dropna().unique())))
    if p_sel:
        df_p = df_total[df_total['Produto'] == p_sel]
        st.metric("Total Faturado", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
        st.markdown("#### Maiores Compradores:")
        st.dataframe(df_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(5))

# --- ABA 5: ASSISTENTE IA ---
elif st.session_state.aba_atual == "🧠 Assistente":
    st.subheader("🧠 Assistente de Inteligência Artificial Integrado")
    
    opcao_ia = st.radio("Selecione a ferramenta de inteligência:", ["💬 Resposta Rápida (Gemini Flash + Tabelas)", "📊 Status do Motor Comercial (Gemini Pro)"], horizontal=True)
    
    st.write("---")
    
    if opcao_ia == "💬 Resposta Rápida (Gemini Flash + Tabelas)":
        st.markdown("#### ⚡ Consultor de Estratégias e Vendas")
        st.write("Digite suas dúvidas. O Gemini Flash analisará as planilhas do Drive em tempo real para te dar respostas instantâneas.")
        
        pergunta_usuario = st.text_input("Sua pergunta:", placeholder="Ex: Quais produtos o cliente X costuma comprar?")
        
        if pergunta_usuario:
            with st.spinner("Analisando base de dados..."):
                try:
                    resumo_clientes = df_total.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).to_string() if not df_total.empty else "Sem clientes"
                    produtos_mais_vendidos = df_total['Produto'].value_counts().nlargest(10).index.tolist() if not df_total.empty else []
                    
                    prompt_contexto = f"""
                    Você é o Assistente Ágil de Vendas da Delly's. O usuário te fez uma pergunta direta.
                    Responda de forma sucinta e inteligente usando o contexto básico do sistema se necessário:
                    
                    Maiores Clientes: {resumo_clientes}
                    Principais Produtos em Giro: {', '.join(produtos_mais_vendidos)}
                    Ofertas Ativas na Memória: {st.session_state.get('memoria_ofertas_cruas_dia', [])}
                    
                    Pergunta do Usuário: "{pergunta_usuario}"
                    """
                    
                    model_flash = genai.GenerativeModel("gemini-1.5-flash")
                    resposta_rapida = model_flash.generate_content(prompt_contexto)
                    st.info(resposta_rapida.text)
                except Exception as e:
                    st.error(f"Erro ao processar a pergunta: {e}")
                    
    elif opcao_ia == "📊 Status do Motor Comercial (Gemini Pro)":
        st.markdown("#### ⚙️ Configuração Automática de Vendas Cruzadas")
        st.success("O Motor Gemini Pro está ativo em segundo plano! 🚀")
        st.write("""
        Você não precisa executar comandos manuais aqui. O algoritmo avançado do Gemini Pro foi incorporado 
        diretamente no **Painel de Ofertas** e na **Consulta de Clientes**. 
        """)
