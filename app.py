import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata

# Configuração de tela para celular
st.set_page_config(page_title="Assistente de Vendas", layout="centered")

st.title("📊 Sistema de Vendas Histórico")
st.write("Conectado diretamente ao Google Drive Nuvem.")

# Função para remover acentos e deixar o texto limpo em minúsculo
def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    # Transforma caracteres especiais e acentos em letras limpas (ex: Á -> a, ç -> c)
    texto_limpo = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return texto_limpo.strip().lower()

# --- FUNÇÃO PARA BAIXAR E UNIFICAR OS ARQUIVOS ---
@st.cache_data(ttl=600)  # Atualiza os dados a cada 10 minutos
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
            
            # 📌 IDENTIFICAÇÃO INTELIGENTE DE COLUNAS (Busca por palavras-chave)
            col_data = next((c for c in df.columns if "dt" in str(c).lower() and "entrega" in str(c).lower()), None)
            col_cliente = next((c for c in df.columns if "cliente" in str(c).lower()), None)
            col_produto = next((c for c in df.columns if "produto" in str(c).lower()), None)
            col_faturamento = next((c for c in df.columns if "faturamento" in str(c).lower() and "brut" in str(c).lower()), None)
            
            # Se encontrou as 4 colunas principais, processa o arquivo
            if col_data and col_cliente and col_produto and col_faturamento:
                df_filtrado = df[[col_data, col_cliente, col_produto, col_faturamento]].copy()
                df_filtrado.columns = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                
                # Tratamento do faturamento brasileiro
                if df_filtrado['Faturamento Brut'].dtype == 'object':
                    df_filtrado['Faturamento Brut'] = df_filtrado['Faturamento Brut'].astype(str).str.replace('.', '', regex=False)
                    df_filtrado['Faturamento Brut'] = df_filtrado['Faturamento Brut'].str.replace(',', '.', regex=False)
                
                df_filtrado['Faturamento Brut'] = pd.to_numeric(df_filtrado['Faturamento Brut'], errors='coerce')
                lista_dfs.append(df_filtrado)
        except:
            continue
            
    if lista_dfs:
        df_unificado = pd.concat(lista_dfs, ignore_index=True)
        # Cria as colunas de busca sem acento e todas minúsculas de forma nativa
        df_unificado['Produto_Busca'] = df_unificado['Produto'].apply(limpar_texto)
        df_unificado['Cliente_Busca'] = df_unificado['Cliente'].apply(limpar_texto)
        return df_unificado
        
    return pd.DataFrame()

# Executa a carga dos dados da nuvem
with st.spinner("Atualizando banco de dados do Google Drive..."):
    df_total = carregar_dados_nuvem()

if df_total.empty:
    st.warning("⚠️ Nenhuma planilha processada ainda. Se o app acabou de atualizar, aguarde 10 segundos e dê F5.")
    st.stop()

# --- INTERFACE VISUAL (ABAS RESPONSIVAS PARA CELULAR) ---
aba1, aba2 = st.tabs(["🔍 Por Produto", "👤 Por Cliente"])

# --- ABA 1: BUSCA POR PRODUTO ---
with aba1:
    st.header("Buscar por Produto")
    palavra_chave = st.text_input("Digite a palavra-chave (ex: alcatra, cox, pesc):", key="prod_input").strip()
    
    # Botão azul e largo ideal para o toque do celular
    botao_buscar_prod = st.button("🔍 Pesquisar Produto", use_container_width=True)

    if botao_buscar_prod and palavra_chave:
        termo_busca = limpar_texto(palavra_chave)
        filtro_prod = df_total[df_total['Produto_Busca'].str.contains(termo_busca, na=False)]
        
        if not filtro_prod.empty:
            ranking_clientes = filtro_prod.groupby('Cliente')['Faturamento Brut'].sum().reset_index()
            ranking_clientes = ranking_clientes.sort_values(by='Faturamento Brut', ascending=False)
            
            st.subheader("🏆 Ranking de Maiores Compradores")
            for idx, row in ranking_clientes.iterrows():
                fat_total = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.markdown(f"👤 **{row['Cliente']}** \n💰 Total: **{fat_total}**")
            
            st.write("---")
            st.subheader("📋 Histórico Detalhado")
            detalhe_vendas = filtro_prod.sort_values(by='Dt. Delivery', ascending=False)
            
            dados_exibicao = detalhe_vendas.copy()
            dados_exibicao['Faturamento Brut'] = dados_exibicao['Faturamento Brut'].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.dataframe(dados_exibicao[['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']], use_container_width=True)
        else:
            st.warning("Nenhum produto correspondente encontrado.")

# --- ABA 2: BUSCA POR CLIENTE ---
with aba2:
    st.header("Histórico do Cliente")
    busca_cliente = st.text_input("Digite o código ou nome do cliente:", key="cli_input").strip()
    
    # Botão azul e largo ideal para o toque do celular
    botao_buscar_cli = st.button("👤 Pesquisar Cliente", use_container_width=True)

    if botao_buscar_cli and busca_cliente:
        termo_busca = limpar_texto(busca_cliente)
        filtro_cliente = df_total[df_total['Cliente_Busca'].str.contains(termo_busca, na=False)]
        
        if not filtro_cliente.empty:
            ranking_produtos = filtro_cliente.groupby('Produto')['Faturamento Brut'].sum().reset_index()
            ranking_produtos = ranking_produtos.sort_values(by='Faturamento Brut', ascending=False)
            
            st.subheader("🥩 Produtos mais comprados por este cliente:")
            for idx, row in ranking_produtos.iterrows():
                fat_prod = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.write(f"• **{row['Produto']}** - Total: {fat_prod}")
        else:
            st.warning("Cliente não encontrado.")
