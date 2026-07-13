import streamlit as st
import pandas as pd
from datetime import date
import os
import gdown
import glob
import unicodedata
import io
import google.generativeai as genai

# --- FUNÇÕES AUXILIARES ---
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

# --- CONFIGURAÇÃO GEMINI ---
try:
    if "google_gemini" in st.secrets and "api_key" in st.secrets["google_gemini"]:
        genai.configure(api_key=st.secrets["google_gemini"]["api_key"])
except Exception as e:
    st.error(f"Erro ao configurar Gemini: Verifique o secrets.toml. Detalhe: {e}")

# --- CARREGAMENTO DE DADOS (CACHE DIÁRIO) ---
@st.cache_data(ttl=86400) 
def carregar_dados_nuvem(data_atual):
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
            
            if c_dt and c_cli and c_prod and c_fat:
                sel = [c_dt, c_cli, c_prod, c_fat]
                heads = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
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
        return unificado
    return pd.DataFrame()

# --- EXECUÇÃO BASE ---
with st.spinner("Sincronizando base de dados..."):
    df_total = carregar_dados_nuvem(date.today())

if df_total.empty:
    st.warning("Base de dados vazia. Verifique a pasta do Drive.")
    st.stop()

mes_atual_referencia = date.today().strftime('%Y-%m')
df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

# --- SISTEMA DE OFERTAS (INTERFACE) ---
st.title("🎯 Geração de Ofertas e Positivação")

st.sidebar.header("Filtros da Marca")
marca_selecionada = st.sidebar.selectbox("Escolha a Marca Parceira", ["McCain", "Lebon", "Confrescor", "Seara", "Doriana"])
produto_filtro = st.sidebar.text_input("Filtrar por Produto Específico (opcional):")
nome_amigavel_marca = marca_selecionada

palavras_da_marca = [nome_amigavel_marca.lower()] 
compradores_alvo_df = pd.DataFrame()

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
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Positivados', startrow=3)
            worksheet = writer.sheets['Positivados']
            worksheet['A1'] = f"Marca Parceira: {nome_amigavel_marca}"
            worksheet['A2'] = f"Quantidade de Clientes Positivados: {len(compradores_alvo)}"
        
        st.download_button(
            label="📥 Baixar Excel (Relatório)",
            data=buffer.getvalue(),
            file_name=f"positivados_{nome_amigavel_marca}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

st.divider()

st.subheader("🤖 Gerador de Pitch de Vendas")
texto_oferta = st.text_area("Cole os produtos e preços que você quer ofertar hoje:")

if st.button("Gerar Script de Vendas"):
    if texto_oferta:
        with st.spinner("O Gemini está criando o seu script..."):
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(f"Crie um script de vendas persuasivo, direto e simpático para o WhatsApp baseado nestas ofertas. Não invente valores que não estão no texto: {texto_oferta}")
                st.write(response.text)
            except Exception as e:
                st.error(f"Erro ao gerar script com a Inteligência Artificial: {e}")
    else:
        st.warning("Por favor, cole as ofertas na caixa de texto primeiro.")
