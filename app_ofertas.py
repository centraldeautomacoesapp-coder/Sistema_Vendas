import streamlit as st
import pandas as pd
from datetime import date
import datetime
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
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'por', 'rs', 'por:', 'r$']
    # Remove caracteres especiais comuns de preços para não atrapalhar a busca de produtos
    termo_limpo = re.sub(r'[0-9:,\.]', '', termo_limpo)
    palavras = [p for p in termo_limpo.split() if p not in ignorar and len(p) > 1]
    if not palavras: return pd.DataFrame() # Retorna vazio se não houver palavras válidas
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

import re

# --- EXECUÇÃO BASE ---
st.set_page_config(page_title="Sistema Integrado de Vendas", layout="wide")

with st.spinner("Sincronizando base de dados com o Drive..."):
    df_total = carregar_dados_nuvem(date.today())

if df_total.empty:
    st.warning("Base de dados vazia. Verifique a pasta do Google Drive.")
    st.stop()

# Definições de datas globais
hoje = date.today()
mes_atual_referencia = hoje.strftime('%Y-%m')
primeiro_dia_mes_atual = hoje.replace(day=1)
ultimo_dia_mes_passado = primeiro_dia_mes_atual - datetime.timedelta(days=1)
mes_passado_referencia = ultimo_dia_mes_passado.strftime('%Y-%m')

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]
df_mes_passado = df_total[df_total['Ano_Mes'] == mes_passado_referencia]

# --- CRIAÇÃO DAS ABAS (SISTEMA UNIFICADO) ---
tab_ofertas, tab_consultas, tab_alertas = st.tabs([
    "🎯 Geração de Ofertas", 
    "🔎 Consulta de Clientes", 
    "🚨 Alertas de Queda"
])

# ==========================================
# TAB 1: GERAÇÃO DE OFERTAS
# ==========================================
with tab_ofertas:
    st.title("🎯 Painel de Ofertas e Positivação")
    
    st.subheader("🤖 Passo 1: Insira suas Ofertas do Dia")
    texto_oferta = st.text_area(
        "Cole aqui a sua lista de ofertas em texto (Ex: Batata McCain R$ 25,00 / Hamburguer Lebon R$ 12,00):",
        height=150,
        key="campo_texto_ofertas"
    )
    
    # LÓGICA CORRIGIDA: Se o usuário colou texto, o sistema busca os clientes AUTOMATICAMENTE
    if texto_oferta.strip():
        st.write("### 👥 Clientes que já compram os produtos da sua lista:")
        
        # Divide o texto colado por linhas para analisar produto por produto
        linhas_oferta = [l.strip() for l in texto_oferta.split('\n') if len(l.strip()) > 3]
        df_clientes_oferta = pd.DataFrame()
        
        for linha in linhas_oferta:
            # Filtra os produtos da base que batem com a descrição da linha
            df_res = filtrar_por_palavras(df_mes_atual, 'Produto_Busca', linha)
            if not df_res.empty:
                df_clientes_oferta = pd.concat([df_clientes_oferta, df_res], ignore_index=True)
        
        if not df_clientes_oferta.empty:
            # Remove duplicados para listar cada cliente e o produto correspondente uma vez
            df_clientes_oferta = df_clientes_oferta.drop_duplicates(subset=['Cliente', 'Produto'])
            
            st.success(f"Encontramos {df_clientes_oferta['Cliente'].nunique()} clientes ideais para receberem essa oferta hoje!")
            
            # Correção do erro de versão do Streamlit aplicada aqui: width='stretch'
            st.dataframe(
                df_clientes_oferta[['Cliente', 'Produto', 'Dt. Delivery']], 
                width='stretch'
            )
            
            # Opção de baixar essa lista de clientes gerada pelo texto
            buffer_texto = io.BytesIO()
            with pd.ExcelWriter(buffer_texto, engine='openpyxl') as writer:
                df_clientes_oferta[['Cliente', 'Produto', 'Dt. Delivery']].to_excel(writer, index=False, sheet_name='Clientes Alvo')
            st.download_button(
                label="📥 Baixar Planilha de Clientes Destinatários",
                data=buffer_texto.getvalue(),
                file_name="clientes_alvo_oferta.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Nenhum cliente comprou esses produtos específicos este mês ainda. Que tal disparar para a base geral?")
            
    st.divider()
    
    st.subheader("📊 Passo 2: Filtro por Marca Parceira (Relatórios)")
    marca_selecionada = st.selectbox("Selecione uma Marca para gerar o KPI mensal:", ["McCain", "Lebon", "Confrescor", "Seara", "Doriana"])
    
    palavras_da_marca = [marca_selecionada.lower()]
    mask_marca = df_mes_atual['Produto_Busca'].apply(lambda x: any(palavra in str(x) for palavra in palavras_da_marca))
    df_marca_filtrada = df_mes_atual[mask_marca]
    compradores_alvo = df_marca_filtrada['Cliente'].unique().tolist()
    
    st.info(f"📈 **KPI {marca_selecionada}:** Temos **{len(compradores_alvo)}** clientes positivados nesta marca no mês atual.")
    
    if not df_marca_filtrada.empty:
        df_marca_filtrada['Data_Formatada'] = pd.to_datetime(df_marca_filtrada['Dt. Delivery']).dt.strftime('%d/%m/%Y')
        df_export = df_marca_filtrada[['Data_Formatada', 'Cliente', 'Produto']].copy()
        df_export.columns = ['Data da Compra', 'Nome Cliente', 'Descrição do Produto']
        
        buffer_marca = io.BytesIO()
        with pd.ExcelWriter(buffer_marca, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Positivados', startrow=3)
            worksheet = writer.sheets['Positivados']
            worksheet['A1'] = f"Marca Parceira: {marca_selecionada}"
            worksheet['A2'] = f"Quantidade de Clientes Positivados: {len(compradores_alvo)}"
            
        st.download_button(
            label=f"📥 Baixar Relatório de Positivados ({marca_selecionada})",
            data=buffer_marca.getvalue(),
            file_name=f"positivados_{marca_selecionada}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.divider()
    st.subheader("✍️ Passo 3: Criar Texto de abordagem no WhatsApp")
    if st.button("Gerar Script de Vendas Inteligente"):
        if texto_oferta.strip():
            with st.spinner("O Gemini está estruturando sua mensagem..."):
                try:
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content(f"Gere uma mensagem comercial excelente e profissional para WhatsApp baseando-se rigorosamente nestes produtos e preços: {texto_oferta}. Use emojis moderadamente e organize em tópicos.")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"Erro na IA: {e}")
        else:
            st.warning("Insira as ofertas no Passo 1 para criar o script.")

# ==========================================
# TAB 2: CONSULTA DE CLIENTES
# ==========================================
with tab_consultas:
    st.title("🔎 Consulta Rápida do Histórico do Cliente")
    
    cliente_busca = st.text_input("Digite o nome da empresa ou razão social para pesquisar:")
    
    if cliente_busca:
        df_filtrado_cli = filtrar_por_palavras(df_total, 'Cliente_Busca', cliente_busca)
        
        if not df_filtrado_cli.empty:
            clientes_encontrados = df_filtrado_cli['Cliente'].unique().tolist()
            cliente_selecionado = st.selectbox("Selecione o Cliente Correto da Lista:", clientes_encontrados)
            
            df_cliente = df_total[df_total['Cliente'] == cliente_selecionado].copy()
            
            faturamento_total = df_cliente['Faturamento Brut'].sum()
            total_pedidos = len(df_cliente)
            
            col1, col2 = st.columns(2)
            col1.metric("Faturamento Histórico Acumulado", f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col2.metric("Total de Itens Já Comprados", total_pedidos)
            
            st.subheader("📝 Todos os Itens Já Comprados")
            df_cliente['Dt. Delivery'] = pd.to_datetime(df_cliente['Dt. Delivery']).dt.strftime('%d/%m/%Y')
            
            # Correção do erro de versão do Streamlit aplicada aqui: width='stretch'
            st.dataframe(
                df_cliente[['Dt. Delivery', 'Produto', 'Faturamento Brut']].sort_values(by='Dt. Delivery', ascending=False), 
                width='stretch'
            )
        else:
            st.warning("Nenhum cliente localizado com os termos digitados.")

# ==========================================
# TAB 3: ALERTAS DE QUEDA (CHURN)
# ==========================================
with tab_alertas:
    st.title("🚨 Alertas de Queda e Clientes Inativos")
    
    clientes_ativos_mes_passado = df_mes_passado['Cliente'].unique()
    clientes_ativos_mes_atual = df_mes_atual['Cliente'].unique()
    
    clientes_inativos = [c for c in clientes_ativos_mes_passado if c not in clientes_ativos_mes_atual]
    
    st.write(f"Comparativo atual: Clientes que registraram compras em **{mes_passado_referencia}** mas estão zerados em **{mes_atual_referencia}**.")
    
    col_alerta1, col_alerta2 = st.columns(2)
    col_alerta1.metric("Clientes Ativos no Mês Passado", len(clientes_ativos_mes_passado))
    col_alerta2.metric("Clientes em Risco (Inativos este Mês)", len(clientes_inativos))
    
    st.divider()
    
    if clientes_inativos:
        st.subheader("📋 Lista de Clientes Urgentes para Recuperação")
        df_inativos = df_mes_passado[df_mes_passado['Cliente'].isin(clientes_inativos)]
        
        df_resumo_alerta = df_inativos.groupby('Cliente').agg(
            Faturamento_Mes_Passado=('Faturamento Brut', 'sum'),
            Produtos_Mais_Comprados=('Produto', lambda x: ', '.join(x.unique()[:3]))
        ).reset_index()
        
        df_resumo_alerta = df_resumo_alerta.sort_values(by='Faturamento_Mes_Passado', ascending=False)
        df_resumo_alerta['Faturamento_Mes_Passado'] = df_resumo_alerta['Faturamento_Mes_Passado'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        # Correção do erro de versão do Streamlit aplicada aqui: width='stretch'
        st.dataframe(
            df_resumo_alerta, 
            width='stretch'
        )
    else:
        st.success("🎉 Excelente! 100% dos clientes do mês passado realizaram compras no mês atual!")
