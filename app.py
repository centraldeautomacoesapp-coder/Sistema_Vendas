import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata

# Configuração de tela para celular
st.set_page_config(page_title="Delly's - Inteligência de Vendas", layout="centered")

# 📸 CABEÇALHO VIA LINK DA INTERNET (Fundo Branco Perfeito)
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# Função para remover acentos e padronizar textos de busca
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
        df_unificado['Data_Datetime'] = pd.to_datetime(df_unificado['Dt. Delivery'], dayfirst=True, errors='coerce')
        df_unificado['Ano_Mes'] = df_unificado['Data_Datetime'].dt.strftime('%Y-%m')
        
        df_unificado['Produto_Busca'] = df_unificado['Produto'].apply(limpar_texto)
        df_unificado['Cliente_Busca'] = df_unificado['Cliente'].apply(limpar_texto)
        return df_unificado
        
    return pd.DataFrame()

with st.spinner("Atualizando base de dados Delly's..."):
    df_total = carregar_dados_nuvem()

if df_total.empty:
    st.warning("⚠️ Nenhuma planilha processada. Aguarde 10 segundos e atualize a página.")
    st.stop()

# Data de referência mais recente do sistema
data_maxima_sistema = df_total['Data_Datetime'].max()

# --- METRICAS GLOBAIS NO TOPO ---
st.write("---")
col1, col2 = st.columns(2)
with col1:
    faturamento_geral = df_total['Faturamento Brut'].sum()
    fat_formatado = f"R$ {faturamento_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.metric(label="💰 Faturamento Total Unificado", value=fat_formatado)
with col2:
    top_produto_nome = df_total.groupby('Produto')['Faturamento Brut'].sum().idxmax()
    st.metric(label="🥩 Campeão Geral de Vendas", value=str(top_produto_nome)[:18] + "...")

# 🚨 NOVA GAVETA DE ALERTAS: CLIENTES TOTALMENTE INATIVOS (> 30 DIAS)
st.write("")
with st.expander("🚨 ALERTA: Clientes Totalmente Inativos (> 30 dias sem comprar NADA)"):
    # Calcula a última compra de QUALQUER item por cliente
    ultimas_compras_geral = df_total.groupby('Cliente')['Data_Datetime'].max().reset_index()
    ultimas_compras_geral['Dias_Sem_Comprar'] = (data_maxima_sistema - ultimas_compras_geral['Data_Datetime']).dt.days
    
    # Filtra os completamente sumidos há mais de 30 dias
    clientes_totalmente_sumidos = ultimas_compras_geral[ultimas_compras_geral['Dias_Sem_Comprar'] > 30].sort_values(by='Dias_Sem_Comprar', ascending=False)
    
    if not clientes_totalmente_sumidos.empty:
        st.write("Os clientes abaixo compravam com você e não fazem nenhum pedido há mais de um mês:")
        for idx, row in clientes_totalmente_sumidos.iterrows():
            dt_com_pt = row['Data_Datetime'].strftime('%d/%m/%Y')
            st.markdown(f"🔴 **{row['Cliente']}** — Está há **{row['Dias_Sem_Comprar']} dias** sem comprar nada. (Última compra: {dt_com_pt})")
    else:
        st.success("✅ Que sucesso! Nenhum cliente da base está há mais de 30 dias sem comprar.")

st.write("---")

# --- ABAS DE PESQUISA ---
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
            # 🚨 RECALIBRADO PARA 30 DIAS: CLIENTES QUE PARARAM DE COMPRAR ESTE ITEM
            st.markdown("### 🚨 Clientes Sumidos (Não compram este item há mais de 30 dias)")
            
            ultimas_compras_clientes = filtro_prod.groupby('Cliente')['Data_Datetime'].max().reset_index()
            ultimas_compras_clientes['Dias_Sem_Comprar'] = (data_maxima_sistema - ultimas_compras_clientes['Data_Datetime']).dt.days
            
            clientes_sumidos = ultimas_compras_clientes[ultimas_compras_clientes['Dias_Sem_Comprar'] > 30].sort_values(by='Dias_Sem_Comprar', ascending=False)
            
            if not clientes_sumidos.empty:
                for idx, row in clientes_sumidos.head(8).iterrows():
                    data_pt = row['Data_Datetime'].strftime('%d/%m/%Y')
                    st.error(f"⚠️ **{row['Cliente']}** não compra este item desde **{data_pt}** (há **{row['Dias_Sem_Comprar']} dias**)")
            else:
                st.success("✅ Todos os clientes compraram este produto nos últimos 30 dias.")
            
            st.write("---")
            st.markdown("### 📈 Evolução das Vendas deste Produto (Mês a Mês)")
            faturamento_mensal = filtro_prod.groupby('Ano_Mes')['Faturamento Brut'].sum().sort_index()
            st.line_chart(faturamento_mensal, color="#00875A")
            
            st.markdown("### 🏆 Ranking de Maiores Compradores deste Item")
            ranking_clientes = filtro_prod.groupby('Cliente')['Faturamento Brut'].sum().reset_index()
            ranking_clientes = ranking_clientes.sort_values(by='Faturamento Brut', ascending=False)
            
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
            nome_cliente_real = filtro_cliente['Cliente'].iloc[0]
            st.markdown(f"## 🏢 Ficha de: {nome_cliente_real}")
            
            # 🚨 NOVO ALERTA CRÍTICO: SE O CLIENTE INTEGRALMENTE SUMIU HÁ MAIS DE 30 DIAS
            ultima_venda_geral_cliente = filtro_cliente['Data_Datetime'].max()
            dias_total_sumido = (data_maxima_sistema - ultima_venda_geral_cliente).days
            
            if dias_total_sumido > 30:
                st.error(f"🔴 **ALERTA CRÍTICO DE INATIVIDADE:** Este cliente está há **{dias_total_sumido} dias** sem fazer NENHUM COMPRA na empresa! (Último pedido geral em: {ultima_venda_geral_cliente.strftime('%d/%m/%Y')})")
            
            # 🚨 RECALIBRADO PARA 30 DIAS: ITENS ESPECÍFICOS ESQUECIDOS
            st.markdown("### 🚨 Itens Esquecidos/Queda por este Cliente (> 30 dias)")
            
            analise_produtos_cliente = filtro_cliente.groupby('Produto').agg(
                Ultima_Compra=('Data_Datetime', 'max'),
                Total_Faturado=('Faturamento Brut', 'sum')
            ).reset_index()
            
            analise_produtos_cliente['Dias_Sem_Comprar'] = (data_maxima_sistema - analise_produtos_cliente['Ultima_Compra']).dt.days
            
            produtos_abandonados = analise_produtos_cliente[analise_produtos_cliente['Dias_Sem_Comprar'] > 30].sort_values(by='Dias_Sem_Comprar', ascending=False)
            
            if not produtos_abandonados.empty:
                for idx, row in produtos_abandonados.head(5).iterrows():
                    data_prod_pt = row['Ultima_Compra'].strftime('%d/%m/%Y')
                    st.warning(f"降低 **Item Abandonado:** Deixou de comprar **{row['Produto']}** desde **{data_prod_pt}** (há **{row['Dias_Sem_Comprar']} dias**)")
            else:
                st.success("✅ Este cliente está comprando o mix tradicional em dia.")
            
            st.write("---")
            st.markdown("### 🏆 Ranking de Produtos Mais Vendidos para este Cliente")
            ranking_produtos = filtro_cliente.groupby('Produto')['Faturamento Brut'].sum().reset_index()
            ranking_produtos = ranking_produtos.sort_values(by='Faturamento Brut', ascending=False)
            
            for idx, row in ranking_produtos.head(10).iterrows():
                fat_prod = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.markdown(f"🥩 **{row['Produto']}** \n💰 Volume Histórico: **{fat_prod}**")
                proporcao_prod = float(row['Faturamento Brut'] / ranking_produtos['Faturamento Brut'].max())
                st.progress(proporcao_prod)

            st.write("---")
            st.markdown("### 📊 Histórico Geral de Compras do Cliente (Mês a Mês)")
            compras_mensais = filtro_cliente.groupby('Ano_Mes')['Faturamento Brut'].sum().sort_index()
            st.bar_chart(compras_mensais, color="#0B4F93")
        else:
            st.warning("Cliente não encontrado.")
