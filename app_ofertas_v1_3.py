import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import random
import json
import datetime
import collections
import streamlit.components.v1 as components
import google.generativeai as genai
from sqlalchemy import create_engine, text
from datetime import date

# ==========================================
# 0. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Delly's Inteligência", layout="centered", initial_sidebar_state="collapsed")

# ==========================================
# ESTILIZAÇÃO VERDE & CABEÇALHO MOBILE
# ==========================================
st.markdown("""
    <style>
    /* Estilo Global e Fundo Verde Suave */
    .stApp {
        background-color: #F4FBF7 !important;
    }
    
    /* Redução de margens internas topo/base para mobile */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    html, body, [class*="css"], p, span { font-size: 15px !important; }
    h3 { font-size: 18px !important; font-weight: bold !important; color: #1B5E20 !important; margin: 0 !important; }
    
    /* Botões do Menu Principal (Grid Compacto 2x2 Mobile) */
    .main-grid button {
        width: 100% !important;
        height: 75px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        margin-bottom: 8px !important;
        border-radius: 14px !important;
        background-color: #FFFFFF !important;
        color: #1B5E20 !important;
        border: 2px solid #A5D6A7 !important;
        box-shadow: 0 3px 6px rgba(0, 135, 90, 0.08) !important;
    }
    
    .main-grid button:hover {
        background-color: #00875A !important;
        color: #FFFFFF !important;
        border-color: #00875A !important;
    }

    /* Links/Botões Compactos do Cabeçalho Superior */
    .top-link button {
        height: 32px !important;
        font-size: 12px !important;
        padding: 2px 4px !important;
        background-color: transparent !important;
        color: #2E7D32 !important;
        border: 1px solid #A5D6A7 !important;
        border-radius: 6px !important;
        box-shadow: none !important;
        margin: 0 !important;
    }

    button[kind="primary"] {
        background-color: #00875A !important;
        color: white !important;
        border: none !important;
    }
    
    code { font-size: 13px !important; white-space: pre-wrap !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. CONFIGURAÇÕES E CHAVES FIXAS
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
NEON_DB_URL = st.secrets["NEON_DB_URL"]
DRIVE_VENDAS = st.secrets["DRIVE_VENDAS"]
DRIVE_CADASTRO = st.secrets["DRIVE_CADASTRO"]

# --- AUXILIARES ---
def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def filtrar_por_palavras(df, coluna_busca, termo_usuario):
    termo_limpo = limpar_texto(termo_usuario)
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'por']
    palavras = [p for p in termo_limpo.split() if p not in ignorar and len(p) > 1]
    if not palavras: palavras = termo_limpo.split()
    if not palavras: return df
    return df[df[coluna_busca].apply(lambda x: all(p in str(x) for p in palavras))]

def extrair_codigo_nome(linha):
    match = re.match(r'^(\d+)\s*[-|–]?\s*(.*)', str(linha).strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", str(linha).strip()

def extrair_palavras_produto(linha):
    _, nome_produto = extrair_codigo_nome(linha)
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(nome_produto))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pc', 'promocao', 'oferta', 'frita', 'fritas', 'congelada', 'congeladas']
    palavras_validas = [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 1 and p not in ignorar]
    return palavras_validas[:3]

# --- CONFIGURAÇÃO DA API DO GEMINI ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo_ia = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )
except Exception as e:
    st.error(f"Erro ao configurar a API do Gemini: {e}")

# --- CARREGAMENTO DE DADOS (DRIVE) ---
@st.cache_data(ttl=86400) 
def carregar_dados_nuvem(data_atual):
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_atual, "planilhas_drive")
    if not os.path.exists(pasta_destino): os.makedirs(pasta_destino)
    
    try:
        gdown.download_folder(DRIVE_VENDAS, output=pasta_destino, quiet=True)
        gdown.download_folder(DRIVE_CADASTRO, output=pasta_destino, quiet=True)
    except: pass
    
    arquivos_excel = glob.glob(os.path.join(pasta_destino, "**", "*.xlsx"), recursive=True)
    
    cod_to_full = {}
    cadastro_clientes = {}
    
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            for col in df.columns:
                s_col = df[col].astype(str)
                mask = s_col.str.contains(r'^\d+\s*[-|–]?\s*.*\s*\[.*\]', regex=True, na=False)
                if mask.any():
                    for val in s_col[mask]:
                        val_str = str(val).strip().upper()
                        m_cod = re.match(r'^(\d+)', val_str)
                        if m_cod:
                            cod = m_cod.group(1)
                            cod_to_full[cod] = val_str 
                            
                            m_fan = re.search(r'\((.*?)\)', val_str)
                            m_mun = re.search(r'\[(.*?)\]', val_str)
                            if val_str not in cadastro_clientes:
                                cadastro_clientes[val_str] = {
                                    "fantasia": m_fan.group(1).strip() if m_fan else "",
                                    "municipio": m_mun.group(1).strip() if m_mun else ""
                                }
        except: pass
        
    lista_dfs = []
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip().str.lower()
            
            c_dt = next((c for c in df.columns if "dt" in c and "entrega" in c), None)
            c_cli_cad = next((c for c in df.columns if "cliente" in c or "nome" in c), None)
            c_prod = next((c for c in df.columns if "produto" in c), None)
            c_fat = next((c for c in df.columns if "faturamento" in c and "brut" in c), None)
            c_fil = next((c for c in df.columns if "filial" in c or "empresa" in c), None)
            
            if c_dt and c_cli_cad and c_prod and c_fat:
                sel = [c_dt, c_cli_cad, c_prod, c_fat]
                heads = ['Dt. Delivery', 'Cliente_Orig', 'Produto', 'Faturamento Brut']
                if c_fil:
                    sel.append(c_fil)
                    heads.append('Filial')
                sub = df[sel].copy()
                sub.columns = heads
                
                def resolve_client(orig):
                    orig_str = str(orig).strip().upper()
                    m_cod = re.match(r'^(\d+)', orig_str)
                    if m_cod:
                        cod = m_cod.group(1)
                        if cod in cod_to_full:
                            return cod_to_full[cod]
                    return orig_str

                sub['Cliente'] = sub['Cliente_Orig'].apply(resolve_client)
                sub.drop(columns=['Cliente_Orig'], inplace=True)
                
                if sub['Faturamento Brut'].dtype == 'object':
                    sub['Faturamento Brut'] = sub['Faturamento Brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['Faturamento Brut'] = pd.to_numeric(sub['Faturamento Brut'], errors='coerce')
                lista_dfs.append(sub)
        except Exception: 
            continue
        
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cliente'] != 'NAN']
        
        for cli in unificado['Cliente'].unique():
            if cli not in cadastro_clientes:
                m_fan = re.search(r'\((.*?)\)', str(cli))
                m_mun = re.search(r'\[(.*?)\]', str(cli))
                cadastro_clientes[cli] = {
                    "fantasia": m_fan.group(1).strip() if m_fan else "",
                    "municipio": m_mun.group(1).strip() if m_mun else ""
                }

        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], dayfirst=True, errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
        unificado['Cliente_Busca'] = unificado['Cliente'].apply(limpar_texto)
        if 'Filial' not in unificado.columns: unificado['Filial'] = "1"
        return {"df": unificado, "cadastro": cadastro_clientes}
    return {"df": pd.DataFrame(), "cadastro": {}}

# --- INTEGRAÇÃO COM BANCO NEON ---
def obter_conexao_neon():
    try:
        url = NEON_DB_URL.replace("postgres://", "postgresql://", 1)
        return create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    except Exception as e:
        st.error(f"⚠️ Erro ao conectar ao Neon DB: {e}")
        return None

def criar_tabelas_neon():
    engine = obter_conexao_neon()
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS produtos_segmentos (
                        cod_produto VARCHAR(50),
                        produto VARCHAR(255) PRIMARY KEY,
                        segmentos TEXT
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS metas_mensais (
                        mes VARCHAR(10) PRIMARY KEY,
                        pos_geral INT, pos_fl2 INT, pos_fl6 INT,
                        fat_geral NUMERIC, fat_fl2 NUMERIC, fat_fl6 NUMERIC
                    );
                """))
        except Exception as e: print(f"Erro ao criar tabelas: {e}")

def carregar_produtos_segmentos():
    engine = obter_conexao_neon()
    mapa = {}
    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT produto, segmentos FROM produtos_segmentos;")).fetchall()
                for row in res:
                    mapa[row[0]] = json.loads(row[1])
        except: pass
    return mapa

def extrair_segmentos_reais_base(dict_cad):
    palavras = []
    ignorar = ['ltda', 'me', 'eireli', 'cia', 'restaurante', 'bar', 'lanchonete', 'comercio', 'alimentos', 'mercado', 'distribuidora', 'hortifruti']
    for info in dict_cad.values():
        fantasia = limpar_texto(info.get('fantasia', ''))
        for p in fantasia.split():
            if len(p) > 3 and p not in ignorar: palavras.append(p)
    contagem = collections.Counter(palavras)
    top_termos = [p[0].capitalize() for p in contagem.most_common(30)]
    return list(set(top_termos))

def classificar_produtos_lote_ia(lista_produtos, dict_cad):
    if not lista_produtos: return
    segmentos_reais = extrair_segmentos_reais_base(dict_cad)
    prompt = f"""Atue como um analista de Food Service.
    Vou te passar uma lista de produtos. Retorne um JSON válido.
    As chaves devem ser o nome exato do produto fornecido.
    Os valores devem ser uma lista com 2 a 4 tipos de estabelecimentos que compram isso.
    
    REGRA ABSOLUTA: Use APENAS segmentos desta lista abaixo:
    {', '.join(segmentos_reais)}
    
    Produtos para classificar: {json.dumps(lista_produtos)}"""
    
    try:
        resp = modelo_ia.generate_content(prompt)
        dados_json = json.loads(resp.text)
        
        engine = obter_conexao_neon()
        if engine:
            with engine.connect() as conn:
                for linha_original, segs in dados_json.items():
                    cod, nome = extrair_codigo_nome(linha_original)
                    conn.execute(text("""
                        INSERT INTO produtos_segmentos (cod_produto, produto, segmentos) VALUES (:c, :p, :s)
                        ON CONFLICT (produto) DO UPDATE SET segmentos = EXCLUDED.segmentos, cod_produto = EXCLUDED.cod_produto;
                    """), {"c": cod, "p": nome if nome else linha_original, "s": json.dumps(segs)})
                    
                    dict_produtos_segmentos[nome if nome else linha_original] = segs
    except Exception as e:
        st.error(f"⚠️ Erro de comunicação com Neon DB / IA: {e}")

# --- SINCRONIZAÇÃO INICIAL ---
with st.spinner("Carregando sistema..."):
    dados_carregados = carregar_dados_nuvem(date.today())
    df_total = dados_carregados["df"]
    dict_cadastro = dados_carregados["cadastro"]
    
    criar_tabelas_neon()
    dict_produtos_segmentos = carregar_produtos_segmentos()

if df_total.empty:
    st.warning("Base de dados vazia ou pendente de processamento no Drive.")
    st.stop()

mes_atual_referencia = date.today().strftime('%Y-%m') 
df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

# INICIALIZAÇÕES DE ESTADO
if 'tela_atual' not in st.session_state: st.session_state.tela_atual = "Menu"
if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = 0

# --- CARREGAMENTO DE METAS E PROGRESSO ---
data_atual_sistema = pd.Timestamp.now().normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')

def carregar_metas_neon(mes_atual):
    engine = obter_conexao_neon()
    if engine:
        try:
            with engine.connect() as conn:
                query = text("SELECT pos_geral, pos_fl2, pos_fl6, fat_geral, fat_fl2, fat_fl6 FROM metas_mensais WHERE mes = :mes")
                result = conn.execute(query, {"mes": mes_atual}).fetchone()
                if result:
                    return {"mes": mes_atual, "pos_geral": int(result[0]), "pos_fl2": int(result[1]), "pos_fl6": int(result[2]), "fat_geral": float(result[3]), "fat_fl2": float(result[4]), "fat_fl6": float(result[5])}
        except: pass
    return {"mes": mes_atual, "pos_geral": 0, "pos_fl2": 0, "pos_fl6": 0, "fat_geral": 0.0, "fat_fl2": 0.0, "fat_fl6": 0.0}

def salvar_metas_neon(m):
    engine = obter_conexao_neon()
    if engine:
        try:
            with engine.connect() as conn:
                query = text("""
                    INSERT INTO metas_mensais (mes, pos_geral, pos_fl2, pos_fl6, fat_geral, fat_fl2, fat_fl6)
                    VALUES (:mes, :pos_geral, :pos_fl2, :pos_fl6, :fat_geral, :fat_fl2, :fat_fl6)
                    ON CONFLICT (mes) DO UPDATE SET pos_geral = EXCLUDED.pos_geral, pos_fl2 = EXCLUDED.pos_fl2, pos_fl6 = EXCLUDED.pos_fl6, fat_geral = EXCLUDED.fat_geral, fat_fl2 = EXCLUDED.fat_fl2, fat_fl6 = EXCLUDED.fat_fl6;
                """)
                conn.execute(query, m)
        except: pass

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
        "envios_hoje": st.session_state.envios_hoje,
        "fila_ofertas_dia": st.session_state.fila_ofertas_dia,
        "fila_ofertas_relampago": st.session_state.fila_ofertas_relampago,
        "memoria_ofertas_cruas_dia": st.session_state.memoria_ofertas_cruas_dia,
        "memoria_ofertas_cruas_rel": st.session_state.memoria_ofertas_cruas_rel,
        "excluidos_ofertas_dia": list(st.session_state.excluidos_ofertas_dia),
        "excluidos_ofertas_relampago": list(st.session_state.excluidos_ofertas_relampago),
        "excluidos_permanente": list(st.session_state.excluidos_permanente),
        "enviados_supervisor_mes": list(st.session_state.enviados_supervisor_mes),
        "metas_config": st.session_state.get('metas_config', {})
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f: json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")
mes_ultimo_acesso = ultimo_acesso[:7] if ultimo_acesso else ""

if 'data_ultimo_acesso' not in st.session_state: st.session_state.data_ultimo_acesso = data_hoje_str
if ultimo_acesso == data_hoje_str:
    for key in ['envios_hoje', 'fila_ofertas_dia', 'fila_ofertas_relampago', 'memoria_ofertas_cruas_dia', 'memoria_ofertas_cruas_rel']:
        if key not in st.session_state: st.session_state[key] = progresso_backup.get(key, 0 if key=='envios_hoje' else ([] if 'memoria' in key else None))
    for key in ['excluidos_ofertas_dia', 'excluidos_ofertas_relampago']:
        if key not in st.session_state: st.session_state[key] = set(progresso_backup.get(key, []))
else:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia, st.session_state.fila_ofertas_relampago = None, None
    st.session_state.memoria_ofertas_cruas_dia, st.session_state.memoria_ofertas_cruas_rel = [], []
    st.session_state.excluidos_ofertas_dia, st.session_state.excluidos_ofertas_relampago = set(), set()

if mes_ultimo_acesso == mes_atual_referencia[:7]:
    if 'enviados_supervisor_mes' not in st.session_state: st.session_state.enviados_supervisor_mes = set(progresso_backup.get("enviados_supervisor_mes", []))
else:
    st.session_state.enviados_supervisor_mes = set()

if 'excluidos_permanente' not in st.session_state: st.session_state.excluidos_permanente = set(progresso_backup.get("excluidos_permanente", []))
for key in ['busca_direta_cliente', 'texto_supervisor_gerado', 'cliente_ia_atual', 'msg_ia_atual']:
    if key not in st.session_state: st.session_state[key] = ""
if 'sub_aba_consulta' not in st.session_state: st.session_state.sub_aba_consulta = "👤 Por Cliente"
if 'clientes_processados_aguardando' not in st.session_state: st.session_state.clientes_processados_aguardando = []

if 'metas_config' not in st.session_state:
    db_metas = carregar_metas_neon(mes_atual_referencia[:7])
    if db_metas.get("pos_geral", 0) == 0:
        local_metas = progresso_backup.get("metas_config", {})
        st.session_state.metas_config = local_metas if (local_metas and local_metas.get("mes") == mes_atual_referencia[:7]) else db_metas
    else: st.session_state.metas_config = db_metas

if st.session_state.metas_config.get("mes") != mes_atual_referencia[:7]:
    st.session_state.metas_config = carregar_metas_neon(mes_atual_referencia[:7])
    salvar_progresso_atual()

if not progresso_backup or ultimo_acesso != data_hoje_str: salvar_progresso_atual()

def adiantar_cliente_fila_callback(id_fila_param):
    chave_selectbox = f"puxar_frente_{id_fila_param}"
    cliente_escolhido = st.session_state.get(chave_selectbox)
    
    if cliente_escolhido and cliente_escolhido != "-- Digite ou selecione um cliente para adiantar --":
        fila_atual = st.session_state.get(id_fila_param)
        if fila_atual and cliente_escolhido in fila_atual:
            dados_alvo = fila_atual.pop(cliente_escolhido)
            nova_fila = {cliente_escolhido: dados_alvo}
            nova_fila.update(fila_atual)
            st.session_state[id_fila_param] = nova_fila
            st.session_state.cliente_ia_atual = ""
            salvar_progresso_atual()
            st.toast(f"🏢 {cliente_escolhido} adiantado!", icon="⚡")
    st.session_state[chave_selectbox] = "-- Digite ou selecione um cliente para adiantar --"

def gerar_mensagem_ia(nome_cliente, ofertas_dict, historico_compras):
    ofertas_hist = ofertas_dict.get("historico", []) if isinstance(ofertas_dict, dict) else ofertas_dict
    ofertas_seg = ofertas_dict.get("segmento", []) if isinstance(ofertas_dict, dict) else []
    
    texto_ofertas_hist = "\n".join([f"- {of}" for of in ofertas_hist]) if ofertas_hist else "Nenhum no momento."
    texto_ofertas_seg = "\n".join([f"- {of}" for of in ofertas_seg]) if ofertas_seg else "Nenhum no momento."
    texto_historico = "\n".join([f"- {hist}" for hist in historico_compras])
    
    prompt = f"""Você é um vendedor experiente da distribuidora Delly's. Escreva uma mensagem de WhatsApp persuasiva para '{nome_cliente}'.
    Histórico: {texto_historico}
    Ofertas do que já compra: {texto_ofertas_hist}
    Ofertas indicadas p/ segmento: {texto_ofertas_seg}
    REGRAS: Retorne a mensagem em texto puro formatado para WhatsApp. Chamada pra ação no final. Sem assinaturas."""
    
    try: 
        modelo_txt = genai.GenerativeModel('gemini-1.5-flash')
        return modelo_txt.generate_content(prompt).text.strip()
    except: 
        return f"Olá!\nSeparei ofertas exclusivas para você!\n\n*🛒 Produtos em oferta:*\n{texto_ofertas_hist}\n\nMe avise se posso garantir o seu pedido! 👍"

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
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:3px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:3px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:3px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:3px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:3px;">⚠️ SUMIDO</span>'
    return html

# ==============================================================================
# NAVEGAÇÃO: BOTÃO DE VOLTAR AO MENU (NAS SUB-TELAS)
# ==============================================================================
if st.session_state.tela_atual != "Menu":
    col_nav1, col_nav2 = st.columns([1, 4])
    with col_nav1:
        if st.button("⬅️ Menu", key="btn_voltar_menu"):
            st.session_state.tela_atual = "Menu"
            st.rerun()

# ==============================================================================
# 📱 TELA PRINCIPAL: MENU DE BOTÕES (GRID MOBILE RESPONSIVO 2X2)
# ==============================================================================
if st.session_state.tela_atual == "Menu":
    # Cabeçalho Compacto: Imagem à Esquerda + Título e Links Rápidos
    col_img, col_info = st.columns([1, 3], vertical_alignment="center")
    
    with col_img:
        st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRyPVIv2occ4qcx4coRayjeLgPd_z_VfLOBVIfgZB27s6EPQnm0UosImhQ&s=10", width=70)
        
    with col_info:
        st.markdown("<h3>Delly's Inteligência</h3>", unsafe_allow_html=True)
        c1_link, c2_link = st.columns(2)
        with c1_link:
            st.markdown('<div class="top-link">', unsafe_allow_html=True)
            if st.button("🔄 Sincronizar", key="hdr_sync"):
                st.cache_data.clear()
                st.toast("Base sincronizada!", icon="🔄")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with c2_link:
            st.markdown('<div class="top-link">', unsafe_allow_html=True)
            if st.button("⚙️ Limpar Neon", key="hdr_neon"):
                engine = obter_conexao_neon()
                if engine:
                    try:
                        with engine.connect() as conn:
                            conn.execute(text("TRUNCATE TABLE produtos_segmentos;"))
                        st.toast("✅ Tabela Neon limpa!", icon="🧹")
                    except Exception as e:
                        st.error(f"Erro: {e}")
            st.markdown('</div>', unsafe_allow_html=True)

    st.write("---")
    
    # Grid 2x2 para caber sem necessidade de scroll no celular
    st.markdown('<div class="main-grid">', unsafe_allow_html=True)
    
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        if st.button("📊 Metas", key="btn_menu_metas"):
            st.session_state.tela_atual = "Metas"
            st.rerun()
            
    with row1_col2:
        if st.button("🟢 Ofertas", key="btn_menu_ofertas"):
            st.session_state.tela_atual = "Ofertas"
            st.rerun()

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        if st.button("🚨 Alertas", key="btn_menu_alertas"):
            st.session_state.tela_atual = "Alertas"
            st.rerun()

    with row2_col2:
        if st.button("🔍 Consultas", key="btn_menu_consultas"):
            st.session_state.tela_atual = "Consultas"
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# 📊 TELA 1: METAS
# ==============================================================================
elif st.session_state.tela_atual == "Metas":
    st.subheader("📊 Painel de Metas")
    
    df_fl2 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('2', na=False)]
    df_fl6 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('6', na=False)]

    real_pos_fl2, real_pos_fl6 = df_fl2['Cliente'].nunique(), df_fl6['Cliente'].nunique()
    real_pos_geral = pd.concat([df_fl2, df_fl6])['Cliente'].nunique() if not df_fl2.empty or not df_fl6.empty else 0
    real_fat_fl2, real_fat_fl6 = df_fl2['Faturamento Brut'].sum(), df_fl6['Faturamento Brut'].sum()
    real_fat_geral = real_fat_fl2 + real_fat_fl6

    def exibir_kpi_linha(label, meta, realizado, eh_faturamento=False):
        c1, c2, c3 = st.columns([1, 1, 1])
        c1.write(f"**{label}**")
        c2.write(f"Meta: {f'R$ {meta:,.0f}' if eh_faturamento else meta}")
        c3.write(f"Real: {f'R$ {realizado:,.0f}' if eh_faturamento else realizado}")
        
        perc = (realizado / meta * 100) if meta > 0 else 0
        cor = "#00875A" if perc >= 100 else "#DE350B"
        st.markdown(f'<div style="background-color:{cor}; color:white; text-align:center; border-radius:4px; font-weight:bold; margin-bottom: 12px; padding: 3px;">{perc:.0f}%</div>', unsafe_allow_html=True)

    if st.button("✏️ Editar Metas do Mês"): st.session_state.editar_aberto = True

    if st.session_state.get('editar_aberto', False):
        with st.expander("Configurar Metas", expanded=True):
            m = st.session_state.metas_config.copy()
            with st.form("form_metas"):
                st.write("Positivação (Qtd Clientes)")
                c1, c2, c3 = st.columns(3)
                m['pos_geral'] = c1.number_input("Geral", value=int(m['pos_geral']), key="inp_pos_geral")
                m['pos_fl2'] = c2.number_input("FL2", value=int(m['pos_fl2']), key="inp_pos_fl2")
                m['pos_fl6'] = c3.number_input("FL6", value=int(m['pos_fl6']), key="inp_pos_fl6")
                
                st.write("Faturamento (R$)")
                c4, c5, c6 = st.columns(3)
                m['fat_geral'] = c4.number_input("Geral", value=float(m['fat_geral']), key="inp_fat_geral")
                m['fat_fl2'] = c5.number_input("FL2", value=float(m['fat_fl2']), key="inp_fat_fl2")
                m['fat_fl6'] = c6.number_input("FL6", value=float(m['fat_fl6']), key="inp_fat_fl6")
                
                if st.form_submit_button("Salvar Metas"):
                    st.session_state.metas_config = m
                    salvar_metas_neon(m)
                    salvar_progresso_atual()
                    st.session_state.editar_aberto = False
                    st.toast("Metas salvas com sucesso!", icon="💾")
                    st.rerun()

    st.markdown("### Positivação")
    m = st.session_state.metas_config
    exibir_kpi_linha("Geral", m['pos_geral'], real_pos_geral)
    exibir_kpi_linha("FL2", m['pos_fl2'], real_pos_fl2)
    exibir_kpi_linha("FL6", m['pos_fl6'], real_pos_fl6)

    st.write("---")
    st.markdown("### ROB FATURAMENTO")
    exibir_kpi_linha("Geral", m['fat_geral'], real_fat_geral, eh_faturamento=True)
    exibir_kpi_linha("FL2", m['fat_fl2'], real_fat_fl2, eh_faturamento=True)
    exibir_kpi_linha("FL6", m['fat_fl6'], real_fat_fl6, eh_faturamento=True)

# ==============================================================================
# 🟢 TELA 2: OFERTAS
# ==============================================================================
elif st.session_state.tela_atual == "Ofertas":
    st.subheader("📋 Painel de Transmissão c/ IA 🧠")
    st.markdown(f"📊 Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    tipo_lista = st.radio("Canal:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    
    cidades_disponiveis = set()
    for cli in dict_cadastro.keys():
        m = re.search(r'\[(.*?)\]', str(cli))
        if m: cidades_disponiveis.add(m.group(1).strip().upper())
    cidades_disponiveis = sorted(list(cidades_disponiveis))

    cidades_selecionadas = st.multiselect("📍 Filtrar por Município(s):", options=cidades_disponiveis, placeholder="Selecione as cidades")

    with st.expander("📝 Inserir Bloco de Ofertas"):
        txt_novas = st.text_area("Cole as linhas de ofertas aqui:", height=100, key=f"txt_{id_fila}")
        if st.button("🚀 Processar Linhas", key=f"btn_proc_{id_fila}"):
            if txt_novas.strip():
                st.session_state[id_excluidos].clear()
                linhas = [l.strip() for l in txt_novas.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas
                
                produtos_desconhecidos = []
                for linha in linhas:
                    cod, nome = extrair_codigo_nome(linha)
                    chave_busca = nome if nome else linha
                    if chave_busca not in dict_produtos_segmentos:
                        produtos_desconhecidos.append(linha)
                
                if produtos_desconhecidos:
                    with st.spinner(f"🧠 IA aprendendo e classificando novos produtos..."):
                        classificar_produtos_lote_ia(produtos_desconhecidos, dict_cadastro)
                
                prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
                prod_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
                nova_fila = {}
                clientes_com_compra_mes_atual = df_mes_atual['Cliente'].unique()
                
                for linha in linhas:
                    chaves = extrair_palavras_produto(linha)
                    if not chaves: continue
                    
                    combs_hist = [orig for orig, busca in prod_busca.items() if all(c in busca for c in chaves)]
                    if not combs_hist and len(chaves) >= 2:
                        combs_hist = [orig for orig, busca in prod_busca.items() if sum(1 for c in chaves if c in busca) >= 2]
                    
                    interessados_hist = set()
                    for c in combs_hist: interessados_hist.update(prod_to_clientes[c])
                    
                    interessados_seg = set()
                    segs_oferta = []
                    
                    _, nome_prod_linha = extrair_codigo_nome(linha)
                    chave_dic = nome_prod_linha if nome_prod_linha else linha
                    if chave_dic in dict_produtos_segmentos:
                        segs_oferta.extend(dict_produtos_segmentos[chave_dic])
                        
                    segs_oferta_limpos = [limpar_texto(s) for s in set(segs_oferta)]

                    for cli_cad, info_cad in dict_cadastro.items():
                        nome_cli_limpo = limpar_texto(cli_cad) 
                        if any(s in nome_cli_limpo for s in segs_oferta_limpos if len(s)>2):
                            interessados_seg.add(cli_cad)
                    
                    for cli in (interessados_hist | interessados_seg):
                        if pd.isna(cli) or str(cli).lower() == 'nan': continue
                        if cli in st.session_state.excluidos_permanente:
                            if cli in clientes_com_compra_mes_atual: st.session_state.excluidos_permanente.remove(cli)
                            else: continue
                                
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = {"historico": [], "segmento": []}
                        
                        if cli in interessados_hist:
                            if linha not in nova_fila[cli]["historico"]: nova_fila[cli]["historico"].append(linha)
                        elif cli in interessados_seg:
                            if linha not in nova_fila[cli]["segmento"]: nova_fila[cli]["segmento"].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.success("Fila vinculada e processada!")
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info("Nenhum cliente na fila de transmissão pendente.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        
        if cidades_selecionadas:
            cidades_sel_limpas = [limpar_texto(c) for c in cidades_selecionadas]
            filtrados = []
            for c in clientes_restantes:
                m_mun = re.search(r'\[(.*?)\]', str(c))
                if m_mun:
                    cidade_cli_limpa = limpar_texto(m_mun.group(1))
                    if any(cs in cidade_cli_limpa or cidade_cli_limpa in cs for cs in cidades_sel_limpas):
                        filtrados.append(c)
            clientes_restantes = filtrados
        
        if not clientes_restantes:
            st.info("Nenhum cliente pendente para os municípios selecionados.")
        else:
            st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
            
            st.selectbox(
                "🚀 Puxar cliente para frente:", 
                options=["-- Digite ou selecione um cliente para adiantar --"] + clientes_restantes,
                key=f"puxar_frente_{id_fila}",
                on_change=adiantar_cliente_fila_callback,
                args=(id_fila,)
            )
                
            st.write("---")
            cliente_atual = clientes_restantes[0]
            ofertas_cliente = fila_ativa[cliente_atual]
            
            st.markdown(f"**🏢 {cliente_atual}**")
            st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
            st.write("")
            
            if st.session_state.cliente_ia_atual != cliente_atual:
                st.session_state.cliente_ia_atual = cliente_atual
                historico = df_total[df_total['Cliente'] == cliente_atual].groupby('Produto')['Faturamento Brut'].sum().nlargest(5).index.tolist()
                with st.spinner("🧠 Gemini gerando mensagem personalizada..."):
                    st.session_state.msg_ia_atual = gerar_mensagem_ia(cliente_atual, ofertas_cliente, historico)
            
            st.code(st.session_state.msg_ia_atual, language=None)
            
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                if st.button("✅ Enviado", type="primary", key=f"env_{str(cliente_atual)[:5]}"):
                    st.session_state.envios_hoje += 1
                    st.session_state[id_excluidos].add(cliente_atual)
                    del st.session_state[id_fila][cliente_atual]
                    st.session_state.cliente_ia_atual = "" 
                    salvar_progresso_atual()
                    st.rerun()
            with col_b2:
                if st.button("❌ Excluir", key=f"ex_{str(cliente_atual)[:5]}"):
                    st.session_state[id_excluidos].add(cliente_atual)
                    del st.session_state[id_fila][cliente_atual]
                    st.session_state.cliente_ia_atual = ""
                    salvar_progresso_atual()
                    st.rerun()
            with col_b3:
                if st.button("⏭️ Pular", key=f"pular_{str(cliente_atual)[:5]}"):
                    dados_cliente = st.session_state[id_fila].pop(cliente_atual)
                    st.session_state[id_fila][cliente_atual] = dados_cliente
                    st.session_state.cliente_ia_atual = ""
                    salvar_progresso_atual()
                    st.toast(f"{cliente_atual} movido para o final!", icon="⏭️")
                    st.rerun()

# ==============================================================================
# 🚨 TELA 3: ALERTAS
# ==============================================================================
elif st.session_state.tela_atual == "Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=180, key="txt_sup_area_fix")
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id="copyBtn" style="width: 100%; background-color: #00875A; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; font-size: 15px; cursor: pointer;">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                navigator.clipboard.writeText({texto_js_safe});
                this.innerText = '✅ Copiado com sucesso!';
                setTimeout(() => {{ this.innerText = '📋 Copiar Relatório'; }}, 2000);
            }});
            </script>
            """
            components.html(html_button_js, height=50)
            
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                    if f"chk_{c_nome}" in st.session_state: st.session_state[f"chk_{c_nome}"] = False
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.rerun()
            st.write("---")

    st.markdown("### Filtros da Lista")
    filtro_status = st.selectbox("Status de envio:", ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"])
    busca_alerta = st.text_input("🔍 Buscar Cliente em Alerta:", placeholder="Digite o nome...").strip()

    grid_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0: continue
        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            ja_reportado = cli in st.session_state.enviados_supervisor_mes
            if filtro_status == "Apenas Não Reportados" and ja_reportado: continue
            if filtro_status == "Apenas Reportados" and not ja_reportado: continue
            grid_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"], "Reportado": ja_reportado})
            
    df_alertas_visuais = pd.DataFrame(grid_alertas)
    if not df_alertas_visuais.empty: df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
        
    if busca_alerta and not df_alertas_visuais.empty:
        termo_limpo = limpar_texto(busca_alerta)
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: termo_limpo in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info("Nenhum cliente localizado.")
    else:
        st.markdown(f"📊 Total: **{len(df_alertas_visuais)}** clientes")
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            if f"chk_{c_nome}" not in st.session_state: st.session_state[f"chk_{c_nome}"] = False
            
            with st.container():
                st.checkbox(f"📍 {c_nome} ({row['Dias']}d sem comprar)", key=f"chk_{c_nome}")
                html_badges = obter_badges_html(c_nome)
                if row["Reportado"]: html_badges += '<span style="background-color:#FFC400; color:#111; padding:2px 4px; border-radius:3px; font-weight:bold; font-size:10px; margin-right:3px;">📅 REPORTADO</span>'
                st.markdown(html_badges, unsafe_allow_html=True)
                
                if st.button(f"🔍 Histórico...", key=f"btn_h_{idx}"):
                    st.session_state.busca_direta_cliente = c_nome
                    st.session_state.sub_aba_consulta = "👤 Por Cliente"
                    st.session_state.tela_atual = "Consultas"  
                    st.rerun()
            st.write("---")
        
        if st.button("⚡ GERAR RELATÓRIO SELECIONADOS", type="primary"):
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
                        novo_texto_acumulado += "   🔹 Mais Comprados pelo Cliente:\n"
                        for item in top_itens: novo_texto_acumulado += f"     ▪️ {item}\n"
                    
                    nome_limpo_cli = limpar_texto(c_nome)
                    sugestoes_seg = []
                    for prod_db, segs in dict_produtos_segmentos.items():
                        if any(limpar_texto(s) in nome_limpo_cli for s in segs if len(s)>2):
                            sugestoes_seg.append(prod_db)
                    
                    if congest := list(set(sugestoes_seg))[:4]:
                        novo_texto_acumulado += "   💡 Oportunidades de Venda Cruzada:\n"
                        for sug in congest: novo_texto_acumulado += f"     ▪️ {sug}\n"
                    novo_texto_acumulado += "\n"
            
            if len(clientes_selecionados_na_rodada) > 0:
                st.session_state.texto_supervisor_gerado = novo_texto_acumulado
                st.session_state.clientes_processados_aguardando = clientes_selecionados_na_rodada
                st.rerun()
            else:
                st.warning("⚠️ Marque ao menos um cliente na lista!")

# ==============================================================================
# 🔍 TELA 4: CONSULTAS
# ==============================================================================
elif st.session_state.tela_atual == "Consultas":
    st.session_state.sub_aba_consulta = st.radio(
        "Filtro:", 
        ["👤 Por Cliente", "📦 Por Produto", "📉 Recuperação", "🏢 Exclusivos FL6", "🏆 Parceiros", "💲 Cotação"], 
        horizontal=True
    )
    st.write("---")
    
    if st.session_state.sub_aba_consulta == "👤 Por Cliente":
        st.subheader("Raio-X do Cliente")
        input_busca = st.text_input("Nome ou Código:", value=st.session_state.busca_direta_cliente).strip()
        
        if input_busca:
            filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', input_busca)
            nomes_encontrados = filtrados['Cliente'].unique()
            
            if len(nomes_encontrados) > 0:
                c_sel = st.selectbox("Selecione o Cliente:", nomes_encontrados)
                st.markdown(f"### Ficha: {c_sel}")
                st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
                
                df_cli = df_total[df_total['Cliente'] == c_sel]
                st.write("**Mix de Itens Históricos:**")
                rank_p = df_cli.groupby('Produto')['Faturamento Brut'].sum().nlargest(10).reset_index()
                
                for i, r in rank_p.iterrows():
                    st.markdown(f"<p style='font-size: 13px; margin-bottom: 2px;'>• {r['Produto']} (R$ {r['Faturamento Brut']:,.2f})</p>", unsafe_allow_html=True)
                
                st.write("---")
                st.write("📉 **Produtos Abandonados:**")
                
                max_dates = df_cli.groupby('Produto')['Data_Datetime'].max()
                abandonados = max_dates[max_dates.apply(lambda x: (data_atual_sistema - x).days > 30)].index.tolist()
                df_ab = df_cli[df_cli['Produto'].isin(abandonados)].groupby('Produto').agg(
                    Fat=('Faturamento Brut', 'sum'), Ult_Compra=('Data_Datetime', 'max')
                ).sort_values('Fat', ascending=False)
                
                ofertas_memoria = st.session_state.memoria_ofertas_cruas_dia + st.session_state.memoria_ofertas_cruas_rel
                html_ab = ""
                texto_abandonados_p_ia = ""
                
                for prod, row in df_ab.head(8).iterrows():
                    dias = (data_atual_sistema - row['Ult_Compra']).days
                    is_oferta = False
                    for of in ofertas_memoria:
                        if all(c in limpar_texto(of) for c in extrair_palavras_produto(prod)[:2]):
                            is_oferta = True
                            break
                    
                    tag_oferta = " <span style='background-color:#DE350B; color:white; padding:1px 3px; border-radius:2px; font-size:9px; font-weight:bold;'>🚨 OFERTA</span>" if is_oferta else ""
                    html_ab += f"<p style='font-size: 13px; margin-bottom: 2px;'>• {prod} <i>(⏳ {dias}d)</i>{tag_oferta}</p>"
                    texto_abandonados_p_ia += f"- {prod} ({dias} dias sem comprar) {'[ESTÁ NA OFERTA]' if is_oferta else ''}\n"
                
                if html_ab:
                    st.markdown(html_ab, unsafe_allow_html=True)
                else:
                    st.markdown("<p style='font-size: 13px;'>Nenhum abandono >30d.</p>", unsafe_allow_html=True)

                st.write("---")
                st.markdown("### 💡 Venda Cruzada Inteligente")
                nome_limpo_cli = limpar_texto(c_sel)
                
                segmentos_do_cliente = set()
                for prod, segs in dict_produtos_segmentos.items():
                    for s in segs:
                        s_limpo = limpar_texto(s)
                        if len(s_limpo) > 2 and s_limpo in nome_limpo_cli:
                            segmentos_do_cliente.add(s)
                            
                produtos_ja_comprados = set(df_cli['Produto'].unique())
                sugestoes_segmento = []
                for prod, segs in dict_produtos_segmentos.items():
                    if any(s in segmentos_do_cliente for s in segs) and prod not in produtos_ja_comprados:
                        sugestoes_segmento.append(prod)
                
                chave_sessao_msg = f'msg_cruzada_{c_sel}'
                
                if st.button("🧠 Gerar Abordagem via IA", type="primary"):
                    prompt_cruzada = f"""
                    Atue como vendedor B2B Delly's. Crie mensagem WhatsApp para '{c_sel}'.
                    Abandonados: {texto_abandonados_p_ia if texto_abandonados_p_ia else "Nenhum."}
                    Sugestões Segmento ({', '.join(segmentos_do_cliente)}): {', '.join(sugestoes_segmento[:5])}
                    Ofertas hoje: {', '.join(ofertas_memoria[:6]) if ofertas_memoria else "Nenhuma"}
                    REGRAS: Pule linhas, emojis, *negrito* nos produtos. Sem preços inventados.
                    """
                    with st.spinner("Conectando ao Gemini..."):
                        try:
                            modelo_msg = genai.GenerativeModel('gemini-1.5-flash')
                            st.session_state[chave_sessao_msg] = modelo_msg.generate_content(prompt_cruzada).text
                        except Exception as e:
                            st.error(f"Erro ao gerar IA: {e}")
                
                if chave_sessao_msg in st.session_state and st.session_state[chave_sessao_msg]:
                    st.text_area("Mensagem Formatada:", value=st.session_state[chave_sessao_msg], height=200)

    elif st.session_state.sub_aba_consulta == "📦 Por Produto":
        st.subheader("Análise por Produto")
        input_prod = st.text_input("Nome do produto:").strip()
        if input_prod:
            filtrados_p = filtrar_por_palavras(df_total, 'Produto_Busca', input_prod)
            if not filtrados_p.empty:
                st.write(f"✅ Encontrados **{len(filtrados_p['Produto'].unique())}** produtos.")
                top_compradores = filtrados_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).reset_index()
                for idx, row in top_compradores.iterrows():
                    st.markdown(f"**{row['Cliente']}** - R$ {row['Faturamento Brut']:,.2f}")
            else:
                st.warning("Nenhum produto encontrado.")

    elif st.session_state.sub_aba_consulta == "📉 Recuperação":
        st.subheader("📉 Ranking de Abandonos")
        dias_corte = st.slider("Considerar abandono após (dias):", min_value=15, max_value=120, value=30, step=5)
        
        with st.spinner("Calculando..."):
            df_calc = df_total.dropna(subset=['Data_Datetime', 'Faturamento Brut', 'Cliente', 'Produto'])
            agrupado = df_calc.groupby(['Cliente', 'Produto']).agg(
                Fat_Total=('Faturamento Brut', 'sum'),
                Ultima_Compra=('Data_Datetime', 'max'),
                Qtd_Compras=('Data_Datetime', 'count')
            ).reset_index()
            
            agrupado['Dias_Sem_Comprar'] = (data_atual_sistema - agrupado['Ultima_Compra']).dt.days
            abandonos = agrupado[(agrupado['Dias_Sem_Comprar'] >= dias_corte) & (agrupado['Fat_Total'] > 0)]
            
            clientes_abandonos = abandonos.groupby('Cliente').agg(
                Fat_Perdido_Total=('Fat_Total', 'sum')
            ).reset_index().sort_values(by='Fat_Perdido_Total', ascending=False).head(50)
            
        if clientes_abandonos.empty:
            st.success("Nenhum abandono identificado!")
        else:
            for idx, row_cli in clientes_abandonos.iterrows():
                cliente_nome = row_cli['Cliente']
                fat_total_cli = row_cli['Fat_Perdido_Total']
                prods_cli = abandonos[abandonos['Cliente'] == cliente_nome].sort_values(by='Fat_Total', ascending=False)
                
                with st.expander(f"🚨 {cliente_nome} — R$ {fat_total_cli:,.2f}"):
                    for _, p_row in prods_cli.iterrows():
                        st.markdown(f"• {p_row['Produto']} | R$ {p_row['Fat_Total']:,.2f} ({p_row['Dias_Sem_Comprar']}d sem comprar)")

    elif st.session_state.sub_aba_consulta == "🏢 Exclusivos FL6":
        st.subheader("🎯 Clientes Exclusivos FL6")
        clientes_fl6_mes = df_fl6['Cliente'].unique() if not df_fl6.empty else []
        clientes_fl2_mes = df_fl2['Cliente'].unique() if not df_fl2.empty else []
        exclusivos_fl6 = [c for c in clientes_fl6_mes if c not in clientes_fl2_mes]
        
        if not exclusivos_fl6:
            st.info("Nenhum cliente exclusivo da Filial 6.")
        else:
            for c_excl in exclusivos_fl6:
                st.write(f"🏢 {c_excl}")

    elif st.session_state.sub_aba_consulta == "🏆 Parceiros":
        st.subheader("🎯 Marcas Estratégicas")
        marcas_parceiras = {
            "Marca 1: Lebon, Doriana, Seara, Frangosul": ["lebon", "doriana", "seara", "frangosul"],
            "Marca 2: Frivatti": ["frivatti"],
            "Marca 3: Brasa": ["brasa"],
            "Marca 4: Mccain": ["mccain"],
            "Marca 5: Ceratti": ["ceratti"],
            "Marca 6: Confrescor": ["confrescor"]
        }
        marca_selecionada = st.selectbox("Selecione:", list(marcas_parceiras.keys()))
        palavras_da_marca = marcas_parceiras[marca_selecionada]
        
        mask_marca = df_mes_atual['Produto_Busca'].apply(lambda x: any(palavra in str(x) for palavra in palavras_da_marca))
        compradores_alvo_df = df_mes_atual[mask_marca]
        st.info(f"📈 Positivados: **{compradores_alvo_df['Cliente'].nunique()}**")

    elif st.session_state.sub_aba_consulta == "💲 Cotação":
        st.subheader("💲 Cotação Ágil")
        texto_cotacao = st.text_area("📋 Cole a lista de produtos:", height=130)
        
        if st.button("🔍 Cruzar Ofertas", type="primary"):
            if texto_cotacao.strip():
                ofertas_memoria = st.session_state.get('memoria_ofertas_cruas_dia', []) + st.session_state.get('memoria_ofertas_cruas_rel', [])
                if not ofertas_memoria:
                    st.warning("⚠️ Insira ofertas na tela 'Ofertas' antes.")
                else:
                    linhas_cot = [l.strip() for l in texto_cotacao.split('\n') if l.strip()]
                    resultado_final = []
                    for linha_cot in linhas_cot:
                        chaves_cot = extrair_palavras_produto(linha_cot)
                        match_encontrado = False
                        if chaves_cot:
                            for of in ofertas_memoria:
                                if len(chaves_cot) >= 2 and all(limpar_texto(c) in limpar_texto(of) for c in chaves_cot[:2]):
                                    resultado_final.append(of)
                                    match_encontrado = True; break
                        if not match_encontrado: resultado_final.append(linha_cot) 
                    st.session_state.resultado_cotacao = "\n".join(resultado_final)
                    st.success("✅ Cotação concluída!")
            else:
                st.warning("Cole os produtos.")
                
        if "resultado_cotacao" in st.session_state and st.session_state.resultado_cotacao:
            st.text_area("🎯 Resultado:", value=st.session_state.resultado_cotacao, height=180)
