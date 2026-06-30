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

# --- OTIMIZAÇÃO VISUAL PARA CELULAR (Fontes maiores e botões robustos) ---
st.markdown("""
    <style>
    /* Estilização global de textos para leitura mobile */
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
    /* Botões grandes e fáceis de tocar no celular */
    div.stButton > button {
        width: 100% !important;
        height: 52px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        margin-bottom: 10px !important;
        border-radius: 8px !important;
    }
    /* Ajuste de tamanho para blocos de código/mensagens */
    code {
        font-size: 14px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 📅 CONTROLE DE DATA ATUAL REAL DO CALENDÁRIO E TRADUÇÃO DE DIAS
data_atual_sistema = pd.Timestamp.now().normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7]

DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira"]
MAPA_DIAS_ING_PORT = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo"
}
# Identifica o dia da semana atual do sistema em formato string português
dia_semana_hoje = MAPA_DIAS_ING_PORT.get(pd.Timestamp.now().weekday(), "Segunda-feira")

# --- 📁 SISTEMA DE PERSISTÊNCIA ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIPO_PROGRESSO):
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
        "cidades_ativas": st.session_state.cidades_ativas,
        "excluidos_ofertas_dia": list(st.session_state.excluidos_ofertas_dia),
        "excluidos_ofertas_relampago": list(st.session_state.excluidos_ofertas_relampago),
        "excluidos_permanente": list(st.session_state.excluidos_permanente),
        "enviados_supervisor_mes": list(st.session_state.enviados_supervisor_mes)
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

# Inicializa as cidades ativas mapeadas por estrutura de dicionário de dias da semana
if 'cidades_ativas' not in st.session_state:
    st.session_state.cidades_ativas = progresso_backup.get("cidades_ativas", {dia: [] for dia in DIAS_SEMANA})

# Fallback caso o JSON antigo estivesse salvo no formato de lista simples
if isinstance(st.session_state.cidades_ativas, list):
    st.session_state.cidades_ativas = {dia: [] for dia in DIAS_SEMANA}

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

if not progresso_backup or ultimo_acesso != data_hoje_str:
    salvar_progresso_atual()

if 'busca_direta_cliente' not in st.session_state: st.session_state.busca_direta_cliente = ""
if 'sub_aba_consulta' not in st.session_state: st.session_state.sub_aba_consulta = "👤 Por Cliente"
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'texto_supervisor_gerado' not in st.session_state: st.session_state.texto_supervisor_gerado = ""
if 'clientes_processados_aguardando' not in st.session_state: st.session_state.clientes_processados_aguardando = []

# --- AUXILIARES ---
def limpar_texto(texto):
    if pd.isna(texto): return ""
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

def filtrar_por_palavras(df, coluna_busca, termo_usuario):
    termo_limpo = limpar_texto(termo_usuario)
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'por']
    palavras = [p for p in termo_limpo.split() if p not in ignorar and len(p) > 1]
    if not palavras: palavras = termo_limpo.split()
    if not palavras: return df
    return df[df[coluna_busca].apply(lambda x: all(p in str(x) for p in palavras))]

def extrair_palavras_produto(linha):
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(linha))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    return [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 1 and p not in ignorar]

def gerar_mensagem_humanizada(ofertas, tipo_lista):
    saudacoes = ["Olá! Tudo bem?", "Buenas! Tudo certo por aí?", "Oi! Como estão as coisas?"]
    termo_oferta = "ofertas relâmpago do dia" if tipo_lista == "relampago" else "ofertas do dia"
    introducoes = [
        f"Separei aqui as melhores {termo_oferta} exclusivas para você:\n\n",
        f"Olha só as {termo_oferta} que separei hoje para o seu estoque:\n\n"
    ]
    fechamentos = ["\n\nMe avisa aqui se posso garantir o seu pedido antes que acabe! 👍", "\n\nQual vamos aproveitar hoje? 🚀"]
    msg = f"{random.choice(saudacoes)} {random.choice(introducoes)}"
    for of in ofertas:
        msg += f"👉 {of}\n"
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

# 🟢 NOVA FUNÇÃO: Carrega a Planilha Estrutural de Clientes vinculada
@st.cache_data(ttl=600)
def carregar_base_clientes_cadastro():
    url = "https://docs.google.com/spreadsheets/d/1QNiwKklXLpBrc_g21p1GRFs4dfFMze6v/export?format=xlsx"
    try:
        df = pd.read_excel(url)
        df.columns = df.columns.str.strip()
        
        # Mapeamento dinâmico inteligente das colunas informadas
        c_cli = next((c for c in df.columns if "cliente" in str(c).lower() or "raz" in str(c).lower() or "nome" in str(c).lower() and "fant" not in str(c).lower()), df.columns[0])
        c_fant = next((c for c in df.columns if "fantasia" in str(c).lower() or "nicho" in str(c).lower()), None)
        c_cid = next((c for c in df.columns if "cidade" in str(c).lower() or "munic" in str(c).lower()), None)
        
        reordenar = {c_cli: 'Cliente'}
        if c_fant: reordenar[c_fant] = 'Nome_Fantasia'
        if c_cid: reordenar[c_cid] = 'Cidade'
        
        df = df.rename(columns=reordenar)
        if 'Nome_Fantasia' not in df.columns: df['Nome_Fantasia'] = ""
        if 'Cidade' not in df.columns: df['Cidade'] = "Não Informada"
        
        df['Cliente_Busca'] = df['Cliente'].apply(limpar_texto)
        return df
    except:
        return pd.DataFrame(columns=['Cliente', 'Nome_Fantasia', 'Cidade', 'Cliente_Busca'])

with st.spinner("Sincronizando bases de dados do Drive..."):
    df_total = carregar_dados_nuvem()
    df_clientes = carregar_base_clientes_cadastro()

if df_total.empty:
    st.warning("Base de dados de vendas vazia.")
    st.stop()

# Montagem de um mapa rápido de consulta cadastral do cliente para cruzar dados
mapa_cadastro_clientes = {}
if not df_clientes.empty:
    for _, r in df_clientes.iterrows():
        mapa_cadastro_clientes[r['Cliente_Busca']] = {
            "Nome": r['Cliente'],
            "Fantasia": str(r['Nome_Fantasia']).strip(),
            "Cidade": str(r['Cidade']).strip()
        }

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    
    for cli in df['Cliente'].unique():
        if pd.isna(cli) or str(cli).lower() == 'nan' or not str(cli).strip():
            continue
            
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
            
        if dias_sem_compra > 30:
            tags.append("SUMIDO")
            
        mapa[cli] = {"tags": tags, "dias": dias_sem_compra, "data_ult": dt_ult}
    return mapa

dict_carteira = analisar_carteira_clientes(df_total, df_mes_atual, data_atual_sistema)

def obter_badges_html(cliente_nome):
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = ""
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">⚠️ SUMIDO</span>'
    return html

# --- CABEÇALHO DA MARCA EM PILHA ---
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)
if st.button("🔄 Sincronizar Sistema"):
    st.cache_data.clear()
    st.toast("Sincronizando...", icon="🔄")
    st.rerun()

# --- 📊 INDICADORES SUPERIORES EM PILHA ---
st.write("---")
f2_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 2" in v["tags"])
f6_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 6" in v["tags"])
nao_pos_mes = sum(1 for c, v in dict_carteira.items() if "NÃO POSITIVADO" in v["tags"])

st.markdown(f"""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 5px solid #00875A; margin-bottom:8px;"><p style="margin:0; font-size:12px; color:#555; font-weight:bold;">🟢 POSITIVADOS FILIAL 2</p><h4 style="margin:0; font-size:16px; font-weight:bold;">{f2_pos} Clientes</h4></div>""", unsafe_allow_html=True)
st.markdown(f"""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 5px solid #FF8B00; margin-bottom:8px;"><p style="margin:0; font-size:12px; color:#555; font-weight:bold;">🟠 POSITIVADOS FILIAL 6</p><h4 style="margin:0; font-size:16px; font-weight:bold;">{f6_pos} Clientes</h4></div>""", unsafe_allow_html=True)
st.markdown(f"""<div style="background-color: #f8f9fa; padding: 10px; border-radius: 6px; border-left: 5px solid #DE350B; margin-bottom:8px;"><p style="margin:0; font-size:12px; color:#555; font-weight:bold;">🔴 NÃO POSITIVADOS NO MÊS</p><h4 style="margin:0; font-size:16px; font-weight:bold;">{nao_pos_mes} Clientes</h4></div>""", unsafe_allow_html=True)

st.write("---")

# --- MENUS DE NAVEGAÇÃO EM PILHA ---
col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    if st.button("🟢 Painel Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"):
        st.session_state.aba_atual = "🟢 Ofertas"; st.rerun()
    if st.button("🔍 Consultas", type="primary" if st.session_state.aba_atual == "🔍 Consulta" else "secondary"):
        st.session_state.aba_atual = "🔍 Consulta"; st.rerun()
with col_nav2:
    if st.button("🚨 Alertas Radar", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"):
        st.session_state.aba_atual = "🚨 Alertas"; st.rerun()
    if st.button("📍 Grade Cidades", type="primary" if st.session_state.aba_atual == "📍 Cidades" else "secondary"):
        st.session_state.aba_atual = "📍 Cidades"; st.rerun()

st.write("---")

# --- ABA DE CONFIGURAÇÃO DE CIDADES (VINCULADA AOS DIAS DA SEMANA) ---
if st.session_state.aba_atual == "📍 Cidades":
    st.subheader("📍 Configuração Manual da Grade de Entrega por Dia")
    st.write(f"Hoje é **{dia_semana_hoje}**. Vincule as cidades para os dias específicos da semana para realizar o cruzamento automático.")
    
    if df_clientes.empty:
        st.error("⚠️ Não foi possível recuperar a lista de cidades da planilha. Verifique a conexão ou os dados.")
    else:
        lista_cidades_cadastro = sorted([str(c).strip() for c in df_clientes['Cidade'].dropna().unique() if str(c).strip()])
        
        st.markdown("### Selecione as cidades correspondentes a cada dia:")
        
        abas_dias = st.tabs(DIAS_SEMANA)
        novas_configuracoes = {}
        
        for idx, dia in enumerate(DIAS_SEMANA):
            with abas_dias[idx]:
                st.markdown(f"#### Rota de {dia}")
                valores_padrao = st.session_state.cidades_ativas.get(dia, []) if isinstance(st.session_state.cidades_ativas, dict) else []
                
                escolhas_dia = st.multiselect(
                    f"Cidades com rota aberta na {dia}:",
                    options=lista_cidades_cadastro,
                    default=[c for c in valores_padrao if c in lista_cidades_cadastro],
                    key=f"multiselect_{dia}"
                )
                novas_configuracoes[dia] = escolhas_dia
        
        if st.button("💾 Salvar Grade Semanal", type="primary"):
            st.session_state.cidades_ativas = novas_configuracoes
            salvar_progresso_atual()
            st.success("Grade semanal de entregas salva com sucesso!")
            st.rerun()

# --- ABA 1: OFERTAS ---
elif st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    st.markdown(f"📊 Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    # Captura a lista de cidades do dia da semana atual
    cidades_hoje = st.session_state.cidades_ativas.get(dia_semana_hoje, []) if isinstance(st.session_state.cidades_ativas, dict) else []
    
    # Aviso explicativo do cruzamento do dia atual
    if cidades_hoje:
        st.info(f"Filtro Geográfico Ativo: Hoje é **{dia_semana_hoje}**, limitando envios para as **{len(cidades_hoje)}** cidades vinculadas a este dia.")
    else:
        st.warning(f"⚠️ Nenhuma cidade ativa cadastrada para hoje (**{dia_semana_hoje}**)! Vá na aba '📍 Grade Cidades' para vincular as rotas.")

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
                
                # Normaliza a lista de cidades de hoje para comparação case-insensitive infalível
                cidades_hoje_limpas = [limpar_texto(c) for c in cidades_hoje]
                
                for linha in linhas:
                    chaves = extrair_palavras_produto(linha)
                    if not chaves: continue
                    combs = [orig for orig, busca in prod_busca.items() if all(c in busca for c in chaves)]
                    
                    interessados = set()
                    for c in combs: interessados.update(prod_to_clientes[c])
                    
                    for cli in interessados:
                        if pd.isna(cli) or str(cli).lower() == 'nan': continue
                        
                        # 📍 CROSS-CHECK GEOGRÁFICO DIÁRIO AUTOMÁTICO REFORÇADO (Sem falhas de letras maiúsculas)
                        cli_limpo = limpar_texto(cli)
                        info_cadastral = mapa_cadastro_clientes.get(cli_limpo, None)
                        cidade_cli = info_cadastral['Cidade'] if info_cadastral else "Não Informada"
                        cidade_cli_limpa = limpar_texto(cidade_cli)
                        
                        # Se houver cidades configuradas para hoje, cruza de forma limpa.
                        if cidades_hoje_limpas:
                            if cidade_cli_limpa not in cidades_hoje_limpas:
                                continue # Ignora se não pertencer à rota de hoje
                        else:
                            continue # Se não houver cidades configuradas hoje, barra

                        if cli in st.session_state.excluidos_permanente:
                            if cli in clientes_com_compra_mes_atual:
                                st.session_state.excluidos_permanente.remove(cli)
                            else: continue
                                
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.success(f"Fila vinculada e filtrada automaticamente para {dia_semana_hoje}!")
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info(f"Nenhum cliente na fila de transmissão para {dia_semana_hoje}.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
        
        cliente_atual = clientes_restantes[0]
        ofertas_cliente = fila_ativa[cliente_atual]
        mensagem_pronta = gerar_mensagem_humanizada(ofertas_cliente, tipo_msg)
        
        cli_l = limpar_texto(cliente_atual)
        cad_info = mapa_cadastro_clientes.get(cli_l, {"Cidade": "Não Encontrada", "Fantasia": "Não Informado"})
        
        st.markdown(f"**🏢 {cliente_atual}**")
        st.markdown(f"📍 Cidade: `{cad_info['Cidade']}` | Ramo: `*{cad_info['Fantasia']}*`")
        st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
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

# --- ABA 2: ALERTAS (INTEGRADO COM FILTRO DE CIDADES E NOME FANTASIA) ---
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    
    cidades_hoje = st.session_state.cidades_ativas.get(dia_semana_hoje, []) if isinstance(st.session_state.cidades_ativas, dict) else []
    cidades_hoje_limpas = [limpar_texto(c) for c in cidades_hoje]
    
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200, key="txt_sup_area_fix")
            
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id=\"copyBtn\" style=\"width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;\">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                const text = {texto_js_safe};
                navigator.clipboard.writeText(text);
                this.innerText = '✅ Copiado com sucesso!';
                setTimeout(() => {{ this.innerText = '📋 Copiar Relatório'; }}, 2000);
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                    if f"chk_{c_nome}" in st.session_state:
                        st.session_state[f"chk_{c_nome}"] = False
                
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.toast("Clientes marcados como reportados com sucesso!", icon="💾")
                st.rerun()
            st.write("---")

    st.markdown("### Filtros da Lista")
    filtro_status = st.selectbox(
        "Filtrar por status de envio:",
        ["Mostrar todos", "Apenas Não Reportados", "Apenas Reportados"]
    )
    
    busca_alerta = st.text_input("🔍 Buscar Cliente em Alerta:", placeholder="Digite o nome...").strip()

    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0:
            continue
        
        cli_l = limpar_texto(cli)
        cad_info = mapa_cadastro_clientes.get(cli_l, None)
        cidade_cli = cad_info['Cidade'] if cad_info else "Não Informada"
        cidade_cli_limpa = limpar_texto(cidade_cli)
        
        # Alertas também passam pelo cruzamento inteligente limpo do dia da semana atual
        if cidades_hoje_limpas and cidade_cli != "Não Informada":
            if cidade_cli_limpa not in cidades_hoje_limpas:
                continue

        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            ja_reportado = cli in st.session_state.enviados_supervisor_mes
            
            if filtro_status == "Apenas Não Reportados" and ja_reportado: continue
            if filtro_status == "Apenas Reportados" and not ja_reportado: continue
                
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"], "Reportado": ja_reportado})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas)
    if not df_alertas_visuais.empty:
        df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
        
    if busca_alerta and not df_alertas_visuais.empty:
        termo_limpo = limpar_texto(busca_alerta)
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: termo_limpo in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info(f"Nenhum cliente em rota crítica localizado para os filtros da rota de {dia_semana_hoje}.")
    else:
        st.markdown(f"📊 Exibindo **{len(df_alertas_visuais)}** clientes em rotas ativas de hoje:")
        
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            if f"chk_{c_nome}" not in st.session_state: st.session_state[f"chk_{c_nome}"] = False
            
            with st.container():
                st.checkbox(f"📍 {c_nome} ({row['Dias']} dias s/ compra)", key=f"chk_{c_nome}")
                
                info_c = mapa_cadastro_clientes.get(limpar_texto(c_nome), {"Cidade": "Não Cadastrada", "Fantasia": ""})
                st.caption(f"🏠 Cidade: {info_c['Cidade']} | Ramo: {info_c['Fantasia']}")
                
                html_badges = obter_badges_html(c_nome)
                if row["Reportado"]:
                    html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 JÁ REPORTADO</span>'
                st.markdown(html_badges, unsafe_allow_html=True)
                
                if st.button(f"🔍 Histórico de {c_nome[:12]}...", key=f"btn_h_{idx}"):
                    st.session_state.busca_direta_cliente = c_nome
                    st.session_state.sub_aba_consulta = "👤 Por Cliente"
                    st.session_state.aba_atual = "🔍 Consulta"  
                    st.rerun()
            st.write("---")
        
        if st.button("⚡ GERAR RELATÓRIO DOS SELECIONADOS", type="primary"):
            novo_texto_acumulado = ""
            clientes_selecionados_na_rodada = []
            
            regras_segmento = {
                "pizzaria": ["Calabresa", "Muçarela", "Presunto", "Bacon", "Molho de Tomate"], 
                "pizza": ["Calabresa", "Muçarela", "Presunto"],
                "lanches": ["Hambúrguer", "Batata Frita", "Cheddar", "Maionese", "Pão"], 
                "burguer": ["Hambúrguer", "Cheddar", "Pão"],
                "pastelaria": ["Massa de Pastel", "Óleo de Fritura", "Carne Moída", "Queijo Prato"],
                "pastel": ["Massa de Pastel", "Óleo de Fritura"],
                "churrascaria": ["Linguiça", "Picanha", "Alcatra", "Carvão"], 
                "churrasco": ["Linguiça", "Picanha", "Carvão"]
            }

            for idx, row in df_alertas_visuais.iterrows():
                c_nome = row["Cliente"]
                
                if st.session_state.get(f"chk_{c_nome}", False):
                    clientes_selecionados_na_rodada.append(c_nome)
                    status_txt = "Sumido" if row["Dias"] > 30 else "Pendente"
                    novo_texto_acumulado += f"📌 {c_nome} ({status_txt} - {row['Dias']} dias sem comprar)\n"
                    
                    df_cli_h = df_total[df_total['Cliente'] == c_nome]
                    if not df_cli_h.empty:
                        top_itens = df_cli_h.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                        novo_texto_acumulado += "    🔹 Mais Comprados pelo Cliente:\n"
                        for item in top_itens: novo_texto_acumulado += f"        ▪️ {item}\n"
                    else:
                        novo_texto_acumulado += "    🔹 Sem histórico recente registrado\n"
                    
                    cli_limpo = limpar_texto(c_nome)
                    info_cad = mapa_cadastro_clientes.get(cli_limpo, None)
                    nicho_real = info_cad['Fantasia'] if info_cad else ""
                    
                    texto_analise_nicho = limpar_texto(nicho_real) + " " + cli_limpo
                    sugestoes_seg = []
                    for chave, itens_sugeridos in regras_segmento.items():
                        if chave in texto_analise_nicho:
                            for item in itens_sugeridos:
                                if item not in sugestoes_seg:
                                    sugestoes_seg.append(item)
                    
                    if sugestoes_seg:
                        novo_texto_acumulado += "    💡 Itens Sugeridos p/ Prospecção:\n"
                        for sug in sugestoes_seg[:4]:
                            novo_texto_acumulado += f"        ▪️ {sug}\n"
                    novo_texto_acumulado += "\n"
            
            st.session_state.texto_supervisor_gerado = novo_texto_acumulado
            st.session_state.clientes_processados_aguardando = clientes_selecionados_na_rodada
            salvar_progresso_atual()
            st.rerun()
