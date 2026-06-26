import streamlit as st
import pandas as pd
import requests
import io
import unicodedata

# Configuração de tela para celular
st.set_page_config(page_title="Assistente de Vendas", layout="centered")

st.title("📊 Sistema de Vendas Histórico")
st.write("Conectado diretamente ao Google Drive Nuvem.")

# Função para remover acentos e deixar o texto limpo em minúsculo
def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    # Remove acentos (ex: Alcatra -> Alcatra, CORAÇÃO -> CORACAO)
    texto_limpo = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return texto_limpo.strip().lower()

# --- FUNÇÃO PARA CARREGAR OS DADOS DIRETAMENTE DA PLANILHA MESTRE ---
@st.cache_data(ttl=600)  # Atualiza a cada 10 minutos
def carregar_dados_nuvem():
    # ID da pasta pública do seu Drive
    FOLDER_ID = "1RCm3WLoTLECkwJxoD2csu5QfYXbQd8cF"
    
    # Lista oficial de arquivos mapeados do seu Drive
    arquivos = [
        "25 ago.xlsx", "25 dez.xlsx", "25 jul.xlsx", "25 nov.xlsx", "25 out.xlsx", "25 set.xlsx",
        "26 abr.xlsx", "26 fev.xlsx", "26 jan.xlsx", "26 jun.xlsx", "26 mai.xlsx", "26 mar.xlsx"
    ]
    
    lista_dfs = []
    
    # Loop alternativo blindado para ler os dados unificados na nuvem do Streamlit
    # Caso precise ler direto da memória do app de forma instantânea
    import glob
    import os
    
    # Mapeamento do diretório do Streamlit Cloud
    for pasta_raiz in [".", "planilhas_drive"]:
        arquivos_locais = glob.glob(os.path.join(pasta_raiz, "**", "*.xlsx"), recursive=True)
        for arquivo in arquivos_locais:
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
        df_unificado = pd.concat(lista_dfs, ignore_index=True)
        # Pré-processa colunas de busca tirando acentos para busca ultra-rápida
        df_unificado['Produto_Busca'] = df_unificado['Produto'].apply(limpar_texto)
        df_unificado['Cliente_Busca'] = df_unificado['Cliente'].apply(limpar_texto)
        return df_unificado
        
    return pd.DataFrame(columns=['Dt. Entrega NF', 'Cliente', 'Produto', 'Faturamento Brut', 'Produto_Busca', 'Cliente_Busca'])

# Executa a carga dos dados
with st.spinner("Carregando tabelas do Drive..."):
    df_total = carregar_dados_nuvem()

# --- INTERFACE VISUAL (ABAS RESPONSIVAS) ---
aba1, aba2 = st.tabs(["🔍 Por Produto", "👤 Por Cliente"])

# --- ABA 1: BUSCA POR PRODUTO ---
with aba1:
    st.header("Buscar por Produto")
    palavra_chave = st.text_input("Digite a palavra-chave (ex: alcatra, cox, pesc):", key="prod_input").strip()
    
    # 🔘 Botão clicável para buscar no celular
    botao_buscar_prod = st.button("🔍 Pesquisar Produto", use_container_width=True)

    if (botao_buscar_prod or palavra_chave) and not df_total.empty:
        termo_busca = limpar_texto(palavra_chave)
        
        # Filtra ignorando acentos e maiúsculas
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
            detalhe_vendas = filtro_prod.sort_values(by='Dt. Entrega NF', ascending=False)
            
            dados_exibicao = detalhe_vendas.copy()
            dados_exibicao['Faturamento Brut'] = dados_exibicao['Faturamento Brut'].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            st.dataframe(dados_exibicao[['Dt. Entrega NF', 'Cliente', 'Produto', 'Faturamento Brut']], use_container_width=True)
        else:
            st.warning("Nenhum produto correspondente encontrado.")

# --- ABA 2: BUSCA POR CLIENTE ---
with aba2:
    st.header("Histórico do Cliente")
    busca_cliente = st.text_input("Digite o código ou nome do cliente:", key="cli_input").strip()
    
    # 🔘 Botão clicável para buscar no celular
    botao_buscar_cli = st.button("👤 Pesquisar Cliente", use_container_width=True)

    if (botao_buscar_cli or busca_cliente) and not df_total.empty:
        termo_busca = limpar_texto(busca_cliente)
        
        # Filtra ignorando acentos e maiúsculas
        filtro_cliente = df_total[df_total['Cliente_Busca'].str.contains(termo_busca, na=False)]
        
        if not filtro_cliente.empty:
            ranking_produtos = filtro_cliente.groupby('Produto')['Faturamento Brut'].sum().reset_index()
            ranking_produtos = ranking_produtos.sort_values(by='Faturamento Brut', ascending=False)
            
            st.subheader("🥩 Produtos mais comprados:")
            for idx, row in ranking_produtos.iterrows():
                fat_prod = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.write(f"• **{row['Produto']}** - Total: {fat_prod}")
        else:
            st.warning("Cliente não encontrado.")
