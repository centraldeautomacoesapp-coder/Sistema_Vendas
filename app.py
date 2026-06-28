import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import random

# Configuração de tela para celular
st.set_page_config(page_title="Delly's - Inteligência de Vendas", layout="centered")

# 📸 CABEÇALHO VIA LINK DA INTERNET (Fundo Branco Perfeito)
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# --- GERENCIAMENTO DE MEMÓRIA (SESSION STATE) ---
if 'termo_busca_cliente' not in st.session_state:
    st.session_state.termo_busca_cliente = ""
if 'lista_fila_whatsapp' not in st.session_state:
    st.session_state.lista_fila_whatsapp = None

# Função para remover acentos e padronizar textos de busca
def limpar_texto(texto):
    if pd.isna(texto):
        return ""
    texto_limpo = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return texto_limpo.strip().lower()

# MOTOR DE BUSCA INTELIGENTE
def filtrar_por_palavras(df, coluna_busca, termo_usuario):
    termo_limpo = limpar_texto(termo_usuario)
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'por']
    palavras = [p for p in termo_limpo.split() if p not in ignorar and len(p) > 1]
    
    if not palavras:
        palavras = termo_limpo.split()
    if not palavras:
        return df
        
    mascara = df[coluna_busca].apply(lambda x: all(p in str(x) for p in palavras))
    return df[mascara]

# LIMPADOR DE TEXTO DE OFERTA: Extrai apenas o nome real do produto
def extrair_palavras_produto(linha):
    linha_limpa = limpar_texto(linha)
    linha_limpa = re.sub(r'[^\w\s]', ' ', line_limpa if 'line_limpa' in locals() else linha_limpa)
    linha_limpa = re.sub(r'[^\w\s]', ' ', linha_limpa)
    palavras = linha_limpa.split()
    
    palavras_validas = []
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    
    for p in palavras:
        p_limpo = re.sub(r'\d+', '', p)
        if not p_limpo or len(p_limpo) <= 1 or p_limpo in ignorar:
            continue
        palavras_validas.append(p_limpo)
    return palavras_validas

# Gerador de Mensagens Humanizadas Rotativas (Evita Spam e padrão de Robô)
def gerar_mensagem_humanizada(cliente_nome, ofertas):
    saudacoes = [
        f"Olá, {cliente_nome}! Tudo bem? Veja as ofertas que separei hoje com base nos itens que você costuma comprar conosco: \n\n",
        f"Bom dia, {cliente_nome}! Espero que esteja tudo ótimo por aí. Passando para te deixar as melhores oportunidades de hoje: \n\n",
        f"Fala, {cliente_nome}! Beleza? Separei em primeira mão esses itens em promoção que têm tudo a ver com o seu perfil: \n\n",
        f"Olá, {cliente_nome}, tudo bem? Dá uma olhada nessas condições especiais que saíram hoje: \n\n"
    ]
    fechamentos = [
        "\n\nMe avisa aqui se posso garantir o seu pedido antes que acabe o estoque! 👍",
        "\n\nSe precisar de algum desses ou de outro item, é só me mandar a quantidade por aqui. Abraço!",
        "\n\nFico à disposição para lançar seu pedido. Qual deles vamos aproveitar hoje? 🚀",
        "\n\nQualquer dúvida estou por aqui. Desejo ótimas vendas!"
    ]
    
    msg = random.choice(saudacoes)
    for of in ofertas:
        msg += f"👉 {of}\n"
    msg += random.choice(fechamentos)
    return msg

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
            col_filial = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower() or "cod.filial" in str(c).lower()), None)
            
            if col_data and col_cliente and col_produto and col_faturamento:
                colunas_selecionadas = [col_data, col_cliente, col_produto, col_faturamento]
                nomes_colunas = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                
                if col_filial:
                    colunas_selecionadas.append(col_filial)
                    nomes_colunas.append('Filial')
                
                df_filtrado = df[colunas_selecionadas].copy()
                df_filtrado.columns = nomes_colunas
                
                if df_filtrado['Faturamento Brut'].dtype == 'object':
                    df_filtrado['Faturamento Brut'] = df_filtrado['Faturamento Brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                
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
        
        if 'Filial' not in df_unificado.columns:
            df_unificado['Filial'] = "1" # Valor padrão caso não exista a coluna
            
        return df_unificado
        
    return pd.DataFrame()

with st.spinner("Atualizando base de dados Delly's..."):
    df_total = carregar_dados_nuvem()

if df_total.empty:
    st.warning("⚠️ Nenhuma planilha processada. Verifique os arquivos no Drive.")
    st.stop()

# 📅 DATA ATUAL EM TEMPO REAL PARA AS TAGS (Referência Dinâmica)
data_atual_sistema = pd.Timestamp.now().normalize()
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m')

# --- 🟢 PANEL DE TAGS INTELIGENTES GLOBAIS ---
@st.cache_data(ttl=300)
def calcular_tags_carteira(df, mes_ref):
    mapa_tags = {}
    todos_clientes = df['Cliente'].unique()
    
    for cli in todos_clientes:
        df_cli = df[df['Cliente'] == cli]
        df_mes_atual = df_cli[df_cli['Ano_Mes'] == mes_ref]
        
        tags_cliente = []
        if not df_mes_atual.empty:
            tags_cliente.append("🟢 [POSITIVADO]")
            
            # Valida as filiais compradas no mês atual (removendo espaços e convertendo para texto)
            filiais = df_mes_atual['Filial'].astype(str).str.strip().unique()
            if '2' in filiais or '02' in filiais:
                tags_cliente.append("🔵 [FILIAL 2]")
            if '6' in filiais or '06' in filiais:
                tags_cliente.append("🟠 [FILIAL 6]")
        else:
            tags_cliente.append("🔴 [NÃO POSITIVADO]")
            
        mapa_tags[cli] = " ".join(tags_cliente)
    return mapa_tags

# Dicionário global de tags por cliente
dict_tags_clientes = calcular_tags_carteira(df_total, mes_atual_referencia)

# Função auxiliar para envelopar o nome do cliente com suas respectivas tags em qualquer tela
def formatar_nome_com_tag(nome_cliente):
    tag = dict_tags_clientes.get(nome_cliente, "")
    return f"{nome_cliente} {tag}"


# --- METRICAS GLOBAIS ---
st.write("---")
col1, col2 = st.columns(2)
with col1:
    faturamento_geral = df_total['Faturamento Brut'].sum()
    fat_formatado = f"R$ {faturamento_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    st.metric(label="💰 Faturamento Total Unificado", value=fat_formatado)
with col2:
    top_produto_nome = df_total.groupby('Produto')['Faturamento Brut'].sum().idxmax()
    st.metric(label="🥩 Campeão Geral de Vendas", value=str(top_produto_nome)[:18] + "...")

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
            ultimas_compras_clientes['Dias_Sem_Comprar'] = (data_atual_sistema - ultimas_compras_clientes['Data_Datetime']).dt.days
            clientes_sumidos = ultimas_compras_clientes[ultimas_compras_clientes['Dias_Sem_Comprar'] > 30].sort_values(by='Dias_Sem_Comprar', ascending=False)
            
            if not clientes_sumidos.empty:
                for idx, row in clientes_sumidos.head(8).iterrows():
                    data_pt = row['Data_Datetime'].strftime('%d/%m/%Y')
                    # Nome do cliente exibido com as Tags Globais
                    st.error(f"⚠️ **{formatar_nome_com_tag(row['Cliente'])}** não compra este item desde **{data_pt}** (há **{row['Dias_Sem_Comprar']} dias**)")
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
                st.markdown(f"👤 **{formatar_nome_com_tag(row['Cliente'])}** \n💰 Total Comprado: **{fat_total}**")
                proporcao = float(row['Faturamento Brut'] / ranking_clientes['Faturamento Brut'].max())
                st.progress(proporcao)
        else:
            st.warning("Nenhum produto encontrado com essas características.")

# --- ABA 2: BUSCA POR CLIENTE ---
with aba2:
    st.subheader("Análise de Cliente")
    input_cliente = st.text_input("Digite o nome ou parte do nome do cliente:", key="cli_input").strip()
    botao_buscar_cli = st.button("📋 Gerar Raio-X do Cliente", use_container_width=True)

    if botao_buscar_cli and input_cliente:
        st.session_state.termo_busca_cliente = input_cliente

    if st.session_state.termo_busca_cliente:
        df_clientes_filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', st.session_state.termo_busca_cliente)
        clientes_encontrados = df_clientes_filtrados['Cliente'].unique()
        
        if len(clientes_encontrados) == 0:
            st.warning("⚠️ Nenhum cliente encontrado com esse termo.")
            st.session_state.termo_busca_cliente = ""
        else:
            # Selectbox aplicando a função de formatação para exibir as tags coloridas na listagem
            cliente_selecionado = st.selectbox(
                f"📋 Encontramos correspondências. Selecione o correto:", 
                clientes_encontrados, 
                format_func=formatar_nome_com_tag
            )
            
            filtro_cliente = df_total[df_total['Cliente'] == cliente_selecionado]
            
            st.write("---")
            st.markdown(f"## 🏢 Ficha Completa: {formatar_nome_com_tag(cliente_selecionado)}")
            
            ultima_venda_geral_cliente = filtro_cliente['Data_Datetime'].max()
            dias_total_sumido = (data_atual_sistema - ultima_venda_geral_cliente).days
            
            if dias_total_sumido > 30:
                st.error(f"🔴 **ALERTA CRÍTICO DE INATIVIDADE:** Este cliente está há **{dias_total_sumido} dias** sem fazer NENHUMA COMPRA!")
            
            st.markdown("### 🚨 Itens Esquecidos/Queda por este Cliente (> 30 dias)")
            analise_produtos_cliente = filtro_cliente.groupby('Produto').agg(
                Ultima_Compra=('Data_Datetime', 'max'),
                Total_Faturado=('Faturamento Brut', 'sum')
            ).reset_index()
            
            analise_produtos_cliente['Dias_Sem_Comprar'] = (data_atual_sistema - analise_produtos_cliente['Ultima_Compra']).dt.days
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

# --- 📱 ABA 3: TEXTO DE OFERTAS COM FILA VIVA DINÂMICA ---
with aba3:
    st.subheader("📋 Painel de Ofertas Inteligente")
    st.write("Cole a lista de ofertas do dia. O sistema cruzará os dados e criará uma fila de atendimento exclusiva cliente por cliente.")
    
    texto_ofertas = st.text_area("Cole aqui a lista de ofertas do dia:", height=150, placeholder="Exemplo:\n10204 - Miolo da Alcatra Friboi KG - R$ 38,90\n9920 - Queijo Mussarela Fatiado R$ 26,00")
    botao_processar_ofertas = st.button("🚀 Processar e Criar Fila de Clientes", use_container_width=True)
    
    if botao_processar_ofertas and texto_ofertas:
        linhas_oferta = [l.strip() for l in texto_ofertas.split('\n') if l.strip()]
        
        prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
        produtos_unicos_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
        
        fila_clientes = {}
        
        with st.spinner("Mapeando histórico de consumo da carteira..."):
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
                    if cli not in fila_clientes:
                        fila_clientes[cli] = []
                    if linha not in fila_clientes[cli]:
                        fila_clientes[cli].append(linha)
                        
        st.session_state.lista_fila_whatsapp = fila_clientes
        st.rerun()
        
    # --- PROCESSAMENTO EXCLUSIVO DA FILA ---
    if st.session_state.lista_fila_whatsapp is not None:
        st.write("---")
        
        if len(st.session_state.lista_fila_whatsapp) == 0:
            st.success("🎉 **Parabéns! Todas as ofertas do dia foram enviadas e a fila foi concluída!**")
            if st.button("🔄 Limpar e Iniciar Nova Lista"):
                st.session_state.lista_fila_whatsapp = None
                st.rerun()
        else:
            total_restante = len(st.session_state.lista_fila_whatsapp)
            st.markdown(f"### 🎯 Clientes Restantes na Fila: **{total_restante}**")
            
            # Seleciona sempre o primeiro cliente ativo na fila
            cliente_atual = list(st.session_state.lista_fila_whatsapp.keys())[0]
            ofertas_do_cliente = st.session_state.lista_fila_whatsapp[cliente_atual]
            
            # Gera a mensagem humanizada rotativa para este cliente
            msg_final = gerar_mensagem_humanizada(cliente_atual, ofertas_do_cliente)
            
            # Caixa informativa destacando o cliente atual e suas tags de status
            st.info(f"👤 **CLIENTE ATUAL:** {formatar_nome_com_tag(cliente_atual)}")
            
            st.write("👇 Clique no ícone de prancheta **(canto superior direito da caixa abaixo)** para copiar o texto automaticamente:")
            # Exibe o texto em bloco de código (que possui botão nativo de copiar perfeito para celular/PC)
            st.code(msg_final, language=None)
            
            # Layout de botões de ação lado a lado
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("📋 Mensagem Copiada!", use_container_width=True, type="secondary"):
                    st.toast("Lembre-se de usar o botão interno da caixa preta acima para copiar!", icon="💡")
            with col_b2:
                # Esse botão retira o cliente da fila temporária e passa para o próximo
                if st.button("❌ Concluído / Próximo Cliente", use_container_width=True, type="primary"):
                    del st.session_state.lista_fila_whatsapp[cliente_atual]
                    st.rerun()
