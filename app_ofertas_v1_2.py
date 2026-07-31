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
st.set_page_config(page_title="Delly's Inteligência", layout="centered")

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
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pc', 'pc', 'promocao', 'oferta', 'frita', 'fritas', 'congelada', 'congeladas']
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
    
    # PASSO 1: Identificar a planilha que possui a coluna unificada (Cód - Nome (Fantasia) [Cidade])
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            for col in df.columns:
                s_col = df[col].astype(str)
                # Verifica se existem valores compatíveis com o novo padrão unificado
                mask = s_col.str.contains(r'^\d+\s*[-|–]?\s*.*\s*\[.*\]', regex=True, na=False)
                if mask.any():
                    for val in s_col[mask]:
                        val_str = str(val).strip().upper()
                        m_cod = re.match(r'^(\d+)', val_str)
                        if m_cod:
                            cod = m_cod.group(1)
                            cod_to_full[cod] = val_str # Mapeia Cód -> String Completa
                            
                            m_fan = re.search(r'\((.*?)\)', val_str)
                            m_mun = re.search(r'\[(.*?)\]', val_str)
                            if val_str not in cadastro_clientes:
                                cadastro_clientes[val_str] = {
                                    "fantasia": m_fan.group(1).strip() if m_fan else "",
                                    "municipio": m_mun.group(1).strip() if m_mun else "",
                                    "cardapio": ""
                                }
        except: pass
        
    # PASSO 2: Carregar faturamento e cruzar Cód para unificar o nome em todas as telas
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
                
                # Substituição inteligente: Lê o cód da venda e injeta o texto completo unificado
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
        except Exception as e: 
            continue
        
    if lista_dfs:
        unificado = pd.concat(lista_dfs, ignore_index=True)
        unificado = unificado[unificado['Cliente'] != 'NAN']
        
        # Garante que todo cliente nas vendas tenha registro na memória
        for cli in unificado['Cliente'].unique():
            if cli not in cadastro_clientes:
                m_fan = re.search(r'\((.*?)\)', str(cli))
                m_mun = re.search(r'\[(.*?)\]', str(cli))
                cadastro_clientes[cli] = {
                    "fantasia": m_fan.group(1).strip() if m_fan else "",
                    "municipio": m_mun.group(1).strip() if m_mun else "",
                    "cardapio": ""
                }

        unificado['Data_Datetime'] = pd.to_datetime(unificado['Dt. Delivery'], dayfirst=True, errors='coerce')
        unificado['Ano_Mes'] = unificado['Data_Datetime'].dt.strftime('%Y-%m')
        unificado['Produto_Busca'] = unificado['Produto'].apply(limpar_texto)
        unificado['Cliente_Busca'] = unificado['Cliente'].apply(limpar_texto)
        if 'Filial' not in unificado.columns: unificado['Filial'] = "1"
        return {"df": unificado, "cadastro": cadastro_clientes}
    return {"df": pd.DataFrame(), "cadastro": {}}

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
                    CREATE TABLE IF NOT EXISTS cardapios_clientes (
                        cliente VARCHAR(255) PRIMARY KEY,
                        fantasia VARCHAR(255),
                        produtos TEXT
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

def carregar_cardapios_neon():
    engine = obter_conexao_neon()
    mapa = {}
    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT cliente, produtos FROM cardapios_clientes;")).fetchall()
                for row in res:
                    mapa[row[0]] = json.loads(row[1])
        except: pass
    return mapa

def salvar_cardapio_neon(cliente, produtos, fantasia=""):
    engine = obter_conexao_neon()
    if engine:
        try:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO cardapios_clientes (cliente, fantasia, produtos) 
                    VALUES (:c, :f, :p)
                    ON CONFLICT (cliente) DO UPDATE SET produtos = EXCLUDED.produtos, fantasia = EXCLUDED.fantasia;
                """), {"c": cliente, "f": fantasia, "p": json.dumps(produtos)})
        except Exception as e: st.error(f"Erro ao salvar cardápio no Neon: {e}")

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
    dict_cardapios_neon = carregar_cardapios_neon()
    
    for cli_neon, prods_neon in dict_cardapios_neon.items():
        if cli_neon in dict_cadastro:
            dict_cadastro[cli_neon]["cardapio"] = ", ".join(prods_neon)
        else:
            dict_cadastro[cli_neon] = {"fantasia": "", "municipio": "", "cardapio": ", ".join(prods_neon)}

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
    </style>
""", unsafe_allow_html=True)

# INICIALIZAÇÕES DE ESTADO
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = 0

# ==============================================================================
# BARRAL LATERAL (SIDEBAR) - NAVEGAÇÃO
# ==============================================================================
with st.sidebar:
    st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)
    st.markdown("### 🧭 Menu de Navegação")
    
    if st.button("🟢 Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"): st.session_state.aba_atual = "🟢 Ofertas"; st.rerun()
    if st.button("🚨 Alertas", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"): st.session_state.aba_atual = "🚨 Alertas"; st.rerun()
    if st.button("🔍 Consulta", type="primary" if st.session_state.aba_atual == "🔍 Consulta" else "secondary"): st.session_state.aba_atual = "🔍 Consulta"; st.rerun()
    if st.button("💲 Cotação", type="primary" if st.session_state.aba_atual == "💲 Cotação" else "secondary"): st.session_state.aba_atual = "💲 Cotação"; st.rerun()
    if st.button("🍔 Cardápios", type="primary" if st.session_state.aba_atual == "🍔 Cardápios" else "secondary"): st.session_state.aba_atual = "🍔 Cardápios"; st.rerun()

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
        modelo_txt = genai.GenerativeModel('gemini-1.5-flash')
        return modelo_txt.generate_content(prompt).text.strip()
    except: 
        return f"Olá!\nSeparei umas ofertas exclusivas para você!\n\n*🛒 Produtos em oferta:*\n{texto_ofertas_hist}\n\nMe avise se posso garantir o seu pedido! 👍"

# ==============================================================================
# PAINEL DE METAS
# ==============================================================================
df_fl2 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('2', na=False)]
df_fl6 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('6', na=False)]

real_pos_fl2, real_pos_fl6 = df_fl2['Cliente'].nunique(), df_fl6['Cliente'].nunique()
real_pos_geral = pd.concat([df_fl2, df_fl6])['Cliente'].nunique() if not df_fl2.empty or not df_fl6.empty else 0
real_fat_fl2, real_fat_fl6 = df_fl2['Faturamento Brut'].sum(), df_fl6['Faturamento Brut'].sum()
real_fat_geral = real_fat_fl2 + real_fat_fl6

def exibir_kpi_linha(label, meta, realizado, eh_faturamento=False):
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    col1.write(f"**{label}**")
    col2.write(f"Meta: {f'R$ {meta:,.0f}' if eh_faturamento else meta}")
    col3.write(f"Real: {f'R$ {realizado:,.0f}' if eh_faturamento else realizado}")
    perc = (realizado / meta * 100) if meta > 0 else 0
    cor = "#00875A" if perc >= 100 else "#DE350B"
    col4.markdown(f'<div style="background-color:{cor}; color:white; text-align:center; border-radius:4px; font-weight:bold;">{perc:.0f}%</div>', unsafe_allow_html=True)

st.subheader("📊 Painel de Metas")
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
                st.toast("Metas salvas com sucesso no Neon!", icon="💾")
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

st.write("---")

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
# --- ABA 1: OFERTAS ---
# ==============================================================================
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão c/ IA 🧠")
    st.markdown(f"📊 Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    tipo_lista = st.radio("Canal:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    
    # Prepara filtro de cidades - Busca apenas dentro dos colchetes unificados []
    cidades_disponiveis = set()
    for cli in dict_cadastro.keys():
        m = re.search(r'\[(.*?)\]', str(cli))
        if m: cidades_disponiveis.add(m.group(1).strip().upper())
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
                        # O nome do cliente já engloba fantasia e municipio!
                        nome_cli_limpo = limpar_texto(cli_cad) 
                        if any(s in nome_cli_limpo for s in segs_oferta_limpos if len(s)>2):
                            interessados_seg.add(cli_cad)
                                        
                        cardapio_texto = limpar_texto(info_cad.get("cardapio", ""))
                        if cardapio_texto and all(c in cardapio_texto for c in chaves):
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
        
        # Filtro de Município após gerar a lista:
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
            
            # Cliente já está com string unificada: Cód - Nome (Fantasia) [Cidade]
            st.markdown(f"**🏢 {cliente_atual}**")
            st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
            st.write("")
            
            if st.session_state.cliente_ia_atual != cliente_atual:
                st.session_state.cliente_ia_atual = cliente_atual
                historico = df_total[df_total['Cliente'] == cliente_atual].groupby('Produto')['Faturamento Brut'].sum().nlargest(5).index.tolist()
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
                st.checkbox(f"📍 {c_nome} ({row['Dias']} dias sem comprar)", key=f"chk_{c_nome}")
                html_badges = obter_badges_html(c_nome)
                if row["Reportado"]: html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 JÁ REPORTADO</span>'
                st.markdown(html_badges, unsafe_allow_html=True)
                
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
                st.warning("⚠️ Por favor, marque pelo menos um Checkbox na lista acima para poder gerar o texto!")

# ==============================================================================
# --- ABA 3: CONSULTA ---
# ==============================================================================
elif st.session_state.aba_atual == "🔍 Consulta":
    st.session_state.sub_aba_consulta = st.radio(
        "Filtro de Pesquisa:", 
        ["👤 Por Cliente", "📦 Por Produto", "🏢 Exclusivos Filial 6", "🏆 Parceiros Estratégicos"], 
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
                st.write("📉 **Produtos Abandonados (Parou de comprar):**")
                
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
                st.markdown("### 💡 Venda Cruzada Inteligente (Oferta + Histórico + Cardápio)")
                
                info_c_extra = dict_cadastro.get(c_sel, {"fantasia": "", "cardapio": ""})
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
                        
                if info_c_extra["cardapio"]:
                    sugestoes_segmento.extend([i.strip() for i in info_c_extra["cardapio"].split(",") if i.strip()])
                
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
                    - Faça links inteligentes ("Vi que você tem Pizzaria, sugiro o produto X...").
                    - Formato exclusivo para WhatsApp: Pule linhas (duplas) entre os assuntos, use Emojis e *negrito* nos nomes dos produtos.
                    - NÃO INVENTE PREÇOS, deixe apenas os produtos.
                    - Mensagem direta e vendedora.
                    """
                    with st.spinner("Conectando ao Gemini..."):
                        try:
                            modelo_msg = genai.GenerativeModel('gemini-1.5-flash')
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
                
    elif st.session_state.sub_aba_consulta == "📦 Por Produto":
        st.subheader("Análise por Produto")
        input_prod = st.text_input("Nome do produto:").strip()
        if input_prod:
            filtrados_p = filtrar_por_palavras(df_total, 'Produto_Busca', input_prod)
            if not filtrados_p.empty:
                st.write(f"✅ Encontrados **{len(filtrados_p['Produto'].unique())}** produtos semelhantes.")
                st.markdown("### Top 10 Compradores deste Item")
                top_compradores = filtrados_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).reset_index()
                for idx, row in top_compradores.iterrows():
                    st.markdown(f"**{row['Cliente']}** - R$ {row['Faturamento Brut']:,.2f}")
            else:
                st.warning("Nenhum produto encontrado com este nome.")

    elif st.session_state.sub_aba_consulta == "🏢 Exclusivos Filial 6":
        st.subheader("🎯 Clientes Exclusivos da Filial 6")
        st.write("Estes clientes compraram somente na Filial 6 este mês. Excelente gancho para oferecer o mix da Filial 2!")
        
        clientes_fl6_mes = df_fl6['Cliente'].unique() if not df_fl6.empty else []
        clientes_fl2_mes = df_fl2['Cliente'].unique() if not df_fl2.empty else []
        exclusivos_fl6 = [c for c in clientes_fl6_mes if c not in clientes_fl2_mes]
        
        if not exclusivos_fl6:
            st.info("Nenhum cliente exclusivo da Filial 6 identificado no mês atual.")
        else:
            st.write(f"Identificados **{len(exclusivos_fl6)}** clientes nesta condição:")
            for c_excl in exclusivos_fl6:
                with st.expander(f"🏢 {c_excl}"):
                    df_c_excl = df_total[df_total['Cliente'] == c_excl]
                    st.markdown("**Top itens comprados na FL6:**")
                    top_compras_excl = df_c_excl.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).reset_index()
                    for _, r in top_compras_excl.iterrows():
                        st.write(f"· {r['Produto']} (R$ {r['Faturamento Brut']:,.2f})")

    elif st.session_state.sub_aba_consulta == "🏆 Parceiros Estratégicos":
        st.subheader("🎯 Oportunidades: Marcas Estratégicas")
        marcas_parceiras = {
            "Marca 1: Lebon, Doriana, Seara, Frangosul": ["lebon", "doriana", "seara", "frangosul"],
            "Marca 2: Frivatti": ["frivatti"],
            "Marca 3: Brasa": ["brasa"],
            "Marca 4: Mccain": ["mccain"],
            "Marca 5: Ceratti": ["ceratti"],
            "Marca 6: Confrescor": ["confrescor"]
        }
        
        col_m1, col_m2, col_m3 = st.columns([1.5, 1.5, 1])
        with col_m1: marca_selecionada = st.selectbox("Selecione a Marca:", list(marcas_parceiras.keys()))
        with col_m2: produto_filtro = st.text_input("Filtro Adicional (Cód. ou Produto):", placeholder="Ex: Batata Mccain...")
        with col_m3: busca_cliente_op = st.text_input("Localizar Cliente:", placeholder="Nome...")
            
        palavras_da_marca = marcas_parceiras[marca_selecionada]
        nome_amigavel_marca = marca_selecionada.split(':')[0]
        
        clientes_compraram_mes = df_mes_atual['Cliente'].unique() if not df_mes_atual.empty else []
        
        if produto_filtro.strip():
            compradores_alvo_df = filtrar_por_palavras(df_mes_atual, 'Produto_Busca', produto_filtro.strip())
            texto_aviso = f"o produto '{produto_filtro.strip()}'"
        else:
            mask_marca = df_mes_atual['Produto_Busca'].apply(lambda x: any(palavra in str(x) for palavra in palavras_da_marca))
            compradores_alvo_df = df_mes_atual[mask_marca]
            texto_aviso = f"nenhum produto da marca selecionada"

        compradores_alvo = compradores_alvo_df['Cliente'].unique().tolist()
            
        col_kpi, col_btn = st.columns([2, 1])
        with col_kpi:
            st.info(f"📈 **KPI da Marca:** Já temos **{len(compradores_alvo)}** clientes positivados com {nome_amigavel_marca if not produto_filtro.strip() else texto_aviso} neste mês!")
        
        with col_btn:
            if not compradores_alvo_df.empty:
                compradores_alvo_df['Data_Formatada'] = pd.to_datetime(compradores_alvo_df['Dt. Delivery']).dt.strftime('%d/%m/%Y')
                df_export = compradores_alvo_df[['Data_Formatada', 'Cliente', 'Produto']].copy()
                df_export.columns = ['Data da Compra', 'Nome Cliente', 'Descrição do Produto']
                import io
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export.to_excel(writer, index=False, sheet_name='Positivados')
                st.download_button(label="📥 Baixar Excel", data=buffer.getvalue(), file_name=f"positivados.xlsx")
        
        clientes_oportunidade_brutos = [c for c in clientes_compraram_mes if c not in compradores_alvo]
        clientes_oportunidade = [c for c in clientes_oportunidade_brutos if busca_cliente_op.strip().upper() in c.upper()]
        
        st.write("---")
        if not clientes_oportunidade:
            st.success(f"Excelente! Todos os clientes positivados este mês já compraram {texto_aviso}.")
        else:
            st.markdown(f"📊 Encontrados **{len(clientes_oportunidade)}** clientes positivados que não compraram {texto_aviso}:")
            for c_op in clientes_oportunidade:
                with st.expander(f"📍 {c_op}"):
                    df_c_op = df_mes_atual[df_mes_atual['Cliente'] == c_op]
                    st.markdown("**O que ele comprou neste mês (Outras Marcas):**")
                    top_compras_op = df_c_op.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).reset_index()
                    for _, r in top_compras_op.iterrows():
                        st.write(f"· {r['Produto']} (R$ {r['Faturamento Brut']:,.2f})")

# ==============================================================================
# --- ABA 4: COTAÇÃO ---
# ==============================================================================
elif st.session_state.aba_atual == "💲 Cotação":
    st.subheader("💲 Sistema Ágil de Cotação")
    st.markdown("Cole sua lista de produtos solicitados pelo cliente. O sistema vai cruzar com as ofertas ativas hoje.")
    
    texto_cotacao = st.text_area("📋 Cole a lista de produtos (um por linha):", height=200)
    
    if st.button("🔍 Cruzar com Ofertas da Memória", type="primary"):
        if texto_cotacao.strip():
            ofertas_memoria = st.session_state.get('memoria_ofertas_cruas_dia', []) + st.session_state.get('memoria_ofertas_cruas_rel', [])
            if not ofertas_memoria:
                st.warning("⚠️ Cole as ofertas do dia na aba 'Ofertas' antes de realizar cotações cruzadas.")
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
                            elif len(chaves_cot) < 2 and limpar_texto(chaves_cot[0]) in limpar_texto(of):
                                resultado_final.append(of)
                                match_encontrado = True; break
                    if not match_encontrado: resultado_final.append(linha_cot) 
                st.session_state.resultado_cotacao = "\n".join(resultado_final)
                st.success("✅ Cotação cruzada com sucesso!")
        else:
            st.warning("Cole alguma lista.")
            
    if "resultado_cotacao" in st.session_state and st.session_state.resultado_cotacao:
        st.text_area("🎯 Lista Pronta para Retorno:", value=st.session_state.resultado_cotacao, height=300)
        
        texto_js_safe_cot = json.dumps(st.session_state.resultado_cotacao)
        components.html(f"""
        <button id="copyBtnCot" style="width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;">📋 Copiar para WhatsApp</button>
        <script>
        document.getElementById('copyBtnCot').addEventListener('click', function() {{
            navigator.clipboard.writeText({texto_js_safe_cot});
            this.innerText = '✅ Copiado com sucesso!';
            setTimeout(() => {{ this.innerText = '📋 Copiar para WhatsApp'; }}, 2000);
        }});
        </script>
        """, height=55)

# ==============================================================================
# --- ABA 5: CARDÁPIOS ---
# ==============================================================================
elif st.session_state.aba_atual == "🍔 Cardápios":
    st.subheader("📝 Cadastro Inteligente de Cardápios")
    st.write("Insira os produtos do cardápio do cliente. O sistema salvará no Neon e cruzará com todas as recomendações da sua carteira.")

    clientes_lista = sorted([c for c in df_total['Cliente'].dropna().unique() if str(c).strip()])
    cliente_selecionado = st.selectbox("🔍 Selecione o Cliente (digite para buscar):", ["-- Selecione --"] + clientes_lista)

    if cliente_selecionado != "-- Selecione --":
        texto_cardapio = st.text_area("📋 Cole os produtos do cardápio (um por linha):", height=150)
        
        if 'alerta_cardapio' not in st.session_state:
            st.session_state.alerta_cardapio = False
        
        if st.button("💾 Analisar e Salvar", type="primary"):
            if texto_cardapio.strip():
                linhas = [l.strip() for l in texto_cardapio.split('\n') if l.strip()]
                novos_produtos = []
                for linha in linhas:
                    limpo = limpar_texto(linha)
                    if limpo and limpo not in novos_produtos:
                        novos_produtos.append(limpo)
                
                st.session_state.temp_novos_produtos = novos_produtos
                
                if cliente_selecionado in dict_cardapios_neon:
                    st.session_state.alerta_cardapio = True
                    st.rerun()
                else:
                    info_cli = dict_cadastro.get(cliente_selecionado, {})
                    salvar_cardapio_neon(cliente_selecionado, novos_produtos, info_cli.get("fantasia", ""))
                    st.success("✅ Cardápio salvo com sucesso no banco de dados!")
                    st.session_state.alerta_cardapio = False
                    st.rerun()
            else:
                st.warning("⚠️ O campo de produtos está vazio.")
                    
        if st.session_state.get('alerta_cardapio', False):
            st.warning(f"⚠️ O cliente **{cliente_selecionado}** já possui um cardápio cadastrado!")
            st.write("**Produtos já existentes:**", ", ".join(dict_cardapios_neon[cliente_selecionado]))
            
            col_up, col_ig = st.columns(2)
            with col_up:
                if st.button("🔄 Atualizar Cardápio (Adicionar Novos)"):
                    produtos_antigos = dict_cardapios_neon[cliente_selecionado]
                    produtos_combinados = list(set(produtos_antigos + st.session_state.temp_novos_produtos))
                    info_cli = dict_cadastro.get(cliente_selecionado, {})
                    salvar_cardapio_neon(cliente_selecionado, produtos_combinados, info_cli.get("fantasia", ""))
                    st.success("✅ Cardápio atualizado com novos itens e Fantasia sincronizada!")
                    st.session_state.alerta_cardapio = False
                    st.rerun()
            with col_ig:
                if st.button("❌ Ignorar (Cancelar)"):
                    st.session_state.alerta_cardapio = False
                    st.info("Ação cancelada.")
                    st.rerun()
