import streamlit as st
import pandas as pd
import gdown
import os
import glob

# Configuração de tela para celular
st.set_page_config(page_title="Assistente de Vendas", layout="centered")

st.title("📊 Sistema de Vendas Histórico")
st.write("Conectado diretamente ao Google Drive Nuvem.")

# ID da sua pasta do Google Drive
FOLDER_ID = "1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF"
PASTA_DESTINO = "planilhas_drive"

# --- FUNÇÃO PARA BAIXAR E UNIFICAR OS ARQUIVOS ---
@st.cache_data(ttl=3600)  # Atualiza os dados a cada 1 hora
def carregar_dados_nuvem():
    if not os.path.exists(PASTA_DESTINO):
        os.makedirs(PASTA_DESTINO)
    
    try:
        # Baixa todos os arquivos da pasta pública do Drive
        url_pasta = f"https://drive.google.com/drive/folders/{FOLDER_ID}"
        gdown.download_folder(url_pasta, output=PASTA_DESTINO, quiet=True)
    except Exception as e:
        st.error(f"Erro ao conectar com o Google Drive: {e}")
    
    # 📌 AJUSTE AQUI: Procura os arquivos dentro de qualquer subpasta criada pelo Drive
    arquivos_excel = glob.glob(os.path.join(PASTA_DESTINO, "**", "*.xlsx"), recursive=True)
    
    if not arquivos_excel:
        return pd.DataFrame()
    
    lista_dfs = []
    
    for arquivo in arquivos_excel:
        try:
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            
            colunas_necessarias = ['Dt. Entrega NF', 'Cliente', 'Produto', 'Faturamento Brut']
            df = df[colunas_necessarias]
            
            # Tratamento do faturamento brasileiro
            if df['Faturamento Brut'].dtype == 'object':
                df['Faturamento Brut'] = df['Faturamento Brut'].astype(str).str.replace('.', '', regex=False)
                df['Faturamento Brut'] = df['Faturamento Brut'].str.replace(',', '.', regex=False)
            
            df['Faturamento Brut'] = pd.to_numeric(df['Faturamento Brut'], errors='coerce')
            lista_dfs.append(df)
        except:
            continue
            
    if lista_dfs:
        return pd.concat(lista_dfs, ignore_index=True)
    return pd.DataFrame()

# Executa a carga dos dados da nuvem
with st.spinner("Atualizando banco de dados do Google Drive..."):
    df_total = carregar_dados_nuvem()

# Se a lista ainda estiver vazia no primeiro segundo, evita travar a tela abaixo
if df_total is None or df_total.empty:
    st.warning("⚠️ Aguardando a leitura das planilhas do Drive. Se as abas não aparecerem em 10 segundos, atualize a página.")
    df_total = pd.DataFrame(columns=['Dt. Entrega NF', 'Cliente', 'Produto', 'Faturamento Brut'])

# --- RECURSO VISUAL PARA CELULAR (ABAS RESPONSIVAS) ---
aba1, aba2 = st.tabs(["🔍 Por Produto", "👤 Por Cliente"])

# --- ABA 1: BUSCA POR PRODUTO ---
with aba1:
    st.header("Buscar por Produto")
    palavra_chave = st.text_input("Digite a palavra-chave (ex: alcatra, cox, frango):", key="prod_input").strip().lower()

    if palavra_chave and not df_total.empty:
        filtro_prod = df_total[df_total['Produto'].astype(str).str.lower().str.contains(palavra_chave, na=False)]
        
        if not filtro_prod.empty:
            ranking_clientes = filtro_prod.groupby('Cliente')['Faturamento Brut'].sum().reset_index()
            ranking_clientes = ranking_clientes.sort_values(by='Faturamento Brut', ascending=False)
            
            st.subheader("🏆 Ranking de Maiores Compradores")
            for idx, row in ranking_clientes.iterrows():
                fat_total = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.markdown(f"👤 **{row['Cliente']}** \n💰 Total: **{fat_total}**")
            
            st.write("---")
            st.subheader("📋 Histórico Detalhado")
            detalhe_vendas = filtro_prod.sort_values(by='Dt. Entrega NF', ascending=False)
            
            # Formata para exibição
            dados_exibicao = detalhe_vendas.copy()
            dados_exibicao['Faturamento Brut'] = dados_exibicao['Faturamento Brut'].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.dataframe(dados_exibicao[['Dt. Entrega NF', 'Cliente', 'Produto', 'Faturamento Brut']], use_container_width=True)
        else:
            st.warning("Nenhum produto correspondente encontrado.")

# --- ABA 2: BUSCA POR CLIENTE ---
with aba2:
    st.header("Histórico do Cliente")
    busca_cliente = st.text_input("Digite o código ou nome do cliente:", key="cli_input").strip().lower()

    if busca_cliente and not df_total.empty:
        filtro_cliente = df_total[df_total['Cliente'].astype(str).str.lower().str.contains(busca_cliente, na=False)]
        
        if not filtro_cliente.empty:
            ranking_produtos = filtro_cliente.groupby('Produto')['Faturamento Brut'].sum().reset_index()
            ranking_produtos = ranking_produtos.sort_values(by='Faturamento Brut', ascending=False)
            
            st.subheader("🥩 Produtos mais comprados por este cliente:")
            for idx, row in ranking_produtos.iterrows():
                fat_prod = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.write(f"• **{row['Produto']}** - Total: {fat_prod}")
        else:
            st.warning("Cliente não encontrado.")
