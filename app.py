import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import json
import google.generativeai as genai

# Configuração de tela limpa, direta e otimizada para mobile
st.set_page_config(page_title="Delly's Inteligência IA", layout="centered")

# --- 🤖 CONFIGURAÇÃO DA IA GEMINI ---
CHAVE_API_GEMINI = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=CHAVE_API_GEMINI)

# --- OTIMIZAÇÃO VISUAL MOBILE AVANÇADA ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span { font-size: 14px !important; }
    h3 { font-size: 18px !important; font-weight: bold !important; }
    h4 { font-size: 16px !important; }
    div.stButton > button {
        width: 100% !important; height: 42px !important; font-size: 12px !important;
        font-weight: bold !important; margin: 0 !important; border-radius: 6px !important;
    }
    code { font-size: 12px !important; line-height: 1.4 !important; white-space: pre-wrap !important; }
    
    /* Grid de marcas compacto em 2 colunas para celular */
    .brand-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
        margin-bottom: 10px;
    }
    .brand-box {
        background-color: #f8f9fa;
        padding: 5px;
        border-radius: 5px;
        border-left: 3px solid #FFC107;
        text-align: center;
        box-shadow: 0px 1px 2px rgba(0,0,0,0.05);
    }
    .brand-title { font-size: 10px !important; color: #555 !important; font-weight: bold !important; text-transform: uppercase; }
    .brand-value { font-size: 13px !important; font-weight: bold !important; color: #111 !important; margin: 1px 0; }
    .brand-sub { font-size: 9px !important; color: #777 !important; }
    
    /* Badges pequenas que não quebram a tela do celular */
    .badge-mobile {
        display: inline-block !important;
        white-space: nowrap !important;
        padding: 2px 5px !important;
        border-radius: 4px !important;
        font-weight: bold !important;
        font-size: 10px !important;
        margin-right: 3px !important;
        margin-bottom: 3px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 📅 CONTROLE DE TEMPO E DATAS (BRASÍLIA)
data_atual_sistema = pd.Timestamp.now(tz='America/Sao_Paulo').tz_localize(None)
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m')

# --- 📁 SISTEMA DE PERSISTÊNCIA COMPLETA ---
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
        "alertas_enviados": list(st.session_state.get("alertas_enviados", set())),
        "meta_pos_f2": st.session_state.get("meta_pos_f2", 0),
        "meta_pos_f6": st.session_state.get("meta_pos_f6", 0),
        "meta_rob_f2": st.session_state.get("meta_rob_f2", 0.0),
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0),
        "meta_m_seara": st.session_state.get("meta_m_seara", 0),
        "meta_m_mccain": st.session_state.get("meta_m_mccain", 0),
        "meta_m_frivatti": st.session_state.get("meta_m_frivatti", 0),
        "meta_m_confrescor": st.session_state.get("meta_m_confrescor", 0),
        "meta_m_brasa": st.session_state.get("meta_m_brasa", 0),
        "meta_m_ceratti": st.session_state.get("meta_m_ceratti", 0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f: json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")

# Lógica de reset automático às 23:59 ou na mudança de dia
if ultimo_acesso != data_hoje_str:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.memoria_ofertas_cruas_dia = []
    st.session_state.memoria_ofertas_cruas_rel = []
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()
    st.session_state.alertas_enviados = set()
else:
    st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
    st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
    st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
    st.session_state.memoria_ofertas_cruas_dia = progresso_backup.get("memoria_ofertas_cruas_dia", [])
    st.session_state.memoria_ofertas_cruas_rel = progresso_backup.get("memoria_ofertas_cruas_rel", [])
    st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
    st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))
    st.session_state.alertas_enviados = set(progresso_backup.get("alertas_enviados", []))

# Inicialização de metas persistentes
if 'meta_pos_f2' not in st.session_state: st.session_state.meta_pos_f2 = progresso_backup.get("meta_pos_f2", 0)
if 'meta_pos_f6' not in st.session_state: st.session_state.meta_pos_f6 = progresso_backup.get("meta_pos_f6", 0)
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)
if 'meta_m_seara' not in st.session_state: st.session_state.meta_m_seara = progresso_backup.get("meta_m_seara", 0)
if 'meta_m_mccain' not in st.session_state: st.session_state.meta_m_mccain = progresso_backup.get("meta_m_mccain", 0)
if 'meta_m_frivatti' not in st.session_state: st.session_state.meta_m_frivatti = progresso_backup.get("meta_m_frivatti", 0)
if 'meta_m_confrescor' not in st.session_state: st.session_state.meta_m_confrescor = progresso_backup.get("meta_m_confrescor", 0)
if 'meta_m_brasa' not in st.session_state: st.session_state.meta_m_brasa = progresso_backup.get("meta_m_brasa", 0)
if 'meta_m_ceratti' not in st.session_state: st.session_state.meta_m_ceratti = progresso_backup.get("meta_m_ceratti", 0)

if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False

def limpar_texto(texto):
    if pd.isna(texto): return ""
    # Remove acentos, ç, espaços extras e coloca em minúsculo para busca perfeita
    texto_normalizado = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z0-9\s]', '', texto_normalizado).strip().lower()

def extrair_codigo(nome_completo):
    match = re.search(r'^(\d+)', str(nome_completo))
    return match.group(1) if match else "S/C"

# --- 🧠 EXTRAÇÃO E PROCESSAMENTO DOS BANCOS DE DADOS ---
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
            c_dt = next((c for c in df.columns if any(k in str(c).lower() for k in ["dt", "data", "delivery", "faturamento"])), None)
            c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "raz" in str(c).lower()), None)
            c_prod = next((c for c in df.columns if "produto" in str(c).lower() or "desc" in str(c).lower()), None)
            c_fat = next((c for c in df.columns if "faturamento" in str(c).lower() or "brut" in str(c).lower() or "valor" in str(c).lower()), None)
            c_fil = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower()), None)
            
            if c_dt and c_cli and c_prod and c_fat:
                sub = df[[c_dt, c_cli, c_prod, c_fat]].copy()
                sub.columns = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                sub['Filial'] = df[c_fil].astype(str).str.strip() if c_fil else "2"
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
            c_cid = next((c for c in df.columns if "cidade" in str(c).lower() or "munic" in str(c).lower()), None)
            
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

with st.spinner("Sincronizando bases mobile Delly's..."):
    df_total = carregar_dados_vendas()
    df_clientes = carregar_base_clientes_cadastro()

# Alinhamento automático do mês ativo
mes_exibicao = mes_atual_referencia
if not df_total.empty:
    meses_com_dados = df_total['Ano_Mes'].dropna().unique()
    if mes_atual_referencia not in meses_com_dados and len(meses_com_dados) > 0:
        mes_exibicao = max(meses_com_dados)

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_exibicao] if not df_total.empty else pd.DataFrame()

# Mapeamentos de Marcas unificados conforme exigência do cliente
regex_seara = "lebon|doriana|seara|frangosul"
regex_mccain = "mccain"
regex_frivatti = "frivatti"
regex_confrescor = "confrescor"
regex_brasa = "brasa"
regex_ceratti = "ceratti"
termo_todas_marcas = f"{regex_seara}|{regex_frivatti}|{regex_brasa}|{regex_mccain}|{regex_confrescor}|{regex_ceratti}"

mapa_cadastro_clientes = {}
if not df_clientes.empty:
    for _, r in df_clientes.iterrows():
        mapa_cadastro_clientes[r['Cliente_Busca']] = {
            "Código": extrair_codigo(r['Cliente']), "Nome": r['Cliente'], "Fantasia": r['Nome_Fantasia'], "Cidade": r['Cidade']
        }

def obter_info_cliente(nome_vendas):
    vendas_limpo = limpar_texto(nome_vendas)
    if b := mapa_cadastro_clientes.get(vendas_limpo): return b
    return {"Código": extrair_codigo(nome_vendas), "Nome": nome_vendas, "Fantasia": "S/F", "Cidade": "Não Localizada"}

@st.cache_data(ttl=600)
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
            filiais = vendas_mes['Filial'].astype(str).str.strip().unique()
            if any(f in filiais for f in ['2', '02', '2.0']): tags.append("PosFL2")
            if any(f in filiais for f in ['6', '06', '6.0']): tags.append("PosFL6")
        else:
            tags.append("NÃO POS")
        if dias_sem_compra > 30: tags.append("SUMIDO")
        mapa[cli] = {"tags": tags, "dias": dias_sem_compra}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

# --- CÁLCULO DOS INDICADORES FINANCEIROS ---
mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0']) if not df_mes_atual.empty else pd.Series()
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0']) if not df_mes_atual.empty else pd.Series()

real_pos_f2 = df_mes_atual[mask_f2]['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_f6 = df_mes_atual[mask_f6]['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_geral = df_mes_atual['Cliente'].nunique() if not df_mes_atual.empty else 0
meta_pos_geral = int(st.session_state.meta_pos_f2) + int(st.session_state.meta_pos_f6)

real_rob_f2 = df_mes_atual[mask_f2]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_f6 = df_mes_atual[mask_f6]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_geral = real_rob_f2 + real_rob_f6
meta_rob_geral = float(st.session_state.meta_rob_f2) + float(st.session_state.meta_rob_f6)

def calcular_real_marca(regex_marca):
    if df_mes_atual.empty: return 0
    return df_mes_atual[df_mes_atual['Produto_Busca'].str.contains(regex_marca, na=False)]['Cliente'].nunique()

real_m_seara = calcular_real_marca(regex_seara)
real_m_mccain = calcular_real_marca(regex_mccain)
real_m_frivatti = calcular_real_marca(regex_frivatti)
real_m_confrescor = calcular_real_marca(regex_confrescor)
real_m_brasa = calcular_real_marca(regex_brasa)
real_m_ceratti = calcular_real_marca(regex_ceratti)

# --- 🎯 EXIBIÇÃO DO CABEÇALHO ---
st.markdown("### 🟢 Delly's Inteligência IA")
st.write("---")

col_tit_meta, col_btn_meta = st.columns([4, 2])
with col_tit_meta: st.markdown("#### 📊 Indicadores Principais")
with col_btn_meta:
    if st.session_state.modo_edicao_metas:
        if st.button("💾 Salvar", key="m_save"): st.session_state.modo_edicao_metas = False; salvar_progresso_atual(); st.rerun()
    else:
        if st.button("📝 Metas", key="m_edit"): st.session_state.modo_edicao_metas = True; st.rerun()

if st.session_state.modo_edicao_metas:
    c_ed1, c_ed2 = st.columns(2)
    with c_ed1:
        st.session_state.meta_pos_f2 = st.number_input("Pos. FL2", value=int(st.session_state.meta_pos_f2), step=1)
        st.session_state.meta_pos_f6 = st.number_input("Pos. FL6", value=int(st.session_state.meta_pos_f6), step=1)
        st.session_state.meta_m_seara = st.number_input("M. Seara", value=int(st.session_state.meta_m_seara), step=1)
        st.session_state.meta_m_mccain = st.number_input("M. McCain", value=int(st.session_state.meta_m_mccain), step=1)
        st.session_state.meta_m_frivatti = st.number_input("M. Frivatti", value=int(st.session_state.meta_m_frivatti), step=1)
    with c_ed2:
        st.session_state.meta_rob_f2 = st.number_input("Fat. FL2 (R$)", value=float(st.session_state.meta_rob_f2), step=1000.0)
        st.session_state.meta_rob_f6 = st.number_input("Fat. FL6 (R$)", value=float(st.session_state.meta_rob_f6), step=1000.0)
        st.session_state.meta_m_confrescor = st.number_input("M. Confrescor", value=int(st.session_state.meta_m_confrescor), step=1)
        st.session_state.meta_m_brasa = st.number_input("M. Brasa", value=int(st.session_state.meta_m_brasa), step=1)
        st.session_state.meta_m_ceratti = st.number_input("M. Ceratti", value=int(st.session_state.meta_m_ceratti), step=1)
else:
    df_indicadores = pd.DataFrame([
        {"Métrica": "🎯 Positivação Geral", "Alvo": meta_pos_geral, "Realizado": f"{real_pos_geral} clis", "Ating.": f"{(real_pos_geral/meta_pos_geral*100) if meta_pos_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ Positivação FL2", "Alvo": st.session_state.meta_pos_f2, "Realizado": f"{real_pos_f2} clis", "Ating.": f"{(real_pos_f2/int(st.session_state.meta_pos_f2)*100) if int(st.session_state.meta_pos_f2)>0 else 0:.1f}%"},
        {"Métrica": "◽ Positivação FL6", "Alvo": st.session_state.meta_pos_f6, "Realizado": f"{real_pos_f6} clis", "Ating.": f"{(real_pos_f6/int(st.session_state.meta_pos_f6)*100) if int(st.session_state.meta_pos_f6)>0 else 0:.1f}%"},
        {"Métrica": "💰 Faturamento Geral", "Alvo": f"R$ {meta_rob_geral:,.2f}", "Realizado": f"R$ {real_rob_geral:,.2f}", "Ating.": f"{(real_rob_geral/meta_rob_geral*100) if meta_rob_geral>0 else 0:.1f}%"}
    ])
    st.table(df_indicadores)
    
    # --- BLOCO MARCAS PARCEIRAS CONDENSADO EM DUAS COLUNAS PARA CELULAR ---
    def html_box_marca(titulo, real, alvo):
        pct = (real / alvo * 100) if alvo > 0 else 0.0
        return f"""
        <div class="brand-box">
            <div class="brand-title">{titulo}</div>
            <div class="brand-value">{real} clis</div>
            <div class="brand-sub">Alvo: {alvo} ({pct:.1f}%)</div>
        </div>
        """
    
    html_grid = f"""
    <div class="brand-grid">
        {html_box_marca("SEARA", real_m_seara, int(st.session_state.meta_m_seara))}
        {html_box_marca("MCCAIN", real_m_mccain, int(st.session_state.meta_m_mccain))}
        {html_box_marca("FRIVATTI", real_m_frivatti, int(st.session_state.meta_m_frivatti))}
        {html_box_marca("CONFRESCOR", real_m_confrescor, int(st.session_state.meta_m_confrescor))}
        {html_box_marca("BRASA", real_m_brasa, int(st.session_state.meta_m_brasa))}
        {html_box_marca("CERATTI", real_m_ceratti, int(st.session_state.meta_m_ceratti))}
    </div>
    """
    st.markdown(html_grid, unsafe_allow_html=True)

st.write("---")

# --- NAVEGAÇÃO MOBILE EM RECORTE DE DUAS COLUNAS ---
c_nav1, c_nav2 = st.columns(2)
with c_nav1:
    if st.button("🟢 Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"): st.session_state.aba_atual = "🟢 Ofertas"; st.rerun()
with c_nav2:
    if st.button("🚨 Alertas", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"): st.session_state.aba_atual = "🚨 Alertas"; st.rerun()

c_nav3, c_nav4 = st.columns(2)
with c_nav3:
    if st.button("🔍 Consulta Cliente", type="primary" if st.session_state.aba_atual == "🔍 Cliente" else "secondary"): st.session_state.aba_atual = "🔍 Cliente"; st.rerun()
with c_nav4:
    if st.button("📦 Consulta Produto", type="primary" if st.session_state.aba_atual == "📦 Produto" else "secondary"): st.session_state.aba_atual = "📦 Produto"; st.rerun()

c_nav5, c_nav6 = st.columns(2)
with c_nav5:
    if st.button("🧠 Assistente", type="primary" if st.session_state.aba_atual == "🧠 Assistente" else "secondary"): st.session_state.aba_atual = "🧠 Assistente"; st.rerun()
with c_nav6:
    if st.button("🏷️ Marcas Exclusivas", type="primary" if st.session_state.aba_atual == "🏷️ Marcas" else "secondary"): st.session_state.aba_atual = "🏷️ Marcas"; st.rerun()

st.write("---")

def renderizar_tags_html(lista_tags):
    cores = {"PosFL2": "#00875A", "PosFL6": "#0052CC", "NÃO POS": "#DE350B", "SUMIDO": "#FF9900", "ENVIADO": "#00875A", "NÃO ENVIADO": "#7A869A", "SEARA": "#8A1C14", "FRIVATTI": "#D01C24", "MCCAIN": "#FFC107", "BRASA": "#E65100", "CONFRESCOR": "#0288D1", "CERATTI": "#4A148C", "VEND CRUZADA": "#6A1B9A", "JÁ COMPROU": "#2E7D32"}
    html = ""
    for t in lista_tags:
        cor = cores.get(t, "#555555")
        cor_txt = "white" if cor != "#FFC107" else "black"
        html += f'<span class="badge-mobile" style="background-color:{cor}; color:{cor_txt};">{t}</span>'
    return html

# ==========================================
# 🟢 ABA OFERTAS (FILAS INDEPENDENTES)
# ==========================================
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão Mobile")
    if df_total.empty:
        st.info("Bancos de dados vazios.")
    else:
        tipo_lista = st.radio("Fila Ativa:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
        id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
        id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
        id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
        
        with st.expander("📝 Configurar Texto das Ofertas"):
            texto_colado = st.text_area("Insira as ofertas (uma por linha):", value="\n".join(st.session_state.get(id_memoria, [])), height=100)
            if st.button("🚀 Processar e Gerar Fila"):
                linhas = [l.strip() for l in texto_colado.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas
                
                # Inicializa a fila cruzando histórico dos clientes com as ofertas coladas
                nova_fila = {}
                for cli in df_total['Cliente'].dropna().unique():
                    if cli in st.session_state[id_excluidos]: continue
                    prods_historico = df_total[df_total['Cliente'] == cli]['Produto_Busca'].unique()
                    combinacoes = []
                    for linha_of in linhas:
                        if limpar_texto(linha_of) in prods_historico or any(limpar_texto(p) in limpar_texto(linha_of) for p in prods_historico):
                            combinacoes.append(linha_of)
                    
                    if combinacoes:
                        nova_fila[cli] = combinacoes
                        
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.rerun()

        fila_ativa = st.session_state.get(id_fila) or {}
        if fila_ativa:
            cli_corrente = list(fila_ativa.keys())[0]
            inf = obter_info_cliente(cli_corrente)
            info_c = dict_carteira.get(cli_corrente, {"tags": []})
            
            st.markdown(f"### 🏢 Código: {inf['Código']}")
            st.markdown(f"**Razão:** {inf['Nome']}\n\n**Fantasia:** {inf['Fantasia']} | **Cidade:** {inf['Cidade']}")
            st.markdown(renderizar_tags_html(info_c["tags"]), unsafe_allow_html=True)
            
            st.markdown("**📱 Copiar texto do WhatsApp:**")
            produtos_match = "\n".join([f"• {p}" for p in fila_ativa[cli_corrente]])
            msg_whatsapp = f"Olá! Tudo bem? Separamos as seguintes oportunidades em destaque que você costuma comprar conosco:\n\n{produtos_match}\n\nConseguimos fechar o pedido dessas opções hoje?"
            st.code(msg_whatsapp, language="text")
            
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                if st.button("✅ Confirmar Envio"):
                    st.session_state.envios_hoje += 1
                    st.session_state[id_excluidos].add(cli_corrente)
                    del st.session_state[id_fila][cli_corrente]
                    salvar_progresso_atual()
                    st.rerun()
            with c_a2:
                if st.button("❌ Pular Cliente"):
                    del st.session_state[id_fila][cli_corrente]
                    st.rerun()
        else:
            st.success("Fila limpa ou concluída por hoje!")

# ==========================================
# 🚨 ABA ALERTAS (RECUPERAÇÃO DE CLIENTES)
# ==========================================
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Recuperação de Clientes Inativos")
    
    # Clientes com mais de 45 dias sem compras
    lista_alertas = []
    for c, d in dict_carteira.items():
        if d["dias"] >= 45:
            inf = obter_info_cliente(c)
            tag_env = "ENVIADO" if c in st.session_state.alertas_enviados else "NÃO ENVIADO"
            lista_alertas.append({
                "Cliente_Id": c, "Código": inf["Código"], "Nome": inf["Nome"],
                "Fantasia": inf["Fantasia"], "Cidade": inf["Cidade"], "Dias": d["dias"], "Status": tag_env
            })
            
    if not lista_alertas:
        st.success("Nenhum cliente acima de 45 dias sumido!")
    else:
        df_alertas_ativos = pd.DataFrame(lista_alertas).sort_values(by="Dias", ascending=False)
        
        # Filtros Mobile Avançados
        c_flt1, c_flt2 = st.columns(2)
        with c_flt1:
            f_status = st.selectbox("Envio:", ["TODOS", "NÃO ENVIADO", "ENVIADO"])
        with c_flt2:
            lista_cidades = ["TODAS"] + sorted(list(df_alertas_ativos['Cidade'].unique()))
            f_cidade = st.selectbox("Cidade:", lista_cidades)
            
        if f_status != "TODOS": df_alertas_ativos = df_alertas_ativos[df_alertas_ativos['Status'] == f_status]
        if f_cidade != "TODAS": df_alertas_ativos = df_alertas_ativos[df_alertas_ativos['Cidade'] == f_cidade]
        
        # Botões de Ação Coletiva
        c_bt_al1, c_bt_al2 = st.columns(2)
        chaves_selecionadas = []
        
        with st.container():
            st.write("---")
            # Listagem com Checkbox Mobile individual
            for idx, row in df_alertas_ativos.iterrows():
                marcado = st.checkbox(f"📍 {row['Código']} - {row['Fantasia'] or row['Nome'][:20]} ({row['Dias']} dias)", key=f"chk_{row['Cliente_Id']}")
                if marcado:
                    chaves_selecionadas.append(row['Cliente_Id'])
                st.markdown(renderizar_tags_html([row['Status'], f"{row['Dias']} DIAS"]), unsafe_allow_html=True)
                st.write(f"*{row['Nome']} | {row['Cidade']}*")
                st.write("---")
                
        with c_bt_al1:
            if st.button("📊 Gerar Relatório"):
                if not chaves_selecionadas:
                    st.warning("Selecione ao menos um cliente.")
                else:
                    txt_relatorio = "📝 SOLICITAÇÃO DE EXCLUSIVA / RECUPERAÇÃO DE CLIENTES\n\n"
                    for cli in chaves_selecionadas:
                        inf_c = obter_info_cliente(cli)
                        dias_s = dict_carteira[cli]["dias"]
                        # Busca até 3 produtos mais comprados historicamente
                        top_prods = df_total[df_total['Cliente'] == cli]['Produto'].value_counts().head(3).index.tolist()
                        txt_relatorio += f"🏢 CÓD: {inf_c['Código']} | {inf_c['Nome']}\n"
                        txt_relatorio += f"🔹 FANTASIA: {inf_c['Fantasia']} | CIDADE: {inf_c['Cidade']}\n"
                        txt_relatorio += f"⚠️ INATIVO HÁ: {dias_s} dias\n"
                        txt_relatorio += "🛒 PRINCIPAIS ITENS HISTÓRICOS:\n"
                        if top_prods:
                            for p in top_prods: txt_relatorio += f"  • {p}\n"
                        else:
                            txt_relatorio += "  • Sem registros detalhados\n"
                        txt_relatorio += "----------------------------------------\n"
                    st.text_area("📋 Copiar para o Supervisor:", value=txt_relatorio, height=200)
                    
        with c_bt_al2:
            if st.button("✅ Marcar Enviados"):
                for cli in chaves_selecionadas:
                    st.session_state.alertas_enviados.add(cli)
                salvar_progresso_atual()
                st.rerun()

# ==========================================
# 🔍 ABA CONSULTA CLIENTE
# ==========================================
elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Painel Executivo do Cliente")
    if not df_total.empty:
        # Busca aproximada por digitação
        busca_cli = st.text_input("Digite parte do nome ou código do cliente:")
        clientes_filtrados = sorted(list(df_total['Cliente'].unique()))
        
        if busca_cli:
            clientes_filtrados = [c for c in clientes_filtrados if limpar_texto(busca_cli) in limpar_texto(c)]
            
        c_sel = st.selectbox("Selecione o Cliente:", [""] + clientes_filtrados)
        if c_sel:
            inf = obter_info_cliente(c_sel)
            info_c = dict_carteira.get(c_sel, {"tags": []})
            
            # Geração Dinâmica de Tags de Marcas com base no faturamento do mês atual
            tags_marcas_faturamento = list(info_c["tags"])
            vendas_c_mes = df_mes_atual[df_mes_atual['Cliente'] == c_sel] if not df_mes_atual.empty else pd.DataFrame()
            if not vendas_c_mes.empty:
                txt_v_mes = " ".join(vendas_c_mes['Produto_Busca'].unique())
                if re.search(regex_seara, txt_v_mes): tags_marcas_faturamento.append("SEARA")
                if re.search(regex_frivatti, txt_v_mes): tags_marcas_faturamento.append("FRIVATTI")
                if re.search(regex_mccain, txt_v_mes): tags_marcas_faturamento.append("MCCAIN")
                if re.search(regex_brasa, txt_v_mes): tags_marcas_faturamento.append("BRASA")
                if re.search(regex_confrescor, txt_v_mes): tags_marcas_faturamento.append("CONFRESCOR")
                if re.search(regex_ceratti, txt_v_mes): tags_marcas_faturamento.append("CERATTI")
                
            st.markdown(f"### {inf['Código']} - {inf['Nome']}")
            st.markdown(f"📍 **Cidade:** {inf['Cidade']} | **Fantasia:** {inf['Fantasia']}")
            st.markdown(renderizar_tags_html(tags_marcas_faturamento), unsafe_allow_html=True)
            st.write("---")
            
            # 1. Produtos que combinam com as ofertas ativas coladas
            st.markdown("🔥 **Produtos em Oferta Combinando com o Histórico:**")
            ofertas_ativas = st.session_state.get("memoria_ofertas_cruas_dia", []) + st.session_state.get("memoria_ofertas_cruas_rel", [])
            prods_historico_todos = df_total[df_total['Cliente'] == c_sel]['Produto_Busca'].unique()
            matches_oferta = []
            for of in ofertas_ativas:
                if limpar_texto(of) in prods_historico_todos or any(limpar_texto(p) in limpar_texto(of) for p in prods_historico_todos):
                    matches_oferta.append(of)
            if matches_oferta:
                for m in set(matches_oferta): st.success(f"• {m}")
            else:
                st.write("*Nenhuma combinação para hoje.*")
                
            # 2. Bloco de Venda Cruzada Inteligente
            st.markdown("💡 **Sugestão de Venda Cruzada:**")
            # Se já compra Batata/McCain mas nunca comprou Frivatti, sugere Frivatti Proteínas (e vice-versa)
            prods_texto_historico = " ".join(prods_historico_todos)
            if "mccain" in prods_texto_historico and "frivatti" not in prods_texto_historico:
                st.info("• Cliente compra McCain. Sugerir Hamburguer/Cortes Frivatti.")
            elif "frivatti" in prods_texto_historico and "mccain" not in prods_texto_historico:
                st.info("• Cliente compra Frivatti. Sugerir Batata McCain para acompanhamento.")
            else:
                st.info("• Ofertar mix complementar das marcas exclusivas Ceratti ou Confrescor.")
                
            # 3. Lista Geral dos 10 mais comprados (Uma linha por produto)
            st.markdown("📊 **Top 10 Produtos Mais Comprados (Frequência):**")
            top_10 = df_total[df_total['Cliente'] == c_sel]['Produto'].value_counts().head(10)
            if not top_10.empty:
                for p, qtd in top_10.items():
                    st.write(f"🔹 {p} ({qtd}x)")
            else:
                st.write("*Sem histórico disponível.*")
                
            # 4. Produtos Abandonados (com tempo calculado)
            st.markdown("⏳ **Produtos Abandonados (Não comprados no mês atual):**")
            df_cli_historico = df_total[df_total['Cliente'] == c_sel]
            ultimas_por_item = df_cli_historico.groupby('Produto')['Data_Datetime'].max()
            abandonados = []
            for prod, dt_u in ultimas_por_item.items():
                if dt_u < pd.to_datetime(mes_exibicao + "-01"):
                    dias_abs = (data_atual_sistema - dt_u).days
                    abandonados.append((prod, dias_abs))
            abandonados = sorted(abandonados, key=lambda x: x[1], reverse=True)[:5]
            if abandonados:
                for prod, d_abs in abandonados:
                    st.warning(f"• {prod} (Há {d_abs} dias)")
            else:
                st.write("*Nenhum item abandonado identificado.*")

# ==========================================
# 📦 ABA CONSULTA POR PRODUTO
# ==========================================
elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Rastreamento e Cruzamento de Itens")
    if not df_total.empty:
        busca_prod = st.text_input("Pesquisar Produto (desconsidera acentos/maiúsculas):")
        produtos_lista = sorted(list(df_total['Produto'].dropna().unique()))
        
        if busca_prod:
            produtos_lista = [p for p in produtos_lista if limpar_texto(busca_prod) in limpar_texto(p)]
            
        p_sel = st.selectbox("Selecione o Item exato:", [""] + produtos_lista)
        if p_sel:
            p_sel_busca = limpar_texto(p_sel)
            df_p = df_total[df_total['Produto_Busca'] == p_sel_busca]
            st.metric("Faturamento Consolidado do Item", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
            
            st.markdown("**🏢 Lista de Clientes Relacionados:**")
            clientes_compraram = set(df_p['Cliente'].unique())
            
            # Exibição textual um embaixo do outro otimizada para celular
            for c in df_total['Cliente'].dropna().unique():
                inf = obter_info_cliente(c)
                if c in clientes_compraram:
                    st.markdown(f"👤 **{inf['Código']} - {inf['Fantasia'] or inf['Nome']}** ({inf['Cidade']})")
                    st.markdown(renderizar_tags_html(["JÁ COMPROU"]), unsafe_allow_html=True)
                    st.write("---")
                elif any(m in p_sel_busca for m in ["mccain", "frivatti", "seara", "ceratti"]):
                    # Lógica simplificada de venda cruzada de marcas parceiras
                    st.markdown(f"👤 **{inf['Código']} - {inf['Fantasia'] or inf['Nome']}** ({inf['Cidade']})")
                    st.markdown(renderizar_tags_html(["VEND CRUZADA"]), unsafe_allow_html=True)
                    st.write("---")

# ==========================================
# 🧠 ABA ASSISTENTE IA
# ==========================================
elif st.session_state.aba_atual == "🧠 Assistente":
    st.subheader("🧠 Consultor Comercial Virtual Delly's")
    p_user = st.text_input("Qual o desafio comercial ou dúvida de mix para hoje?")
    if p_user:
        with st.spinner("Analisando cenário comercial..."):
            try:
                model_flash = genai.GenerativeModel("gemini-1.5-flash")
                resposta = model_flash.generate_content(p_user).text
                st.info(resposta)
            except Exception as e:
                st.error("Erro ao conectar com a IA Gemini. Verifique sua chave secreta.")

# ==========================================
# 🏷️ ABA MARCAS EXCLUSIVAS
# ==========================================
elif st.session_state.aba_atual == "🏷️ Marcas":
    st.subheader("🏷️ Painel Alvo de Marcas Exclusivas")
    if df_total.empty:
        st.info("Sem dados consolidados.")
    else:
        opcao_tela_marca = st.radio("Cenário de Análise:", ["⚠️ Já Compraram", "🎯 Nunca Compraram"], horizontal=True)
        marca_alvo = st.selectbox("Selecione a Marca Parceira:", ["SEARA/LEBON/DORIANA", "MCCAIN", "FRIVATTI", "CONFRESCOR", "BRASA", "CERATTI"])
        
        regex_mapa = {
            "SEARA/LEBON/DORIANA": regex_seara, "MCCAIN": regex_mccain, "FRIVATTI": regex_frivatti,
            "CONFRESCOR": regex_confrescor, "BRASA": regex_brasa, "CERATTI": regex_ceratti
        }
        reg_marca_sel = regex_mapa[marca_alvo]
        
        # Filtros de Ativação do Mês Corrente
        clientes_com_compra_mes = set(df_mes_atual[df_mes_atual['Produto_Busca'].str.contains(reg_marca_sel, na=False)]['Cliente'].unique()) if not df_mes_atual.empty else set()
        clientes_historico_marca = set(df_total[df_total['Produto_Busca'].str.contains(reg_marca_sel, na=False)]['Cliente'].unique())
        todos_clientes_sistema = set(df_total['Cliente'].dropna().unique())
        
        if "⚠️ Já Compraram" in opcao_tela_marca:
            st.markdown(f"**Clientes que já compraram {marca_alvo}, mas NÃO compraram neste mês:**")
            # Devem ter comprado no passado mas estar zerados no mês atual (Churn da Marca)
            alvos_ja_compraram = clientes_historico_marca - clientes_com_compra_mes
            
            if alvos_ja_compraram:
                for c in alvos_ja_compraram:
                    inf = obter_info_cliente(c)
                    st.markdown(f"🏢 **{inf['Código']} - {inf['Nome']}** ({inf['Cidade']})")
                    # Busca os produtos daquela marca comprados anteriormente
                    prods_marca_hist = df_total[(df_total['Cliente'] == c) & (df_total['Produto_Busca'].str.contains(reg_marca_sel, na=False))]['Produto'].unique()
                    st.write("📋 *Itens já comprados:*", ", ".join(list(prods_marca_hist)[:10]))
                    st.write("---")
            else:
                st.success("Toda a carteira histórica está ativa na marca neste mês!")
                
        else:
            st.markdown(f"**Clientes que NUNCA compraram a marca {marca_alvo} no mês corrente:**")
            # Clientes do sistema que estão sem positivação do item no mês
            alvos_nunca_compraram = todos_clientes_sistema - clientes_com_compra_mes
            
            if alvos_nunca_compraram:
                for c in alvos_nunca_compraram:
                    inf = obter_info_cliente(c)
                    st.markdown(f"🏢 **{inf['Código']} - {inf['Nome']}** ({inf['Cidade']})")
                    st.write("❌ *Sem positivação registrada neste período.*")
                    st.write("---")
            else:
                st.success("Incrível! 100% dos clientes compraram essa marca neste mês.")
