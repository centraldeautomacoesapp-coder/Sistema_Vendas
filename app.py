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

# 📸 CABEÇALHO VIA LINK DA INTERNET
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# --- GERENCIAMENTO DE MEMÓRIA (SESSION STATE) ---
if 'termo_busca_cliente' not in st.session_state:
    st.session_state.termo_busca_cliente = ""
if 'lista_fila_whatsapp' not in st.session_state:
    st.session_state.lista_fila_whatsapp = None
if 'texto_ofertas_bruto' not in st.session_state:
    st.session_state.texto_ofertas_bruto = ""

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

# LIMPADOR DE TEXTO DE OFERTA
def extrair_palavras_produto(linha):
    linha_limpa = limpar_texto(linha)
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

# Gerador de Mensagens Humanizadas
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
            df_unificado['Filial'] = "1"
            
        return df_unificado
        
    return pd.DataFrame()

with st.spinner("Atualizando base de dados Delly's..."):
    df_total = carregar_dados_nuvem()

if df_total.empty:
    st.warning("⚠️ Nenhuma planilha processada. Verifique os arquivos no Drive.")
    st.stop()

# 📅 1. REFERÊNCIA SEMPRE DO DIA ATUAL EM TEMPO REAL (Fuso Horário Local)
data_atual_sistema = pd.Timestamp.now().normalize()
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m')

# --- CALCULADORA DE TAGS DA CARTEIRA ---
@st.cache_data(ttl=300)
def calcular_tags_carteira(df, mes_ref):
    mapa_tags = {}
    todos_clientes = df['Cliente'].unique()
    
    for cli in todos_clientes:
        df_cli = df[df['Cliente'] == cli]
        df_mes_atual = df_cli[df_cli['Ano_Mes'] == mes_ref]
        
        tags_cliente = []
        if not df_mes_atual.empty:
            tags_cliente.append("POSITIVADO")
            filiais = df_mes_atual['Filial'].astype(str).str.strip().unique()
            if '2' in filiais or '02' in filiais: tags_cliente.append("FILIAL 2")
            if '6' in filiais or '06' in filiais: tags_cliente.append("FILIAL 6")
        else:
            tags_cliente.append("NÃO POSITIVADO")
            
        mapa_tags[cli] = tags_cliente
    return mapa_tags

dict_tags_clientes = calcular_tags_carteira(df_total, mes_atual_referencia)

# 🎨 2. GERADOR DE QUADRADOS PREENCHIDOS (HTML BADGES)
def obter_badges_html(cliente_nome):
    tags_lista = dict_tags_clientes.get(cliente_nome, [])
    html = ""
    for tag in tags_lista:
        if tag == "POSITIVADO":
            html += '<span style="background-color: #00875A; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-right: 6px; display: inline-block; border: none;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO":
            html += '<span style="background-color: #DE350B; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-right: 6px; display: inline-block; border: none;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2":
            html += '<span style="background-color: #0052CC; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-right: 6px; display: inline-block; border: none;">FILIAL 2</span>'
        elif tag == "FILIAL 6":
            html += '<span style="background-color: #FF8B00; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-right: 6px; display: inline-block; border: none;">FILIAL 6</span>'
    return html

# Formatação limpa para componentes que não aceitam HTML (como Selectbox)
def formatar_nome_selectbox(nome_cliente):
    tags_lista = dict_tags_clientes.get(nome_cliente, [])
    res = []
    if "POSITIVADO" in tags_lista: res.append("[POS]")
    if "NÃO POSITIVADO" in tags_lista: res.append("[⚠️NÃO_POS]")
    if "FILIAL 2" in tags_lista: res.append("[F2]")
    if "FILIAL 6" in tags_lista: res.append("[F6]")
    return f"{nome_cliente} {' '.join(res)}"

# METRICAS
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

# --- 🏢 AS 4 ABAS ORGANIZADAS ---
aba1, aba2, aba3, aba4 = st.tabs(["📱 Ofertas p/ WhatsApp", "🚨 Alertas & Oportunidades", "🔍 Consultar Produto", "👤 Consultar Cliente"])

# --- ABA 1: WHATSAPP E FILA VIVA ---
with aba1:
    st.subheader("📋 Painel de Ofertas Inteligente")
    
    st.session_state.texto_ofertas_bruto = st.text_area("Cole aqui a lista de ofertas do dia:", value=st.session_state.texto_ofertas_bruto, height=120, placeholder="Exemplo:\n10204 - Miolo da Alcatra Friboi KG - R$ 38,90")
    botao_processar_ofertas = st.button("🚀 Processar e Criar Fila de Clientes", use_container_width=True)
    
    if botao_processar_ofertas and st.session_state.texto_ofertas_bruto:
        linhas_oferta = [l.strip() for l in st.session_state.texto_ofertas_bruto.split('\n') if l.strip()]
        prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
        produtos_unicos_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
        
        fila_clientes = {}
        for linha in linhas_oferta:
            palavras_chave = extrair_palavras_produto(linha)
            if not palavras_chave: continue
            
            produtos_combinados = [p_orig for p_orig, p_busca in produtos_unicos_busca.items() if all(p in p_busca for p in palavras_chave)]
            clientes_interessados = set()
            for prod in produtos_combinados:
                clientes_interessados.update(prod_to_clientes[prod])
                
            for cli in clientes_interessados:
                if cli not in fila_clientes: fila_clientes[cli] = []
                if linha not in fila_clientes[cli]: fila_clientes[cli].append(linha)
                        
        st.session_state.lista_fila_whatsapp = fila_clientes
        st.rerun()
        
    if st.session_state.lista_fila_whatsapp is not None:
        st.write("---")
        if len(st.session_state.lista_fila_whatsapp) == 0:
            st.success("🎉 **Parabéns! Todas as propostas foram copiadas e enviadas! Fila Zerada.**")
            if st.button("🔄 Reiniciar Nova Fila"):
                st.session_state.lista_fila_whatsapp = None
                st.rerun()
        else:
            total_restante = len(st.session_state.lista_fila_whatsapp)
            st.markdown(f"### 🎯 Clientes Restantes na Fila: **{total_restante}**")
            
            cliente_atual = list(st.session_state.lista_fila_whatsapp.keys())[0]
            ofertas_do_cliente = st.session_state.lista_fila_whatsapp[cliente_atual]
            msg_final = gerar_mensagem_humanizada(cliente_atual, ofertas_do_cliente)
            
            # Exibição do Cliente Atual usando os Quadrados Coloridos (HTML)
            st.markdown(f"#### 👤 Cliente da Vez:")
            st.markdown(f"<div style='font-size:18px; font-weight:bold; margin-bottom:8px;'>{cliente_atual}</div>", unsafe_allow_html=True)
            st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
            st.write("")
            
            st.write("👇 Copie no ícone de prancheta da caixa preta abaixo:")
            st.code(msg_final, language=None)
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("📋 Marcar como Copiado", use_container_width=True):
                    st.toast("Copiado com sucesso pelo botão nativo da caixa acima!", icon="👍")
            with col_b2:
                # 3. BOTÃO EXCLUIR DA FILA DIÁRIA (Mantém o cliente no banco de dados)
                if st.button("❌ Concluído / Próximo Cliente", use_container_width=True, type="primary"):
                    del st.session_state.lista_fila_whatsapp[cliente_atual]
                    st.rerun()

# --- ABA 2: 🚨 NOVA ABA DE ALERTAS E OPORTUNIDADES INTELIGENTES ---
with aba2:
    st.subheader("🚨 Radar de Oportunidades & Avisos de Giro")
    st.write("Clientes sumidos ou não positivados este mês, cruzando o que eles mais compram com as ofertas que você cadastrou hoje.")
    
    # Descobre os clientes sumidos (Mais de 30 dias baseado na data de HOJE REAL)
    ultimas_compras_geral = df_total.groupby('Cliente')['Data_Datetime'].max().reset_index()
    # 1. Cálculo baseado na data do dia atual real
    ultimas_compras_geral['Dias_Inativo'] = (data_atual_sistema - ultimas_compras_geral['Data_Datetime']).dt.days
    
    clientes_alerta = ultimas_compras_geral[ultimas_compras_geral['Dias_Inativo'] > 30].sort_values(by='Dias_Inativo', ascending=False)
    
    if clientes_alerta.empty:
        st.success("✅ Excelente! Nenhum cliente da sua carteira está há mais de 30 dias sem comprar.")
    else:
        # Prepara palavras-chave das ofertas de hoje para o cruzamento inteligente
        ofertas_hoje_texto = limpar_texto(st.session_state.texto_ofertas_bruto)
        
        for idx, row in clientes_alerta.head(15).iterrows():
            cliente_alerta_nome = row['Cliente']
            dias_inativo = row['Dias_Inativo']
            
            # Busca os 3 produtos mais comprados historicamente por esse cliente específico
            df_cli_hist = df_total[df_total['Cliente'] == cliente_alerta_nome]
            top_produtos_cliente = df_cli_hist.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
            
            with st.container():
                st.markdown(f"---")
                # Nome do cliente e novos Quadrados Preenchidos em HTML
                st.markdown(f"<span style='font-size:16px; font-weight:bold;'>🏢 {cliente_alerta_nome}</span>", unsafe_allow_html=True)
                st.markdown(obter_badges_html(cliente_alerta_nome), unsafe_allow_html=True)
                st.markdown(f"⚠️ **Inativo há {dias_inativo} dias** (Última compra: {row['Data_Datetime'].strftime('%d/%m/%Y')})")
                
                # Exibe o que ele costuma comprar
                st.markdown(f"**🛍️ Itens mais comprados no histórico:**")
                
                # 3. Analisa se o produto preferido dele está nas ofertas do dia
                for prod in top_produtos_cliente:
                    match_oferta = False
                    palavras_prod = extrair_palavras_produto(prod)
                    
                    if ofertas_hoje_texto and palavras_prod:
                        if all(p in ofertas_hoje_texto for p in palavras_prod):
                            match_oferta = True
                    
                    if match_oferta:
                        st.markdown(f"🔥 <span style='background-color:#EAE6FF; color:#403294; padding:2px 6px; border-radius:4px; font-weight:bold;'>💡 OPORTUNIDADE:</span> O item **{prod}** está na sua lista de ofertas de hoje!", unsafe_allow_html=True)
                    else:
                        st.markdown(f"· {prod}")

# --- ABA 3: CONSULTAR PRODUTO ---
with aba3:
    st.subheader("🔍 Consultar Histórico por Produto")
    palavra_chave = st.text_input("Qual produto deseja analisar?", key="prod_input").strip()
    if st.button("📊 Gerar Relatório de Produto", use_container_width=True) and palavra_chave:
        filtro_prod = filtrar_por_palavras(df_total, 'Produto_Busca', palavra_chave)
        if not filtro_prod.empty:
            st.markdown("### Ranking de Maiores Compradores deste Item")
            ranking_clientes = filtro_prod.groupby('Cliente')['Faturamento Brut'].sum().reset_index().sort_values(by='Faturamento Brut', ascending=False)
            for idx, row in ranking_clientes.head(10).iterrows():
                fat_total = f"R$ {row['Faturamento Brut']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                st.markdown(f"👤 {formatar_nome_selectbox(row['Cliente'])} | Total: **{fat_total}**")
                st.markdown(obter_badges_html(row['Cliente']), unsafe_allow_html=True)
        else:
            st.warning("Nenhum produto encontrado.")

# --- ABA 4: CONSULTAR CLIENTE ---
with aba4:
    st.subheader("👤 Raio-X Individual do Cliente")
    input_cliente = st.text_input("Digite o nome ou parte do nome do cliente para consulta:", key="cli_input").strip()
    if st.button("📋 Buscar Cliente", use_container_width=True) and input_cliente:
        st.session_state.termo_busca_cliente = input_cliente

    if st.session_state.termo_busca_cliente:
        df_clientes_filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', st.session_state.termo_busca_cliente)
        clientes_encontrados = df_clientes_filtrados['Cliente'].unique()
        if len(clientes_encontrados) > 0:
            cliente_selecionado = st.selectbox("Selecione o cliente:", clientes_encontrados, format_func=formatar_nome_selectbox)
            
            st.markdown(f"## 🏢 Ficha Completa: {cliente_selecionado}")
            st.markdown(obter_badges_html(cliente_selecionado), unsafe_allow_html=True)
            
            filtro_cliente = df_total[df_total['Cliente'] == cliente_selecionado]
            st.write("---")
            st.markdown("### 🏆 Produtos Mais Comprados por Ele")
            ranking_produtos = filtro_cliente.groupby('Produto')['Faturamento Brut'].sum().reset_index().sort_values(by='Faturamento Brut', ascending=False)
            for idx, row in ranking_produtos.head(8).iterrows():
                st.markdown(f"🥩 **{row['Produto']}** (R$ {row['Faturamento Brut']:,.2f})")
