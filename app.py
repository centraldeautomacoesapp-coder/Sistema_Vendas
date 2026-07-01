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
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f: json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")

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

if 'meta_pos_f2' not in st.session_state: st.session_state.meta_pos_f2 = progresso_backup.get("meta_pos_f2", 0)
if 'meta_pos_f6' not in st.session_state: st.session_state.meta_pos_f6 = progresso_backup.get("meta_pos_f6", 0)
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)

if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False

def limpar_texto(texto):
    if pd.isna(texto): return ""
    texto_normalizado = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z0-9\s]', '', texto_normalizado).strip().lower()

def extrair_codigo(nome_completo):
    match = re.search(r'^(\d+)', str(nome_completo))
    return match.group(1) if match else "S/C"

# --- 📁 CONEXÃO E CAPTURA DE PLANILHAS (DRIVE) ---
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

with st.spinner("Sincronizando inteligência de dados Delly's..."):
    df_total = carregar_dados_vendas()
    df_clientes = carregar_base_clientes_cadastro()

mes_exibicao = mes_atual_referencia
if not df_total.empty:
    meses_com_dados = df_total['Ano_Mes'].dropna().unique()
    if mes_atual_referencia not in meses_com_dados and len(meses_com_dados) > 0:
        mes_exibicao = max(meses_com_dados)

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_exibicao] if not df_total.empty else pd.DataFrame()

# Mapeamento estrito de marcas parceiras
regex_seara = "lebon|doriana|seara|frangosul"
regex_mccain = "mccain"
regex_frivatti = "frivatti"
regex_confrescor = "confrescor"
regex_brasa = "brasa"
regex_ceratti = "ceratti"

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

# --- 🌐 LÓGICA ESPECIALIZADA DE NICHOS COMERCIAIS ---
def identificar_nicho(nome, fantasia):
    texto = limpar_texto(nome) + " " + limpar_texto(fantasia)
    if any(w in texto for w in ["restaurante", "rest", "gourmet", "cozinha", "grill", "buffet", "comida"]): return "Restaurante"
    if any(w in texto for w in ["pizzaria", "pizza"]): return "Pizzaria"
    if any(w in texto for w in ["hamburgueria", "burger", "burguer"]): return "Hamburgueria"
    if any(w in texto for w in ["mercado", "mercadinho", "supermercado", "mercearia", "aspa", "venda"]): return "Mercado"
    if any(w in texto for w in ["padaria", "panificadora", "confeitaria", "bolo"]): return "Padaria"
    if any(w in texto for w in ["lanchonete", "lanche", "snack", "pastel", "dog", "sub"]): return "Lanchonete"
    if any(w in texto for w in ["churrascaria", "espeto", "espetinho", "assado", "carne"]): return "Churrascaria"
    return "Geral"

@st.cache_data(ttl=600)
def calcular_produtos_por_nicho(df):
    nicho_produtos = {}
    if df.empty: return nicho_produtos
    mapa_nichos = {}
    for cli in df['Cliente'].unique():
        inf = obter_info_cliente(cli)
        mapa_nichos[cli] = identificar_nicho(inf['Nome'], inf['Fantasia'])
    
    df_temp = df.copy()
    df_temp['Nicho'] = df_temp['Cliente'].map(mapa_nichos)
    for nicho in df_temp['Nicho'].unique():
        top_items = df_temp[df_temp['Nicho'] == nicho]['Produto_Busca'].value_counts().head(15).index.tolist()
        nicho_produtos[nicho] = top_items
    return nicho_produtos

nichos_produtos_db = calcular_produtos_por_nicho(df_total)

def verificar_match_produto(linha_oferta, produto_busca):
    linha_limpa = limpar_texto(linha_oferta)
    if produto_busca in linha_limpa or linha_limpa in produto_busca: return True
    tokens_prod = [p for p in produto_busca.split() if len(p) > 3]
    if tokens_prod and all(t in linha_limpa for t in tokens_prod): return True
    return False

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

# --- FUNÇÃO CORRIGIDA PARA IDENTIFICAR POSITIVAÇÃO DE MARCAS ---
def calcular_real_marca(regex_marca):
    if df_mes_atual.empty: return 0
    mask = df_mes_atual['Produto_Busca'].str.contains(regex_marca, na=False)
    return df_mes_atual[mask]['Cliente'].nunique()

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
    with c_ed2:
        st.session_state.meta_rob_f2 = st.number_input("Fat. FL2 (R$)", value=float(st.session_state.meta_rob_f2), step=1000.0)
        st.session_state.meta_rob_f6 = st.number_input("Fat. FL6 (R$)", value=float(st.session_state.meta_rob_f6), step=1000.0)
else:
    df_indicadores = pd.DataFrame([
        {"Métrica": "🎯 Positivação Geral", "Alvo": meta_pos_geral, "Realizado": f"{real_pos_geral} clis", "Ating.": f"{(real_pos_geral/meta_pos_geral*100) if meta_pos_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ Positivação FL2", "Alvo": st.session_state.meta_pos_f2, "Realizado": f"{real_pos_f2} clis", "Ating.": f"{(real_pos_f2/int(st.session_state.meta_pos_f2)*100) if int(st.session_state.meta_pos_f2)>0 else 0:.1f}%"},
        {"Métrica": "◽ Positivação FL6", "Alvo": st.session_state.meta_pos_f6, "Realizado": f"{real_pos_f6} clis", "Ating.": f"{(real_pos_f6/int(st.session_state.meta_pos_f6)*100) if int(st.session_state.meta_pos_f6)>0 else 0:.1f}%"},
        {"Métrica": "💰 Faturamento Geral", "Alvo": f"R$ {meta_rob_geral:,.2f}", "Realizado": f"R$ {real_rob_geral:,.2f}", "Ating.": f"{(real_rob_geral/meta_rob_geral*100) if meta_rob_geral>0 else 0:.1f}%"},
        {"Métrica": "◽ Faturamento FL2", "Alvo": f"R$ {float(st.session_state.meta_rob_f2):,.2f}", "Realizado": f"R$ {real_rob_f2:,.2f}", "Ating.": f"{(real_rob_f2/float(st.session_state.meta_rob_f2)*100) if float(st.session_state.meta_rob_f2)>0 else 0:.1f}%"},
        {"Métrica": "◽ Faturamento FL6", "Alvo": f"R$ {float(st.session_state.meta_rob_f6):,.2f}", "Realizado": f"R$ {real_rob_f6:,.2f}", "Ating.": f"{(real_rob_f6/float(st.session_state.meta_rob_f6)*100) if float(st.session_state.meta_rob_f6)>0 else 0:.1f}%"}
    ])
    st.table(df_indicadores)
    
    st.markdown("#### 🏷️ Marcas Parceiras (Positivas no Mês)")
    
    def renderizar_box_marca(titulo, real):
        return f"""<div style="background-color: #f8f9fa; padding: 6px; border-radius: 6px; border-left: 3px solid #FFC107; margin-bottom: 8px; text-align: center; box-shadow: 0px 1px 3px rgba(0,0,0,0.05);"><div style="font-size: 11px; color: #555; font-weight: bold; text-transform: uppercase;">{titulo}</div><div style="font-size: 15px; font-weight: bold; color: #111; margin: 2px 0;">{real} clis</div></div>"""

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.markdown(renderizar_box_marca("SEARA", real_m_seara), unsafe_allow_html=True)
        st.markdown(renderizar_box_marca("FRIVATTI", real_m_frivatti), unsafe_allow_html=True)
        st.markdown(renderizar_box_marca("BRASA", real_m_brasa), unsafe_allow_html=True)
    with b_col2:
        st.markdown(renderizar_box_marca("MCCAIN", real_m_mccain), unsafe_allow_html=True)
        st.markdown(renderizar_box_marca("CONFRESCOR", real_m_confrescor), unsafe_allow_html=True)
        st.markdown(renderizar_box_marca("CERATTI", real_m_ceratti), unsafe_allow_html=True)

st.write("---")

# --- NAVEGAÇÃO INTERNA MOBILE ---
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
# 🟢 ABA OFERTAS (FILAS CRUZADAS + NICHO)
# ==========================================
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão Segmentado")
    if df_total.empty:
        st.info("Bancos de dados vazios.")
    else:
        tipo_lista = st.radio("Fila Ativa:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
        id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
        id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
        id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
        
        with st.expander("📝 Configurar Texto das Ofertas"):
            texto_colado = st.text_area("Insira as ofertas do dia:", value="\n".join(st.session_state.get(id_memoria, [])), height=100)
            if st.button("🚀 Processar Inteligência Comercial"):
                linhas = [l.strip() for l in texto_colado.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas
                
                nova_fila = {}
                for cli in df_total['Cliente'].dropna().unique():
                    if cli in st.session_state[id_excluidos]: continue
                    inf_c = obter_info_cliente(cli)
                    nicho_c = identificar_nicho(inf_c['Nome'], inf_c['Fantasia'])
                    
                    prods_historico = set(df_total[df_total['Cliente'] == cli]['Produto_Busca'].unique())
                    prods_sugeridos_nicho = set(nichos_produtos_db.get(nicho_c, []))
                    
                    matches_historico = []
                    matches_niche = []
                    
                    for linha_of in linhas:
                        hist_match = False
                        for p_hist in prods_historico:
                            if verificar_match_produto(linha_of, p_hist):
                                matches_historico.append(linha_of)
                                hist_match = True
                                break
                        
                        if not hist_match:
                            for p_nicho in prods_sugeridos_nicho:
                                if p_nicho not in prods_historico:
                                    if verificar_match_produto(linha_of, p_nicho):
                                        matches_niche.append(linha_of)
                                        break
                                        
                    if matches_historico or matches_niche:
                        nova_fila[cli] = {
                            "historico": list(set(matches_historico)),
                            "nicho": list(set(matches_niche))
                        }
                        
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.rerun()

        fila_ativa = st.session_state.get(id_fila) or {}
        if fila_ativa:
            cli_corrente = list(fila_ativa.keys())[0]
            inf = obter_info_cliente(cli_corrente)
            info_c = dict_carteira.get(cli_corrente, {"tags": []})
            nicho_atual = identificar_nicho(inf['Nome'], inf['Fantasia'])
            
            st.markdown(f"### 🏢 Código: {inf['Código']}")
            st.markdown(f"**Razão:** {inf['Nome']}\n\n**Fantasia:** {inf['Fantasia']} | **Cidade:** {inf['Cidade']}")
            st.markdown(renderizar_tags_html(info_c["tags"]), unsafe_allow_html=True)
            
            st.markdown("**📱 Texto Gerado para WhatsApp:**")
            dados_oferta = fila_ativa[cli_corrente]
            
            msg_whatsapp = f"Olá! Tudo bem? Separamos algumas oportunidades exclusivas de itens que você já trabalha conosco da Delly's:\n\n"
            if dados_oferta["historico"]:
                for p in dados_oferta["historico"]: msg_whatsapp += f"{p}\n"
            else:
                msg_whatsapp += "• (Consulte nossa tabela para reposição de estoque!)\n"
                
            if dados_oferta["nicho"]:
                msg_whatsapp += f"\n💡 *Recomendado para o segmento {nicho_atual} (Novidades mais vendidas):*\n"
                for p in dados_oferta["nicho"]: msg_whatsapp += f"{p}\n"
                
            msg_whatsapp += "\nVamos aproveitar para garantir estas opções no pedido de hoje?"
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
            st.success("Fila limpa ou concluída para o dia atual!")

# ==========================================
# 🚨 ABA ALERTAS
# ==========================================
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Recuperação de Clientes Inativos")
    
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
        st.success("Nenhum cliente inativo acima de 45 dias!")
    else:
        df_alertas_ativos = pd.DataFrame(lista_alertas).sort_values(by="Dias", ascending=False)
        
        c_flt1, c_flt2 = st.columns(2)
        with c_flt1: f_status = st.selectbox("Envio:", ["TODOS", "NÃO ENVIADO", "ENVIADO"])
        with c_flt2: f_cidade = st.selectbox("Cidade:", ["TODAS"] + sorted(list(df_alertas_ativos['Cidade'].unique())))
            
        if f_status != "TODOS": df_alertas_ativos = df_alertas_ativos[df_alertas_ativos['Status'] == f_status]
        if f_cidade != "TODAS": df_alertas_ativos = df_alertas_ativos[df_alertas_ativos['Cidade'] == f_cidade]
        
        c_bt_al1, c_bt_al2 = st.columns(2)
        chaves_selecionadas = []
        
        with st.container():
            st.write("---")
            for idx, row in df_alertas_ativos.iterrows():
                marcado = st.checkbox(f"📍 {row['Código']} - {row['Fantasia'] or row['Nome'][:20]}", key=f"chk_{row['Cliente_Id']}")
                if marcado: chaves_selecionadas.append(row['Cliente_Id'])
                st.markdown(renderizar_tags_html([row['Status'], f"{row['Dias']} DIAS"]), unsafe_allow_html=True)
                st.write(f"*{row['Nome']} | {row['Cidade']}*")
                st.write("---")
                
        with c_bt_al1:
            if st.button("📊 Gerar Relatório"):
                if not chaves_selecionadas: st.warning("Selecione clientes.")
                else:
                    txt_relatorio = "📝 REQUERIMENTO DE RECUPERAÇÃO EXCLUSIVA\n\n"
                    for cli in chaves_selecionadas:
                        inf_c = obter_info_cliente(cli)
                        dias_s = dict_carteira[cli]["dias"]
                        top_prods = df_total[df_total['Cliente'] == cli]['Produto'].value_counts().head(3).index.tolist()
                        txt_relatorio += f"🏢 CÓD: {inf_c['Código']} | {inf_c['Nome']}\n"
                        txt_relatorio += f"⚠️ OUT: {dias_s} dias | CIDADE: {inf_c['Cidade']}\n"
                        txt_relatorio += "🛒 PRODUTOS HISTÓRICOS CHAVE:\n"
                        for p in top_prods: txt_relatorio += f"  • {p}\n"
                        txt_relatorio += "----------------------------------------\n"
                    st.text_area("📋 Copiar para Supervisor:", value=txt_relatorio, height=180)
                    
        with c_bt_al2:
            if st.button("✅ Marcar Enviados"):
                for cli in chaves_selecionadas: st.session_state.alertas_enviados.add(cli)
                salvar_progresso_atual(); st.rerun()

# ==========================================
# 🔍 ABA CONSULTA CLIENTE
# ==========================================
elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Histórico Executivo por Cliente")
    if not df_total.empty:
        busca_cli = st.text_input("Buscar por código, razão ou fantasia:")
        clientes_filtrados = sorted(list(df_total['Cliente'].unique()))
        if busca_cli:
            clientes_filtrados = [c for c in clientes_filtrados if limpar_texto(busca_cli) in limpar_texto(c)]
            
        c_sel = st.selectbox("Selecione o Cliente:", [""] + clientes_filtrados)
        if c_sel:
            inf = obter_info_cliente(c_sel)
            info_c = dict_carteira.get(c_sel, {"tags": []})
            nicho_c = identificar_nicho(inf['Nome'], inf['Fantasia'])
            
            tags_completas = list(info_c["tags"])
            vendas_c_mes = df_mes_atual[df_mes_atual['Cliente'] == c_sel] if not df_mes_atual.empty else pd.DataFrame()
            if not vendas_c_mes.empty:
                txt_v_mes = " ".join(vendas_c_mes['Produto_Busca'].unique())
                if re.search(regex_seara, txt_v_mes): tags_completas.append("SEARA")
                if re.search(regex_frivatti, txt_v_mes): tags_completas.append("FRIVATTI")
                if re.search(regex_mccain, txt_v_mes): tags_completas.append("MCCAIN")
                if re.search(regex_brasa, txt_v_mes): tags_completas.append("BRASA")
                if re.search(regex_confrescor, txt_v_mes): tags_completas.append("CONFRESCOR")
                if re.search(regex_ceratti, txt_v_mes): tags_completas.append("CERATTI")
            
            st.markdown(f"### {inf['Código']} - {inf['Nome']}")
            st.markdown(f"📍 Cidade: {inf['Cidade']} | Segmento: **{nicho_c}**")
            st.markdown(renderizar_tags_html(tags_completas), unsafe_allow_html=True)
            st.write("---")
            
            st.markdown("🔥 **Produtos em Oferta Combinando com o Cliente:**")
            ofertas_ativas = st.session_state.get("memoria_ofertas_cruas_dia", []) + st.session_state.get("memoria_ofertas_cruas_rel", [])
            prods_historico_todos = df_total[df_total['Cliente'] == c_sel]['Produto_Busca'].unique()
            matches_oferta = []
            for of in ofertas_ativas:
                for p in prods_historico_todos:
                    if verificar_match_produto(of, p): matches_oferta.append(of); break
            if matches_oferta:
                for m in set(matches_oferta): st.success(f"• {m}")
            else: st.write("*Nenhuma combinação para hoje.*")
            
            st.markdown(f"💡 **Produtos Recomendados para o Segmento ({nicho_c}):**")
            prods_populares_nicho = nichos_produtos_db.get(nicho_c, [])
            recomendados_nicho = [p for p in prods_populares_nicho if p not in prods_historico_todos][:5]
            if recomendados_nicho:
                for p_rec in recomendados_nicho: st.info(f"• {p_rec.upper()} (O segmento usa muito)")
            else: st.write("*Mix do segmento completo.*")
            
            st.markdown("📊 **Top 10 Produtos Mais Comprados:**")
            top_10 = df_total[df_total['Cliente'] == c_sel]['Produto'].value_counts().head(10)
            for p, qtd in top_10.items(): st.write(f"🔹 {p} ({qtd}x)")
                
            st.markdown("⏳ **Produtos Abandonados:**")
            ultimas_por_item = df_total[df_total['Cliente'] == c_sel].groupby('Produto')['Data_Datetime'].max()
            for prod, dt_u in ultimas_por_item.items():
                if dt_u < pd.to_datetime(mes_exibicao + "-01"):
                    st.warning(f"• {prod} (Último em: {dt_u.strftime('%d/%m/%Y')})")

# ==========================================
# 📦 ABA CONSULTA PRODUTO
# ==========================================
elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Rastreamento por Item e Nicho")
    if not df_total.empty:
        busca_prod = st.text_input("Buscar Produto (Desconsidera acentos/ç):")
        produtos_lista = sorted(list(df_total['Produto'].dropna().unique()))
        if busca_prod:
            produtos_lista = [p for p in produtos_lista if limpar_texto(busca_prod) in limpar_texto(p)]
            
        p_sel = st.selectbox("Selecione o Item:", [""] + produtos_lista)
        if p_sel:
            p_sel_busca = limpar_texto(p_sel)
            df_p = df_total[df_total['Produto_Busca'] == p_sel_busca]
            st.metric("Total Faturado no Item", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
            
            nichos_compradores = []
            for c_comprador in df_p['Cliente'].unique():
                inf_cc = obter_info_cliente(c_comprador)
                nichos_compradores.append(identificar_nicho(inf_cc['Nome'], inf_cc['Fantasia']))
            nicho_predominante = max(set(nichos_compradores), key=nichos_compradores.count) if nichos_compradores else "Geral"
            
            st.markdown("**🏢 Recomendações de Clientes e Prospecção:**")
            for c in df_total['Cliente'].dropna().unique():
                inf = obter_info_cliente(c)
                clientes_compraram = set(df_p['Cliente'].unique())
                nicho_deste_cli = identificar_nicho(inf['Nome'], inf['Fantasia'])
                
                if c in clientes_compraram:
                    st.markdown(f"👤 **{inf['Código']} - {inf['Fantasia'] or inf['Nome']}** ({inf['Cidade']})")
                    st.markdown(renderizar_tags_html(["JÁ COMPROU"]), unsafe_allow_html=True)
                    st.write("---")
                elif nicho_deste_cli == nicho_predominante:
                    st.markdown(f"👤 **{inf['Código']} - {inf['Fantasia'] or inf['Nome']}** ({inf['Cidade']})")
                    st.markdown(renderizar_tags_html(["VEND CRUZADA"]), unsafe_allow_html=True)
                    st.write(f"*Cliente pertence ao nicho {nicho_deste_cli}, que mais consome este item.*")
                    st.write("---")

# ==========================================
# 🧠 ABA ASSISTENTE IA
# ==========================================
elif st.session_state.aba_atual == "🧠 Assistente":
    st.subheader("🧠 Consultor Virtual Delly's")
    p_user = st.text_input("Qual a dúvida comercial hoje?")
    if p_user:
        model_flash = genai.GenerativeModel("gemini-1.5-flash")
        st.info(model_flash.generate_content(p_user).text)

# ==========================================
# 🏷️ ABA MARCAS EXCLUSIVAS
# ==========================================
elif st.session_state.aba_atual == "🏷️ Marcas":
    st.subheader("🏷️ Painel de Alvos de Marcas")
    opcao_tela_marca = st.radio("Filtro Comercial:", ["⚠️ Já Compraram", "🎯 Nunca Compraram"], horizontal=True)
    marca_alvo = st.selectbox("Selecione a Marca:", ["SEARA", "MCCAIN", "FRIVATTI", "CONFRESCOR", "BRASA", "CERATTI"])
    
    regex_mapa = {"SEARA": regex_seara, "MCCAIN": regex_mccain, "FRIVATTI": regex_frivatti, "CONFRESCOR": regex_confrescor, "BRASA": regex_brasa, "CERATTI": regex_ceratti}
    reg_marca_sel = regex_mapa[marca_alvo]
    
    clientes_com_compra_mes = set(df_mes_atual[df_mes_atual['Produto_Busca'].str.contains(reg_marca_sel, na=False)]['Cliente'].unique()) if not df_mes_atual.empty else set()
    clientes_historico_marca = set(df_total[df_total['Produto_Busca'].str.contains(reg_marca_sel, na=False)]['Cliente'].unique())
    todos_clientes_sistema = set(df_total['Cliente'].dropna().unique())
    
    if "⚠️ Já Compraram" in opcao_tela_marca:
        alvos = clientes_historico_marca - clientes_com_compra_mes
        for c in alvos:
            inf = obter_info_cliente(c)
            st.markdown(f"🏢 **{inf['Código']} - {inf['Nome']}** ({inf['Cidade']})")
            prods_hist = df_total[(df_total['Cliente'] == c) & (df_total['Produto_Busca'].str.contains(reg_marca_sel, na=False))]['Produto'].unique()
            st.write("📋 *Já comprou:*", ", ".join(list(prods_hist)[:5]))
            st.write("---")
    else:
        alvos = todos_clientes_sistema - clientes_com_compra_mes
        for c in alvos:
            inf = obter_info_cliente(c)
            st.markdown(f"🏢 **{inf['Código']} - {inf['Nome']}** ({inf['Cidade']})")
            st.write("❌ *Nunca positivou este item.*")
            st.write("---")
