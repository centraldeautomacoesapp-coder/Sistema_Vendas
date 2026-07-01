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

# --- OTIMIZAÇÃO VISUAL MOBILE E FORMATO DE GRADES ---
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
    
    .brand-box {
        background-color: #f8f9fa;
        padding: 6px;
        border-radius: 6px;
        border-left: 3px solid #FFC107;
        margin-bottom: 8px;
        text-align: center;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.05);
    }
    .brand-title { font-size: 11px !important; color: #555 !important; font-weight: bold !important; text-transform: uppercase; }
    .brand-value { font-size: 15px !important; font-weight: bold !important; color: #111 !important; margin: 2px 0; }
    .brand-sub { font-size: 10px !important; color: #777 !important; }
    </style>
""", unsafe_allow_html=True)

# 📅 CONTROLE DE TEMPO E DATAS (BRASÍLIA)
data_atual_sistema = pd.Timestamp.now(tz='America/Sao_Paulo').tz_localize(None).normalize()
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
        "mes_referencia_salvo": mes_atual_referencia,
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
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0),
        "meta_m_lds": st.session_state.get("meta_m_lds", 0),
        "meta_m_frivatti": st.session_state.get("meta_m_frivatti", 0),
        "meta_m_brasa": st.session_state.get("meta_m_brasa", 0),
        "meta_m_mccain": st.session_state.get("meta_m_mccain", 0),
        "meta_m_confrescor": st.session_state.get("meta_m_confrescor", 0),
        "meta_m_ceratti": st.session_state.get("meta_m_ceratti", 0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f: json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
mes_salvo = progresso_backup.get("mes_referencia_salvo", "")

# 🔄 --- LÓGICA DE ZERAMENTO AUTOMÁTICO SE MUDAR O MÊS ---
if mes_salvo != "" and mes_salvo != mes_atual_referencia:
    # Virou o mês! Zera todas as metas e filas do arquivo de backup
    progresso_backup = {
        "mes_referencia_salvo": mes_atual_referencia,
        "data_ultimo_acesso": data_hoje_str,
        "envios_hoje": 0, "fila_ofertas_dia": None, "fila_ofertas_relampago": None,
        "memoria_ofertas_cruas_dia": [], "memoria_ofertas_cruas_rel": [],
        "excluidos_ofertas_dia": [], "excluidos_ofertas_relampago": [],
        "meta_pos_f2": 0, "meta_pos_f6": 0, "meta_rob_f2": 0.0, "meta_rob_f6": 0.0,
        "meta_m_lds": 0, "meta_m_frivatti": 0, "meta_m_brasa": 0, "meta_m_mccain": 0, "meta_m_confrescor": 0, "meta_m_ceratti": 0
    }

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

if 'meta_m_lds' not in st.session_state: st.session_state.meta_m_lds = progresso_backup.get("meta_m_lds", 0)
if 'meta_m_frivatti' not in st.session_state: st.session_state.meta_m_frivatti = progresso_backup.get("meta_m_frivatti", 0)
if 'meta_m_brasa' not in st.session_state: st.session_state.meta_m_brasa = progresso_backup.get("meta_m_brasa", 0)
if 'meta_m_mccain' not in st.session_state: st.session_state.meta_m_mccain = progresso_backup.get("meta_m_mccain", 0)
if 'meta_m_confrescor' not in st.session_state: st.session_state.meta_m_confrescor = progresso_backup.get("meta_m_confrescor", 0)
if 'meta_m_ceratti' not in st.session_state: st.session_state.meta_m_ceratti = progresso_backup.get("meta_m_ceratti", 0)

if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False
if 'cache_ia_gemini' not in st.session_state: st.session_state.cache_ia_gemini = {}

def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

# --- 🧠 EXTRAÇÃO E VINCULAÇÃO POR CÓDIGO DO CLIENTE ---
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
            
            c_cod = next((c for c in df.columns if any(k in str(c).lower() for k in ["cod", "id", "codigo", "cd_cl"])), None)
            c_dt = next((c for c in df.columns if any(k in str(c).lower() for k in ["dt", "data", "delivery", "faturamento"])), None)
            c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "raz" in str(c).lower()), None)
            c_prod = next((c for c in df.columns if "produto" in str(c).lower() or "desc" in str(c).lower()), None)
            c_fat = next((c for c in df.columns if "faturamento" in str(c).lower() or "brut" in str(c).lower() or "valor" in str(c).lower()), None)
            c_fil = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower()), None)
            
            if c_dt and c_cli and c_prod and c_fat:
                sub = pd.DataFrame()
                sub['Dt. Delivery'] = df[c_dt]
                sub['Cod_Cliente'] = df[c_cod].astype(str).str.strip() if c_cod else df[c_cli].apply(limpar_texto)
                sub['Cliente'] = df[c_cli].astype(str).str.strip()
                sub['Produto'] = df[c_prod].astype(str).str.strip()
                sub['Faturamento Brut'] = df[c_fat]
                sub['Filial'] = df[c_fil].astype(str).str.strip() if c_fil else "2"
                    
                if sub['Faturamento Brut'].dtype == 'object':
                    sub['Faturamento Brut'] = sub['Faturamento Brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['Faturamento Brut'] = pd.to_numeric(sub['Faturamento Brut'], errors='coerce')
                lista_dfs.append(sub)
        except: continue
        
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cod_Cliente'].notna()]
        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
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
            c_cod = next((c for c in df.columns if any(k in str(c).lower() for k in ["cod", "id", "codigo", "cd_cl"])), None)
            c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "raz" in str(c).lower()), None)
            c_fant = next((c for c in df.columns if "fantasia" in str(c).lower() or "nome" in str(c).lower()), None)
            c_cid = next((c for c in df.columns if "cidade" in str(c).lower() or "munic" in str(c).lower()), None)
            
            if c_cli:
                sub = pd.DataFrame()
                sub['Cod_Cliente'] = df[c_cod].astype(str).str.strip() if c_cod else df[c_cli].apply(limpar_texto)
                sub['Razao_Social'] = df[c_cli].astype(str).str.strip()
                sub['Nome_Fantasia'] = df[c_fant].astype(str).str.strip() if c_fant else ""
                sub['Cidade'] = df[c_cid].astype(str).str.strip() if c_cid else "Não Informada"
                lista_dfs_cli.append(sub)
        except: continue
        
    if lista_dfs_cli:
        return pd.concat(lista_dfs_cli, ignore_index=True).drop_duplicates(subset=['Cod_Cliente'])
    return pd.DataFrame()

with st.spinner("Conectando e sincronizando bases Delly's por Chave de Código..."):
    df_total = carregar_dados_vendas()
    df_clientes = carregar_base_clientes_cadastro()

mes_exibicao = mes_atual_referencia
if not df_total.empty:
    meses_com_dados = df_total['Ano_Mes'].dropna().unique()
    if mes_atual_referencia not in meses_com_dados and len(meses_com_dados) > 0:
        mes_exibicao = max(meses_com_dados)

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_exibicao] if not df_total.empty else pd.DataFrame()
termo_todas_marcas = "lebon|doriana|seara|frivatti|brasa|mccain|confrescor|ceratti"

# Mapa indexado por Código do Cliente
mapa_cadastro_clientes = {}
if not df_clientes.empty:
    for _, r in df_clientes.iterrows():
        mapa_cadastro_clientes[str(r['Cod_Cliente'])] = {
            "Cod": r['Cod_Cliente'], "Razao": r['Razao_Social'], "Fantasia": r['Nome_Fantasia'], "Cidade": r['Cidade']
        }

def obter_info_cliente(cod_cliente):
    cod_str = str(cod_cliente)
    if b := mapa_cadastro_clientes.get(cod_str): return b
    # Fallback se não achar no cadastro externo
    if not df_total.empty:
        sub_c = df_total[df_total['Cod_Cliente'] == cod_str]
        if not sub_c.empty:
            return {"Cod": cod_str, "Razao": sub_c['Cliente'].iloc[0], "Fantasia": "", "Cidade": "Não Localizada"}
    return {"Cod": cod_str, "Razao": f"Cod: {cod_str}", "Fantasia": "", "Cidade": "Não Localizada"}

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    if df.empty: return mapa
    ultimas_compras = df.groupby('Cod_Cliente')['Data_Datetime'].max().to_dict()
    for cod_cli in df['Cod_Cliente'].unique():
        tags = []
        dt_ult = ultimas_compras.get(cod_cli, data_hoje)
        dias_sem_compra = (data_hoje - dt_ult).days
        vendas_mes = df_mes[df_mes['Cod_Cliente'] == cod_cli] if not df_mes.empty else pd.DataFrame()
        
        if not vendas_mes.empty:
            tags.append("POSITIVADO")
            filiais = vendas_mes['Filial'].astype(str).str.strip().unique()
            if any(f in filiais for f in ['2', '02', '2.0']): tags.append("FILIAL 2")
            if any(f in filiais for f in ['6', '06', '6.0']): tags.append("FILIAL 6")
        else:
            tags.append("NÃO POSITIVADO")
        if dias_sem_compra > 30: tags.append("SUMIDO")
        mapa[str(cod_cli)] = {"tags": tags, "dias": dias_sem_compra}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0']) if not df_mes_atual.empty else pd.Series()
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0']) if not df_mes_atual.empty else pd.Series()

real_pos_f2 = df_mes_atual[mask_f2]['Cod_Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_f6 = df_mes_atual[mask_f6]['Cod_Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_geral = df_mes_atual['Cod_Cliente'].nunique() if not df_mes_atual.empty else 0

meta_pos_f2, meta_pos_f6 = int(st.session_state.meta_pos_f2), int(st.session_state.meta_pos_f6)
meta_pos_geral = meta_pos_f2 + meta_pos_f6

real_rob_f2 = df_mes_atual[mask_f2]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_f6 = df_mes_atual[mask_f6]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_geral = real_rob_f2 + real_rob_f6

meta_rob_f2, meta_rob_f6 = float(st.session_state.meta_rob_f2), float(st.session_state.meta_rob_f6)
meta_rob_geral = meta_rob_f2 + meta_rob_f6

def calcular_real_marca(regex_marca):
    if df_mes_atual.empty: return 0
    return df_mes_atual[df_mes_atual['Produto_Busca'].str.contains(regex_marca, na=False)]['Cod_Cliente'].nunique()

real_m_lds = calcular_real_marca("lebon|doriana|seara")
real_m_frivatti = calcular_real_marca("frivatti")
real_m_brasa = calcular_real_marca("brasa")
real_m_mccain = calcular_real_marca("mccain")
real_m_confrescor = calcular_real_marca("confrescor")
real_m_ceratti = calcular_real_marca("ceratti")

# --- 🎯 EXIBIÇÃO DO CABEÇALHO COMPLETO ---
st.markdown("# 🟢 Delly's Inteligência IA")
st.write("---")

col_tit_meta, col_btn_meta = st.columns([4, 2])
with col_tit_meta: st.markdown("### 📊 Indicadores Principais")
with col_btn_meta:
    if st.session_state.modo_edicao_metas:
        if st.button("💾 Salvar Metas", key="m_save"):
            st.session_state.modo_edicao_metas = False; salvar_progresso_atual(); st.rerun()
    else:
        if st.button("📝 Editar Metas", key="m_edit"): st.session_state.modo_edicao_metas = True; st.rerun()

if st.session_state.modo_edicao_metas:
    c_ed1, c_ed2 = st.columns(2)
    with c_ed1:
        st.markdown("**Metas de Positivação**")
        st.session_state.meta_pos_f2 = st.number_input("Positivação FL2", value=meta_pos_f2, step=1)
        st.session_state.meta_pos_f6 = st.number_input("Positivação FL6", value=meta_pos_f6, step=1)
        st.markdown("**Metas Marcas Parceiras**")
        st.session_state.meta_m_lds = st.number_input("Lebon/Doriana/Seara", value=int(st.session_state.meta_m_lds), step=1)
        st.session_state.meta_m_frivatti = st.number_input("Frivatti", value=int(st.session_state.meta_m_frivatti), step=1)
        st.session_state.meta_m_brasa = st.number_input("Brasa", value=int(st.session_state.meta_m_brasa), step=1)
        st.session_state.meta_m_mccain = st.number_input("McCain", value=int(st.session_state.meta_m_mccain), step=1)
        st.session_state.meta_m_confrescor = st.number_input("Confrescor", value=int(st.session_state.meta_m_confrescor), step=1)
        st.session_state.meta_m_ceratti = st.number_input("Ceratti", value=int(st.session_state.meta_m_ceratti), step=1)
    with c_ed2:
        st.markdown("**Metas de Faturamento**")
        st.session_state.meta_rob_f2 = st.number_input("Faturamento FL2 (R$)", value=meta_rob_f2, step=1000.0)
        st.session_state.meta_rob_f6 = st.number_input("Faturamento FL6 (R$)", value=meta_rob_f6, step=1000.0)
else:
    df_indicadores = pd.DataFrame([
        {"Métrica": "🎯 Positivação Geral", "Alvo": meta_pos_geral, "Realizado": f"{real_pos_geral} clis", "Atingimento": f"{(real_pos_geral/meta_pos_geral*100) if meta_pos_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ Positivação FL2", "Alvo": meta_pos_f2, "Realizado": f"{real_pos_f2} clis", "Atingimento": f"{(real_pos_f2/meta_pos_f2*100) if meta_pos_f2>0 else 0:.1f}%"},
        {"Métrica": "◽ Positivação FL6", "Alvo": meta_pos_f6, "Realizado": f"{real_pos_f6} clis", "Atingimento": f"{(real_pos_f6/meta_pos_f6*100) if meta_pos_f6>0 else 0:.1f}%"},
        {"Métrica": "💰 Faturamento Geral", "Alvo": f"R$ {meta_rob_geral:,.2f}", "Realizado": f"R$ {real_rob_geral:,.2f}", "Atingimento": f"{(real_rob_geral/meta_rob_geral*100) if meta_rob_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ Faturamento FL2", "Alvo": f"R$ {meta_rob_f2:,.2f}", "Realizado": f"R$ {real_rob_f2:,.2f}", "Atingimento": f"{(real_rob_f2/meta_rob_f2*100) if meta_rob_f2>0 else 0:.1f}%"},
        {"Métrica": "◽ Faturamento FL6", "Alvo": f"R$ {meta_rob_f6:,.2f}", "Realizado": f"R$ {real_rob_f6:,.2f}", "Atingimento": f"{(real_rob_f6/meta_rob_f6*100) if meta_rob_f6>0 else 0:.1f}%"}
    ])
    st.table(df_indicadores)
    
    st.markdown("#### 🏷️ Marcas Parceiras (Ativação no Mês)")
    def exibir_box_marca(titulo, real, alvo):
        pct = (real / alvo * 100) if alvo > 0 else 0.0
        return f"""
        <div class="brand-box">
            <div class="brand-title">{titulo}</div>
            <div class="brand-value">{real} clis</div>
            <div class="brand-sub">Alvo: {alvo} ({pct:.1f}%)</div>
        </div>
        """
        
    bm_col1, bm_col2, bm_col3 = st.columns(3)
    with bm_col1:
        st.markdown(exibir_box_marca("Lebon/Doriana/Seara", real_m_lds, int(st.session_state.meta_m_lds)), unsafe_allow_html=True)
        st.markdown(exibir_box_marca("McCain", real_m_mccain, int(st.session_state.meta_m_mccain)), unsafe_allow_html=True)
    with bm_col2:
        st.markdown(exibir_box_marca("Frivatti", real_m_frivatti, int(st.session_state.meta_m_frivatti)), unsafe_allow_html=True)
        st.markdown(exibir_box_marca("Confrescor", real_m_confrescor, int(st.session_state.meta_m_confrescor)), unsafe_allow_html=True)
    with bm_col3:
        st.markdown(exibir_box_marca("Brasa", real_m_brasa, int(st.session_state.meta_m_brasa)), unsafe_allow_html=True)
        st.markdown(exibir_box_marca("Ceratti", real_m_ceratti, int(st.session_state.meta_m_ceratti)), unsafe_allow_html=True)

st.write("---")

# --- BOTÕES DE NAVEGAÇÃO ---
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

def obter_badges_html(cod_cliente):
    html = ""
    if df_mes_atual.empty: return html
    vendas_c = df_mes_atual[df_mes_atual['Cod_Cliente'] == str(cod_cliente)]
    if not vendas_c.empty:
        if vendas_c['Produto_Busca'].str.contains(termo_todas_marcas, na=False).any():
            html += '<span style="background-color:#FFF0B3; color:#172B4D; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">COMPROU MARCAS</span>'
    info = dict_carteira.get(str(cod_cliente), {"tags": []})
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">RECUADO</span>'
    return html

# --- INTERFACES ABAS CONTROLADAS PELA GEMINI IA ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão por Combinação de Palavras-Chave")
    if df_total.empty:
        st.info("Bancos de dados vazios.")
    else:
        tipo_lista = st.radio("Fila Ativa:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
        id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
        id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
        id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
        
        with st.expander("📝 Colar Itens de Ofertas"):
            texto_colado = st.text_area("Produtos por linha:", value="\n".join(st.session_state.get(id_memoria, [])), height=120)
            if st.button("🚀 Gerar Fila Inteligente"):
                linhas_ofertas = [l.strip() for l in texto_colado.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas_ofertas
                st.session_state.cache_ia_gemini = {}
                
                # 🧠 ENGINE DE CRUZAMENTO POR PALAVRA-CHAVE (Mapeia nichos mesmo de marcas diferentes)
                nova_fila_filtrada = {}
                # Extrai raízes de palavras significativas com mais de 3 letras das ofertas coladas
                for cod_cli, grupo_historico in df_total.groupby('Cod_Cliente'):
                    if cod_cli in st.session_state[id_excluidos]: continue
                    
                    produtos_comprados_historico = " ".join(grupo_historico['Produto_Busca'].astype(str).unique())
                    ofertas_que_combinam = []
                    
                    for oferta in linhas_ofertas:
                        palavras_oferta = re.findall(r'\b\w{4,}\b', limpar_texto(oferta))
                        # Se o cliente já comprou termos parecidos (Ex: comprou batata tradicional, oferta é batata McCain)
                        if any(p in produtos_comprados_historico for p in palavras_oferta):
                            ofertas_que_combinam.append(oferta)
                            
                    if ofertas_que_combinam:
                        nova_fila_filtrada[str(cod_cli)] = ofertas_que_combinam
                
                st.session_state[id_fila] = nova_fila_filtrada
                salvar_progresso_atual(); st.rerun()

        fila_ativa = st.session_state.get(id_fila)
        if fila_ativa:
            cod_cli_corrente = list(fila_ativa.keys())[0]
            inf = obter_info_cliente(cod_cli_corrente)
            
            st.markdown(f"### 🏢 {inf['Razao']} \n *({inf['Nome_Fantasia'] if inf['Fantasia'] else 'Sem Fantasia'} - {inf['Cidade']})*")
            st.markdown(f"**Código Interno:** {cod_cli_corrente}")
            st.markdown(obter_badges_html(cod_cli_corrente), unsafe_allow_html=True)
            
            historico_produtos = df_total[df_total['Cod_Cliente'] == cod_cli_corrente]['Produto'].dropna().unique()
            produtos_combinados_hoje = fila_ativa[cod_cli_corrente]
            
            chave_cache = f"{cod_cli_corrente}_{id_fila}"
            
            if chave_cache not in st.session_state.cache_ia_gemini:
                with st.spinner("🧠 Gemini estruturando a oferta com base no nicho encontrado..."):
                    try:
                        prompt_ia = f"""
                        Você é o consultor master da distribuidora Delly's. 
                        Escreva uma mensagem comercial exclusiva para WhatsApp focando nos produtos em oferta que COMBINAM com o perfil desse cliente.
                        
                        CLIENTE: {inf['Razao']} (Fantasia: {inf['Fantasia']})
                        LOCAL: {inf['Cidade']}
                        
                        PRODUTOS QUE ELE JÁ COMPROU NO PASSADO (Nicho dele):
                        {list(historico_produtos)[:12]}
                        
                        OFERTAS DA DELLY'S QUE COMBINAM COM ELE HOJE (Foque nisso):
                        {produtos_combinados_hoje}
                        
                        REGRAS: Estilo direto, parágrafos curtos, gatilho de oportunidade rápida, use pouquíssimos emojis. Sem inventar dados.
                        """
                        model_flash = genai.GenerativeModel("gemini-1.5-flash")
                        st.session_state.cache_ia_gemini[chave_cache] = model_flash.generate_content(prompt_ia).text
                    except:
                        st.session_state.cache_ia_gemini[chave_cache] = "Olá! Identificamos que as novas ofertas de marcas parceiras combinam muito com seu histórico de compras. Vamos repor o estoque?"

            st.markdown("**📝 Texto de Abordagem Sugerido pela IA:**")
            st.code(st.session_state.cache_ia_gemini[chave_cache])
            
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                if st.button("✅ Confirmar e Ir Próximo"):
                    st.session_state.envios_hoje += 1; st.session_state[id_excluidos].add(cod_cli_corrente)
                    del st.session_state[id_fila][cod_cli_corrente]; salvar_progresso_atual(); st.rerun()
            with c_a2:
                if st.button("❌ Pular Cliente"): del st.session_state[id_fila][cod_cli_corrente]; st.rerun()
        else:
            st.success("🎉 Nenhuma oferta pendente ou sem combinações encontradas para os alvos colados!")

elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Alertas de Churn Analisados pela IA")
    alertas_lista = [{"Cod": c, "Razao": obter_info_cliente(c)["Razao"], "Dias_Inativo": d["dias"]} for c, d in dict_carteira.items() if d["dias"] > 30]
    
    if alertas_lista:
        df_alerta = pd.DataFrame(alertas_lista).sort_values(by="Dias_Inativo", ascending=False)
        st.dataframe(df_alerta, use_container_width=True)
        
        if st.button("🧠 Solicitar Plano de Ação Geral ao Gemini"):
            with st.spinner("Analisando carteira inativa..."):
                prompt_alerta = f"Com base nessa amostra de clientes da distribuidora que sumiram há mais de 30 dias: {alertas_lista[:10]}. Dê 3 dicas cirúrgicas e comerciais para a equipe de vendas reverter esse cenário imediatamente."
                model_flash = genai.GenerativeModel("gemini-1.5-flash")
                st.info(model_flash.generate_content(prompt_alerta).text)
    else: st.success("Nenhum cliente em Churn de faturamento!")

elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Diagnóstico Comercial Inteligente")
    if not df_total.empty:
        codigos_unicos = sorted(list(df_total['Cod_Cliente'].unique()))
        c_sel = st.selectbox("Selecione o Código do Cliente:", [""] + codigos_unicos)
        if c_sel:
            inf = obter_info_cliente(c_sel)
            st.markdown(f"### {inf['Razao']}")
            st.markdown(f"📍 **Cidade:** {inf['Cidade']} | **Nome Fantasia:** {inf['Fantasia']}")
            st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
            
            prods = df_total[df_total['Cod_Cliente'] == c_sel]['Produto'].dropna().unique()
            st.write("🛒 **Histórico Físico de Itens:**", ", ".join(list(prods)[:20]))
            
            if st.button("🧠 Pedir Análise de Perfil ao Gemini"):
                with st.spinner("Estudando comportamento..."):
                    prompt_perfil = f"O cliente '{inf['Razao']}' possui este histórico de compras: {list(prods)[:30]}. Defina em uma linha qual é o provável nicho dele (ex: pizzaria, mercado, etc) e qual produto complementar das marcas McCain, Seara ou Ceratti deveríamos oferecer."
                    model_flash = genai.GenerativeModel("gemini-1.5-flash")
                    st.success(model_flash.generate_content(prompt_perfil).text)

elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Otimização Comercial de Itens")
    if not df_total.empty:
        p_sel = st.selectbox("Selecione o Produto:", [""] + sorted(list(df_total['Produto'].dropna().unique())))
        if p_sel:
            df_p = df_total[df_total['Produto'] == p_sel]
            st.metric("Total Faturado no Item", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
            
            if st.button("🧠 Gerar Argumento de Venda com Gemini"):
                with st.spinner("Criando pitch..."):
                    prompt_prod = f"Gere um argumento de vendas matador de 2 frases para o produto '{p_sel}' focado em convencer donos de estabelecimentos comerciais de alimentação."
                    model_flash = genai.GenerativeModel("gemini-1.5-flash")
                    st.warning(model_flash.generate_content(prompt_prod).text)

elif st.session_state.aba_atual == "🧠 Assistente":
    st.subheader("🧠 Consultor Virtual de Vendas")
    p_user = st.text_input("Qual a dúvida comercial ou estratégica hoje?")
    if p_user:
        model_flash = genai.GenerativeModel("gemini-1.5-flash")
        st.info(model_flash.generate_content(p_user).text)

elif st.session_state.aba_atual == "🏷️ Marcas":
    st.subheader("🏷️ Campanhas Estratégicas para Marcas Exclusivas")
    if df_total.empty:
        st.info("Sem dados consolidados para cruzar.")
    else:
        mask_m_total = df_total['Produto_Busca'].str.contains(termo_todas_marcas, na=False)
        clientes_historico_marcas = set(df_total[mask_m_total]['Cod_Cliente'].unique())
        
        if not df_mes_atual.empty:
            mask_m_mes = df_mes_atual['Produto_Busca'].str.contains(termo_todas_marcas, na=False)
            clientes_marcas_mes = set(df_mes_atual[mask_m_mes]['Cod_Cliente'].unique())
        else:
            clientes_marcas_mes = set()
            
        clientes_churn_marcas = clientes_historico_marcas - clientes_marcas_mes
        
        st.markdown(f"**Clientes que abandonaram marcas parceiras neste mês:** {len(clientes_churn_marcas)}")
        if clientes_churn_marcas and st.button("🧠 Criar Pitch de Reativação para Marcas"):
            with st.spinner("Gerando campanha..."):
                ex_clientes = [obter_info_cliente(c)["Razao"] for c in list(clientes_churn_marcas)[:5]]
                prompt_m = f"Monte uma mensagem curta de reengajamento direcionada a clientes como {ex_clientes} que já compraram nossas marcas exclusivas (Seara, McCain, Ceratti, Frivatti, Brasa) mas não realizaram nenhum pedido delas esse mês."
                model_flash = genai.GenerativeModel("gemini-1.5-flash")
                st.write(model_flash.generate_content(prompt_m).text)
