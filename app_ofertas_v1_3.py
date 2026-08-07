import os
import re
import unicodedata
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
import google.generativeai as genai
import gdown

# ---------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA E CHAVES VIA ST.SECRETS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Central de Automações & Vendas",
    page_icon="🚀",
    layout="wide"
)

# Recuperação de Secrets
NEON_DB_URL = st.secrets.get("NEON_DB_URL", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
DRIVE_FILE_ID = st.secrets.get("DRIVE_FILE_ID", "")

# Configuração do Gemini 1.5 Flash
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    gemini_model = None

# Configuração de Conexão com Banco Neon DB (PostgreSQL) com Pooling Resiliente
@st.cache_resource
def get_db_engine():
    if not NEON_DB_URL:
        st.error("URL do Neon DB não configurada em st.secrets.")
        return None
    return create_engine(
        NEON_DB_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_pre_ping=True
    )

engine = get_db_engine()

# ---------------------------------------------------------
# 2. FUNÇÕES AUXILIARES E NORMALIZAÇÃO DE DADOS
# ---------------------------------------------------------
def normalize_text(text_val: str) -> str:
    """Remove acentos, caracteres especiais e converte para maiúsculas."""
    if not text_val or pd.isna(text_val):
        return ""
    text_val = str(text_val)
    nfkd_form = unicodedata.normalize('NFKD', text_val)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('utf-8')
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', only_ascii)
    return cleaned.strip().upper()

def format_whatsapp_number(phone_raw: str) -> str:
    """Extrai apenas os dígitos para o link do WhatsApp."""
    if not phone_raw or pd.isna(phone_raw):
        return ""
    digits = re.sub(r'\D', '', str(phone_raw))
    if len(digits) in [10, 11] and not digits.startswith("55"):
        digits = "55" + digits
    return digits

@st.cache_data(ttl=3600)
def load_drive_data(file_id: str):
    """Carrega dados do Google Drive via gdown e normaliza colunas/textos."""
    if not file_id:
        return pd.DataFrame()
    url = f'https://drive.google.com/uc?id={file_id}'
    output = 'dados_vendas.xlsx'
    try:
        gdown.download(url, output, quiet=True)
        df = pd.read_excel(output)
        
        cols_map = {c: c.strip().lower() for c in df.columns}
        df.rename(columns=cols_map, inplace=True)
        
        if 'cliente' in df.columns:
            df['cliente_norm'] = df['cliente'].apply(normalize_text)
        if 'produto' in df.columns:
            df['produto_norm'] = df['produto'].apply(normalize_text)
        if 'municipio' in df.columns:
            df['municipio_norm'] = df['municipio'].apply(normalize_text)
        if 'marca' in df.columns:
            df['marca_norm'] = df['marca'].apply(normalize_text)
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados do Google Drive: {e}")
        return pd.DataFrame()

def init_db_tables():
    """Inicializa tabelas no Neon DB usando conexões seguras via engine.begin()."""
    if not engine:
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS produtos_segmentos (
                    id SERIAL PRIMARY KEY,
                    produto VARCHAR(255) NOT NULL,
                    segmento VARCHAR(100) NOT NULL,
                    marca VARCHAR(100),
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cardapios_clientes (
                    id SERIAL PRIMARY KEY,
                    cliente_id VARCHAR(100) NOT NULL,
                    cliente_nome VARCHAR(255) NOT NULL,
                    itens_cardapio TEXT,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS metas_mensais (
                    id SERIAL PRIMARY KEY,
                    mes_ano VARCHAR(7) NOT NULL,
                    meta_valor NUMERIC(12,2) NOT NULL,
                    realizado_valor NUMERIC(12,2) DEFAULT 0
                );
            """))
    except Exception as e:
        st.error(f"Erro ao inicializar tabelas no Neon DB: {e}")

init_db_tables()

# ---------------------------------------------------------
# 3. BARRA LATERAL (PAINEL DE CONTROLE)
# ---------------------------------------------------------
st.sidebar.title("🛠️ Painel de Controle")

drive_id_input = st.sidebar.text_input("ID do Arquivo Google Drive", value=DRIVE_FILE_ID)
if st.sidebar.button("🔄 Recarregar Planilha"):
    st.cache_data.clear()
    st.rerun()

df_vendas = load_drive_data(drive_id_input)

if not df_vendas.empty:
    st.sidebar.success(f"Base carregada: {len(df_vendas)} registros")
else:
    st.sidebar.warning("Nenhuma base carregada ou ID do Drive pendente.")

# ---------------------------------------------------------
# 4. APLICAÇÃO PRINCIPAL (MÓDULOS SISTÊMICOS)
# ---------------------------------------------------------
st.title("🚀 Central de Automações & Vendas")

tab_ofertas, tab_alertas, tab_consulta, tab_cotacao, tab_cardapios = st.tabs([
    "🟢 Ofertas Smart",
    "🚨 Alertas & Inativos",
    "🔍 Consulta & Cross-Sell",
    "💲 Cotação Dinâmica",
    "🍔 Gestão de Cardápios"
])

# =========================================================
# MÓDULO 1: OFERTAS (WHATSAPP + GEMINI 1.5 FLASH)
# =========================================================
with tab_ofertas:
    st.header("🟢 Fila Inteligente de Disparos de Ofertas")
    
    col_off1, col_off2 = st.columns([1, 2])
    
    with col_off1:
        st.subheader("Configuração da Oferta")
        segmento_sel = st.selectbox("Segmento Alvo", ["Todos", "Food Service", "Pizzaria", "Hamburgueria", "Restaurante", "Varejo"])
        produto_oferta = st.text_input("Produto em Promoção", "Mussarela Fatiada 1kg")
        preco_oferta = st.number_input("Preço Promocional (R$)", value=34.90, step=0.50)
        validade_oferta = st.date_input("Validade da Oferta", datetime.now() + timedelta(days=3))
        tom_mensagem = st.selectbox("Tom da Mensagem", ["Persuasivo & Direto", "Urgência / Estoque Limitado", "Parceria Exclusiva"])
        
    with col_off2:
        st.subheader("Geração de Copy Inteligente (Gemini 1.5 Flash)")
        
        nome_cliente_demo = st.text_input("Nome do Cliente", "Restaurante Sabor Real")
        contato_demo = st.text_input("WhatsApp do Cliente (com DDD)", "11999999999")
        
        if st.button("✨ Gerar Copy com IA"):
            if not gemini_model:
                st.error("Chave da API Gemini não configurada em st.secrets.")
            else:
                prompt = f"""
                Você é um especialista em vendas B2B alimentícias.
                Crie uma mensagem curta, altamente persuasiva e adaptada para envio direto via WhatsApp.
                
                Dados da oferta:
                - Cliente: {nome_cliente_demo}
                - Segmento: {segmento_sel}
                - Produto em Oferta: {produto_oferta}
                - Preço Promocional: R$ {preco_oferta:.2f}
                - Validade da Oferta: {validade_oferta.strftime('%d/%m/%Y')}
                - Tom de Comunicação: {tom_mensagem}
                
                Instruções:
                - Use emojis estratégicos sem exageros.
                - Texto limpo e direto ao ponto para leitura rápida no celular.
                - Inclua uma chamada para ação (CTA) clara para o cliente responder solicitando o pedido.
                """
                with st.spinner("Gerando mensagem personalizada com Gemini 1.5 Flash..."):
                    res = gemini_model.generate_content(prompt)
                    st.session_state['generated_copy'] = res.text

        msg_gerada = st.session_state.get('generated_copy', '')
        copy_text = st.text_area("Mensagem Final (pronta para envio)", value=msg_gerada, height=180)
        
        if copy_text and contato_demo:
            phone_clean = format_whatsapp_number(contato_demo)
            encoded_msg = urllib.parse.quote(copy_text)
            whatsapp_url = f"https://api.whatsapp.com/send?phone={phone_clean}&text={encoded_msg}"
            st.markdown(f'👉 [**Abrir Conversa e Enviar no WhatsApp**]({whatsapp_url})', unsafe_allow_html=True)

# =========================================================
# MÓDULO 2: ALERTAS & CLIENTES INATIVOS
# =========================================================
with tab_alertas:
    st.header("🚨 Gestão de Clientes Sumidos e Não Positivados")
    
    col_al1, col_al2 = st.columns(2)
    with col_al1:
        dias_inativo = st.slider("Dias Sem Comprar (Inatividade)", min_value=15, max_value=120, value=30, step=5)
    with col_al2:
        municipio_filtro = st.text_input("Filtrar Município (Opcional)", "").strip()
        
    if not df_vendas.empty and 'data' in df_vendas.columns and 'cliente' in df_vendas.columns:
        df_vendas['data'] = pd.to_datetime(df_vendas['data'], errors='coerce')
        max_date = df_vendas['data'].max()
        
        group_cols = ['cliente']
        if 'municipio' in df_vendas.columns:
            group_cols.append('municipio')
            
        df_ult_compra = df_vendas.groupby(group_cols)['data'].max().reset_index()
        df_ult_compra['dias_sem_comprar'] = (max_date - df_ult_compra['data']).dt.days
        
        df_inativos = df_ult_compra[df_ult_compra['dias_sem_comprar'] >= dias_inativo]
        
        if municipio_filtro and 'municipio' in df_inativos.columns:
            m_norm = normalize_text(municipio_filtro)
            df_inativos = df_inativos[df_inativos['municipio'].apply(normalize_text).str.contains(m_norm, na=False)]
            
        st.subheader(f"Clientes Sem Compras há {dias_inativo}+ dias ({len(df_inativos)} encontrados)")
        st.dataframe(df_inativos.sort_values(by='dias_sem_comprar', ascending=False), use_container_width=True)
        
        csv_data = df_inativos.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Relatório em CSV",
            data=csv_data,
            file_name=f"relatorio_inativos_{dias_inativo}_dias.csv",
            mime="text/csv"
        )
    else:
        st.info("Carregue uma planilha com as colunas 'cliente' e 'data' para visualizar os alertas de inatividade.")

# =========================================================
# MÓDULO 3: CONSULTA & CROSS-SELL
# =========================================================
with tab_consulta:
    st.header("🔍 Consulta Detalhada e Vendas Cruzadas")
    
    marcas_parceiras = ["LEBON", "MCCAIN", "CERATTI", "SADIA", "PERDIGAO", "SEARA"]
    
    col_c1, col_c2 = st.columns([1, 1])
    with col_c1:
        marca_filtro = st.multiselect("Filtrar Marcas Parceiras", marcas_parceiras, default=["MCCAIN", "CERATTI"])
    with col_c2:
        busca_cliente = st.text_input("Buscar Cliente por Nome")
        
    if not df_vendas.empty:
        df_filtered = df_vendas.copy()
        
        if busca_cliente and 'cliente_norm' in df_filtered.columns:
            cliente_n = normalize_text(busca_cliente)
            df_filtered = df_filtered[df_filtered['cliente_norm'].str.contains(cliente_n, na=False)]
            
        if marca_filtro and 'marca_norm' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['marca_norm'].isin(marca_filtro)]
            
        st.subheader("Histórico de Compras Filtrado")
        st.dataframe(df_filtered, use_container_width=True)
        
        st.subheader("💡 Oportunidades de Cross-Selling (Produtos Não Comprados)")
        if busca_cliente and not df_filtered.empty and 'produto_norm' in df_vendas.columns:
            prods_comprados = set(df_filtered['produto_norm'].unique())
            todos_produtos = set(df_vendas['produto_norm'].unique())
            prods_oportunidade = list(todos_produtos - prods_comprados)[:10]
            
            st.write(f"Produtos do portfólio que **{busca_cliente}** ainda não comprou nos últimos 30 dias:")
            st.write(prods_oportunidade)

# =========================================================
# MÓDULO 4: COTAÇÃO DINÂMICA
# =========================================================
with tab_cotacao:
    st.header("💲 Cotação Dinâmica com Listas de Preços")
    
    st.write("Insira uma lista bruta enviada pelo cliente para cruzamento automático com os preços ativos da base.")
    
    raw_list = st.text_area("Lista de itens (Ex: 5kg Mussarela, 2cx Batata McCain, 1cx Presunto)", height=150)
    
    if st.button("⚡ Processar Cotação"):
        if raw_list and not df_vendas.empty and 'preco' in df_vendas.columns and 'produto_norm' in df_vendas.columns:
            linhas = [l.strip() for l in raw_list.split("\n") if l.strip()]
            resultados = []
            
            for linha in linhas:
                linha_norm = normalize_text(linha)
                palavras_chave = [w for w in linha_norm.split() if len(w) > 2]
                
                if palavras_chave:
                    matches = df_vendas[df_vendas['produto_norm'].apply(lambda x: all(word in x for word in palavras_chave))]
                    if matches.empty:
                        matches = df_vendas[df_vendas['produto_norm'].apply(lambda x: any(word in x for word in palavras_chave))]
                        
                    if not matches.empty:
                        menor_preco = matches['preco'].min()
                        prod_nome = matches.iloc[0]['produto'] if 'produto' in matches.columns else matches.iloc[0]['produto_norm']
                        resultados.append({"Item Solicitado": linha, "Produto Match": prod_nome, "Menor Preço": f"R$ {menor_preco:.2f}"})
                    else:
                        resultados.append({"Item Solicitado": linha, "Produto Match": "Não Encontrado", "Menor Preço": "N/A"})
                else:
                    resultados.append({"Item Solicitado": linha, "Produto Match": "Não Encontrado", "Menor Preço": "N/A"})
                    
            st.table(pd.DataFrame(resultados))
        else:
            st.warning("Informe uma lista válida para cotação e garanta que a base contenha as colunas 'produto' e 'preco'.")

# =========================================================
# MÓDULO 5: GESTÃO DE CARDÁPIOS (NEON DB)
# =========================================================
with tab_cardapios:
    st.header("🍔 Mapeamento e Persistência de Cardápios no Neon DB")
    
    col_cd1, col_cd2 = st.columns([1, 1])
    
    with col_cd1:
        st.subheader("Cadastrar / Atualizar Cardápio")
        with st.form("form_cardapio"):
            cli_id = st.text_input("Código/ID do Cliente")
            cli_nome = st.text_input("Nome Razão / Fantasia")
            itens_txt = st.text_area("Itens do Cardápio (Ex: Pizza Calabresa, Hambúrguer Smash, Porção Batata)")
            submitted = st.form_submit_button("💾 Salvar no Neon DB")
            
            if submitted:
                if cli_id and cli_nome and engine:
                    try:
                        with engine.begin() as conn:
                            conn.execute(
                                text("""
                                    INSERT INTO cardapios_clientes (cliente_id, cliente_nome, itens_cardapio, atualizado_em)
                                    VALUES (:cid, :cnome, :itens, CURRENT_TIMESTAMP)
                                """),
                                {"cid": cli_id, "cnome": cli_nome, "itens": itens_txt}
                            )
                        st.success(f"Cardápio de '{cli_nome}' salvo no PostgreSQL com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco: {e}")
                else:
                    st.error("Preencha todos os campos e certifique-se de que a conexão com o Neon DB está ativa.")

    with col_cd2:
        st.subheader("Cardápios Cadastrados")
        if engine:
            try:
                df_cardapios = pd.read_sql("SELECT cliente_id, cliente_nome, itens_cardapio, atualizado_em FROM cardapios_clientes ORDER BY atualizado_em DESC", con=engine)
                st.dataframe(df_cardapios, use_container_width=True)
            except Exception as e:
                st.info("Nenhum cardápio cadastrado no banco até o momento.")
