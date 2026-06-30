import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import random
import json
import streamlit.components.v1 as components

# Configuração de tela
st.set_page_config(page_title="Delly's Inteligência", layout="centered")

# --- OTIMIZAÇÃO VISUAL PARA CELULAR ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span {
        font-size: 16px !important;
    }
    h3 {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    h4 {
        font-size: 18px !important;
    }
    
    div.stButton > button {
        width: 100% !important;
        height: 46px !important;
        font-size: 13px !important;
        font-weight: bold !important;
        margin: 0 !important;
        border-radius: 8px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    code {
        font-size: 14px !important;
    }
    
    /* CORREÇÃO DO ESPAÇAMENTO E DA LARGURA DOS BOTÕES (LADO A LADO) */
    div[data-testid="stHorizontalBlock"]:has(div.stButton):not(:has([data-testid="stMarkdownContainer"])) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        gap: 8px !important;
        padding: 0 !important;
    }
    
    div[data-testid="stHorizontalBlock"]:has(div.stButton):not(:has([data-testid="stMarkdownContainer"])) > div {
        width: calc(50% - 4px) !important;
        flex: 1 1 calc(50% - 4px) !important;
        min-width: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 📅 CONTROLE DE DATA AJUSTADO PARA O HORÁRIO DE BRASÍLIA
MAPA_DIAS_ING_PORT = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

data_atual_sistema = pd.Timestamp.now(tz='America/Sao_Paulo').tz_localize(None).normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7]
dia_semana_hoje = MAPA_DIAS_ING_PORT.get(pd.Timestamp.now(tz='America/Sao_Paulo').weekday(), "Segunda-feira")

# --- 📁 SISTEMA DE PERSISTÊNCIA COMPLETO ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIVO_PROGRESSO):
        try:
            with open(ARQUIVO_PROGRESSO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def salvar_progresso_atual():
    dados = {
        "data_ultimo_acesso": data_hoje_str,
        "envios_hoje": st.session_state.envios_hoje,
        "fila_ofertas_dia": st.session_state.fila_ofertas_dia,
        "fila_ofertas_relampago": st.session_state.fila_ofertas_relampago,
        "memoria_ofertas_cruas_dia": st.session_state.memoria_ofertas_cruas_dia,
        "memoria_ofertas_cruas_rel": st.session_state.memoria_ofertas_cruas_rel,
        "excluidos_ofertas_dia": list(st.session_state.excluidos_ofertas_dia),
        "excluidos_ofertas_relampago": list(st.session_state.excluidos_ofertas_relampago),
        "excluidos_permanente": list(st.session_state.excluidos_permanente),
        "enviados_supervisor_mes": list(st.session_state.enviados_supervisor_mes),
        "meta_pos_f2": st.session_state.get("meta_pos_f2", 0),
        "meta_pos_f6": st.session_state.get("meta_pos_f6", 0),
        "meta_rob_f2": st.session_state.get("meta_rob_f2", 0.0),
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except:
        pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")
mes_ultimo_acesso = ultimo_acesso[:7] if ultimo_acesso else ""

if 'data_ultimo_acesso' not in st.session_state:
    st.session_state.data_ultimo_acesso = data_hoje_str

if ultimo_acesso == data_hoje_str:
    if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
    if 'fila_ofertas_dia' not in st.session_state: st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
    if 'fila_ofertas_relampago' not in st.session_state: st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
    if 'memoria_ofertas_cruas_dia' not in st.session_state: st.session_state.memoria_ofertas_cruas_dia = progresso_backup.get("memoria_ofertas_cruas_dia", [])
    if 'memoria_ofertas_cruas_rel' not in st.session_state: st.session_state.memoria_ofertas_cruas_rel = progresso_backup.get("memoria_ofertas_cruas_rel", [])
    if 'excluidos_ofertas_dia' not in st.session_state: st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
    if 'excluidos_ofertas_relampago' not in st.session_state: st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))
else:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.memoria_ofertas_cruas_dia = []
    st.session_state.memoria_ofertas_cruas_rel = []
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()

if mes_ultimo_acesso == mes_atual_referencia:
    if 'enviados_supervisor_mes' not in st.session_state: st.session_state.enviados_supervisor_mes = set(progresso_backup.get("enviados_supervisor_mes", []))
else:
    st.session_state.enviados_supervisor_mes = set()

if 'excluidos_permanente' not in st.session_state:
    st.session_state.excluidos_permanente = set(progresso_backup.get("excluidos_permanente", []))

if 'meta_pos_f2' not in st.session_state: st.session_state.meta_pos_f2 = progresso_backup.get("meta_pos_f2", 0)
if 'meta_pos_f6' not in st.session_state: st.session_state.meta_pos_f6 = progresso_backup.get("meta_pos_f6", 0)
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)
if 'modo_edicao_metas' not in st.session_state: st.session_state.modo_edicao_metas = False

if not progresso_backup or ultimo_acesso != data_hoje_str:
    salvar_progresso_atual()

if 'busca_direta_cliente' not in st.session_state: st.session_state.busca_direta_cliente = ""
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'texto_supervisor_gerado' not in st.session_state: st.session_state.texto_supervisor_gerado = ""
if 'clientes_processados_aguardando' not in st.session_state: st.session_state.clientes_processados_aguardando = []

# --- CONFIGURAÇÃO GLOBAL DE MARCAS ---
MARCAS_CONFIG = {
    "LEBON": ["lebon", "seara", "doriana", "frangosul"],
    "FRIVATTI": ["frivatti"],
    "MCCAIN": ["mccain"],
    "CONFRESCOR": ["confrescor"],
    "BRASA": ["brasa"],
    "CERATTI": ["ceratti"]
}

# --- AUXILIARES ---
def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def extrair_palavras_produto(linha):
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(linha))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    return [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 1 and p not in ignorar]

# --- 🚀 ENGINE COMPLETA E AVANÇADA DE VENDA CRUZADA (SISTEMA DE SCORE POR NICHO) ---
def recomendar_venda_cruzada_avancada(cliente, df_total, df_clientes, todas_ofertas_disponiveis=None, top_n=3):
    # 1. Histórico de compras do cliente
    df_cli_hist = df_total[df_total['Cliente'] == cliente]
    produtos_historicos = set(df_cli_hist['Produto_Busca'].unique())
    
    # 2. Identificação do Nicho Comercial do Cliente pelas palavras chaves do nome
    info_c = obter_info_cliente(cliente)
    texto_perfil = limpar_texto(cliente) + " " + limpar_texto(info_c.get('Fantasia', ''))
    
    nicho = None
    if any(k in texto_perfil for k in ['pizza', 'pizzaria', 'massa']): nicho = 'pizza'
    elif any(k in texto_perfil for k in ['burger', 'hamburguer', 'lanche', 'burguer', 'snack']): nicho = 'burger'
    elif any(k in texto_perfil for k in ['padaria', 'confeitaria', 'pao', 'panificadora']): nicho = 'padaria'
    elif any(k in texto_perfil for k in ['restaurante', 'buffet', 'comida', 'churrascaria', 'grill']): nicho = 'restaurante'
    
    # Afinidade de palavras por segmento gastronômico
    afinidade_nicho = {
        'pizza': ['queijo', 'mussarela', 'calabresa', 'presunto', 'molho', 'bacon', 'catupiry', 'cheddar', 'lombo', 'trigo', 'tomate'],
        'burger': ['hamburguer', 'carne', 'bacon', 'cheddar', 'batata', 'maionese', 'molho', 'pao', 'frango', 'onion', 'cebola'],
        'padaria': ['trigo', 'farinha', 'margarina', 'ovos', 'leite', 'doce', 'chocolate', 'queijo', 'presunto', 'recheio', 'creme'],
        'restaurante': ['carne', 'frango', 'arroz', 'oleo', 'azeite', 'queijo', 'molho', 'verdura', 'batata', 'feijao', 'suino']
    }
    
    # Encontrar compradores semelhantes na base (afinidade de carteira)
    compradores_similares = df_total[df_total['Produto_Busca'].isin(produtos_historicos)]['Cliente'].unique() if produtos_historicos else []
    compradores_similares = [c for c in compradores_similares if c != cliente]

    # Se tivermos um bloco de ofertas digitado (Contexto de Mensagem/Busca Cliente)
    if todas_ofertas_disponiveis:
        ofertas_com_score = []
        for linha in todas_ofertas_disponiveis:
            linha_limpa = limpar_texto(linha)
            chaves = extrair_palavras_produto(linha)
            if not chaves: continue
            
            score = 0
            # Regra 1: Bônus por nicho comercial correspondente
            if nicho and any(af in linha_limpa for af in afinidade_nicho[nicho]):
                score += 25
                
            # Regra 2: Popularidade entre compradores do mesmo nicho/carteira
            if compradores_similares:
                mask_similares = df_total['Cliente'].isin(compradores_similares)
                for c in chaves:
                    if len(c) > 2:
                        match_count = df_total[mask_similares]['Produto_Busca'].str.contains(c, case=False, na=False).sum()
                        score += min(match_count * 0.1, 15)
                        
            # Regra 3: Penalizar levemente se ele já compra muito o item idêntico para priorizar itens "novos" (Cross-selling real)
            if any(any(c in p_hist for c in chaves) for p_hist in produtos_historicos):
                score -= 10
                
            ofertas_com_score.append((linha, score))
            
        ofertas_com_score.sort(key=lambda x: x[1], reverse=True)
        return [o[0] for o in ofertas_com_score[:top_n]]
        
    else:
        # Se for para listar na aba interna produtos da base pura que ele nunca comprou
        if compradores_similares:
            df_filtrado = df_total[df_total['Cliente'].isin(compradores_similares) & (~df_total['Produto_Busca'].isin(produtos_historicos))]
            if not df_filtrado.empty:
                return df_filtrado['Produto'].value_counts().index.tolist()[:top_n]
        return df_total[~df_total['Produto_Busca'].isin(produtos_historicos)]['Produto'].value_counts().index.tolist()[:top_n]

# --- 🚀 ENGINE DE ANÁLISE DE MARCAS ---
def analisar_clientes_por_marca(marca_selecionada, df_total):
    kws_marca = MARCAS_CONFIG[marca_selecionada]
    
    # Mapeamento de termos genéricos da categoria do produto para pegar substituição de concorrência
    termos_genericos = {
        "LEBON": ['frango', 'margarina', 'coxinha', 'file', 'sassami', 'hamburguer', 'empanado'],
        "FRIVATTI": ['carne', 'bovino', 'suino', 'linguica', 'espetinho', 'costela'],
        "MCCAIN": ['batata', 'cebola', 'palito', 'canoa', 'anel de cebola'],
        "CONFRESCOR": ['peixe', 'tilapia', 'cacao', 'camarao', 'frutos do mar'],
        "BRASA": ['carvao', 'linguica', 'churrasco'],
        "CERATTI": ['mortadela', 'presunto', 'salame', 'bacon', 'peito de peru']
    }[marca_selecionada]
    
    todos_clientes = set(df_total['Cliente'].dropna().unique())
    
    # 1. Clientes que já compraram a marca real
    mask_marca = df_total['Produto_Busca'].apply(lambda x: any(m in str(x) for m in kws_marca))
    clientes_ja_compraram = set(df_total[mask_marca]['Cliente'].unique())
    
    # 2. Clientes que compram produtos da categoria, mas de outras marcas (Substituição)
    mask_generico = df_total['Produto_Busca'].apply(lambda x: any(g in str(x) for g in termos_genericos))
    clientes_compram_generico = set(df_total[mask_generico]['Cliente'].unique())
    
    clientes_substituicao = clientes_compram_generico - clientes_ja_compraram
    
    # 3. Clientes que nunca compraram nada da categoria ou marca
    clientes_nunca_compraram = todos_clientes - clientes_ja_compraram - clientes_compram_generico
    
    return clientes_ja_compraram, clientes_substituicao, clientes_nunca_compraram

# --- GERADOR DE MENSAGEM INTEGRADO COM VENDA CRUZADA ---
def gerar_mensagem_unificada_venda(ofertas_normais, ofertas_cross, tipo_lista):
    saudacoes = ["Olá! Tudo bem?", "Buenas! Tudo certo por aí?", "Oi! Como estão as coisas?"]
    termo_oferta = "ofertas relâmpago do dia" if tipo_lista == "relampago" else "ofertas do dia"
    
    msg = f"{random.choice(saudacoes)}\n\n"
    msg += f"Separei aqui as melhores {termo_oferta} exclusivas de itens que você já costuma abastecer:\n"
    for of in ofertas_normais:
        msg += f"👉 {of}\n"
        
    if ofertas_cross:
        msg += f"\n🔥 E veja também essas oportunidades de **Venda Cruzada** que separamos para o seu segmento hoje:\n"
        for of_cz in ofertas_cross:
            msg += f"✨ {of_cz}\n"
            
    fechamentos = ["\nMe avisa aqui se posso garantir o seu pedido antes que acabe! 👍", "\nQual vamos aproveitar hoje? 🚀"]
    msg += random.choice(fechamentos)
    return msg

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=600)
def carregar_dados_nuvem():
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
            c_fil = next((c for c in df.columns if "filial" in str(c).lower() or "empresa" in str(c).lower() or "cod.filial" in str(c).lower()), None)
            
            if c_dt and c_cli and c_prod and c_fat:
                sel = [c_dt, c_cli, c_prod, c_fat]
                heads = ['Dt. Delivery', 'Cliente', 'Produto', 'Faturamento Brut']
                if c_fil:
                    sel.append(c_fil)
                    heads.append('Filial')
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
        if 'Filial' not in unificado.columns: unificado['Filial'] = "1"
        return unificado
    return pd.DataFrame()

@st.cache_data(ttl=600)
def carregar_base_clientes_cadastro():
    url = "https://docs.google.com/spreadsheets/d/1QNiwKklXLpBrc_g21p1GRFs4dfFMze6v/export?format=xlsx"
    try:
        df = pd.read_excel(url)
        df.columns = df.columns.str.strip()
        
        c_cli, c_fant, c_cid = None, None, None
        for col in df.columns:
            col_lower = str(col).lower()
            if "cliente" in col_lower or "razao" in col_lower or "razão" in col_lower:
                c_cli = col
            elif "fantasia" in col_lower or "nicho" in col_lower or "nome" in col_lower:
                c_fant = col
            elif "cidade" in col_lower or "munic" in col_lower:
                c_cid = col
        
        if not c_cli: c_cli = df.columns[0]
        if not c_fant: c_fant = c_cli
        if not c_cid: c_cid = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        
        df_reordenado = pd.DataFrame()
        df_reordenado['Cliente'] = df[c_cli].astype(str).str.strip()
        df_reordenado['Nome_Fantasia'] = df[c_fant].astype(str).str.strip() if c_fant in df.columns else ""
        df_reordenado['Cidade'] = df[c_cid].astype(str).str.strip() if c_cid in df.columns else "Não Informada"
        df_reordenado['Cliente_Busca'] = df_reordenado['Cliente'].apply(limpar_texto)
        return df_reordenado
    except:
        return pd.DataFrame(columns=['Cliente', 'Nome_Fantasia', 'Cidade', 'Cliente_Busca'])

with st.spinner("Sincronizando bases de dados..."):
    df_total = carregar_dados_nuvem()
    df_clientes = carregar_base_clientes_cadastro()

if df_total.empty:
    st.warning("Base de dados de vendas vazia.")
    st.stop()

mapa_cadastro_clientes = {}
if not df_clientes.empty:
    for _, r in df_clientes.iterrows():
        cli_nome = str(r['Cliente']).strip()
        fantasia = str(r['Nome_Fantasia']).strip()
        cidade = str(r['Cidade']).strip()
        
        info_dict = {
            "Nome": cli_nome,
            "Fantasia": fantasia if fantasia.lower() != "nan" else "",
            "Cidade": cidade if cidade.lower() != "nan" else "Não Informada"
        }
        mapa_cadastro_clientes[limpar_texto(cli_nome)] = info_dict
        if fantasia:
            mapa_cadastro_clientes[limpar_texto(fantasia)] = info_dict

def obter_info_cliente(nome_vendas):
    if pd.isna(nome_vendas) or not str(nome_vendas).strip():
        return {"Nome": "Desconhecido", "Fantasia": "Não Informado", "Cidade": "Não Informada"}
    vendas_limpo = limpar_texto(nome_vendas)
    if vendas_limpo in mapa_cadastro_clientes:
        return mapa_cadastro_clientes[vendas_limpo]
    vendas_sem_codigo = re.sub(r'^\d+\s*[-–_]?\s*', '', vendas_limpo).strip()
    if vendas_sem_codigo in mapa_cadastro_clientes:
        return mapa_cadastro_clientes[vendas_sem_codigo]
    for chave_cadastro, dados in mapa_cadastro_clientes.items():
        if chave_cadastro in vendas_limpo or vendas_limpo in chave_cadastro or chave_cadastro in vendas_sem_codigo:
            return dados
    return {"Nome": nome_vendas, "Fantasia": "Não Localizado", "Cidade": "Não Localizada"}

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

# --- COMPUTAÇÃO DA CARTEIRA LEBON & MARCAS ---
mask_lebon_g = df_mes_atual['Produto_Busca'].apply(lambda x: any(kw in str(x) for kw in ["lebon", "seara", "doriana", "frangosul"]))
clientes_grupo_lebon = set(df_mes_atual[mask_lebon_g]['Cliente'].unique())

def calcular_marcas_foco(df_mes):
    resultados = {}
    for nome, kws in MARCAS_CONFIG.items():
        m_mask = df_mes['Produto_Busca'].apply(lambda x: any(kw in str(x) for kw in kws))
        resultados[nome] = df_mes[m_mask]['Cliente'].nunique()
    return resultados

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    for cli in df['Cliente'].unique():
        if pd.isna(cli) or str(cli).lower() == 'nan' or not str(cli).strip(): continue
        tags = []
        dt_ult = ultimas_compras.get(cli, data_hoje)
        dias_sem_compra = (data_hoje - dt_ult).days
        vendas_mes = df_mes[df_mes['Cliente'] == cli]
        if not vendas_mes.empty:
            tags.append("POSITIVADO")
            filiais = vendas_mes['Filial'].astype(str).str.strip().unique()
            if any(f in filiais for f in ['2', '02', '2.0']): tags.append("FILIAL 2")
            if any(f in filiais for f in ['6', '06', '6.0']): tags.append("FILIAL 6")
        else:
            tags.append("NÃO POSITIVADO")
        if dias_sem_compra > 30: tags.append("SUMIDO")
        mapa[cli] = {"tags": tags, "dias": dias_sem_compra, "data_ult": dt_ult}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

def obter_badges_html(cliente_nome):
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = ""
    if cliente_nome in clientes_grupo_lebon:
        html += '<span style="background-color:#E3FCEF; color:#006644; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">LEBON</span>'
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">⚠️ SUMIDO</span>'
    return html

# --- CABEÇALHO DA MARCA ---
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# --- CABEÇALHO DE INDICADORES ---
st.write("---")

col_tit_meta, col_btn_meta = st.columns([4, 2])
with col_tit_meta:
    st.markdown("### 📊 Indicadores Gerais")
with col_btn_meta:
    if st.session_state.modo_edicao_metas:
        if st.button("💾 Salvar Metas", key="meta_salvar_btn"):
            st.session_state.modo_edicao_metas = False
            salvar_progresso_atual()
            st.rerun()
    else:
        if st.button("📝 Editar Metas", key="meta_editar_btn"):
            st.session_state.modo_edicao_metas = True
            st.rerun()

mask_f2 = df_mes_atual['Filial'].astype(str).str.strip().isin(['2', '02', '2.0'])
mask_f6 = df_mes_atual['Filial'].astype(str).str.strip().isin(['6', '06', '6.0'])

real_pos_f2 = df_mes_atual[mask_f2]['Cliente'].nunique()
real_pos_f6 = df_mes_atual[mask_f6]['Cliente'].nunique()
real_pos_geral = df_mes_atual[mask_f2 | mask_f6]['Cliente'].nunique()

meta_pos_f2 = int(st.session_state.meta_pos_f2)
meta_pos_f6 = int(st.session_state.meta_pos_f6)
meta_pos_geral = meta_pos_f2 + meta_pos_f6

perf_pos_f2 = (real_pos_f2 / meta_pos_f2 * 100) if meta_pos_f2 > 0 else 0.0
perf_pos_f6 = (real_pos_f6 / meta_pos_f6 * 100) if meta_pos_f6 > 0 else 0.0
perf_pos_geral = (real_pos_geral / meta_pos_geral * 100) if meta_pos_geral > 0 else 0.0

real_rob_f2 = df_mes_atual[mask_f2]['Faturamento Brut'].sum()
real_rob_f6 = df_mes_atual[mask_f6]['Faturamento Brut'].sum()
real_rob_geral = real_rob_f2 + real_rob_f6

meta_rob_f2 = float(st.session_state.meta_rob_f2)
meta_rob_f6 = float(st.session_state.meta_rob_f6)
meta_rob_geral = meta_rob_f2 + meta_rob_f6

perf_rob_f2 = (real_rob_f2 / meta_rob_f2 * 100) if meta_rob_f2 > 0 else 0.0
perf_rob_f6 = (real_rob_f6 / meta_rob_f6 * 100) if meta_rob_f6 > 0 else 0.0
perf_rob_geral = (real_rob_geral / meta_rob_geral * 100) if meta_rob_geral > 0 else 0.0

if st.session_state.modo_edicao_metas:
    st.markdown("<b style='font-size:13px;'>✏️ DIGITE AS METAS DO MÊS:</b>", unsafe_allow_html=True)
    c_ed1, c_ed2 = st.columns(2)
    with c_ed1:
        st.session_state.meta_pos_f2 = st.number_input("Meta Pos. Filial 2", value=meta_pos_f2, step=1)
        st.session_state.meta_pos_f6 = st.number_input("Meta Pos. Filial 6", value=meta_pos_f6, step=1)
    with c_ed2:
        st.session_state.meta_rob_f2 = st.number_input("Meta ROB Filial 2 (R$)", value=meta_rob_f2, step=1000.0)
        st.session_state.meta_rob_f6 = st.number_input("Meta ROB Filial 6 (R$)", value=meta_rob_f6, step=1000.0)
else:
    html_painel = f"""
    <style>
        .titulo-secao {{
            font-size: 13px; font-weight: bold; color: #111; margin-top: 10px; margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.3px;
        }}
        .bloco-container {{
            display: flex; flex-direction: column; gap: 2px; background: #fafafa; padding: 5px; border-radius: 6px; margin-bottom: 8px; border: 1px solid #eee;
        }}
        .linha-dados {{
            display: flex; justify-content: space-between; align-items: center; font-size: 11px; padding: 3px 2px; border-bottom: 1px dashed #eee;
        }}
        .linha-dados:last-child {{ border-bottom: none; }}
        .c-col-alvo {{ flex: 1.1; text-align: left; font-weight: bold; color: #444; }}
        .c-col-valores {{ flex: 2.5; text-align: left; color: #555; }}
        .c-col-porcento {{ flex: 1; text-align: right; font-weight: bold; color: #0052CC; }}
        
        .destaque-geral {{
            background-color: #f1f3f9; border-radius: 4px; font-weight: bold; padding: 3px 4px;
        }}
        .destaque-geral .c-col-alvo {{ color: #000; }}
        .destaque-geral .c-col-porcento {{ color: #00875A; }}
    </style>

    <div class="titulo-secao">📌 POSITIVAÇÕES</div>
    <div class="bloco-container">
        <div class="linha-dados destaque-geral">
            <div class="c-col-alvo">GERAL</div>
            <div class="c-col-valores">Meta: {meta_pos_geral} | Real: {real_pos_geral} clis</div>
            <div class="c-col-porcento">{perf_pos_geral:.1f}%</div>
        </div>
        <div class="linha-dados">
            <div class="c-col-alvo">Filial 2</div>
            <div class="c-col-valores">Meta: {meta_pos_f2} | Real: {real_pos_f2} clis</div>
            <div class="c-col-porcento">{perf_pos_f2:.1f}%</div>
        </div>
        <div class="linha-dados">
            <div class="c-col-alvo">Filial 6</div>
            <div class="c-col-valores">Meta: {meta_pos_f6} | Real: {real_pos_f6} clis</div>
            <div class="c-col-porcento">{perf_pos_f6:.1f}%</div>
        </div>
    </div>

    <div class="titulo-secao">💰 ROB (Faturamento)</div>
    <div class="bloco-container">
        <div class="linha-dados destaque-geral">
            <div class="c-col-alvo">GERAL</div>
            <div class="c-col-valores">Meta: R$ {meta_rob_geral:,.2f} | Real: R$ {real_rob_geral:,.2f}</div>
            <div class="c-col-porcento">{perf_rob_geral:.1f}%</div>
        </div>
        <div class="linha-dados">
            <div class="c-col-alvo">Filial 2</div>
            <div class="c-col-valores">Meta: R$ {meta_rob_f2:,.2f} | Real: R$ {real_rob_f2:,.2f}</div>
            <div class="c-col-porcento">{perf_rob_f2:.1f}%</div>
        </div>
        <div class="linha-dados">
            <div class="c-col-alvo">Filial 6</div>
            <div class="c-col-valores">Meta: R$ {meta_rob_f6:,.2f} | Real: R$ {real_rob_f6:,.2f}</div>
            <div class="c-col-porcento">{perf_rob_f6:.1f}%</div>
        </div>
    </div>
    """
    st.markdown(html_painel, unsafe_allow_html=True)

# Seção Marcas Parceiras
st.markdown("<p style='font-size:13px; font-weight:bold; color:#111; margin-top:4px; margin-bottom:3px; text-transform: uppercase;'>🤝 Marcas Parceiras (Foco)</p>", unsafe_allow_html=True)
dict_marcas_foco = calcular_marcas_foco(df_mes_atual)
m_keys = list(dict_marcas_foco.keys())

html_marcas = f"""
<style>
    .grade-marcas {{
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px; font-size: 10.5px; background: #fafafa; padding: 5px; border-radius: 4px; border: 1px solid #eee;
    }}
    .item-marca {{
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #444; font-weight: 500;
    }}
</style>
<div class="grade-marcas">
    <div class="item-marca">▪️ LEBON: <b>{dict_marcas_foco.get('LEBON', 0)}</b></div>
    <div class="item-marca">▪️ FRIVATTI: <b>{dict_marcas_foco.get('FRIVATTI', 0)}</b></div>
    <div class="item-marca">▪️ MCCAIN: <b>{dict_marcas_foco.get('MCCAIN', 0)}</b></div>
    <div class="item-marca">▪️ CONFRES.: <b>{dict_marcas_foco.get('CONFRESCOR', 0)}</b></div>
    <div class="item-marca">▪️ BRASA: <b>{dict_marcas_foco.get('BRASA', 0)}</b></div>
    <div class="item-marca">▪️ CERATTI: <b>{dict_marcas_foco.get('CERATTI', 0)}</b></div>
</div>
"""
st.markdown(html_marcas, unsafe_allow_html=True)

st.write("---")

# --- 📱 BOTÕES DE NAVEGAÇÃO MOBILE PERFEITOS ---
c_nav1, c_nav2 = st.columns(2)
with c_nav1:
    if st.button("🟢 Painel Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"):
        st.session_state.aba_atual = "🟢 Ofertas"
        st.rerun()
with c_nav2:
    if st.button("🚨 Alertas Radar", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"):
        st.session_state.aba_atual = "🚨 Alertas"
        st.rerun()

c_nav3, c_nav4 = st.columns(2)
with c_nav3:
    if st.button("🔍 Consulta Cliente", type="primary" if st.session_state.aba_atual == "🔍 Cliente" else "secondary"):
        st.session_state.aba_atual = "🔍 Cliente"
        st.rerun()
with c_nav4:
    if st.button("📦 Consulta Produto", type="primary" if st.session_state.aba_atual == "📦 Produto" else "secondary"):
        st.session_state.aba_atual = "📦 Produto"
        st.rerun()

if st.button("🤝 Marcas Parceiras (Foco)", type="primary" if st.session_state.aba_atual == "🤝 Marcas" else "secondary"):
    st.session_state.aba_atual = "🤝 Marcas"
    st.rerun()

st.write("---")

# --- 🟢 ABA 1: OFERTAS ---
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    st.markdown(f"🗓️ Hoje: **{dia_semana_hoje}** | Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    tipo_lista = st.radio("Canal:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    tipo_msg = "dia" if "☀️" in tipo_lista else "relampago"
    
    with st.expander("📝 Inserir Bloco de Ofertas"):
        txt_novas = st.text_area("Cole as linhas de ofertas aqui:", height=100, key=f"txt_{id_fila}")
        if st.button("🚀 Processar Linhas", key=f"btn_proc_{id_fila}"):
            if txt_novas.strip():
                linhas = [l.strip() for l in txt_novas.split('\n') if l.strip()]
                st.session_state[id_memoria] = linhas
                
                prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
                prod_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
                
                nova_fila = {}
                clientes_com_compra_mes_atual = df_mes_atual['Cliente'].unique()
                
                for linha in linhas:
                    chaves = extrair_palavras_produto(linha)
                    if not chaves: continue
                    combs = [orig for orig, busca in prod_busca.items() if all(c in busca for c in chaves)]
                    
                    interessados = set()
                    for c in combs: interessados.update(prod_to_clientes[c])
                    
                    for cli in interessados:
                        if pd.isna(cli) or str(cli).lower() == 'nan': continue
                        if cli in st.session_state.excluidos_permanente:
                            if cli in clientes_com_compra_mes_atual: st.session_state.excluidos_permanente.remove(cli)
                            else: continue
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info("Nenhum cliente na fila de transmissão para envio.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
        
        cliente_atual = clientes_restantes[0]
        ofertas_cliente = fila_ativa[cliente_atual]
        todas_ofertas_bloco = st.session_state[id_memoria]
        
        # 🧠 Venda Cruzada Inteligente Filtrada por Nicho
        ofertas_cross_disponiveis = [l for l in todas_ofertas_bloco if l not in ofertas_cliente]
        ofertas_venda_cruzada = recomendar_venda_cruzada_avancada(cliente_atual, df_total, df_clientes, ofertas_cross_disponiveis, top_n=2)
        
        mensagem_pronta = gerar_mensagem_unificada_venda(ofertas_cliente, ofertas_venda_cruzada, tipo_msg)
        cad_info = obter_info_cliente(cliente_atual)
        
        st.markdown(f"### 🏢 {cliente_atual}")
        if cad_info['Fantasia'] and cad_info['Fantasia'] not in ["Não Localizado", "Não Informado"]:
            st.markdown(f"⭐ **Nome Fantasia:** *{cad_info['Fantasia']}*")
        
        tag_cidade_html = f'<span style="background-color:#EAE6FF; color:#403294; padding:6px 10px; border-radius:4px; font-weight:bold; font-size:13px; margin-right:6px; border: 1px solid #C0B6F2; display: inline-block;">📍 {cad_info["Cidade"]}</span>'
        st.markdown(tag_cidade_html + obter_badges_html(cliente_atual), unsafe_allow_html=True)
        st.write("")
        
        st.code(mensagem_pronta, language=None)
        
        if st.button("✅ Enviado", type="primary", key=f"env_{str(cliente_atual)[:5]}"):
            st.session_state.envios_hoje += 1
            st.session_state[id_excluidos].add(cliente_atual)
            del st.session_state[id_fila][cliente_atual]
            salvar_progresso_atual()
            st.rerun()
            
        if st.button("❌ Excluir da Fila", key=f"ex_{str(cliente_atual)[:5]}"):
            st.session_state.excluidos_permanente.add(cliente_atual)
            del st.session_state[id_fila][cliente_atual]
            salvar_progresso_atual()
            st.rerun()

# --- 🚨 ABA 2: ALERTAS ---
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200)
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id="copyBtn" style="width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px;">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                navigator.clipboard.writeText({texto_js_safe});
                this.innerText = '✅ Copiado!';
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.rerun()

    filtro_status = st.selectbox("Filtrar por status de envio:", ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"])
    busca_alerta = st.text_input("🔍 Buscar Cliente em Alerta:", placeholder="Digite o nome...").strip()

    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0: continue
        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            ja_reportado = cli in st.session_state.enviados_supervisor_mes
            if filtro_status == "Apenas Não Reportados" and ja_reportado: continue
            if filtro_status == "Apenas Reportados" and not ja_reportado: continue
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"], "Reportado": ja_reportado})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas)
    if not df_alertas_visuais.empty: df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
    if busca_alerta and not df_alertas_visuais.empty:
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: limpar_texto(busca_alerta) in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info("Nenhum cliente crítico localizado.")
    else:
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            st.checkbox(f"🏢 {c_nome} ({row['Dias']} dias s/ compra)", key=f"chk_{c_nome}")
            info_c = obter_info_cliente(c_nome)
            if info_c['Fantasia'] and info_c['Fantasia'] not in ["Não Localizado", "Não Informado"]:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;*Fantasia: {info_c['Fantasia']}*")
            html_badges = obter_badges_html(c_nome)
            if row["Reportado"]: html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 REPORTADO</span>'
            tag_cidade_alerta = f'<span style="background-color:#EAE6FF; color:#403294; padding:4px 8px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px; border: 1px solid #C0B6F2; display: inline-block;">📍 {info_c["Cidade"]}</span>'
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{tag_cidade_alerta}{html_badges}", unsafe_allow_html=True)
            st.write("---")
            
        if st.button("⚡ GERAR RELATÓRIO DOS SELECIONADOS", type="primary"):
            novo_texto_acumulado = ""
            sel_rodada = []
            for idx, row in df_alertas_visuais.iterrows():
                cn = row["Cliente"]
                if st.session_state.get(f"chk_{cn}", False):
                    sel_rodada.append(cn)
                    novo_texto_acumulado += f"📌 {cn} ({row['Dias']} dias sem comprar)\n"
                    df_ch = df_total[df_total['Cliente'] == cn]
                    if not df_ch.empty:
                        top_i = df_ch.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                        for item in top_i: novo_texto_acumulado += f"        ▪️ {item}\n"
                    novo_texto_acumulado += "\n"
            st.session_state.texto_supervisor_gerado = novo_texto_acumulado
            st.session_state.clientes_processados_aguardando = sel_rodada
            salvar_progresso_atual()
            st.rerun()

# --- 🔍 ABA 3: CONSULTA CLIENTE (TEXTO PURO COPIÁVEL DE ACORDO COM ARQUIVO 1000550617.jpg) ---
elif st.session_state.aba_atual == "🔍 Cliente":
    st.subheader("🔍 Consulta Detalhada por Cliente")
    lista_clis = sorted(list(df_total['Cliente'].dropna().unique()))
    c_sel = st.selectbox("Selecione o Cliente:", [""] + lista_clis)
    
    if c_sel:
        inf = obter_info_cliente(c_sel)
        st.markdown(f"### 🏢 {c_sel}")
        if inf['Fantasia'] and inf['Fantasia'] not in ["Não Localizado", "Não Informado"]:
            st.markdown(f"⭐ **Nome Fantasia:** *{inf['Fantasia']}*")
        t_cid = f'<span style="background-color:#EAE6FF; color:#403294; padding:6px 10px; border-radius:4px; font-weight:bold; font-size:13px; margin-right:6px; border: 1px solid #C0B6F2; display: inline-block;">📍 {inf["Cidade"]}</span>'
        st.markdown(t_cid + obter_badges_html(c_sel), unsafe_allow_html=True)
        
        df_cli = df_total[df_total['Cliente'] == c_sel]
        c_i = dict_carteira.get(c_sel, {"dias": 0})
        col1, col2 = st.columns(2)
        col1.metric("Dias sem Comprar", f"{c_i['dias']} dias")
        col2.metric("Faturamento Total", f"R$ {df_cli['Faturamento Brut'].sum():,.2f}")
        
        # 📦 Mudança: Top 5 agora em Texto Puro para Cópia Direta
        st.markdown("#### 📦 Top 5 Produtos mais Comprados")
        if not df_cli.empty:
            top_p = df_cli.groupby('Produto')['Faturamento Brut'].agg(['sum', 'count']).nlargest(5, 'sum')
            texto_top5_copiar = ""
            for idx, (p_nome, r_p) in enumerate(top_p.iterrows(), 1):
                texto_top5_copiar += f"▪️ {p_nome} (R$ {r_p['sum']:,.2f} | {r_p['count']} ped)\n"
            st.code(texto_top5_copiar.strip(), language=None)
            
            # 🚨 Mudança: Cruzamento com Ofertas em formato de Texto Puro Copiável
            produtos_totais_cliente = df_cli['Produto'].unique()
            ofertas_dia = st.session_state.get("memoria_ofertas_cruas_dia", [])
            ofertas_rel = st.session_state.get("memoria_ofertas_cruas_rel", [])
            todas_ofertas_atendidas = (ofertas_dia or []) + (ofertas_rel or [])
            
            itens_encontrados_em_oferta = []
            for prod in produtos_totais_cliente:
                prod_limpo = limpar_texto(prod)
                for of in todas_ofertas_atendidas:
                    chaves = extrair_palavras_produto(of)
                    if chaves and all(c in prod_limpo for c in chaves):
                        itens_encontrados_em_oferta.append(of)
                        break
                        
            st.markdown("#### 🚨 Itens Usuais deste Cliente Disponíveis em Oferta Hoje!")
            if itens_encontrados_em_oferta:
                st.code("\n".join(itens_encontrados_em_oferta), language=None)
            else:
                st.info("Nenhum item histórico dele está nas ofertas ativas de hoje.")
            
            # ✨ Mudança: Sugestões de Venda Cruzada baseada em nicho em formato de Texto Puro Copiável
            st.markdown("#### ✨ Sugestões de Venda Cruzada para o Perfil")
            st.markdown("<p style='font-size:13px; color:#555;'>Produtos com altíssima afinidade comercial com o perfil dele, vindos das ofertas ativas de hoje:</p>", unsafe_allow_html=True)
            
            if todas_ofertas_atendidas:
                ofertas_cross_reais = [l for l in todas_ofertas_atendidas if l not in itens_encontrados_em_oferta]
                sugestoes_cross = recomendar_venda_cruzada_avancada(c_sel, df_total, df_clientes, ofertas_cross_reais, top_n=4)
                if sugestoes_cross:
                    st.code("\n".join(sugestoes_cross), language=None)
                else:
                    st.info("Sem ofertas de venda cruzada compatíveis com o perfil hoje.")
            else:
                # Fallback se não existirem ofertas coladas no dia (puxa itens sugeridos gerais do histórico)
                sugestoes_cross_historicas = recomendar_venda_cruzada_avancada(c_sel, df_total, df_clientes, top_n=5)
                texto_cross_hist = ""
                for s_h in sugestoes_cross_historicas:
                    texto_cross_hist += f"🔹 {s_h}\n"
                st.code(texto_cross_hist.strip(), language=None)

# --- 📦 ABA 4: CONSULTA PRODUTO ---
elif st.session_state.aba_atual == "📦 Produto":
    st.subheader("📦 Consulta Estratégica por Produto")
    lista_prods = sorted(list(df_total['Produto'].dropna().unique()))
    p_sel = st.selectbox("Selecione o Produto:", [""] + lista_prods)
    
    if p_sel:
        df_p = df_total[df_total['Produto'] == p_sel]
        st.markdown(f"### 📦 {p_sel}")
        col1, col2 = st.columns(2)
        col1.metric("Faturamento Histórico", f"R$ {df_p['Faturamento Brut'].sum():,.2f}")
        col2.metric("Clientes Compradores", f"{df_p['Cliente'].nunique()} Clis")
        
        st.markdown("#### 🏆 Top 10 Maiores Compradores deste Item")
        if not df_p.empty:
            top_c = df_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).reset_index()
            top_c['Cidade'] = top_c['Cliente'].apply(lambda x: obter_info_cliente(x)['Cidade'])
            top_c['Nome Fantasia'] = top_c['Cliente'].apply(lambda x: obter_info_cliente(x)['Fantasia'])
            st.dataframe(top_c, use_container_width=True)

# --- 🤝 ABA 5: MARCAS PARCEIRAS (RETORNO DO HUB DE CHURN E CAPTAÇÃO COMPLETO) ---
elif st.session_state.aba_atual == "🤝 Marcas":
    st.subheader("🤝 Central Marcas Parceiras (Foco)")
    
    marca_sel = st.selectbox("Selecione a Marca para Análise Comercial:", ["LEBON", "FRIVATTI", "MCCAIN", "CONFRESCOR", "BRASA", "CERATTI"])
    
    # 1. Puxar dinamicamente as ofertas inseridas no dia pertencentes a essa marca
    of_dia = st.session_state.get("memoria_ofertas_cruas_dia", [])
    of_rel = st.session_state.get("memoria_ofertas_cruas_rel", [])
    total_of_inseridas = (of_dia or []) + (of_rel or [])
    
    kws_m = MARCAS_CONFIG[marca_sel]
    ofertas_da_marca_hoje = [o for o in total_of_inseridas if any(k in limpar_texto(o) for k in kws_m)]
    
    st.markdown(f"### 📝 Ofertas Ativas do Dia - {marca_sel}")
    if ofertas_da_marca_hoje:
        st.code("\n".join(ofertas_da_marca_hoje), language=None)
    else:
        st.info(f"Nenhuma oferta contendo termos de {marca_sel} foi colada no Painel de Ofertas hoje.")
        
    # 2. Processar Listagem de Clientes por Status da Marca
    with st.spinner("Classificando comportamento dos clientes..."):
        ja_compram, substituicao, nunca_compraram = analisar_clientes_por_marca(marca_sel, df_total)
        
    st.markdown(f"#### 🎯 Direcionamento Estratégico de Clientes ({marca_sel})")
    
    tab_sub, tab_nunca, tab_ja = st.tabs([
        f"🔄 Substituição ({len(substituicao)})", 
        f"❌ Nunca Compraram ({len(nunca_compraram)})", 
        f"✅ Já Compram ({len(ja_compram)})"
    ])
    
    with tab_sub:
        st.markdown("<p style='font-size:13px; color:#c45100; font-weight:bold;'>🔥 ALERTA CHURN: Compram produtos dessa categoria de OUTRAS marcas concorrentes. Ofereça a oferta acima!</p>", unsafe_allow_html=True)
        if substituicao:
            st.code("\n".join(sorted(list(substituicao))), language=None)
        else:
            st.success("Nenhum cliente mapeado comprando marcas concorrentes deste segmento!")
            
    with tab_nunca:
        st.markdown("<p style='font-size:13px; color:#555;'>Clientes que nunca consumiram essa categoria de produto na distribuidora. Ótima oportunidade de introdução de mix:</p>", unsafe_allow_html=True)
        if nunca_compraram:
            st.code("\n".join(sorted(list(nunca_compraram))), language=None)
        else:
            st.success("Toda a sua carteira já está ativada nesse segmento!")
            
    with tab_ja:
        st.markdown("<p style='font-size:13px; color:#006644; font-weight:bold;'>✅ Clientes recorrentes do portfólio da marca (Manutenção):</p>", unsafe_allow_html=True)
        if ja_compram:
            st.code("\n".join(sorted(list(ja_compram))), language=None)
