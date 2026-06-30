import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import random
import json
import streamlit.components.v1 as components

# Configuração de tela
st.set_page_config(page_title="Delly's Inteligência", layout="centered")

# --- OTIMIZAÇÃO VISUAL PARA CELULAR ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span {
        font-size: 16px !important;
    }
    h3 {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    h4 {
        font-size: 18px !important;
    }
    div.stButton > button {
        width: 100% !important;
        height: 50px !important;
        font-size: 15px !important;
        font-weight: bold !important;
        margin-bottom: 5px !important;
        border-radius: 8px !important;
    }
    code {
        font-size: 14px !important;
    }
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
dia_semana_hoje = MAPA_DIAS_ING_PORT.get(pd.Timestamp.now(tz='America/Sao_Paulo').weekday(), "Segunda-feira")

# --- 📁 SISTEMA DE PERSISTÊNCIA ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIVO_PROGRESSO):
        try:
            with open(ARQUIVO_PROGRESSO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def salvar_progresso_atual():
    dados = {
        "data_ultimo_acesso": data_hoje_str,
        "envios_hoje": st.session_state.envios_hoje,
        "fila_ofertas_dia": st.session_state.fila_ofertas_dia,
        "fila_ofertas_relampago": st.session_state.fila_ofertas_relampago,
        "memoria_ofertas_cruas_dia": st.session_state.memoria_ofertas_cruas_dia,
        "memoria_ofertas_cruas_rel": st.session_state.memoria_ofertas_cruas_rel,
        "excluidos_ofertas_dia": list(st.session_state.excluidos_ofertas_dia),
        "excluidos_ofertas_relampago": list(st.session_state.excluidos_ofertas_relampago),
        "excluidos_permanente": list(st.session_state.excluidos_permanente),
        "enviados_supervisor_mes": list(st.session_state.enviados_supervisor_mes)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")
mes_ultimo_acesso = ultimo_acesso[:7] if ultimo_acesso else ""

if 'data_ultimo_acesso' not in st.session_state:
    st.session_state.data_ultimo_acesso = data_hoje_str

if ultimo_acesso == data_hoje_str:
    if 'envios_hoje' not in st.session_state:
        st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
    if 'fila_ofertas_dia' not in st.session_state:
        st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
    if 'fila_ofertas_relampago' not in st.session_state:
        st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
    if 'memoria_ofertas_cruas_dia' not in st.session_state:
        st.session_state.memoria_ofertas_cruas_dia = progresso_backup.get("memoria_ofertas_cruas_dia", [])
    if 'memoria_ofertas_cruas_rel' not in st.session_state:
        st.session_state.memoria_ofertas_cruas_rel = progresso_backup.get("memoria_ofertas_cruas_rel", [])
    if 'excluidos_ofertas_dia' not in st.session_state:
        st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
    if 'excluidos_ofertas_relampago' not in st.session_state:
        st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))
else:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.memoria_ofertas_cruas_dia = []
    st.session_state.memoria_ofertas_cruas_rel = []
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()

if mes_ultimo_acesso == mes_atual_referencia:
    if 'enviados_supervisor_mes' not in st.session_state:
        st.session_state.enviados_supervisor_mes = set(progresso_backup.get("enviados_supervisor_mes", []))
else:
    st.session_state.enviados_supervisor_mes = set()

if 'excluidos_permanente' not in st.session_state:
    st.session_state.excluidos_permanente = set(progresso_backup.get("excluidos_permanente", []))

if not progresso_backup or ultimo_acesso != data_hoje_str:
    salvar_progresso_atual()

if 'aba_atual' not in st.session_state:
    st.session_state.aba_atual = "🟢 Ofertas"
if 'texto_supervisor_gerado' not in st.session_state:
    st.session_state.texto_supervisor_gerado = ""
if 'clientes_processados_aguardando' not in st.session_state:
    st.session_state.clientes_processados_aguardando = []

# --- CALLBACK PARA ALTERAÇÃO DE ABA ---
def navegar_para_aba(nome_aba):
    st.session_state.aba_atual = nome_aba

# --- AUXILIARES ---
def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def extrair_palavras_produto(linha):
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(linha))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    return [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 1 and p not in ignorar]

def gerar_mensagem_humanizada(ofertas, tipo_lista):
    saudacoes = ["Olá! Tudo bem?", "Buenas! Tudo certo por aí?", "Oi! Como estão as coisas?"]
    termo_oferta = "ofertas relâmpago do dia" if tipo_lista == "relampago" else "ofertas do dia"
    introducoes = [f"Separei aqui as melhores {termo_oferta} exclusivas para você:\n\n", f"Olha só as {termo_oferta} que separei hoje para o seu estoque:\n\n"]
    fechamentos = ["\n\nMe avisa aqui se posso garantir o seu pedido antes que acabe! 👍", "\n\nQual vamos aproveitar hoje? 🚀"]
    msg = f"{random.choice(saudacoes)} {random.choice(introducoes)}"
    for of in ofertas:
        msg += f"👉 {of}\n"
    msg += random.choice(fechamentos)
    return msg

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=600)
def carregar_dados_nuvem():
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_atual, "planilhas_drive")
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    try:
        gdown.download_folder("https://drive.google.com/drive/folders/1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF", output=pasta_destino, quiet=True)
    except Exception:
        pass
    
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
            c_fil = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower() or "cod.filial" in str(c).lower()), None)
            
            if c_dt and c_cli and c_prod and c_fat:
                sel = [c_dt, c_cli, c_prod, c_fat]
                heads = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                if c_fil:
                    sel.append(c_fil)
                    heads.append('Filial')
                sub = df[sel].copy()
                sub.columns = heads
                if sub['Faturamento Brut'].dtype == 'object':
                    sub['Faturamento Brut'] = sub['Faturamento Brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['Faturamento Brut'] = pd.to_numeric(sub['Faturamento Brut'], errors='coerce')
                lista_dfs.append(sub)
        except Exception:
            continue
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cliente'].notna()]
        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], dayfirst=True, errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
        unificado['Cliente_Busca'] = unificado['Cliente'].apply(limpar_texto)
        if 'Filial' not in unificado.columns:
            unificado['Filial'] = "1"
        return unificado
    return pd.DataFrame()

@st.cache_data(ttl=600)
def carregar_base_clientes_cadastro():
    url = "https://docs.google.com/spreadsheets/d/1QNiwKklXLpBrc_g21p1GRFs4dfFMze6v/export?format=xlsx"
    try:
        df = pd.read_excel(url)
        df.columns = df.columns.str.strip()
        c_cli, c_fant, c_cid = None, None, None
        for col in df.columns:
            col_lower = str(col).lower()
            if "cliente" in col_lower or "razao" in col_lower or "razão" in col_lower:
                c_cli = col
            elif "fantasia" in col_lower or "nicho" in col_lower or "nome" in col_lower:
                c_fant = col
            elif "cidade" in col_lower or "munic" in col_lower:
                c_cid = col
        
        if not c_cli:
            c_cli = df.columns[0]
        if not c_fant:
            c_fant = c_cli
        if not c_cid:
            c_cid = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        df_reordenado = pd.DataFrame()
        df_reordenado['Cliente'] = df[c_cli].astype(str).str.strip()
        df_reordenado['Nome_Fantasia'] = df[c_fant].astype(str).str.strip() if c_fant in df.columns else ""
        df_reordenado['Cidade'] = df[c_cid].astype(str).str.strip() if c_cid in df.columns else "Não Informada"
        df_reordenado['Cliente_Busca'] = df_reordenado['Cliente'].apply(limpar_texto)
        return df_reordenado
    except Exception:
        return pd.DataFrame(columns=['Cliente', 'Nome_Fantasia', 'Cidade', 'Cliente_Busca'])

with st.spinner("Sincronizando bases de dados..."):
    df_total = carregar_dados_nuvem()
    df_clientes = carregar_base_clientes_cadastro()

if df_total.empty:
    st.warning("Base de dados de vendas vazia.")
    st.stop()

# Montagem do mapa do Drive
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
        if fantasia:
            mapa_cadastro_clientes[limpar_texto(fantasia)] = info_dict

def obter_info_cliente(nome_vendas):
    if pd.isna(nome_vendas) or not str(nome_vendas).strip():
        return {"Nome": "Desconhecido", "Fantasia": "Não Informado", "Cidade": "Não Informada"}
    vendas_limpo = limpar_texto(nome_vendas)
    if vendas_limpo in mapa_cadastro_clientes:
        return mapa_cadastro_clientes[vendas_limpo]
    vendas_sem_codigo = re.sub(r'^\d+\s*[-–_]?\s*', '', vendas_limpo).strip()
    if vendas_sem_codigo in mapa_cadastro_clientes:
        return mapa_cadastro_clientes[vendas_sem_codigo]
    for chave_cadastro, dados in mapa_cadastro_clientes.items():
        if chave_cadastro in vendas_limpo or vendas_limpo in chave_cadastro or chave_cadastro in vendas_sem_codigo:
            return dados
    return {"Nome": nome_vendas, "Fantasia": "Não Localizado", "Cidade": "Não Localizada"}

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    for cli in df['Cliente'].unique():
        if pd.isna(cli) or str(cli).lower() == 'nan' or not str(cli).strip():
            continue
        tags = []
        dt_ult = ultimas_compras.get(cli, data_hoje)
        dias_sem_compra = (data_hoje - dt_ult).days
        vendas_mes = df_mes[df_mes['Cliente'] == cli]
        if not vendas_mes.empty:
            tags.append("POSITIVADO")
            filiais = vendas_mes['Filial'].astype(str).str.strip().unique()
            if any(f in filiais for f in ['2', '02', '2.0']):
                tags.append("FILIAL 2")
            if any(f in filiais for f in ['6', '06', '6.0']):
                tags.append("FILIAL 6")
        else:
            tags.append("NÃO POSITIVADO")
        if dias_sem_compra > 30:
            tags.append("SUMIDO")
        mapa[cli] = {"tags": tags, "dias": dias_sem_compra, "data_ult": dt_ult}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

# --- TAGS COMPACTAS EM FLEXBOX PARA CELULAR ---
def obter_badges_html(cliente_nome, ja_reportado=False):
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = '<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; align-items: center;">'
    for tag in info["tags"]:
        if tag == "POSITIVADO":
            html += '<span style="background-color:#00875A; color:white; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px; white-space:nowrap;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO":
            html += '<span style="background-color:#DE350B; color:white; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px; white-space:nowrap;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2":
            html += '<span style="background-color:#0052CC; color:white; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px; white-space:nowrap;">FILIAL 2</span>'
        elif tag == "FILIAL 6":
            html += '<span style="background-color:#FF8B00; color:white; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px; white-space:nowrap;">FILIAL 6</span>'
        elif tag == "SUMIDO":
            html += '<span style="background-color:#6554C0; color:white; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px; white-space:nowrap;">⚠️ SUMIDO</span>'
    if ja_reportado:
        html += '<span style="background-color:#FFC400; color:#111; padding:2px 5px; border-radius:4px; font-weight:bold; font-size:11px; white-space:nowrap;">📅 JÁ REPORTADO</span>'
    html += '</div>'
    return html

# Regras Globais de Venda Cruzada
REGRAS_VENDA_CRUZADA = {
    "pizzaria": ["Calabresa Montadas", "Muçarela Bloco", "Presunto Cozido", "Bacon Defumado", "Molho de Tomate Pouch"], 
    "pizza": ["Calabresa Montadas", "Muçarela Bloco", "Presunto Cozido"],
    "lanches": ["Hambúrguer Bovino", "Batata Frita Pré-Frita", "Queijo Cheddar", "Maionese Balde", "Pão de Hambúrguer"], 
    "burguer": ["Hambúrguer Bovino", "Queijo Cheddar", "Pão de Hambúrguer"],
    "pastelaria": ["Massa de Pastel Rolo", "Óleo de Fritura Coamo", "Carne Moída Confeccionada", "Queijo Prato"],
    "pastel": ["Massa de Pastel Rolo", "Óleo de Fritura Coamo"],
    "churrascaria": ["Linguiça Toscana", "Picanha Importada", "Alcatra Completa", "Carvão Vegetal"], 
    "churrasco": ["Linguiça Toscana", "Picanha Importada", "Carvão Vegetal"]
}

# --- CABEÇALHO DA MARCA ---
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)
if st.button("🔄 Sincronizar Base Geral"):
    st.cache_data.clear()
    st.toast("Sincronizando...", icon="🔄")
    st.rerun()

# --- 📊 INDICADORES SUPERIORES ---
st.write("---")
f2_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 2" in v["tags"])
f6_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 6" in v["tags"])
nao_pos_mes = sum(1 for c, v in dict_carteira.items() if "NÃO POSITIVADO" in v["tags"])

st.markdown(f"""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 5px solid #00875A; margin-bottom:8px;"><p style="margin:0; font-size:12px; color:#555; font-weight:bold;">🟢 POSITIVADOS FILIAL 2</p><h4 style="margin:0; font-size:16px; font-weight:bold;">{f2_pos} Clientes</h4></div>""", unsafe_allow_html=True)
st.markdown(f"""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 5px solid #FF8B00; margin-bottom:8px;"><p style="margin:0; font-size:12px; color:#555; font-weight:bold;">🟠 POSITIVADOS FILIAL 6</p><h4 style="margin:0; font-size:16px; font-weight:bold;">{f6_pos} Clientes</h4></div>""", unsafe_allow_html=True)
st.markdown(f"""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 5px solid #DE350B; margin-bottom:8px;"><p style="margin:0; font-size:12px; color:#555; font-weight:bold;">🔴 NÃO POSITIVADOS NO MÊS</p><h4 style="margin:0; font-size:16px; font-weight:bold;">{nao_pos_mes} Clientes</h4></div>""", unsafe_allow_html=True)

st.write("---")

# --- MENUS DE NAVEGAÇÃO EM GRADE 2x2 ---
col_row1_1, col_row1_2 = st.columns(2)
with col_row1_1:
    st.button("🟢 Painel Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary", on_click=navegar_para_aba, args=("🟢 Ofertas",))
with col_row1_2:
    st.button("🚨 Alertas Radar", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary", on_click=navegar_para_aba, args=("🚨 Alertas",))

col_row2_1, col_row2_2 = st.columns(2)
with col_row2_1:
    st.button("🔍 Consulta Cliente", type="primary" if st.session_state.aba_atual == "🔍 Cliente" else "secondary", on_click=navegar_para_aba, args=("🔍 Cliente",))
with col_row2_2:
    st.button("📦 Consulta Produto", type="primary" if st.session_state.aba_atual == "📦 Produto" else "secondary", on_click=navegar_para_aba, args=("📦 Produto",))

st.write("---")

# --- 🟢 ABA 1: OFERTAS ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão (Sem Filtros Geográficos)")
    st.markdown(f"🗓️ Hoje é **{dia_semana_hoje}** | Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    tipo_lista = st.radio("Canal:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    tipo_msg = "dia" if "☀️" in tipo_lista else "relampago"
    
    with st.expander("📝 Inserir Bloco de Ofertas"):
        txt_novas = st.text_area("Cole as linhas de ofertas aqui:", height=100, key=f"txt_{id_fila}")
        if st.button("🚀 Processar Linhas", key=f"btn_proc_{id_fila}"):
            if txt_novas.strip():
                linhas = [l.strip() for l in txt_novas.split('\n') if l.strip()]
                st.session_state[id_memoria] = lines if 'lines' in globals() else linhas
                
                prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
                prod_busca = {}
                for p in prod_to_clientes.keys():
                    prod_busca[p] = limpar_texto(p)
                
                nova_fila = {}
                clientes_com_compra_mes_atual = df_mes_atual['Cliente'].unique()
                
                for linha in linhas:
                    chaves = extrair_palavras_produto(linha)
                    if not chaves:
                        continue
                    
                    combs = []
                    for orig, busca in prod_busca.items():
                        match_ok = True
                        for c in chaves:
                            if c not in busca:
                                match_ok = False
                                break
                        if match_ok:
                            combs.append(orig)
                    
                    interessados = set()
                    for c in combs:
                        interessados.update(prod_to_clientes[c])
                    
                    for cli in interessados:
                        if pd.isna(cli) or str(cli).lower() == 'nan':
                            continue
                        if cli in st.session_state.excluidos_permanente:
                            if cli in clientes_com_compra_mes_atual:
                                st.session_state.excluidos_permanente.remove(cli)
                            else:
                                continue
                        if cli in st.session_state[id_excluidos]:
                            continue
                        if cli not in nova_fila:
                            nova_fila[cli] = []
                        if linha not in nova_fila[cli]:
                            nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.success(f"Fila total gerada com sucesso!")
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info(f"Nenhum cliente na fila de transmissão para envio.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
        
        cliente_atual = clientes_restantes[0]
        ofertas_cliente = fila_ativa[cliente_atual]
        mensagem_pronta = gerar_mensagem_humanizada(ofertas_cliente, tipo_msg)
        
        cad_info = obter_info_cliente(cliente_atual)
        
        st.markdown(f"### 🏢 {cliente_atual}")
        
        if cad_info['Fantasia'] and cad_info['Fantasia'] not in ["Não Localizado", "Não Informado"]:
            st.markdown(f"⭐ **Fantasia:** {cad_info['Fantasia']}")
            
        # Ajuste Crítico: Força a tag de cidade a ficar embaixo em bloco sem quebrar o nome ao meio
        st.markdown(f'<div style="color: #403294; font-weight: bold; background-color: #EAE6FF; padding: 2px 6px; border-radius: 4px; font-size: 12px; border: 1px solid #C0B6F2; display: inline-block; margin-top: 2px; margin-bottom: 4px; white-space: nowrap;">📍 {cad_info["Cidade"]}</div>', unsafe_allow_html=True)
            
        st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
        st.write("")
        
        st.code(mensagem_pronta, language=None)
        
        if st.button("✅ Enviado", type="primary", key=f"env_{str(cliente_atual)[:5]}"):
            st.session_state.envios_hoje += 1
            st.session_state[id_excluidos].add(cliente_atual)
            del st.session_state[id_fila][cliente_atual]
            salvar_progresso_atual()
            st.rerun()
            
        if st.button("❌ Excluir da Fila", key=f"ex_{str(cliente_atual)[:5]}"):
            st.session_state.excluidos_permanente.add(cliente_atual)
            del st.session_state[id_fila][cliente_atual]
            salvar_progresso_atual()
            st.rerun()

# --- 🔍 ABA 2: CONSULTA POR CLIENTE ---
elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Consulta Detalhada do Cliente")
    
    lista_clientes_busca = sorted(list(df_total['Cliente'].dropna().unique()))
    cliente_selecionado = st.selectbox("Selecione um cliente para analisar:", [""] + lista_clientes_busca)
    
    if cliente_selecionado:
        cad_info = obter_info_cliente(cliente_selecionado)
        
        st.markdown(f"### 🏢 {cliente_selecionado}")
        
        if cad_info['Fantasia'] and cad_info['Fantasia'] not in ["Não Localizado", "Não Informado"]:
            st.markdown(f"⭐ **Fantasia:** {cad_info['Fantasia']}")
            
        # Ajuste Crítico: Cidade embaixo de forma limpa e visível
        st.markdown(f'<div style="color: #403294; font-weight: bold; background-color: #EAE6FF; padding: 2px 6px; border-radius: 4px; font-size: 12px; border: 1px solid #C0B6F2; display: inline-block; margin-top: 2px; margin-bottom: 4px; white-space: nowrap;">📍 {cad_info["Cidade"]}</div>', unsafe_allow_html=True)
            
        st.markdown(obter_badges_html(cliente_selecionado), unsafe_allow_html=True)
        st.write("")
        
        df_cli = df_total[df_total['Cliente'] == cliente_selecionado]
        carteira_info = dict_carteira.get(cliente_selecionado, {"dias": 0})
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Dias sem Comprar", f"{carteira_info['dias']} dias")
        with col2:
            st.metric("Faturamento Histórico", f"R$ {df_cli['Faturamento Brut'].sum():,.2f}")
            
        st.markdown("#### 🔝 Top 10 Produtos Mais Comprados")
        if not df_cli.empty:
            top_produtos = df_cli.groupby('Produto')['Faturamento Brut'].agg(['sum', 'count']).nlargest(10, 'sum')
            top_produtos.columns = ['Faturamento Acumulado (R$)', 'Qtd Pedidos']
            st.dataframe(top_produtos, use_container_width=True)
            
            produtos_historicos = set(df_cli['Produto'].dropna().unique())
            produtos_mes_atual = set(df_mes_atual[df_mes_atual['Cliente'] == cliente_selecionado]['Produto'].dropna().unique())
            deixou_de_comprar = produtos_historicos - produtos_mes_atual
            
            st.markdown("#### 🛑 Produtos que o cliente deixou de comprar no mês atual")
            if deixou_de_comprar:
                df_importancia = df_cli[df_cli['Produto'].isin(deixou_de_comprar)].groupby('Produto')['Faturamento Brut'].sum().sort_values(ascending=False)
                for prod_item, fat_item in df_importancia.items():
                    st.markdown(f"💔 **{prod_item}** *(Faturamento histórico interno: R$ {fat_item:,.2f})*")
            else:
                st.success("✅ Excelente! O cliente comprou todos os seus principais produtos históricos neste mês.")
                
            st.markdown("#### 💡 Recomendações de Venda Cruzada")
            texto_busca_nicho = limpar_texto(cad_info['Fantasia']) + " " + limpar_texto(cliente_selecionado)
            sugestoes_encontradas = []
            for chave, itens in REGRAS_VENDA_CRUZADA.items():
                if chave in texto_busca_nicho:
                    for it in itens:
                        if it not in sugestoes_encontradas:
                            sugestoes_encontradas.append(it)
            
            if sugestoes_encontradas:
                for sug in sugestoes_encontradas:
                    st.markdown(f"🛒 Sugestão: **{sug}** (Item de alto consumo para o nicho deste cliente)")
            else:
                st.info("Nenhuma sugestão padronizada de nicho mapeada para o nome deste cliente.")
        else:
            st.info("Nenhum histórico localizado.")

# --- 📦 ABA 3: CONSULTA POR PRODUTO ---
elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Consulta de Clientes por Produto (Filtro por Descrição)")
    
    lista_produtos_busca = sorted(list(df_total['Produto'].dropna().unique()))
    produto_selecionado = st.selectbox("Selecione um produto abaixo para ver quem compra:", [""] + lista_produtos_busca)
    
    if produto_selecionado:
        st.markdown(f"### 📋 Clientes Compradores de: **{produto_selecionado}**")
        
        df_prod = df_total[df_total['Produto'] == produto_selecionado]
        if not df_prod.empty:
            compradores = df_prod.groupby('Cliente')['Faturamento Brut'].agg(['sum', 'count']).reset_index()
            compradores.columns = ['Cliente', 'Faturamento Acumulado (R$)', 'Vezes Comprado']
            
            cidades_mapeadas = []
            for _, r in compradores.iterrows():
                info_c = obter_info_cliente(r['Cliente'])
                cidades_mapeadas.append(info_c['Cidade'])
            
            compradores['📍 Cidade (Filtro Drive)'] = cidades_mapeadas
            compradores = compradores.sort_values(by='Faturamento Acumulado (R$)', ascending=False)
            
            st.dataframe(compradores[['Cliente', '📍 Cidade (Filtro Drive)', 'Faturamento Acumulado (R$)', 'Vezes Comprado']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de venda para a descrição selecionada.")

# --- 🚨 ABA 4: ALERTAS ---
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200, key="txt_sup_area_fix")
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id=\"copyBtn\" style=\"width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;\">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                const text = {texto_js_safe};
                navigator.clipboard.writeText(text);
                this.innerText = '✅ Copiado com sucesso!';
                setTimeout(() => {{ this.innerText = '📋 Copiar Relatório'; }}, 2000);
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                    if f"chk_{c_nome}" in st.session_state:
                        st.session_state[f"chk_{c_nome}"] = False
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.toast("Clientes marcados como reportados!", icon="💾")
                st.rerun()
            st.write("---")

    st.markdown("### Filtros da Lista")
    filtro_status = st.selectbox("Filtrar por status de envio:", ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"])
    busca_alerta = st.text_input("🔍 Buscar Cliente em Alerta:", placeholder="Digite o nome...").strip()

    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0:
            continue
        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            ja_reportado = cli in st.session_state.enviados_supervisor_mes
            if filtro_status == "Apenas Não Reportados" and ja_reportado:
                continue
            if filtro_status == "Apenas Reportados" and not ja_reportado:
                continue
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"], "Reportado": ja_reportado})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas)
    if not df_alertas_visuais.empty:
        df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
    if busca_alerta and not df_alertas_visuais.empty:
        termo_limpo = limpar_texto(busca_alerta)
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: termo_limpo in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info(f"Nenhum cliente em rota crítica localizado.")
    else:
        st.markdown(f"📊 Exibindo **{len(df_alertas_visuais)}** clientes em atraso:")
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            if f"chk_{c_nome}" not in st.session_state:
                st.session_state[f"chk_{c_nome}"] = False
            
            with st.container():
                st.checkbox(f"🏢 {c_nome} ({row['Dias']} dias s/ compra)", key=f"chk_{c_nome}")
                info_c = obter_info_cliente(c_nome)
                
                if info_c['Fantasia'] and info_c['Fantasia'] not in ["Não Localizado", "Não Informado"]:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;*Fantasia: {info_c['Fantasia']}*")
                
                # Ajuste Crítico no Alerta: Mantém o recuo e empurra a tag de cidade para baixo da Fantasia de forma inline-block
                st.markdown(f'<div style="color: #403294; font-weight: bold; background-color: #EAE6FF; padding: 2px 5px; border-radius: 4px; font-size: 11px; border: 1px solid #C0B6F2; display: inline-block; margin-top: 2px; margin-bottom: 2px; margin-left: 20px; white-space: nowrap;">📍 {info_c["Cidade"]}</div>', unsafe_allow_html=True)
                
                # Renderiza os chips reduzidos e organizados
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{obter_badges_html(c_nome, row['Reportado'])}", unsafe_allow_html=True)
            st.write("---")
        
        if st.button("⚡ GERAR RELATÓRIO DOS SELECIONADOS", type="primary"):
            novo_texto_acumulado = ""
            clientes_selecionados_na_rodada = []
            
            for idx, row in df_alertas_visuais.iterrows():
                c_nome = row["Cliente"]
                if st.session_state.get(f"chk_{c_nome}", False):
                    clientes_selecionados_na_rodada.append(c_nome)
                    status_txt = "Sumido" if row["Dias"] > 30 else "Pendente"
                    novo_texto_acumulado += f"📌 {c_nome} ({status_txt} - {row['Dias']} dias sem comprar)\n"
                    
                    df_cli_h = df_total[df_total['Cliente'] == c_nome]
                    if not df_cli_h.empty:
                        top_itens = df_cli_h.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                        novo_texto_acumulado += "    🔹 Mais Comprados pelo Cliente:\n"
                        for item in top_itens:
                            novo_texto_acumulado += f"        ▪️ {item}\n"
                    else:
                        novo_texto_acumulado += "    🔹 Sem histórico recente registrado\n"
                    
                    info_cad = obter_info_cliente(c_nome)
                    texto_analise_nicho = limpar_texto(info_cad['Fantasia']) + " " + limpar_texto(c_nome)
                    sugestoes_seg = []
                    for chave, itens_sugeridos in REGRAS_VENDA_CRUZADA.items():
                        if chave in texto_analise_nicho:
                            for item in itens_sugeridos:
                                if item not in sugestoes_seg:
                                    sugestoes_seg.append(item)
                    if sugestoes_seg:
                        novo_texto_acumulado += "    💡 Itens Sugeridos p/ Prospecção:\n"
                        for sug in sugestoes_seg[:4]:
                            novo_texto_acumulado += f"        ▪️ {sug}\n"
                    novo_texto_acumulado += "\n"
            
            st.session_state.texto_supervisor_gerado = novo_texto_acumulado
            st.session_state.clientes_processados_aguardando = clientes_selecionados_na_rodada
            salvar_progresso_atual()
            st.rerun()
