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
# 0. CONFIGURAÇÃO DA PÁGINA (Deve ser o 1º comando)
# ==========================================
st.set_page_config(page_title="Pixel Vendas", layout="centered")

# ==========================================
# 1. CONFIGURAÇÕES E CHAVES FIXAS
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
NEON_DB_URL = st.secrets["NEON_DB_URL"]
DRIVE_HISTORICO_COMPRAS = st.secrets["DRIVE_HISTORICO_COMPRAS"]
DRIVE_LISTA_CLIENTES = st.secrets["DRIVE_LISTA_CLIENTES"]
DRIVE_GRADE_ENTREGAS = st.secrets["DRIVE_GRADE_ENTREGAS"]
DRIVE_CLIENTES_CHURN = st.secrets["DRIVE_CLIENTES_CHURN"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

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

def ler_planilha_generica(caminho_arquivo):
    """Lê arquivos nos formatos Excel (.xlsx, .xls) e CSV (.csv)."""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    if extensao == '.csv':
        try:
            return pd.read_csv(caminho_arquivo, sep=None, engine='python', encoding='utf-8')
        except UnicodeDecodeError:
            return pd.read_csv(caminho_arquivo, sep=None, engine='python', encoding='latin1')
    else:
        return pd.read_excel(caminho_arquivo)

# --- EXTRAÇÃO E COMPOSIÇÃO DO CARD DO CLIENTE ---
def extrair_detalhes_cliente(cliente_nome, dict_cadastro, dict_produtos_segmentos):
    cliente_str = str(cliente_nome).strip()
    
    # 1. Código
    m_cod = re.match(r'^(\d+)', cliente_str)
    codigo = m_cod.group(1) if m_cod else "S/C"
    
    # 2. Dados do cadastro (Busca por Nome ou Código)
    info = dict_cadastro.get(cliente_str, {})
    if not info and codigo != "S/C":
        info = dict_cadastro.get(codigo, {})
        
    fantasia = info.get("fantasia", "").strip()
    cidade = info.get("cidade", "").strip() or info.get("cidade", "").strip()
    segmento_cad = info.get("segmento", "").strip()
    
    if not fantasia:
        m_fan = re.search(r'\((.*?)\)', cliente_str)
        if m_fan: fantasia = m_fan.group(1).strip()
        
    if not cidade:
        m_mun = re.search(r'\[(.*?)\]', cliente_str)
        if m_mun: cidade = m_mun.group(1).strip()
        
    # 3. Nome Limpo do Cliente (sem código, fantasia ou cidade)
    nome_limpo = cliente_str
    if m_cod:
        nome_limpo = re.sub(r'^\d+\s*[-|–]?\s*', '', nome_limpo)
    nome_limpo = re.sub(r'\s*\(.*?\)', '', nome_limpo)
    nome_limpo = re.sub(r'\s*\[.*?\]', '', nome_limpo).strip()
    if not nome_limpo:
        nome_limpo = cliente_str
        
    # 4. Segmento do Cliente (Cruzamento inteligente com o cadastro / IA)
    segmentos_encontrados = set()
    if segmento_cad:
        segmentos_encontrados.add(segmento_cad.capitalize())

    nome_busca = limpar_texto(cliente_str) + " " + limpar_texto(fantasia)
    for prod, segs in dict_produtos_segmentos.items():
        for s in segs:
            s_limp = limpar_texto(s)
            if len(s_limp) > 2 and s_limp in nome_busca:
                segmentos_encontrados.add(s.capitalize())
                    
    segmento_str = ", ".join(sorted(list(segmentos_encontrados))) if segmentos_encontrados else "Geral / Não Especificado"
    
    return {
        "codigo": codigo,
        "nome": nome_limpo,
        "fantasia": fantasia if fantasia else "Não informada",
        "cidade": cidade if cidade else "Não informada",
        "segmento": segmento_str
    }

def renderizar_card_cliente(cliente_nome, dict_cadastro, dict_produtos_segmentos, badges_html=""):
    detalhes = extrair_detalhes_cliente(cliente_nome, dict_cadastro, dict_produtos_segmentos)
    
    html_card = f"""
    <div style="background-color: #ffffff; border: 1px solid #dcdfe6; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
        <div style="font-size: 16px; font-weight: bold; color: #172b4d; margin-bottom: 4px;">
            🏢 {detalhes['codigo']} - {detalhes['nome']}
        </div>
        <div style="font-size: 14px; color: #253858; margin-bottom: 4px;">
            <b>🏷️ Fantasia:</b> {detalhes['fantasia']}
        </div>
        <div style="font-size: 13px; color: #5e6c84; margin-bottom: 8px;">
            <b>📍 Cidade:</b> {detalhes['cidade']} &nbsp;|&nbsp; <b>🍽️ Segmento:</b> {detalhes['segmento']}
        </div>
        <div>
            {badges_html}
        </div>
    </div>
    """
    st.markdown(html_card, unsafe_allow_html=True)

# --- CONFIGURAÇÃO DA API DO GEMINI ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    modelo_ia = genai.GenerativeModel(
        model_name='gemini-3.5-flash-lite',
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
        gdown.download_folder(DRIVE_HISTORICO_COMPRAS, output=pasta_destino, quiet=True)
        gdown.download_folder(DRIVE_LISTA_CLIENTES, output=pasta_destino, quiet=True)
        gdown.download_folder(DRIVE_GRADE_ENTREGAS, output=pasta_destino, quiet=True)
        gdown.download_folder(DRIVE_CLIENTES_CHURN, output=pasta_destino, quiet=True)
        
    except: pass
    
    # Busca por planilhas Excel (.xlsx, .xls) e arquivos CSV (.csv)
    arquivos_planilhas = glob.glob(os.path.join(pasta_destino, "**", "*.xlsx"), recursive=True) + \
                         glob.glob(os.path.join(pasta_destino, "**", "*.xls"), recursive=True) + \
                         glob.glob(os.path.join(pasta_destino, "**", "*.csv"), recursive=True)
    
    cod_to_full = {}
    cadastro_clientes = {}
    
    # PASSO 1: Mapear Planilhas de Cadastro e Colunas Unificadas
    for arquivo in arquivos_planilhas:
        try:
            df = ler_planilha_generica(arquivo)
            df_cols_clean = [limpar_texto(c) for c in df.columns]
            
            # Identifica colunas específicas de cadastro na planilha
            c_cod = next((df.columns[i] for i, c in enumerate(df_cols_clean) if any(k in c for k in ['cod', 'codigo'])), None)
            c_cli = next((df.columns[i] for i, c in enumerate(df_cols_clean) if any(k in c for k in ['cliente', 'razao', 'nome']) and 'fantasia' not in c), None)
            c_fan = next((df.columns[i] for i, c in enumerate(df_cols_clean) if 'fantasia' in c), None)
            c_cid = next((df.columns[i] for i, c in enumerate(df_cols_clean) if any(k in c for k in ['cidade', 'cidade'])), None)
            c_seg = next((df.columns[i] for i, c in enumerate(df_cols_clean) if any(k in c for k in ['segmento', 'ramo'])), None)

            # 1.1 Mapeia linhas das colunas estruturadas
            if (c_cod or c_cli) and (c_fan or c_cid or c_seg):
                for _, row in df.iterrows():
                    cod_val = str(row[c_cod]).strip() if c_cod and pd.notna(row[c_cod]) else ""
                    m_c = re.match(r'^(\d+)', cod_val)
                    if m_c: cod_val = m_c.group(1)
                    
                    fan_val = str(row[c_fan]).strip() if c_fan and pd.notna(row[c_fan]) else ""
                    cid_val = str(row[c_cid]).strip() if c_cid and pd.notna(row[c_cid]) else ""
                    seg_val = str(row[c_seg]).strip() if c_seg and pd.notna(row[c_seg]) else ""
                    
                    if fan_val.lower() == 'nan': fan_val = ""
                    if cid_val.lower() == 'nan': cid_val = ""
                    if seg_val.lower() == 'nan': seg_val = ""

                    dict_info = {
                        "fantasia": fan_val,
                        "cidade": cid_val,
                        "cidade": cid_val,
                        "segmento": seg_val,
                    }

                    if cod_val:
                        if cod_val not in cadastro_clientes or not cadastro_clientes[cod_val].get("fantasia"):
                            cadastro_clientes[cod_val] = dict_info
                    if c_cli and pd.notna(row[c_cli]):
                        cli_val = str(row[c_cli]).strip().upper()
                        if cli_val not in cadastro_clientes or not cadastro_clientes[cli_val].get("fantasia"):
                            cadastro_clientes[cli_val] = dict_info

            # 1.2 Procura por colunas unificadas tipo "CÓDIGO - NOME (FANTASIA) [CIDADE]"
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
                            
                            fan_ext = m_fan.group(1).strip() if m_fan else ""
                            cid_ext = m_mun.group(1).strip() if m_mun else ""
                            
                            exist = cadastro_clientes.get(val_str, {})
                            cadastro_clientes[val_str] = {
                                "fantasia": exist.get("fantasia") or fan_ext,
                                "cidade": exist.get("cidade") or cid_ext,
                                "cidade": exist.get("cidade") or cid_ext,
                                "segmento": exist.get("segmento") or "",
                            }
        except: pass
        
    # PASSO 2: Carregar faturamento
    lista_dfs = []
    for arquivo in arquivos_planilhas:
        try:
            df = ler_planilha_generica(arquivo)
            df.columns = df.columns.str.strip().str.lower()
            
            c_dt = next((c for c in df.columns if "dt" in c and "entrega" in c), None)
            c_cli_cad = next((c for c in df.columns if "cliente" in c or "nome" in c), None)
            c_prod = next((c for c in df.columns if "produto" in c), None)
            c_fat = next((c for c in df.columns if "faturamento" in c and "brut" in c), None)
            c_fil = next((c for c in df.columns if "filial" in c or "empresa" in c), None)
            
            if c_dt and c_cli_cad and c_prod and c_fat:
                sel = [c_dt, c_cli_cad, c_prod, c_fat]
                heads = ['Dt. Delivery', 'Cliente_Orig', 'Produto', 'Faturamento Bruto']
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
                
                if sub['Faturamento Bruto'].dtype == 'object':
                    sub['Faturamento Bruto'] = sub['Faturamento Bruto'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['Faturamento Bruto'] = pd.to_numeric(sub['Faturamento Bruto'], errors='coerce')
                lista_dfs.append(sub)
        except Exception as e: 
            continue
        
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cliente'] != 'NAN']
        
        for cli in unificado['Cliente'].unique():
            m_cod = re.match(r'^(\d+)', str(cli))
            cod = m_cod.group(1) if m_cod else ""
            
            info_existente = cadastro_clientes.get(cli) or cadastro_clientes.get(cod, {})
            
            m_fan = re.search(r'\((.*?)\)', str(cli))
            m_mun = re.search(r'\[(.*?)\]', str(cli))
            
            fan_final = info_existente.get("fantasia") or (m_fan.group(1).strip() if m_fan else "")
            cid_final = info_existente.get("cidade") or info_existente.get("cidade") or (m_mun.group(1).strip() if m_mun else "")
            seg_final = info_existente.get("segmento", "") 

            cadastro_clientes[cli] = {
                "fantasia": fan_final,
                "cidade": cid_final,
                "cidade": cid_final,
                "segmento": seg_final,
            }

        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], dayfirst=True, errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
        unificado['Cliente_Busca'] = unificado['Cliente'].apply(limpar_texto)
        if 'Filial' not in unificado.columns: unificado['Filial'] = "1"
        return {"df": unificado, "cadastro": cadastro_clientes}
    return {"df": pd.DataFrame(), "cadastro": cadastro_clientes}

# --- 🗄️ INTEGRAÇÃO COM O BANCO DE DADOS NEON ---
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
        seg = limpar_texto(info.get('segmento', ''))
        for p in (fantasia + " " + seg).split():
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
    
    REGRA ABSOLUTA: Use APENAS segmentos desta lista abaixo (existem na base):
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
        st.error(f"⚠️ Erro de comunicação com o banco Neon ou com a IA: {e}")

# --- SINCRONIZAÇÃO INICIAL ---
with st.spinner("Sincronizando base de dados e IA..."):
    dados_carregados = carregar_dados_nuvem(date.today())
    df_total = dados_carregados["df"]
    dict_cadastro = dados_carregados["cadastro"]
    
    criar_tabelas_neon()
    dict_produtos_segmentos = carregar_produtos_segmentos()
    
if df_total.empty:
    st.warning("Base de dados de vendas vazia ou pendente de processamento no Drive.")
    st.stop()

mes_atual_referencia = date.today().strftime('%Y-%m') 
df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

# --- ESTILIZAÇÃO E MENU LATERAL ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span { font-size: 16px !important; }
    h3 { font-size: 20px !important; font-weight: bold !important; }
    h4 { font-size: 18px !important; }
    div.stButton > button {
        width: 100% !important; height: 52px !important; font-size: 16px !important;
        font-weight: bold !important; margin-bottom: 10px !important; border-radius: 8px !important;
    }
    code { font-size: 14px !important; white-space: pre-wrap !important; }
    .st-emotion-cache-12w0q32 { padding-top: 1.5rem !important; }
    </style>
""", unsafe_allow_html=True)

# INICIALIZAÇÕES DE ESTADO
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = 0

# ==============================================================================
# BARRA LATERAL (SIDEBAR) - NAVEGAÇÃO
# ==============================================================================
with st.sidebar:
    st.markdown("### 🧭 Menu de Navegação")
    
    if st.button("📊 Painel Metas", type="primary" if st.session_state.aba_atual == "📊 Painel Metas" else "secondary"): 
        st.session_state.aba_atual = "📊 Painel Metas"
        st.rerun()
    if st.button("🟢 Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"): 
        st.session_state.aba_atual = "🟢 Ofertas"
        st.rerun()
    if st.button("🚨 Alertas", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"): 
        st.session_state.aba_atual = "🚨 Alertas"
        st.rerun()
    if st.button("🔍 Consulta", type="primary" if st.session_state.aba_atual == "🔍 Consulta" else "secondary"): 
        st.session_state.aba_atual = "🔍 Consulta"
        st.rerun()

    st.write("---")
    
    if st.button("🔄 Sincronizar / Zerar IA"):
        st.cache_data.clear()
        st.toast("Sincronizando...", icon="🔄")
        st.rerun() 
        
    with st.expander("⚙️ Manutenção do Sistema (Neon)"):
        st.write("Se os segmentos estiverem estáticos ou errados, limpe a memória.")
        if st.button("🧹 Limpar Banco de Segmentos"):
            engine = obter_conexao_neon()
            if engine:
                try:
                    with engine.connect() as conn:
                        conn.execute(text("TRUNCATE TABLE produtos_segmentos;"))
                    st.success("✅ Tabela limpa com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao limpar: {e}")

# ==============================================================================
# CARREGAMENTO DE METAS E PROGRESSO
# ==============================================================================
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
            st.toast(f"🏢 {cliente_escolhido} foi puxado para a frente!", icon="⚡")
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
    REGRAS: Retorne a mensagem em texto puro formatado para WhatsApp (com pular linhas e emojis). NÃO retorne em formato JSON para esta tarefa. Termine chamando pra ação. Sem 'Assinado'."""
    
    try: 
        modelo_txt = genai.GenerativeModel('gemini-3.5-flash')
        return modelo_txt.generate_content(prompt).text.strip()
    except: 
        return f"Olá!\nSeparei umas ofertas exclusivas para você!\n\n*🛒 Produtos em oferta:*\n{texto_ofertas_hist}\n\nMe avise se posso garantir o seu pedido! 👍"

# ==============================================================================
# CÁLCULOS DAS METAS E BARRINHA MINIMALISTA NO TOPO
# ==============================================================================
df_fl2 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('2', na=False)]
df_fl6 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('6', na=False)]

real_pos_fl2, real_pos_fl6 = df_fl2['Cliente'].nunique(), df_fl6['Cliente'].nunique()
real_pos_geral = pd.concat([df_fl2, df_fl6])['Cliente'].nunique() if not df_fl2.empty or not df_fl6.empty else 0
real_fat_fl2, real_fat_fl6 = df_fl2['Faturamento Bruto'].sum(), df_fl6['Faturamento Bruto'].sum()
real_fat_geral = real_fat_fl2 + real_fat_fl6

m = st.session_state.metas_config

# Cálculos das Porcentagens
p_fat_g = (real_fat_geral / m['fat_geral'] * 100) if m['fat_geral'] > 0 else 0
p_fat_f2 = (real_fat_fl2 / m['fat_fl2'] * 100) if m['fat_fl2'] > 0 else 0
p_fat_f6 = (real_fat_fl6 / m['fat_fl6'] * 100) if m['fat_fl6'] > 0 else 0

p_pos_g = (real_pos_geral / m['pos_geral'] * 100) if m['pos_geral'] > 0 else 0
p_pos_f2 = (real_pos_fl2 / m['pos_fl2'] * 100) if m['pos_fl2'] > 0 else 0
p_pos_f6 = (real_pos_fl6 / m['pos_fl6'] * 100) if m['pos_fl6'] > 0 else 0

def formatar_brl(valor):
    return f"R${valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def obter_cor_pct(p):
    if p < 50:
        return "#DE350B"  # Vermelho (0 a 49%)
    elif p < 80:
        return "#D97706"  # Amarelo (50 a 79%)
    elif p < 100:
        return "#0052CC"  # Azul (80 a 99%)
    else:
        return "#00875A"  # Verde (100% ou mais)

def fmt_pct_html(p):
    cor = obter_cor_pct(p)
    return f'<span style="color: {cor}; font-weight: bold;">{p:.1f}%</span>'

# --- BARRINHA FIXA MINIMALISTA EM 2 LINHAS NO TOPO DA TELA ---
st.markdown(f"""
<div style="background-color: #f4f5f7; border: 1px solid #dcdfe6; border-radius: 6px; padding: 6px 12px; text-align: center; margin-bottom: 12px; font-size: 13px; color: #172b4d; line-height: 1.6;">
    <div><b>ROB:</b> G {fmt_pct_html(p_fat_g)} | FL2 {fmt_pct_html(p_fat_f2)} | FL6 {fmt_pct_html(p_fat_f6)}</div>
    <div><b>POS:</b> G {fmt_pct_html(p_pos_g)} | FL2 {fmt_pct_html(p_pos_f2)} | FL6 {fmt_pct_html(p_pos_f6)}</div>
</div>
""", unsafe_allow_html=True)

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
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">⚠️ SUMIDO</span>'
    return html

# ==============================================================================
# --- ABA PAINEL DE METAS (ISOLADA) ---
# ==============================================================================
if st.session_state.aba_atual == "📊 Painel Metas":
    st.subheader("📊 Painel Detalhado de Metas")
    
    if st.button("✏️ Editar Metas do Mês"): st.session_state.editar_aberto = True

    if st.session_state.get('editar_aberto', False):
        with st.expander("Configurar Metas", expanded=True):
            m_edit = st.session_state.metas_config.copy()
            with st.form("form_metas"):
                st.write("Positivação (FL2 e FL6)")
                c1, c2 = st.columns(2)
                m_edit['pos_fl2'] = c1.number_input("FL2 (Qtd)", value=int(m_edit['pos_fl2']), key="inp_pos_fl2")
                m_edit['pos_fl6'] = c2.number_input("FL6 (Qtd)", value=int(m_edit['pos_fl6']), key="inp_pos_fl6")
                
                st.write("Faturamento (FL2 e FL6)")
                c3, c4 = st.columns(2)
                m_edit['fat_fl2'] = c3.number_input("FL2 (R$)", value=float(m_edit['fat_fl2']), format="%.2f", key="inp_fat_fl2")
                m_edit['fat_fl6'] = c4.number_input("FL6 (R$)", value=float(m_edit['fat_fl6']), format="%.2f", key="inp_fat_fl6")
                
                if st.form_submit_button("Salvar Metas"):
                    m_edit['pos_geral'] = int(m_edit['pos_fl2'] + m_edit['pos_fl6'])
                    m_edit['fat_geral'] = float(m_edit['fat_fl2'] + m_edit['fat_fl6'])
                    
                    st.session_state.metas_config = m_edit
                    salvar_metas_neon(m_edit)
                    salvar_progresso_atual()
                    st.session_state.editar_aberto = False
                    st.toast("Metas salvas! Valores 'Geral' somados automaticamente.", icon="💾")
                    st.rerun()

    def render_meia_lua_card(subtitulo, realizado, meta, eh_faturamento=False):
        perc = (realizado / meta * 100) if meta > 0 else 0
        perc_display = f"{perc:.1f}%".replace('.', ',')
        
        if eh_faturamento:
            meta_str = formatar_brl(meta)
            real_str = formatar_brl(realizado)
        else:
            meta_str = f"{int(meta)}"
            real_str = f"{int(realizado)}"
            
        perc_clamped = min(max(perc, 0), 100)
        dashoffset = 125.66 * (1 - (perc_clamped / 100))
        cor_barra = "#00875A" if perc >= 100 else "#0052CC"
        
        return f"""
        <div style="background-color: #ffffff; border-radius: 8px; padding: 8px 4px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.1); border: 1px solid #e1e4e8; margin-bottom: 5px;">
            <div style="font-weight: bold; font-size: 13px; color: #333; margin-bottom: 2px;">{subtitulo}</div>
            <div style="position: relative; width: 100%; max-width: 110px; margin: 0 auto;">
                <svg viewBox="0 0 100 55" style="width: 100%; height: auto; display: block;">
                    <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="#EAEAEA" stroke-width="12" stroke-linecap="round" />
                    <path d="M 10 50 A 40 40 0 0 1 90 50" fill="none" stroke="{cor_barra}" stroke-width="12" stroke-dasharray="125.66" stroke-dashoffset="{dashoffset}" stroke-linecap="round" />
                    <text x="50" y="46" text-anchor="middle" font-size="15" font-weight="bold" fill="#172B4D">{perc_display}</text>
                </svg>
            </div>
            <div style="font-size: 10px; color: #5e6c84; margin-top: 2px; line-height: 1.2;">
                <b>Meta:</b> {meta_str}<br><b>Real:</b> {real_str}
            </div>
        </div>
        """

    st.markdown("### 📈 Positivação")
    col1, col2, col3 = st.columns(3)
    with col1: st.markdown(render_meia_lua_card("Geral", real_pos_geral, m['pos_geral']), unsafe_allow_html=True)
    with col2: st.markdown(render_meia_lua_card("FL2", real_pos_fl2, m['pos_fl2']), unsafe_allow_html=True)
    with col3: st.markdown(render_meia_lua_card("FL6", real_pos_fl6, m['pos_fl6']), unsafe_allow_html=True)

    st.markdown("### 💰 ROB Faturamento")
    col4, col5, col6 = st.columns(3)
    with col4: st.markdown(render_meia_lua_card("Geral", real_fat_geral, m['fat_geral'], eh_faturamento=True), unsafe_allow_html=True)
    with col5: st.markdown(render_meia_lua_card("FL2", real_fat_fl2, m['fat_fl2'], eh_faturamento=True), unsafe_allow_html=True)
    with col6: st.markdown(render_meia_lua_card("FL6", real_fat_fl6, m['fat_fl6'], eh_faturamento=True), unsafe_allow_html=True)

# ==============================================================================
# --- ABA 1: OFERTAS ---
# ==============================================================================
elif st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão c/ IA 🧠")
    st.markdown(f"📊 Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    tipo_lista = st.radio("Canal:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    
    # Extração robusta das cidades para o Filtro de Município
    cidades_disponiveis = set()
    for cli_cad, info_cad in dict_cadastro.items():
        cid = info_cad.get("cidade") or info_cad.get("cidade")
        if cid and str(cid).strip() and str(cid).strip().lower() != 'nan':
            cidades_disponiveis.add(str(cid).strip().upper())
        m = re.search(r'\[(.*?)\]', str(cli_cad))
        if m and m.group(1).strip():
            cidades_disponiveis.add(m.group(1).strip().upper())

    for cli in df_total['Cliente'].unique():
        if pd.isna(cli) or str(cli).lower() == 'nan': continue
        m_cod = re.match(r'^(\d+)', str(cli))
        codigo = m_cod.group(1) if m_cod else ""
        info = dict_cadastro.get(str(cli), {}) or (dict_cadastro.get(codigo, {}) if codigo else {})
        cid = info.get("cidade") or info.get("cidade")
        if cid and str(cid).strip() and str(cid).strip().lower() != 'nan':
            cidades_disponiveis.add(str(cid).strip().upper())
        m = re.search(r'\[(.*?)\]', str(cli))
        if m and m.group(1).strip():
            cidades_disponiveis.add(m.group(1).strip().upper())

    cidades_disponiveis = sorted(list(cidades_disponiveis))

    cidades_selecionadas = st.multiselect("📍 Filtrar lista de disparo por Município(s):", options=cidades_disponiveis, placeholder="Selecione as cidades (deixe vazio para todas)")

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
                    with st.spinner(f"🧠 IA aprendendo e classificando {len(produtos_desconhecidos)} novos produtos..."):
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
                        nome_cli_limpo = limpar_texto(cli_cad) + " " + limpar_texto(info_cad.get("fantasia", "")) + " " + limpar_texto(info_cad.get("segmento", ""))
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
                st.success("Fila vinculada! Ofertas separadas (Histórico / Segmento)!")
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
                m_cod = re.match(r'^(\d+)', str(c))
                codigo = m_cod.group(1) if m_cod else ""
                info = dict_cadastro.get(str(c), {}) or (dict_cadastro.get(codigo, {}) if codigo else {})
                cidade_cli = info.get("cidade") or info.get("cidade") or ""
                cidade_cli_limpa = limpar_texto(cidade_cli)
                
                if not cidade_cli_limpa:
                    m_mun = re.search(r'\[(.*?)\]', str(c))
                    if m_mun:
                        cidade_cli_limpa = limpar_texto(m_mun.group(1))
                        
                if cidade_cli_limpa and any(cs in cidade_cli_limpa or cidade_cli_limpa in cs for cs in cidades_sel_limpas):
                    filtrados.append(c)
            clientes_restantes = filtrados
        
        if not clientes_restantes:
            st.info("Nenhum cliente pendente na fila para os municípios selecionados.")
        else:
            st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
            
            st.selectbox(
                "🚀 Puxar cliente para a frente da fila:", 
                options=["-- Digite ou selecione um cliente para adiantar --"] + clientes_restantes,
                key=f"puxar_frente_{id_fila}",
                on_change=adiantar_cliente_fila_callback,
                args=(id_fila,)
            )
                
            st.write("---")
            cliente_atual = clientes_restantes[0]
            ofertas_cliente = fila_ativa[cliente_atual]
            
            # --- CARD VISUAL E ESTRUTURADO DO CLIENTE ---
            renderizar_card_cliente(cliente_atual, dict_cadastro, dict_produtos_segmentos, obter_badges_html(cliente_atual))
            
            if st.session_state.cliente_ia_atual != cliente_atual:
                st.session_state.cliente_ia_atual = cliente_atual
                historico = df_total[df_total['Cliente'] == cliente_atual].groupby('Produto')['Faturamento Bruto'].sum().nlargest(5).index.tolist()
                with st.spinner("🧠 Gemini analisando cruzamentos e organizando formatação para WhatsApp..."):
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
                if st.button("❌ Excluir da Fila", key=f"ex_{str(cliente_atual)[:5]}"):
                    st.session_state[id_excluidos].add(cliente_atual)
                    del st.session_state[id_fila][cliente_atual]
                    st.session_state.cliente_ia_atual = ""
                    salvar_progresso_atual()
                    st.rerun()
            with col_b3:
                if st.button("⏭️ Pular p/ Final", key=f"pular_{str(cliente_atual)[:5]}"):
                    dados_cliente = st.session_state[id_fila].pop(cliente_atual)
                    st.session_state[id_fila][cliente_atual] = dados_cliente
                    st.session_state.cliente_ia_atual = ""
                    salvar_progresso_atual()
                    st.toast(f"{cliente_atual} jogado para o final da fila!", icon="⏭️")
                    st.rerun()

# ==============================================================================
# --- ABA 2: ALERTAS ---
# ==============================================================================
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200, key="txt_sup_area_fix")
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id="copyBtn" style="width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                navigator.clipboard.writeText({texto_js_safe});
                this.innerText = '✅ Copiado com sucesso!';
                setTimeout(() => {{ this.innerText = '📋 Copiar Relatório'; }}, 2000);
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            
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
    filtro_status = st.selectbox("Filtrar por status de envio:", ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"])
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
        st.info("Nenhum cliente localizado para os filtros selecionados.")
    else:
        st.markdown(f"📊 Exibindo **{len(df_alertas_visuais)}** clientes nesta lista:")
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            if f"chk_{c_nome}" not in st.session_state: st.session_state[f"chk_{c_nome}"] = False
            
            with st.container():
                st.checkbox(f"📍 Selecionar para Relatório ({row['Dias']} dias sem comprar)", key=f"chk_{c_nome}")
                html_badges = obter_badges_html(c_nome)
                if row["Reportado"]: html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 JÁ REPORTADO</span>'
                renderizar_card_cliente(c_nome, dict_cadastro, dict_produtos_segmentos, html_badges)
                
                if st.button(f"🔍 Histórico...", key=f"btn_h_{idx}"):
                    st.session_state.busca_direta_cliente = c_nome
                    st.session_state.sub_aba_consulta = "👤 Por Cliente"
                    st.session_state.aba_atual = "🔍 Consulta"  
                    st.rerun()
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
                        top_itens = df_cli_h.groupby('Produto')['Faturamento Bruto'].sum().nlargest(3).index.tolist()
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
                st.warning("⚠️ Por favor, marque pelo menos um Checkbox na lista acima para poder gerar o texto!")

# ==============================================================================
# ==============================================================================
# ==============================================================================
# --- ABA 3: CONSULTA ---
# ==============================================================================
elif st.session_state.aba_atual == "🔍 Consulta":
    st.radio(
        "Filtro de Pesquisa:", 
        ["👤 Por Cliente", "📦 Por Produto", "📉 Recuperação", "🏢 Exclusivos Filial 6", "🏆 Parceiros Estratégicos"], 
        horizontal=True,
        key="sub_aba_consulta"
    )
    st.write("---")
    
    sub_atual = st.session_state.sub_aba_consulta
    
    # Obter mês e ano atuais para filtros mensais
    mes_atual_sis = data_atual_sistema.month
    ano_atual_sis = data_atual_sistema.year
    
    df_mes_atual = pd.DataFrame()
    if not df_total.empty and 'Data_Datetime' in df_total.columns:
        df_mes_atual = df_total[
            (df_total['Data_Datetime'].dt.month == mes_atual_sis) & 
            (df_total['Data_Datetime'].dt.year == ano_atual_sis)
        ]

    if sub_atual == "👤 Por Cliente":
        st.subheader("Raio-X do Cliente")
        input_busca = st.text_input("Nome ou Código:", value=st.session_state.busca_direta_cliente).strip()
        
        if input_busca:
            filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', input_busca)
            nomes_encontrados = filtrados['Cliente'].unique()
            
            if len(nomes_encontrados) > 0:
                c_sel = st.selectbox("Selecione o Cliente:", nomes_encontrados)
                
                renderizar_card_cliente(c_sel, dict_cadastro, dict_produtos_segmentos, obter_badges_html(c_sel))
                
                df_cli = df_total[df_total['Cliente'] == c_sel]
                st.write("**Mix de Itens Históricos:**")
                rank_p = df_cli.groupby('Produto')['Faturamento Bruto'].sum().nlargest(10).reset_index()
                
                for i, r in rank_p.iterrows():
                    st.markdown(f"<p style='font-size: 13px; margin-bottom: 2px;'>• {r['Produto']} (R$ {r['Faturamento Bruto']:,.2f})</p>", unsafe_allow_html=True)
                
                st.write("---")
                st.write("📉 **Produtos Abandonados (Parou de comprar):**")
                
                max_dates = df_cli.groupby('Produto')['Data_Datetime'].max()
                abandonados = max_dates[max_dates.apply(lambda x: (data_atual_sistema - x).days > 30)].index.tolist()
                df_ab = df_cli[df_cli['Produto'].isin(abandonados)].groupby('Produto').agg(
                    Fat=('Faturamento Bruto', 'sum'), Ult_Compra=('Data_Datetime', 'max')
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
                    
                    tag_oferta = " <span style='background-color:#DE350B; color:white; padding:2px 4px; border-radius:3px; font-size:10px; font-weight:bold;'>🚨 NA OFERTA!</span>" if is_oferta else ""
                    html_ab += f"<p style='font-size: 13px; margin-bottom: 3px;'>• {prod} <i>(⏳ {dias} dias)</i>{tag_oferta}</p>"
                    texto_abandonados_p_ia += f"- {prod} ({dias} dias sem comprar) {'[ESTÁ NA OFERTA]' if is_oferta else ''}\n"
                
                if html_ab:
                    st.markdown(html_ab, unsafe_allow_html=True)
                    texto_js_abandonados = json.dumps("Produtos Abandonados pelo Cliente:\n" + texto_abandonados_p_ia)
                    components.html(f"""
                        <button id="copyBtnAb" style="width: 100%; max-width: 200px; background-color: #42526E; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold; font-size: 13px; cursor: pointer; margin-top: 5px;">📋 Copiar Abandonados</button>
                        <script>
                        document.getElementById('copyBtnAb').addEventListener('click', function() {{
                            navigator.clipboard.writeText({texto_js_abandonados});
                            this.innerText = '✅ Copiado!';
                            setTimeout(() => {{ this.innerText = '📋 Copiar Abandonados'; }}, 2000);
                        }});
                        </script>
                    """, height=50)
                else:
                    st.markdown("<p style='font-size: 13px;'>Nenhum abandono acima de 30 dias detectado.</p>", unsafe_allow_html=True)

                st.write("---")
                st.markdown("### 💡 Venda Cruzada Inteligente (Oferta + Histórico)")
                
                m_cod_c = re.match(r'^(\d+)', str(c_sel))
                cod_c = m_cod_c.group(1) if m_cod_c else ""
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
                
                if st.button("🧠 Gerar Abordagem de Vendas via IA", type="primary"):
                    prompt_cruzada = f"""
                    Atue como um excelente vendedor B2B da distribuidora Delly's. Crie uma mensagem curta de WhatsApp para o cliente '{c_sel}'.
                    
                    Use ESTES DADOS para construir a mensagem:
                    1. Produtos que ele parou de comprar (Abandonados): 
                    {texto_abandonados_p_ia if texto_abandonados_p_ia else "Nenhum no momento."}
                    2. Sugestões inovadoras para o segmento dele ({', '.join(segmentos_do_cliente)}):
                    {', '.join(sugestoes_segmento[:5])}
                    3. Principais Ofertas de hoje:
                    {', '.join(ofertas_memoria[:6]) if ofertas_memoria else "Nenhuma no momento"}
                    
                    REGRAS PARA A MENSAGEM:
                    - MUITO IMPORTANTE: Se houver algum 'Produto Abandonado' que 'ESTÁ NA OFERTA', você DEVE enfatizar isso dizendo que o preço do que ele costumava comprar baixou.
                    - Faça links inteligentes.
                    - Formato exclusivo para WhatsApp: Pule linhas (duplas) entre os assuntos, use Emojis e *negrito* nos nomes dos produtos.
                    - NÃO INVENTE PREÇOS, deixe apenas os produtos.
                    - Mensagem direta e vendedora.
                    """
                    with st.spinner("Conectando ao Gemini..."):
                        try:
                            modelo_msg = genai.GenerativeModel('gemini-3.5-flash')
                            st.session_state[chave_sessao_msg] = modelo_msg.generate_content(prompt_cruzada).text
                        except Exception as e:
                            st.error(f"Erro ao gerar com IA: {e}")
                
                if chave_sessao_msg in st.session_state and st.session_state[chave_sessao_msg]:
                    st.text_area("Mensagem Formatada:", value=st.session_state[chave_sessao_msg], height=220)
                    texto_js_cruzada = json.dumps(st.session_state[chave_sessao_msg])
                    components.html(f"""
                        <button id="copyBtnCrz" style="width: 100%; background-color: #00875A; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; font-size: 15px; cursor: pointer;">📋 Copiar Mensagem para WhatsApp</button>
                        <script>
                        document.getElementById('copyBtnCrz').addEventListener('click', function() {{
                            navigator.clipboard.writeText({texto_js_cruzada});
                            this.innerText = '✅ Copiado com sucesso!';
                            setTimeout(() => {{ this.innerText = '📋 Copiar Mensagem para WhatsApp'; }}, 2000);
                        }});
                        </script>
                    """, height=55)

            else:
                st.warning("Cliente não encontrado.")
                
    elif sub_atual == "📦 Por Produto":
        st.subheader("Análise por Produto")
        input_prod = st.text_input("Nome do produto:").strip()
        if input_prod:
            filtrados_p = filtrar_por_palavras(df_total, 'Produto_Busca', input_prod)
            if not filtrados_p.empty:
                st.write(f"✅ Encontrados **{len(filtrados_p['Produto'].unique())}** produtos semelhantes.")
                st.markdown("### Top 10 Compradores deste Item")
                top_compradores = filtrados_p.groupby('Cliente')['Faturamento Bruto'].sum().nlargest(10).reset_index()
                for idx, row in top_compradores.iterrows():
                    st.markdown(f"**{row['Cliente']}** - R$ {row['Faturamento Bruto']:,.2f}")
            else:
                st.warning("Nenhum produto encontrado com este nome.")

    elif sub_atual == "📉 Recuperação":
        st.subheader("📉 Ranking de Produtos Abandonados (Recuperação)")
        st.write("Identifique clientes que compravam determinados itens e pararam. Ordenado do maior para o menor valor em R$ em aberto.")
        
        if not df_total.empty:
            if df_total['Faturamento Bruto'].dtype == object or not pd.api.types.is_numeric_dtype(df_total['Faturamento Bruto']):
                df_total['Faturamento Bruto'] = (
                    df_total['Faturamento Bruto'].astype(str)
                    .str.replace('R$', '', regex=True)
                    .str.replace('.', '', regex=False)
                    .str.replace(',', '.', regex=False)
                    .str.strip()
                )
                df_total['Faturamento Bruto'] = pd.to_numeric(df_total['Faturamento Bruto'], errors='coerce').fillna(0.0)

            cidades_disponiveis_rec = set()
            for cli_cad, info_cad in dict_cadastro.items():
                cid = info_cad.get("cidade")
                if cid and str(cid).strip() and str(cid).strip().lower() != 'nan':
                    cidades_disponiveis_rec.add(str(cid).strip().upper())
                m = re.search(r'\[(.*?)\]', str(cli_cad))
                if m and m.group(1).strip():
                    cidades_disponiveis_rec.add(m.group(1).strip().upper())
                    
            for cli in df_total['Cliente'].unique():
                if pd.isna(cli) or str(cli).lower() == 'nan': continue
                m_cod = re.match(r'^(\d+)', str(cli))
                codigo = m_cod.group(1) if m_cod else ""
                info = dict_cadastro.get(str(cli), {})
                if not info and codigo:
                    info = dict_cadastro.get(codigo, {})
                cid = info.get("cidade") if info else None
                if cid and str(cid).strip() and str(cid).strip().lower() != 'nan':
                    cidades_disponiveis_rec.add(str(cid).strip().upper())
                m = re.search(r'\[(.*?)\]', str(cli))
                if m and m.group(1).strip():
                    cidades_disponiveis_rec.add(m.group(1).strip().upper())

            cidades_disponiveis_rec = sorted(list(cidades_disponiveis_rec))
            
            cidades_selecionadas_rec = st.multiselect(
                "📍 Filtrar Ranking por Município(s):", 
                options=cidades_disponiveis_rec, 
                placeholder="Selecione as cidades (deixe vazio para o ranking geral)",
                key="multiselect_rec_cidades"
            )

            dias_corte = st.slider("Considerar abandono após (dias sem comprar):", min_value=15, max_value=120, value=30, key="slider_dias_corte_rec")

            with st.spinner("Calculando itens abandonados por cliente..."):
                max_datas_cli_prod = df_total.groupby(['Cliente', 'Produto'])['Data_Datetime'].max().reset_index()
                max_datas_cli_prod['Dias_Sem_Compra'] = (data_atual_sistema - max_datas_cli_prod['Data_Datetime']).dt.days
                
                df_abandonados = max_datas_cli_prod[max_datas_cli_prod['Dias_Sem_Compra'] > dias_corte].copy()
                
                if not df_abandonados.empty:
                    df_fat_prod = df_total.groupby(['Cliente', 'Produto'])['Faturamento Bruto'].sum().reset_index()
                    df_abandonados = pd.merge(df_abandonados, df_fat_prod, on=['Cliente', 'Produto'], how='left')
                    
                    ranking_clientes = df_abandonados.groupby('Cliente').agg(
                        Fat_Total_Abandonado=('Faturamento Bruto', 'sum'),
                        Qtd_Itens_Abandonados=('Produto', 'count')
                    ).reset_index().sort_values(by='Fat_Total_Abandonado', ascending=False)
                    
                    if cidades_selecionadas_rec:
                        cidades_sel_limpas = [limpar_texto(c) for c in cidades_selecionadas_rec]
                        clientes_filtrados_cidade = []
                        for c in ranking_clientes['Cliente']:
                            m_cod = re.match(r'^(\d+)', str(c))
                            codigo = m_cod.group(1) if m_cod else ""
                            info = dict_cadastro.get(str(c), {})
                            if not info and codigo:
                                info = dict_cadastro.get(codigo, {})
                            cidade_cli = info.get("cidade", "") if info else ""
                            cidade_cli_limpa = limpar_texto(cidade_cli)
                            if not cidade_cli_limpa:
                                m_mun = re.search(r'\[(.*?)\]', str(c))
                                if m_mun: cidade_cli_limpa = limpar_texto(m_mun.group(1))
                            
                            if cidade_cli_limpa and any(cs in cidade_cli_limpa or cidade_cli_limpa in cs for cs in cidades_sel_limpas):
                                clientes_filtrados_cidade.append(c)
                        ranking_clientes = ranking_clientes[ranking_clientes['Cliente'].isin(clientes_filtrados_cidade)]

                    st.markdown(f"### 🏆 Total de Clientes com Oportunidades de Recuperação: **{len(ranking_clientes)}**")
                    
                    for idx, row in ranking_clientes.head(30).iterrows():
                        c_nome = row['Cliente']
                        fat_perdido = row['Fat_Total_Abandonado']
                        qtd_itens = row['Qtd_Itens_Abandonados']
                        
                        with st.container():
                            badge_fat = f'<span style="background-color:#0052CC; color:white; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:13px; margin-right:6px;">💰 R$ {fat_perdido:,.2f} em aberto ({qtd_itens} itens)</span>'
                            renderizar_card_cliente(c_nome, dict_cadastro, dict_produtos_segmentos, badge_fat)
                            
                            itens_cli_ab = df_abandonados[df_abandonados['Cliente'] == c_nome].sort_values(by='Faturamento Bruto', ascending=False)
                            
                            texto_itens_ab = ""
                            for _, it_row in itens_cli_ab.iterrows():
                                fat_item = it_row['Faturamento Bruto']
                                dias_item = it_row['Dias_Sem_Compra']
                                texto_itens_ab += f"  • {it_row['Produto']} — R$ {fat_item:,.2f} ({dias_item} dias sem comprar)\n"
                            
                            with st.expander(f"📦 Ver os {qtd_itens} itens abandonados e gerar abordagem"):
                                st.markdown(f"<pre style='font-size:12px; background:#f4f5f7; padding:8px;'>{texto_itens_ab}</pre>", unsafe_allow_html=True)
                                
                                chave_msg_rec = f"msg_rec_{idx}"
                                
                                if st.button("🧠 Gerar Mensagem de Resgate via IA", key=f"btn_ia_rec_{idx}", type="primary"):
                                    prompt_rec = f"""
                                    Atue como um excelente representante comercial B2B da distribuidora Delly's. 
                                    Crie uma mensagem curta de WhatsApp para o cliente '{c_nome}'.
                                    O objetivo é entender por que he parou de comprar e resgatá-lo em relação aos seguintes produtos de alto volume que he abandonou há algum tempo:
                                    {texto_itens_ab}
                                    
                                    REGRAS PARA A MENSAGEM:
                                    - Tom empático, curioso e profissional.
                                    - Formato exclusivo para WhatsApp: Pule linhas duplas, use Emojis e *negrito* nos nomes dos produtos abandonados.
                                    - Termine abrindo espaço para o diálogo.
                                    """
                                    with st.spinner("Gerando mensagem personalizada..."):
                                        try:
                                            modelo_msg = genai.GenerativeModel('gemini-3.5-flash')
                                            st.session_state[chave_msg_rec] = modelo_msg.generate_content(prompt_rec).text
                                        except Exception as e:
                                            st.error(f"Erro ao gerar com IA: {e}")
                                
                                if chave_msg_rec in st.session_state and st.session_state[chave_msg_rec]:
                                    st.text_area("Mensagem de Abordagem:", value=st.session_state[chave_msg_rec], height=180, key=f"txt_area_rec_{idx}")
                                    
                        st.write("---")
                else:
                    st.info("Nenhum produto abandonado encontrado para o período de corte selecionado.")
        else:
            st.warning("Carregue os dados de vendas primeiro para visualizar a recuperação.")

    elif sub_atual == "🏢 Exclusivos Filial 6":
        st.subheader("🏢 Clientes Exclusivos da Filial 6 (No Mês)")
        st.write("Clientes que compraram produtos da **Filial 6 no mês atual**, mas ainda não compraram na **Filial 2**.")
        
        if not df_mes_atual.empty:
            cli_fl2_mes = set(df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('2', na=False)]['Cliente'].unique())
            cli_fl6_mes = set(df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('6', na=False)]['Cliente'].unique())
            
            exclusivos_f6_mes = sorted(list(cli_fl6_mes - cli_fl2_mes))
            
            if exclusivos_f6_mes:
                st.markdown(f"📊 Total de Clientes Exclusivos Filial 6 no mês: **{len(exclusivos_f6_mes)}**")
                
                cidades_fl6 = set()
                for c in exclusivos_f6_mes:
                    m_cod = re.match(r'^(\d+)', str(c))
                    cod = m_cod.group(1) if m_cod else ""
                    info = dict_cadastro.get(str(c), {}) or (dict_cadastro.get(cod, {}) if cod else {})
                    cid = info.get("cidade") or ""
                    if cid: cidades_fl6.add(cid.upper())
                
                cidades_fl6_list = sorted(list(cidades_fl6))
                cidade_filtro_f6 = st.multiselect("📍 Filtrar por Município (Filial 6):", options=cidades_fl6_list, key="multiselect_f6_cid")
                
                clientes_exibicao_f6 = exclusivos_f6_mes
                if cidade_filtro_f6:
                    cidades_sel_limpas = [limpar_texto(c) for c in cidade_filtro_f6]
                    clientes_exibicao_f6 = []
                    for c in exclusivos_f6_mes:
                        m_cod = re.match(r'^(\d+)', str(c))
                        cod = m_cod.group(1) if m_cod else ""
                        info = dict_cadastro.get(str(c), {}) or (dict_cadastro.get(cod, {}) if cod else {})
                        cid = limpar_texto(info.get("cidade", ""))
                        if any(cs in cid or cid in cs for cs in cidades_sel_limpas):
                            clientes_exibicao_f6.append(c)
                
                st.markdown(f"Exibindo **{len(clientes_exibicao_f6)}** clientes:")
                for c_nome in clientes_exibicao_f6[:50]:
                    fat_cli_f6 = df_mes_atual[(df_mes_atual['Cliente'] == c_nome) & (df_mes_atual['Filial'].astype(str).str.contains('6', na=False))]['Faturamento Bruto'].sum()
                    badge_f6 = f'<span style="background-color:#FF8B00; color:white; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:13px;">💰 Faturamento Filial 6 (Mês): R$ {fat_cli_f6:,.2f}</span>'
                    renderizar_card_cliente(c_nome, dict_cadastro, dict_produtos_segmentos, badge_f6)
            else:
                st.info("Nenhum cliente exclusivo da Filial 6 encontrado para o mês atual.")
        else:
            st.warning("Não há dados de vendas registrados para o mês atual.")

    elif sub_atual == "🏆 Parceiros Estratégicos":
        st.subheader("🏆 Análise de Parceiros Estratégicos (No Mês)")
        st.write("Selecione um parceiro estratégico para ver quantos clientes foram positivados no mês e quais clientes ativos ainda não compram dele.")
        
        if not df_mes_atual.empty:
            # Tentar identificar coluna de parceiro/fornecedor/marca/segmento
            colunas_parceiro_cand = [c for c in ['Fornecedor', 'Marca', 'Fabricante', 'Segmento', 'Categoria'] if c in df_mes_atual.columns]
            
            if colunas_parceiro_cand:
                col_parceiro_escolhida = colunas_parceiro_cand[0]
                parceiros_disponiveis = sorted([str(x) for x in df_mes_atual[col_parceiro_escolhida].dropna().unique() if str(x).strip()])
            else:
                # Fallback: extrair segmentos do dicionário ou usar produtos
                parceiros_disponiveis = sorted(list(dict_produtos_segmentos.keys())) if dict_produtos_segmentos else []
            
            if parceiros_disponiveis:
                parceiro_selecionado = st.selectbox("Selecione o Parceiro Estratégico:", options=parceiros_disponiveis, key="select_parceiro_est")
                
                if parceiro_selecionado:
                    # Identificar clientes que compraram deste parceiro no mês
                    if colunas_parceiro_cand:
                        cli_compraram_parceiro = set(df_mes_atual[df_mes_atual[col_parceiro_escolhida].astype(str) == str(parceiro_selecionado)]['Cliente'].unique())
                    else:
                        # Buscar por produtos associados ao segmento/parceiro
                        prods_parceiro = [p for p, segs in dict_produtos_segmentos.items() if parceiro_selecionado in segs]
                        cli_compraram_parceiro = set(df_mes_atual[df_mes_atual['Produto'].isin(prods_parceiro)]['Cliente'].unique())
                    
                    # Clientes positivados no mês total
                    cli_ativos_mes = set(df_mes_atual['Cliente'].unique())
                    
                    # Clientes que compraram no mês mas NÃO compraram deste parceiro
                    cli_nao_compraram_parceiro = sorted(list(cli_ativos_mes - cli_compraram_parceiro))
                    
                    # Métricas e contagem
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.metric("✅ Clientes Positivados do Parceiro", len(cli_compraram_parceiro))
                    with col_m2:
                        st.metric("🎯 Oportunidades (Ativos no Mês sem este Parceiro)", len(cli_nao_compraram_parceiro))
                    
                    st.write("---")
                    st.markdown(f"### 📋 Clientes Ativos no Mês que **ainda não comprou** de `{parceiro_selecionado}`:")
                    
                    if cli_nao_compraram_parceiro:
                        for c_nome in cli_nao_compraram_parceiro[:50]:
                            fat_mes_cli = df_mes_atual[df_mes_atual['Cliente'] == c_nome]['Faturamento Bruto'].sum()
                            badge_parc = f'<span style="background-color:#6554C0; color:white; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:13px;">🛒 Faturamento no Mês: R$ {fat_mes_cli:,.2f}</span>'
                            renderizar_card_cliente(c_nome, dict_cadastro, dict_produtos_segmentos, badge_parc)
                    else:
                        st.info("Todos os clientes ativos no mês já compraram deste parceiro estratégico!")
            else:
                st.warning("Nenhum parceiro ou categoria identificada nos dados para seleção.")
        else:
            st.warning("Não há dados de vendas registrados para o mês atual.")
