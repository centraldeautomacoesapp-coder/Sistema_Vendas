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

# --- 🧠 CONEXÃO ROBUSTA E EXTRAÇÃO DE BANCOS DE DADOS DELIVERIES ---
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

with st.spinner("Conectando e sincronizando bases Delly's..."):
    df_total = carregar_dados_vendas()
    df_clientes = carregar_base_clientes_cadastro()

mes_exibicao = mes_atual_referencia
if not df_total.empty:
    meses_com_dados = df_total['Ano_Mes'].dropna().unique()
    if mes_atual_referencia not in meses_com_dados and len(meses_com_dados) > 0:
        mes_exibicao = max(meses_com_dados)

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_exibicao] if not df_total.empty else pd.DataFrame()

termo_todas_marcas = "lebon|doriana|seara|frivatti|brasa|mccain|confrescor|ceratti"

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

mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0']) if not df_mes_atual.empty else pd.Series()
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0']) if not df_mes_atual.empty else pd.Series()

real_pos_f2 = df_mes_atual[mask_f2]['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_f6 = df_mes_atual[mask_f6]['Cliente'].nunique() if not df_mes_atual.empty else 0
real_pos_geral = df_mes_atual['Cliente'].nunique() if not df_mes_atual.empty else 0

meta_pos_f2, meta_pos_f6 = int(st.session_state.meta_pos_f2), int(st.session_state.meta_pos_f6)
meta_pos_geral = meta_pos_f2 + meta_pos_f6

real_rob_f2 = df_mes_atual[mask_f2]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_f6 = df_mes_atual[mask_f6]['Faturamento Brut'].sum() if not df_mes_atual.empty else 0.0
real_rob_geral = real_rob_f2 + real_rob_f6

meta_rob_f2, meta_rob_f6 = float(st.session_state.meta_rob_f2), float(st.session_state.meta_rob_f6)
meta_rob_geral = meta_rob_f2 + meta_rob_f6

def calcular_real_marca(regex_marca):
    if df_mes_atual.empty: return 0
    return df_mes_atual[df_mes_atual['Produto_Busca'].str.contains(regex_marca, na=False)]['Cliente'].nunique()

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

def obter_badges_html(cliente_nome):
    html = ""
    if df_mes_atual.empty: return html
    vendas_c = df_mes_atual[df_mes_atual['Cliente'] == cliente_nome]
    if not vendas_c.empty:
        if vendas_c['Produto_Busca'].str.contains(termo_todas_marcas, na=False).any():
            html += '<span style="background-color:#FFF0B3; color:#172B4D; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">COMPROU MARCAS</span>'
    info = dict_carteira.get(cliente_nome, {"tags": []})
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">RECUADO</span>'
    return html

# --- INTERFACES DAS ABAS ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão Inteligente")
    if df_total.empty:
        st.info("Bancos de dados vazios.")
    else:
        tipo_lista = st.radio("Fila Ativa:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
        id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
        id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
        id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
        
        with st.expander("📝 Colar Itens de Ofertas"):
            texto_colado = st.text_area("Produtos por linha:", value="\n".join(st.session_state.get(id_memoria, [])), height=120)
            if st.button("🚀 Atualizar Fila"):
                linhas = [l.strip() for l in texto_colado.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas
                st.session_state[id_fila] = {c: linhas for c in df_total['Cliente'].dropna().unique() if c not in st.session_state[id_excluidos]}
                st.session_state.cache_ia_gemini = {} # Limpa o cache ao mudar ofertas
                salvar_progresso_atual(); st.rerun()

        fila_ativa = st.session_state.get(id_fila)
        if fila_ativa:
            cli_corrente = list(fila_ativa.keys())[0]
            inf = obter_info_cliente(cli_corrente)
            
            st.markdown(f"### 🏢 {cli_corrente} ({inf['Cidade']})")
            st.markdown(obter_badges_html(cli_corrente), unsafe_allow_html=True)
            
            # 🧠 --- AQUI ENTRA O CRUZA-DADOS DA IA VERDADEIRA ---
            # Puxamos o que ele já comprou na história para a IA analisar o nicho/perfil dele
            historico_produtos = df_total[df_total['Cliente'] == cli_corrente]['Produto'].dropna().unique()
            produtos_oferecidos_hoje = fila_ativa[cli_corrente]
            
            # Chave única de identificação no cache para não gastar sua API toda hora que a tela recarregar
            chave_cache = f"{cli_corrente}_{id_fila}"
            
            if chave_cache not in st.session_state.cache_ia_gemini:
                with st.spinner("🧠 Gemini analisando histórico do cliente e criando oferta personalizada..."):
                    try:
                        prompt_ia = f"""
                        Você é o especialista comercial de inteligência da distribuidora Delly's.
                        Gere uma mensagem comercial curta e persuasiva para enviar via WhatsApp para o cliente '{cli_corrente}' de '{inf['Cidade']}'.

                        HISTÓRICO REAL DE COMPRAS DELE (Use para entender o nicho dele):
                        {list(historico_produtos)[:15]}

                        PRODUTOS EM OFERTA HOJE (Escolha os melhores ou relacione com as marcas parceiras):
                        {produtos_oferecidos_hoje}

                        NOSSAS MARCAS EXCLUSIVAS/PARCEIRAS EM FOCO:
                        Lebon, Doriana, Seara, Frivatti, Brasa, McCain, Confrescor e Ceratti.

                        REGRAS DA MENSAGEM:
                        1. Seja muito direto, simpático e profissional.
                        2. Use quebras de linha e poucos emojis para leitura rápida no celular.
                        3. Cite o nome de alguma marca parceira se fizer sentido com o nicho dele (ex: se ele compra muita batata, foque na McCain).
                        4. Não invente preços ou prazos. Apenas monte o texto de abordagem comercial.
                        """
                        model_flash = genai.GenerativeModel("gemini-1.5-flash")
                        resposta_ia = model_flash.generate_content(prompt_ia).text
                        st.session_state.cache_ia_gemini[chave_cache] = resposta_ia
                    except Exception as e:
                        st.session_state.cache_ia_gemini[chave_cache] = f"Olá! Separamos excelentes oportunidades em marcas parceiras como McCain, Seara e Frivatti hoje para o seu negócio. Vamos aproveitar?"

            msg_venda = st.session_state.cache_ia_gemini[chave_cache]
            
            st.markdown("**📝 Abordagem Gerada por Inteligência Artificial:**")
            st.code(msg_venda)
            
            c_a1, c_a2 = st.columns(2)
            with c_a1:
                if st.button("✅ Confirmar Envio"):
                    st.session_state.envios_hoje += 1; st.session_state[id_excluidos].add(cli_corrente)
                    del st.session_state[id_fila][cli_corrente]; salvar_progresso_atual(); st.rerun()
            with c_a2:
                if st.button("❌ Pular"): del st.session_state[id_fila][cli_corrente]; st.rerun()
        else:
            st.success("🎉 Nenhuma oferta pendente nesta fila!")

elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Clientes Inativos (Mais de 30 dias)")
    alertas = [{"Cliente": c, "Dias Inativo": d["dias"]} for c, d in dict_carteira.items() if d["dias"] > 30]
    if alertas: st.dataframe(pd.DataFrame(alertas).sort_values(by="Dias Inativo", ascending=False), use_container_width=True)
    else: st.success("Nenhum cliente em Churn de faturamento!")

elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Histórico e Cruzamentos por Cliente")
    if not df_total.empty:
        c_sel = st.selectbox("Selecione o Cliente:", [""] + sorted(list(df_total['Cliente'].unique())))
        if c_sel:
            inf = obter_info_cliente(c_sel)
            st.markdown(f"### {inf['Nome']}")
            st.markdown(f"📍 Cidade: {inf['Cidade']} | Fantasia: {inf['Fantasia']}")
            st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
            prods = df_total[df_total['Cliente'] == c_sel]['Produto'].dropna().unique()
            st.write("🛒 **Produtos comprados anteriormente:**", ", ".join(list(prods)[:40]))

elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Análise de Faturamento por Item")
    if not df_total.empty:
        p_sel = st.selectbox("Selecione o Produto para Rastrear:", [""] + sorted(list(df_total['Produto'].dropna().unique())))
        if p_sel:
            df_p = df_total[df_total['Produto'] == p_sel]
            st.metric("Total Faturado no Item", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
            st.dataframe(df_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(15))

elif st.session_state.aba_atual == "🧠 Assistente":
    st.subheader("🧠 Consultor Virtual de Vendas")
    p_user = st.text_input("Qual a dúvida comercial hoje?")
    if p_user:
        model_flash = genai.GenerativeModel("gemini-1.5-flash")
        st.info(model_flash.generate_content(p_user).text)

elif st.session_state.aba_atual == "🏷️ Marcas":
    st.subheader("🏷️ Painel de Alvos de Marcas Parceiras")
    if df_total.empty:
        st.info("Sem dados consolidados para cruzar.")
    else:
        mask_m_total = df_total['Produto_Busca'].str.contains(termo_todas_marcas, na=False)
        clientes_historico_marcas = set(df_total[mask_m_total]['Cliente'].unique())
        
        if not df_mes_atual.empty:
            mask_m_mes = df_mes_atual['Produto_Busca'].str.contains(termo_todas_marcas, na=False)
            clientes_marcas_mes = set(df_mes_atual[mask_m_mes]['Cliente'].unique())
        else:
            clientes_marcas_mes = set()
            
        clientes_churn_marcas = clientes_historico_marcas - clientes_marcas_mes
        todos_cadastro = set(df_clientes['Cliente'].unique()) if not df_clientes.empty else set(df_total['Cliente'].unique())
        clientes_nunca_marcas = todos_cadastro - clientes_historico_marcas
        
        tab_m1, tab_m2 = st.tabs(["⚠️ Pararam de Comprar Marcas", "🎯 Nunca Compraram Marcas"])
        with tab_m1:
            if clientes_churn_marcas:
                df_c_m = pd.DataFrame([obter_info_cliente(c) for c in clientes_churn_marcas])
                st.dataframe(df_c_m[['Nome', 'Fantasia', 'Cidade']].drop_duplicates(), use_container_width=True)
            else: st.success("Nenhum cliente ativo abandonou as marcas parceiras!")
        with tab_m2:
            if clientes_nunca_marcas:
                df_n_m = pd.DataFrame([obter_info_cliente(c) for c in clientes_nunca_marcas])
                st.dataframe(df_n_m[['Nome', 'Fantasia', 'Cidade']].drop_duplicates(), use_container_width=True)
            else: st.info("Todos os clientes já positivaram alguma marca parceira na história.")
