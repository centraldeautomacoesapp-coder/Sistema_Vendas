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

# --- OTIMIZAÇÃO VISUAL PARA CELULAR (Fontes maiores e botões robustos) ---
st.markdown("""
    <style>
    /* Estilização global de textos para leitura mobile */
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
    /* Botões grandes e fáceis de tocar no celular */
    div.stButton > button {
        width: 100% !important;
        height: 48px !important;
        font-size: 15px !important;
        font-weight: bold !important;
        margin-bottom: 8px !important;
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

# --- 📁 SISTEMA DE PERSISTÊNCIA COMPLETO ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIVO_PROGRESSO):
        try:
            with open(ARQUIVO_PROGRESSO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
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
        "enviados_supervisor_mes": list(st.session_state.enviados_supervisor_mes),
        # Persistência das Metas Manuais
        "meta_pos_f2": st.session_state.get("meta_pos_f2", 0),
        "meta_pos_f6": st.session_state.get("meta_pos_f6", 0),
        "meta_rob_f2": st.session_state.get("meta_rob_f2", 0.0),
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except:
        pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")
mes_ultimo_acesso = ultimo_acesso[:7] if ultimo_acesso else ""

if 'data_ultimo_acesso' not in st.session_state:
    st.session_state.data_ultimo_acesso = data_hoje_str

if ultimo_acesso == data_hoje_str:
    if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
    if 'fila_ofertas_dia' not in st.session_state: st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
    if 'fila_ofertas_relampago' not in st.session_state: st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
    if 'memoria_ofertas_cruas_dia' not in st.session_state: st.session_state.memoria_ofertas_cruas_dia = progresso_backup.get("memoria_ofertas_cruas_dia", [])
    if 'memoria_ofertas_cruas_rel' not in st.session_state: st.session_state.memoria_ofertas_cruas_rel = progresso_backup.get("memoria_ofertas_cruas_rel", [])
    if 'excluidos_ofertas_dia' not in st.session_state: st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
    if 'excluidos_ofertas_relampago' not in st.session_state: st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))
else:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.memoria_ofertas_cruas_dia = []
    st.session_state.memoria_ofertas_cruas_rel = []
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()

if mes_ultimo_acesso == mes_atual_referencia:
    if 'enviados_supervisor_mes' not in st.session_state: st.session_state.enviados_supervisor_mes = set(progresso_backup.get("enviados_supervisor_mes", []))
else:
    st.session_state.enviados_supervisor_mes = set()

if 'excluidos_permanente' not in st.session_state:
    st.session_state.excluidos_permanente = set(progresso_backup.get("excluidos_permanente", []))

# Inicialização das metas da memória
if 'meta_pos_f2' not in st.session_state: st.session_state.meta_pos_f2 = progresso_backup.get("meta_pos_f2", 0)
if 'meta_pos_f6' not in st.session_state: st.session_state.meta_pos_f6 = progresso_backup.get("meta_pos_f6", 0)
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False

if not progresso_backup or ultimo_acesso != data_hoje_str:
    salvar_progresso_atual()

if 'busca_direta_cliente' not in st.session_state: st.session_state.busca_direta_cliente = ""
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'texto_supervisor_gerado' not in st.session_state: st.session_state.texto_supervisor_gerado = ""
if 'clientes_processados_aguardando' not in st.session_state: st.session_state.clientes_processados_aguardando = []

# --- AUXILIARES ---
def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def extrair_palavras_produto(linha):
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(linha))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    return [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 1 and p not in ignorar]

def gerar_mensagem_humanizada(ofertas, tipo_lista):
    saudacoes = ["Olá! Tudo bem?", "Buenas! Tudo certo por aí?", "Oi! Como estão as coisas?"]
    termo_oferta = "ofertas relâmpago do dia" if tipo_lista == "relampago" else "ofertas do dia"
    introducoes = [
        f"Separei aqui as melhores {termo_oferta} exclusivas para você:\n\n",
        f"Olha só as {termo_oferta} que separei hoje para o seu estoque:\n\n"
    ]
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
    if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
    try:
        gdown.download_folder("https://drive.google.com/drive/folders/1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF", output=pasta_destino, quiet=True)
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
        
        if not c_cli: c_cli = df.columns[0]
        if not c_fant: c_fant = c_cli
        if not c_cid: c_cid = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        df_reordenado = pd.DataFrame()
        df_reordenado['Cliente'] = df[c_cli].astype(str).str.strip()
        df_reordenado['Nome_Fantasia'] = df[c_fant].astype(str).str.strip() if c_fant in df.columns else ""
        df_reordenado['Cidade'] = df[c_cid].astype(str).str.strip() if c_cid in df.columns else "Não Informada"
        df_reordenado['Cliente_Busca'] = df_reordenado['Cliente'].apply(limpar_texto)
        return df_reordenado
    except:
        return pd.DataFrame(columns=['Cliente', 'Nome_Fantasia', 'Cidade', 'Cliente_Busca'])

with st.spinner("Sincronizando bases de dados..."):
    df_total = carregar_dados_nuvem()
    df_clientes = carregar_base_clientes_cadastro()

if df_total.empty:
    st.warning("Base de dados de vendas vazia.")
    st.stop()

# Mapeamento do Drive
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

# --- 🚀 COMPUTAÇÃO DO GRUPO UNIFICADO LEBON & MARCAS ---
# Lebon, Seara, Doriana e Frangosul formam um único cálculo chamado LEBON
mask_lebon_g = df_mes_atual['Produto_Busca'].apply(lambda x: any(kw in str(x) for kw in ["lebon", "seara", "doriana", "frangosul"]))
clientes_grupo_lebon = set(df_mes_atual[mask_lebon_g]['Cliente'].unique())

def calcular_marcas_foco(df_mes):
    marcas_dict = {
        "LEBON (Grupo)": ["lebon", "seara", "doriana", "frangosul"],
        "FRIVATTI": ["frivatti"],
        "MCCAIN": ["mccain"],
        "CONFRESCOR": ["confrescor"],
        "BRASA": ["brasa"],
        "CERATTI": ["ceratti"]
    }
    resultados = {}
    for nome, kws in marcas_dict.items():
        m_mask = df_mes['Produto_Busca'].apply(lambda x: any(kw in str(x) for kw in kws))
        resultados[nome] = df_mes[m_mask]['Cliente'].nunique()
    return resultados

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    for cli in df['Cliente'].unique():
        if pd.isna(cli) or str(cli).lower() == 'nan' or not str(cli).strip(): continue
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
        mapa[cli] = {"tags": tags, "dias": dias_sem_compra, "data_ult": dt_ult}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

def obter_badges_html(cliente_nome):
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = ""
    # Tag Estratégica do Grupo Lebon
    if cliente_nome in clientes_grupo_lebon:
        html += '<span style="background-color:#E3FCEF; color:#006644; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">LEBON</span>'
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">⚠️ SUMIDO</span>'
    return html

# --- CABEÇALHO DA MARCA ---
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# --- 📊 NOVO CABEÇALHO ESTRUTURADO DE METAS (FONTES MENORES DE REFERÊNCIA) ---
st.write("---")

col_tit_meta, col_btn_meta = st.columns([4, 2])
with col_tit_meta:
    st.markdown("### 📊 Indicadores Gerais do Mês")
with col_btn_meta:
    if st.session_state.modo_edicao_metas:
        if st.button("💾 Salvar Metas", key="meta_salvar_btn"):
            st.session_state.modo_edicao_metas = False
            salvar_progresso_atual()
            st.rerun()
    else:
        if st.button("📝 Editar Metas", key="meta_editar_btn"):
            st.session_state.modo_edicao_metas = True
            st.rerun()

# Filtragens de Filiais para os cálculos
mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0'])
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0'])

# 1. Seção POSITIVAÇÕES
st.markdown("<p style='font-size:14px; font-weight:bold; color:#111; margin-bottom:5px; text-transform: uppercase; letter-spacing: 0.5px;'>📌 POSITIVAÇÕES</p>", unsafe_allow_html=True)
real_pos_f2 = df_mes_atual[mask_f2]['Cliente'].nunique()
real_pos_f6 = df_mes_atual[mask_f6]['Cliente'].nunique()

c_p1, c_p2, c_p3 = st.columns(3)
with c_p1:
    if st.session_state.modo_edicao_metas:
        st.session_state.meta_pos_f2 = st.number_input("Filial 2 Meta (Clis)", value=int(st.session_state.meta_pos_f2), step=1)
    else:
        st.markdown(f"<span style='font-size:13px; color:#444;'>Filial 2 Meta: <b>{st.session_state.meta_pos_f2}</b></span>", unsafe_allow_html=True)
with c_p2:
    st.markdown(f"<span style='font-size:13px; color:#444;'>Realizado: <b>{real_pos_f2} clis</b></span>", unsafe_allow_html=True)
with c_p3:
    perf_p2 = (real_pos_f2 / st.session_state.meta_pos_f2 * 100) if st.session_state.meta_pos_f2 > 0 else 0.0
    st.markdown(f"<span style='font-size:13px; color:#444;'>Perf: <b>{perf_p2:.1f}%</b></span>", unsafe_allow_html=True)

c_p4, c_p5, c_p6 = st.columns(3)
with c_p4:
    if st.session_state.modo_edicao_metas:
        st.session_state.meta_pos_f6 = st.number_input("Filial 6 Meta (Clis)", value=int(st.session_state.meta_pos_f6), step=1)
    else:
        st.markdown(f"<span style='font-size:13px; color:#444;'>Filial 6 Meta: <b>{st.session_state.meta_pos_f6}</b></span>", unsafe_allow_html=True)
with c_p5:
    st.markdown(f"<span style='font-size:13px; color:#444;'>Realizado: <b>{real_pos_f6} clis</b></span>", unsafe_allow_html=True)
with c_p6:
    perf_p6 = (real_pos_f6 / st.session_state.meta_pos_f6 * 100) if st.session_state.meta_pos_f6 > 0 else 0.0
    st.markdown(f"<span style='font-size:13px; color:#444;'>Perf: <b>{perf_p6:.1f}%</b></span>", unsafe_allow_html=True)

st.write("") # Linha em branco separadora

# 2. Seção ROB (Faturamento)
st.markdown("<p style='font-size:14px; font-weight:bold; color:#111; margin-bottom:5px; text-transform: uppercase; letter-spacing: 0.5px;'>💰 ROB (Faturamento)</p>", unsafe_allow_html=True)
real_rob_f2 = df_mes_atual[mask_f2]['Faturamento Brut'].sum()
real_rob_f6 = df_mes_atual[mask_f6]['Faturamento Brut'].sum()

c_r1, c_r2, c_r3 = st.columns(3)
with c_r1:
    if st.session_state.modo_edicao_metas:
        st.session_state.meta_rob_f2 = st.number_input("Filial 2 ROB Meta (R$)", value=float(st.session_state.meta_rob_f2), step=1000.0)
    else:
        st.markdown(f"<span style='font-size:13px; color:#444;'>Filial 2 Meta: <b>R$ {st.session_state.meta_rob_f2:,.2f}</b></span>", unsafe_allow_html=True)
with c_r2:
    st.markdown(f"<span style='font-size:13px; color:#444;'>Realizado: <b>R$ {real_rob_f2:,.2f}</b></span>", unsafe_allow_html=True)
with c_r3:
    perf_r2 = (real_rob_f2 / st.session_state.meta_rob_f2 * 100) if st.session_state.meta_rob_f2 > 0 else 0.0
    st.markdown(f"<span style='font-size:13px; color:#444;'>Perf: <b>{perf_r2:.1f}%</b></span>", unsafe_allow_html=True)

c_r4, c_r5, c_r6 = st.columns(3)
with c_r4:
    if st.session_state.modo_edicao_metas:
        st.session_state.meta_rob_f6 = st.number_input("Filial 6 ROB Meta (R$)", value=float(st.session_state.meta_rob_f6), step=1000.0)
    else:
        st.markdown(f"<span style='font-size:13px; color:#444;'>Filial 6 Meta: <b>R$ {st.session_state.meta_rob_f6:,.2f}</b></span>", unsafe_allow_html=True)
with c_r5:
    st.markdown(f"<span style='font-size:13px; color:#444;'>Realizado: <b>R$ {real_rob_f6:,.2f}</b></span>", unsafe_allow_html=True)
with c_r6:
    perf_r6 = (real_rob_f6 / st.session_state.meta_rob_f6 * 100) if st.session_state.meta_rob_f6 > 0 else 0.0
    st.markdown(f"<span style='font-size:13px; color:#444;'>Perf: <b>{perf_r6:.1f}%</b></span>", unsafe_allow_html=True)

st.write("") # Linha em branco separadora

# 3. Seção Marcas Parceiras
st.markdown("<p style='font-size:14px; font-weight:bold; color:#111; margin-bottom:5px; text-transform: uppercase; letter-spacing: 0.5px;'>🤝 Marcas Parceiras (Foco)</p>", unsafe_allow_html=True)
dict_marcas_foco = calcular_marcas_foco(df_mes_atual)

c_m1, c_m2, c_m3 = st.columns(3)
m_keys = list(dict_marcas_foco.keys())
with c_m1:
    st.markdown(f"<span style='font-size:12px; color:#555;'>▪️ {m_keys[0]}: <b>{dict_marcas_foco[m_keys[0]]} Clis</b></span>", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:12px; color:#555;'>▪️ {m_keys[1]}: <b>{dict_marcas_foco[m_keys[1]]} Clis</b></span>", unsafe_allow_html=True)
with c_m2:
    st.markdown(f"<span style='font-size:12px; color:#555;'>▪️ {m_keys[2]}: <b>{dict_marcas_foco[m_keys[2]]} Clis</b></span>", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:12px; color:#555;'>▪️ {m_keys[3]}: <b>{dict_marcas_foco[m_keys[3]]} Clis</b></span>", unsafe_allow_html=True)
with c_m3:
    st.markdown(f"<span style='font-size:12px; color:#555;'>▪️ {m_keys[4]}: <b>{dict_marcas_foco[m_keys[4]]} Clis</b></span>", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:12px; color:#555;'>▪️ {m_keys[5]}: <b>{dict_marcas_foco[m_keys[5]]} Clis</b></span>", unsafe_allow_html=True)

st.write("---")

# --- MENUS DE NAVEGAÇÃO MOBILE GRADE 2X2 ---
c_nav1, c_nav2 = st.columns(2)
with c_nav1:
    if st.button("🟢 Painel Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"):
        st.session_state.aba_atual = "🟢 Ofertas"; st.rerun()
with c_nav2:
    if st.button("🚨 Alertas Radar", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"):
        st.session_state.aba_atual = "🚨 Alertas"; st.rerun()

c_nav3, c_nav4 = st.columns(2)
with c_nav3:
    if st.button("🔍 Consulta Cliente", type="primary" if st.session_state.aba_atual == "🔍 Cliente" else "secondary"):
        st.session_state.aba_atual = "🔍 Cliente"; st.rerun()
with c_nav4:
    if st.button("📦 Consulta Produto", type="primary" if st.session_state.aba_atual == "📦 Produto" else "secondary"):
        st.session_state.aba_atual = "📦 Produto"; st.rerun()

st.write("---")

# --- 🟢 ABA 1: OFERTAS ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    st.markdown(f"🗓️ Hoje: **{dia_semana_hoje}** | Envia hoje: **{st.session_state.envios_hoje}** listas")
    
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
                st.session_state[id_memoria] = lines = linhas
                
                prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
                prod_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
                
                nova_fila = {}
                clientes_com_compra_mes_atual = df_mes_atual['Cliente'].unique()
                
                for linha in linhas:
                    chaves = extrair_palavras_produto(linha)
                    if not chaves: continue
                    combs = [orig for orig, busca in prod_busca.items() if all(c in busca for c in chaves)]
                    
                    interessados = set()
                    for c in combs: interessados.update(prod_to_clientes[c])
                    
                    for cli in interessados:
                        if pd.isna(cli) or str(cli).lower() == 'nan': continue
                        if cli in st.session_state.excluidos_permanente:
                            if cli in clientes_com_compra_mes_atual: st.session_state.excluidos_permanente.remove(cli)
                            else: continue
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info("Nenhum cliente na fila de transmissão para envio.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
        
        cliente_atual = clientes_restantes[0]
        ofertas_cliente = fila_ativa[cliente_atual]
        mensagem_pronta = gerar_mensagem_humanizada(ofertas_cliente, tipo_msg)
        cad_info = obter_info_cliente(cliente_atual)
        
        st.markdown(f"### 🏢 {cliente_atual}")
        if cad_info['Fantasia'] and cad_info['Fantasia'] not in ["Não Localizado", "Não Informado"]:
            st.markdown(f"⭐ **Nome Fantasia:** *{cad_info['Fantasia']}*")
        
        tag_cidade_html = f'<span style="background-color:#EAE6FF; color:#403294; padding:6px 10px; border-radius:4px; font-weight:bold; font-size:13px; margin-right:6px; border: 1px solid #C0B6F2; display: inline-block;">📍 {cad_info["Cidade"]}</span>'
        st.markdown(tag_cidade_html + obter_badges_html(cliente_atual), unsafe_allow_html=True)
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

# --- 🚨 ABA 2: ALERTAS ---
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200)
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id="copyBtn" style="width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px;">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                navigator.clipboard.writeText({texto_js_safe});
                this.innerText = '✅ Copiado!';
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.rerun()

    filtro_status = st.selectbox("Filtrar por status de envio:", ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"])
    busca_alerta = st.text_input("🔍 Buscar Cliente em Alerta:", placeholder="Digite o nome...").strip()

    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0: continue
        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            ja_reportado = cli in st.session_state.enviados_supervisor_mes
            if filtro_status == "Apenas Não Reportados" and ja_reportado: continue
            if filtro_status == "Apenas Reportados" and not ja_reportado: continue
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"], "Reportado": ja_reportado})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas)
    if not df_alertas_visuais.empty: df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
    if busca_alerta and not df_alertas_visuais.empty:
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: limpar_texto(busca_alerta) in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info("Nenhum cliente crítico localizado.")
    else:
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            st.checkbox(f"🏢 {c_nome} ({row['Dias']} dias s/ compra)", key=f"chk_{c_nome}")
            info_c = obter_info_cliente(c_nome)
            if info_c['Fantasia'] and info_c['Fantasia'] not in ["Não Localizado", "Não Informado"]:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;*Fantasia: {info_c['Fantasia']}*")
            html_badges = obter_badges_html(c_nome)
            if row["Reportado"]: html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 REPORTADO</span>'
            tag_cidade_alerta = f'<span style="background-color:#EAE6FF; color:#403294; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px; border: 1px solid #C0B6F2; display: inline-block;">📍 {info_c["Cidade"]}</span>'
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{tag_cidade_alerta}{html_badges}", unsafe_allow_html=True)
            st.write("---")
            
        if st.button("⚡ GERAR RELATÓRIO DOS SELECIONADOS", type="primary"):
            novo_texto_acumulado = ""
            sel_rodada = []
            for idx, row in df_alertas_visuais.iterrows():
                cn = row["Cliente"]
                if st.session_state.get(f"chk_{cn}", False):
                    sel_rodada.append(cn)
                    novo_texto_acumulado += f"📌 {cn} ({row['Dias']} dias sem comprar)\n"
                    df_ch = df_total[df_total['Cliente'] == cn]
                    if not df_ch.empty:
                        top_i = df_ch.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                        for item in top_i: novo_texto_acumulado += f"        ▪️ {item}\n"
                    novo_texto_acumulado += "\n"
            st.session_state.texto_supervisor_gerado = novo_texto_acumulado
            st.session_state.clientes_processados_aguardando = sel_rodada
            salvar_progresso_atual()
            st.rerun()

# --- 🔍 ABA 3: CONSULTA CLIENTE ---
elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Consulta Detalhada por Cliente")
    lista_clis = sorted(list(df_total['Cliente'].dropna().unique()))
    c_sel = st.selectbox("Selecione o Cliente:", [""] + lista_clis)
    
    if c_sel:
        inf = obter_info_cliente(c_sel)
        st.markdown(f"### 🏢 {c_sel}")
        if inf['Fantasia'] and inf['Fantasia'] not in ["Não Localizado", "Não Informado"]:
            st.markdown(f"⭐ **Nome Fantasia:** *{inf['Fantasia']}*")
        t_cid = f'<span style="background-color:#EAE6FF; color:#403294; padding:6px 10px; border-radius:4px; font-weight:bold; font-size:13px; margin-right:6px; border: 1px solid #C0B6F2; display: inline-block;">📍 {inf["Cidade"]}</span>'
        st.markdown(t_cid + obter_badges_html(c_sel), unsafe_allow_html=True)
        
        df_cli = df_total[df_total['Cliente'] == c_sel]
        c_i = dict_carteira.get(c_sel, {"dias": 0})
        col1, col2 = st.columns(2)
        col1.metric("Dias sem Comprar", f"{c_i['dias']} dias")
        col2.metric("Faturamento Total", f"R$ {df_cli['Faturamento Brut'].sum():,.2f}")
        
        st.markdown("#### 📦 Top 5 Produtos mais Comprados")
        if not df_cli.empty:
            top_p = df_cli.groupby('Produto')['Faturamento Brut'].agg(['sum', 'count']).nlargest(5, 'sum')
            top_p.columns = ['Faturamento (R$)', 'Pedidos']
            st.dataframe(top_p, use_container_width=True)

# --- 📦 ABA 4: CONSULTA PRODUTO ---
elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Consulta Estratégica por Produto")
    lista_prods = sorted(list(df_total['Produto'].dropna().unique()))
    p_sel = st.selectbox("Selecione o Produto:", [""] + lista_prods)
    
    if p_sel:
        df_p = df_total[df_total['Produto'] == p_sel]
        st.markdown(f"### 📦 {p_sel}")
        col1, col2 = st.columns(2)
        col1.metric("Faturamento Histórico", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
        col2.metric("Clientes Compradores", f"{df_p['Cliente'].nunique()} Clis")
        
        st.markdown("#### 🏆 Top 10 Maiores Compradores deste Item")
        if not df_p.empty:
            top_c = df_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).reset_index()
            top_c['Cidade'] = top_c['Cliente'].apply(lambda x: obter_info_cliente(x)['Cidade'])
            top_c['Nome Fantasia'] = top_c['Cliente'].apply(lambda x: obter_info_cliente(x)['Fantasia'])
            st.dataframe(top_c, use_container_width=True)
