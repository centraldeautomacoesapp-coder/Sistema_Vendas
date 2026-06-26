import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata

# Configuração de tela para celular
st.set_page_config(page_title="Delly's - Painel de Vendas", layout="centered")

# 📸 DETECTOR DE LOGOTIPO BLINDADO
# Ele vai procurar o arquivo independentemente de estar em PNG, JPG ou JPEG
logo_arquivo = None
for nome in os.listdir("."):
    if nome.lower() in ["logo.jpg", "logo.jpeg", "logo.png"]:
        logo_arquivo = nome
        break

if logo_arquivo:
    st.image(logo_arquivo, use_container_width=True)
else:
    st.title("📊 Delly's - Sistema de Vendas Histórico")
    st.info("💡 Para ativar o cabeçalho personalizado, suba a imagem no GitHub com o nome 'logo.jpg'")

# Função para remover acentos e padronizar textos
def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    texto_limpo = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return texto_limpo.strip().lower()

@st.cache_data(ttl=600)
def carregar_dados_nuvem():
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    pasta_destino = os.path.join(diretorio_atual, "planilhas_drive")
    
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    
    try:
        folder_id = "1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF"
        url_pasta = f"https://drive.google.com/drive/folders/{folder_id}"
        gdown.download_folder(url_pasta, output=pasta_destino, quiet=True)
    except Exception as e:
        st.error(f"Erro ao conectar com o Google Drive: {e}")
    
    arquivos_excel = glob.glob(os.path.join(pasta_destino, "**", "*.xlsx"), recursive=True)
    lista_dfs = []
    
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            
            col_data = next((c for c in df.columns if "dt" in str(c).lower() and "entrega" in str(c).lower()), None)
            col_cliente = next((c for c in df.columns if "cliente" in str(c).lower()), None)
            col_produto = next((c for c in df.columns if "produto" in str(c).lower()), None)
            col_faturamento = next((c for c in df.columns if "faturamento" in str(c).lower() and "brut" in str(c).lower()), None)
            
            if col_data and col_cliente and col_produto and col_faturamento:
                df_filtrado = df[[col_data, col_cliente, col_produto, col_faturamento]].copy()
                df_filtrado.columns = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                
                if df_filtrado['Faturamento Brut'].dtype == 'object':
                    df_filtrado['Faturamento Brut'] = df_filtrado['Faturamento Brut'].astype(str).str.replace('.', '', regex=False)
                    df_filtrado['Faturamento Brut'] = df_filtrado['Faturamento Brut'].str.replace(',', '.', regex=False)
                
                df_filtrado['Faturamento Brut'] = pd.to_numeric(df_filtrado['Faturamento Brut'], errors='coerce')
                lista_dfs.append(df_filtrado)
        except:
            continue
            
    if lista_dfs:
        df_unificado = pd.concat(lista_dfs, ignore_index=True)
        df_unificado['Data_Datetime'] = pd.to_datetime(df_unificado['Dt. Delivery'], errors='coerce')
        df_unificado['Ano_Mes'] = df_unificado['Data_Datetime'].dt.strftime('%Y-%m')
        
        df_unificado['Produto_Busca'] = df_unificado['Produto'].apply(limpar_texto)
        df_unificado['Cliente_Busca'] = df_unificado['Cliente'].apply(limpar_texto)
        return df_unificado
        
    return pd.DataFrame()

with st.spinner("Atualizando banco de dados Delly's..."):
    df_total = carregar_dados_nuvem()

if df_total.empty:
    st.warning("⚠️ Nenhuma planilha processada. Aguarde 10 segundos e atualize a página.")
    st.stop()

# --- METRICAS GLOBAIS (DESIGN REFRESH) ---
st.write("---")
col1, col2 = st.columns(2)

with col1:
    faturamento_geral = df_total['Faturamento Brut'].sum()
    fat_formatado = f"R$ {faturamento_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.metric(label="💰 Faturamento Histórico Total", value=fat_formatado)

with col2:
    top_produto_nome = df_total.groupby('Produto')['Faturamento Brut'].sum().idxmax()
    st.metric(label="🥩 Produto Campeão de Vendas", value=str(top_produto_nome)[:18] + "...")

st.write("---")

# --- INTERFACE VISUAL EM ABAS ---
aba1, aba2 = st.tabs(["🔍 Por Produto", "👤 Por Cliente"])

# --- ABA 1: BUSCA POR PRODUTO ---
with aba1:
    st.subheader("Análise de Produto")
    palavra_chave = st.text_input("Qual produto deseja analisar?", key="prod_input").strip()
    botao_buscar_prod = st.button("📊 Gerar Relatório de Produto", use_container_width=True)

    if botao_buscar_prod and palavra_chave:
        termo_busca = limpar_texto(palavra_chave)
        filtro_prod = df_total[df_total['Produto_Busca'].str.contains(termo_busca, na=False)]
        
        if not filtro_prod.empty:
            st.markdown("### 📈 Evolução das Vendas deste Produto (Mês a Mês)")
            faturamento_mensal = filtro_prod.groupby('Ano_Mes')['Faturamento Brut'].sum().sort_index()
            st.line_chart(faturamento_mensal, color="#00875A") # Verde Delly's
            
            ranking_clientes = filtro_prod.groupby('Cliente')['Faturamento Brut'].sum().reset_index()
            ranking_clientes = ranking_clientes.sort_values(by='Faturamento Brut', ascending=False)
            
            st.markdown("### 🏆 Maiores Compradores deste Item")
            for idx, row in ranking_clientes.head(10).iterrows():
                fat_total = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.markdown(f"👤 **{row['Cliente']}** \n💰 Total Comprado: **{fat_total}**")
                proporcao = float(row['Faturamento Brut'] / ranking_clientes['Faturamento Brut'].max())
                st.progress(proporcao)
        else:
            st.warning("Nenhum produto encontrado.")

# --- ABA 2: BUSCA POR CLIENTE ---
with aba2:
    st.subheader("Análise de Cliente")
    busca_cliente = st.text_input("Qual código ou nome do cliente?", key="cli_input").strip()
    botao_buscar_cli = st.button("📋 Gerar Raio-X do Cliente", use_container_width=True)

    if botao_buscar_cli and busca_cliente:
        termo_busca = limpar_texto(busca_cliente)
        filtro_cliente = df_total[df_total['Cliente_Busca'].str.contains(termo_busca, na=False)]
        
        if not filtro_cliente.empty:
            st.markdown("### 📊 Histórico de Compras do Cliente (Mês a Mês)")
            compras_mensais = filtro_cliente.groupby('Ano_Mes')['Faturamento Brut'].sum().sort_index()
            st.bar_chart(compras_mensais, color="#0B4F93") # Azul Delly's
            
            ranking_produtos = filtro_cliente.groupby('Produto')['Faturamento Brut'].sum().reset_index()
            ranking_produtos = ranking_produtos.sort_values(by='Faturamento Brut', ascending=False)
            
            st.markdown("### 🥩 Mix de Produtos Mais Comprados por Ele")
            for idx, row in ranking_produtos.head(10).iterrows():
                fat_prod = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.write(f"• **{row['Produto']}** - Total: {fat_prod}")
        else:
            st.warning("Cliente não encontrado.")
