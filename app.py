import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re

# Configuração de tela para celular
st.set_page_config(page_title="Delly's - Inteligência de Vendas", layout="centered")

# 📸 CABEÇALHO VIA LINK DA INTERNET (Fundo Branco Perfeito)
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# Memória do Streamlit para a busca de clientes não sumir
if 'termo_busca_cliente' not in st.session_state:
    st.session_state.termo_busca_cliente = ""

# Função para remover acentos e padronizar textos de busca
def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    texto_limpo = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return texto_limpo.strip().lower()

# MOTOR DE BUSCA INTELIGENTE: Quebra o texto e valida palavras em qualquer ordem/posição
def filtrar_por_palavras(df, coluna_busca, termo_usuario):
    termo_limpo = limpar_texto(termo_usuario)
    # Remove conectores comuns e foca nas palavras principais
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'por']
    palavras = [p for p in termo_limpo.split() if p not in ignorar and len(p) > 1]
    
    if not palavras:
        palavras = termo_limpo.split()
    if not palavras:
        return df
        
    # Valida linha por linha se TODAS as palavras principais estão contidas no texto do banco
    mascara = df[coluna_busca].apply(lambda x: all(p in str(x) for p in palavras))
    return df[mascara]

# LIMPADOR DE TEXTO DE OFERTA: Extrai apenas o nome real do produto ignorando preços/pesos/códigos
def extrair_palavras_produto(linha):
    linha_limpa = limpar_texto(linha)
    linha_limpa = re.sub(r'[^\w\s]', ' ', linha_limpa) # Remove pontuações
    palavras = linha_limpa.split()
    
    palavras_validas = []
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    
    for p in palavras:
        # Remove números grudados em letras (ex: '1kg' vira 'kg', '35,90' vira '')
        p_limpo = re.sub(r'\d+', '', p)
        if not p_limpo or len(p_limpo) <= 1 or p_limpo in ignorar:
            continue
        palavras_validas.append(p_limpo)
    return palavras_validas

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

# 🚨 GAVETA DE ALERTAS: CLIENTES TOTALMENTE INATIVOS (> 30 DIAS)
st.write("")
with st.expander("🚨 ALERTA: Clientes Totalmente Inativos (> 30 dias sem comprar NADA)"):
    ultimas_compras_geral = df_total.groupby('Cliente')['Data_Datetime'].max().reset_index()
    # LINHA CORRIGIDA AQUI:
    ultimas_compras_geral['Dias_Sem_Comprar'] = (data_maxima_sistema - ultimas_compras_geral['Data_Datetime']).dt.days
    clientes_totalmente_sumidos = ultimas_compras_geral[ultimas_compras_geral['Dias_Sem_Comprar'] > 30].sort_values(by='Dias_Sem_Comprar', ascending=False)
    
    if not clientes_totalmente_sumidos.empty:
        st.write("Os clientes abaixo compravam com você e não fazem nenhum pedido há mais de um mês:")
        for idx, row in clientes_totalmente_sumidos.iterrows():
            dt_com_pt = row['Data_Datetime'].strftime('%d/%m/%Y')
            st.markdown(f"🔴 **{row['Cliente']}** — Está há **{row['Dias_Sem_Comprar']} dias** sem comprar nada. (Última compra: {dt_com_pt})")
    else:
        st.success("✅ Que sucesso! Nenhum cliente da base está há mais de 30 dias sem comprar.")

st.write("---")

# --- AS 3 ABAS OPERACIONAIS ---
aba1, aba2, aba3 = st.tabs(["🔍 Por Produto", "👤 Por Cliente", "📱 Ofertas p/ WhatsApp"])

# --- ABA 1: BUSCA POR PRODUTO ---
with aba1:
    st.subheader("Análise de Produto")
    palavra_chave = st.text_input("Qual produto deseja analisar?", key="prod_input").strip()
    botao_buscar_prod = st.button("📊 Gerar Relatório de Produto", use_container_width=True)

    if botao_buscar_prod and palavra_chave:
        filtro_prod = filtrar_por_palavras(df_total, 'Produto_Busca', palavra_chave)
        
        if not filtro_prod.empty:
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
            st.warning("Nenhum produto encontrado com essas características.")

# --- ABA 2: BUSCA POR CLIENTE ---
with aba2:
    st.subheader("Análise de Cliente")
    input_cliente = st.text_input("Digite o nome, parte do nome ou código do cliente:", key="cli_input").strip()
    botao_buscar_cli = st.button("📋 Gerar Raio-X do Cliente", use_container_width=True)

    if botao_buscar_cli and input_cliente:
        st.session_state.termo_busca_cliente = input_cliente

    if st.session_state.termo_busca_cliente:
        df_clientes_filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', st.session_state.termo_busca_cliente)
        clientes_encontrados = df_clientes_filtrados['Cliente'].unique()
        
        if len(clientes_encontrados) == 0:
            st.warning("⚠️ Nenhum cliente encontrado com esse termo ou código.")
            st.session_state.termo_busca_cliente = ""
        else:
            if len(clientes_encontrados) > 1:
                cliente_selecionado = st.selectbox(f"📋 Encontramos {len(clientes_encontrados)} correspondências. Selecione o correto:", clientes_encontrados)
            else:
                cliente_selecionado = clientes_encontrados[0]
                st.success(f"🏢 Cliente Encontrado: **{cliente_selecionado}**")
            
            filtro_cliente = df_total[df_total['Cliente'] == cliente_selecionado]
            
            st.write("---")
            st.markdown(f"## 🏢 Ficha Completa: {cliente_selecionado}")
            
            ultima_venda_geral_cliente = filtro_cliente['Data_Datetime'].max()
            dias_total_sumido = (data_maxima_sistema - ultima_venda_geral_cliente).days
            
            if dias_total_sumido > 30:
                st.error(f"🔴 **ALERTA CRÍTICO DE INATIVIDADE:** Este cliente está há **{dias_total_sumido} dias** sem fazer NENHUMA COMPRA! (Último pedido geral em: {ultima_venda_geral_cliente.strftime('%d/%m/%Y')})")
            
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
                    st.warning(f"📉 **Item Abandonado:** Deixou de comprar **{row['Produto']}** desde **{data_prod_pt}** (há **{row['Dias_Sem_Comprar']} dias**)")
            else:
                st.success("✅ Este cliente está com todo o seu mix tradicional em dia.")
            
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

# --- 📱 ABA 3: TEXTO DE OFERTAS BRUTO PARA LISTA DE WHATSAPP ---
with aba3:
    st.subheader("📋 Gerador de Ofertas Direcionadas para WhatsApp")
    st.write("Cole abaixo a lista de ofertas enviada pela empresa (pode conter códigos, preços e descrições misturadas). O app analisará as palavras e montará mensagens personalizadas separadas por cliente.")
    
    texto_ofertas = st.text_area("Cole aqui a lista de ofertas do dia:", height=200, placeholder="Exemplo de colagem:\n10204 - Miolo da Alcatra Friboi KG - R$ 38,90\n9920 - Queijo Mussarela Fatiado R$ 26,00\nMoela de Frango Sadia Pct - R$ 12,50")
    botao_processar_ofertas = st.button("🚀 Processar e Cruzar com Banco de Dados", use_container_width=True)
    
    if botao_processar_ofertas and texto_ofertas:
        linhas_oferta = [l.strip() for l in texto_ofertas.split('\n') if l.strip()]
        
        prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
        produtos_unicos_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
        
        mensagens_por_cliente = {}
        
        with st.spinner("Analisando perfil de consumo dos clientes..."):
            for linha in linhas_oferta:
                palavras_chave = extrair_palavras_produto(linha)
                if not palavras_chave:
                    continue
                
                produtos_combinados = []
                for prod_original, prod_busca in produtos_unicos_busca.items():
                    if all(p in prod_busca for p in palavras_chave):
                        produtos_combinados.append(prod_original)
                
                clientes_interessados = set()
                for prod in produtos_combinados:
                    clientes_interessados.update(prod_to_clientes[prod])
                
                for cli in clientes_interessados:
                    if cli not in mensagens_por_cliente:
                        mensagens_por_cliente[cli] = []
                    if linha not in mensagens_por_cliente[cli]:
                        mensagens_por_cliente[cli].append(linha)
                        
        if mensajes_por_cliente:
            st.success(f"🔥 Sucesso! Geradas ofertas customizadas para {len(mensagens_por_cliente)} clientes da sua carteira.")
            st.write("Clique no ícone de prancheta 📋 no canto direito de cada caixa para copiar a mensagem instantaneamente.")
            
            for cli in sorted(mensagens_por_cliente.keys()):
                ofertas_do_cliente = mensagens_por_cliente[cli]
                
                msg_final = f"Olá! Veja as nossas ofertas de hoje que separamos com base nos itens que você costuma comprar conosco:\n\n"
                for of in ofertas_do_cliente:
                    msg_final += f"👉 {of}\n"
                msg_final += f"\nFico à disposição para lançar o seu pedido! Se precisar de algo mais, é só avisar. 👍"
                
                st.markdown(f"#### 👤 {cli}")
                st.code(msg_final, language=None)
                st.write("")
        else:
            st.warning("⚠️ O sistema leu as linhas, mas nenhuma palavra-chave bateu com o histórico de compras de produtos do seu Drive. Verifique a grafia dos itens.")
