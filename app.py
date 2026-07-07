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
import google.generativeai as genai

# --- CONFIGURAÇÃO DA API DO GEMINI (COM FALLBACK ANTI-ERRO 404) ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Tenta carregar o modelo de forma segura
    try:
        modelo_ia = genai.GenerativeModel(model_name='gemini-1.5-flash')
    except:
        modelo_ia = genai.GenerativeModel(model_name='gemini-1.5-pro')
except Exception as e:
    st.error("Erro ao configurar a API. Verifique se a GEMINI_API_KEY está nos Secrets do Streamlit.")

# Configuração de tela
st.set_page_config(page_title="Delly's Inteligência", layout="centered")

# --- OTIMIZAÇÃO VISUAL PARA CELULAR ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span { font-size: 16px !important; }
    h3 { font-size: 20px !important; font-weight: bold !important; }
    h4 { font-size: 18px !important; }
    div.stButton > button {
        width: 100% !important; height: 52px !important; font-size: 16px !important;
        font-weight: bold !important; margin-bottom: 10px !important; border-radius: 8px !important;
    }
    code { font-size: 14px !important; white-space: pre-wrap !important; }
    </style>
""", unsafe_allow_html=True)

# 📅 CONTROLE DE DATA ATUAL REAL DO CALENDÁRIO
data_atual_sistema = pd.Timestamp.now().normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7]

# --- 📁 SISTEMA DE PERSISTÊNCIA ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIVO_PROGRESSO):
        try:
            with open(ARQUIVO_PROGRESSO, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
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
        "metas_config": st.session_state.get('metas_config', {})
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
ultimo_acesso = progresso_backup.get("data_ultimo_acesso", "")
mes_ultimo_acesso = ultimo_acesso[:7] if ultimo_acesso else ""

if 'data_ultimo_acesso' not in st.session_state: st.session_state.data_ultimo_acesso = data_hoje_str

if ultimo_acesso == data_hoje_str:
    for key in ['envios_hoje', 'fila_ofertas_dia', 'fila_ofertas_relampago', 'memoria_ofertas_cruas_dia', 'memoria_ofertas_cruas_rel']:
        if key not in st.session_state: st.session_state[key] = progresso_backup.get(key, 0 if key=='envios_hoje' else ([] if 'memoria' in key else None))
    for key in ['excluidos_ofertas_dia', 'excluidos_ofertas_relampago']:
        if key not in st.session_state: st.session_state[key] = set(progresso_backup.get(key, []))
else:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia, st.session_state.fila_ofertas_relampago = None, None
    st.session_state.memoria_ofertas_cruas_dia, st.session_state.memoria_ofertas_cruas_rel = [], []
    st.session_state.excluidos_ofertas_dia, st.session_state.excluidos_ofertas_relampago = set(), set()

if mes_ultimo_acesso == mes_atual_referencia:
    if 'enviados_supervisor_mes' not in st.session_state: st.session_state.enviados_supervisor_mes = set(progresso_backup.get("enviados_supervisor_mes", []))
else:
    st.session_state.enviados_supervisor_mes = set()

if 'excluidos_permanente' not in st.session_state: st.session_state.excluidos_permanente = set(progresso_backup.get("excluidos_permanente", []))
if not progresso_backup or ultimo_acesso != data_hoje_str: salvar_progresso_atual()

if 'busca_direta_cliente' not in st.session_state: st.session_state.busca_direta_cliente = ""
if 'sub_aba_consulta' not in st.session_state: st.session_state.sub_aba_consulta = "👤 Por Cliente"
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'texto_supervisor_gerado' not in st.session_state: st.session_state.texto_supervisor_gerado = ""
if 'clientes_processados_aguardando' not in st.session_state: st.session_state.clientes_processados_aguardando = []

# Variáveis de cache para a IA não gerar a mesma mensagem duas vezes
if 'cliente_ia_atual' not in st.session_state: st.session_state.cliente_ia_atual = ""
if 'msg_ia_atual' not in st.session_state: st.session_state.msg_ia_atual = ""

if 'metas_config' not in st.session_state:
    st.session_state.metas_config = progresso_backup.get("metas_config", {
        "mes": mes_atual_referencia,
        "pos_geral": 0, "pos_fl2": 0, "pos_fl6": 0,
        "fat_geral": 0, "fat_fl2": 0, "fat_fl6": 0
    })

# Reset automático de metas na virada do mês
if st.session_state.metas_config.get("mes") != mes_atual_referencia:
    st.session_state.metas_config = {
        "mes": mes_atual_referencia,
        "pos_geral": 0, "pos_fl2": 0, "pos_fl6": 0,
        "fat_geral": 0, "fat_fl2": 0, "fat_fl6": 0
    }
    salvar_progresso_atual()

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

# --- NOVA REGRA: CRUZAMENTO AMPLO (Pega só as 2 primeiras palavras) ---
def extrair_palavras_produto(linha):
    linha_limpa = re.sub(r'[^\w\s]', ' ', limpar_texto(linha))
    ignorar = ['da', 'de', 'do', 'e', 'o', 'a', 'com', 'para', 'em', 'kg', 'g', 'un', 'cx', 'rl', 'pct', 'rs', 'r', 'unid', 'pç', 'pc', 'promocao', 'oferta']
    # Extrai palavras válidas ignorando medidas e números
    palavras_validas = [re.sub(r'\d+', '', p) for p in linha_limpa.split() if re.sub(r'\d+', '', p) and len(re.sub(r'\d+', '', p)) > 1 and p not in ignorar]
    # Retorna apenas as 3 primeiras palavras para cruzar categorias inteiras (ex: miolo alcatra friboi -> ['miolo', 'alcatra'])
    return palavras_validas[:3]

# --- FUNÇÃO DE GERAÇÃO COM IA GEMINI ---
def gerar_mensagem_ia(nome_cliente, ofertas, historico_compras):
    texto_ofertas = "\n".join([f"- {of}" for of in ofertas])
    texto_historico = "\n".join([f"- {hist}" for hist in historico_compras])
    
    prompt = f"""
    Você é um vendedor(a) experiente e simpático da distribuidora de alimentos Delly's.
    Escreva uma mensagem de WhatsApp persuasiva e personalizada para o cliente '{nome_cliente}'.
    
    O cliente já costuma comprar estes produtos conosco (este é o histórico dele):
    {texto_historico}
    
    Hoje nós temos as seguintes OFERTAS que deram match com o perfil de compra dele:
    {texto_ofertas}
    
    REGRAS DA MENSAGEM:
    1. Seja natural, caloroso, mas direto ao ponto.
    2. Mostre que você lembrou dele ao ver as ofertas (ex: "Vi essa oferta e lembrei que você sempre compra...").
    3. Apresente os produtos da oferta de forma clara.
    4. Use emojis com moderação, sem exagerar.
    5. Termine com uma chamada para ação suave (ex: "Posso separar essas ofertas para você?").
    6. Não inclua placeholders como [Seu Nome]. Aja como se a mensagem já estivesse pronta.
    """
    
    try:
        response = modelo_ia.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Lista de variações para a frase principal
        frases_ofertas = [
            "Olha só as ofertas que separei com base nos produtos que você costuma levar:",
            "Preparei uma lista especial de ofertas baseada nas suas compras anteriores:",
            "Separei algumas sugestões que têm tudo a ver com o que você gosta:",
            "Confira estas condições exclusivas que selecionei especialmente para você:",
            "Aproveite estas ofertas que escolhi pensando no seu perfil de compra:"
        ]
        
        saudacoes = ["Olá! Tudo bem?", "Buenas! Tudo certo por aí?"]
        
        # Seleção aleatória tanto da saudação quanto da frase principal
        saudacao_escolhida = random.choice(saudacoes)
        frase_escolhida = random.choice(frases_ofertas)
        
        msg = f"{saudacao_escolhida}\n{frase_escolhida}\n\n"
        
        for of in ofertas: 
            msg += f"👉 {of}\n"
        
        msg += "\nMe avisa aqui se posso garantir o seu pedido! 👍"
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

with st.spinner("Sincronizando base de dados..."):
    df_total = carregar_dados_nuvem()

if df_total.empty:
    st.warning("Base de dados vazia.")
    st.stop()

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia]

# --- CABEÇALHO ---
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)
if st.button("🔄 Sincronizar Sistema"):
    st.cache_data.clear()
    st.toast("Sincronizando...", icon="🔄")
    st.rerun() 

# --- CÁLCULOS DOS REAIS (METAS) ---
df_fl2 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('2', na=False)]
df_fl6 = df_mes_atual[df_mes_atual['Filial'].astype(str).str.contains('6', na=False)]

real_pos_fl2 = df_fl2['Cliente'].nunique()
real_pos_fl6 = df_fl6['Cliente'].nunique()
real_pos_geral = real_pos_fl2 + real_pos_fl6

real_fat_fl2 = df_fl2['Faturamento Brut'].sum()
real_fat_fl6 = df_fl6['Faturamento Brut'].sum()
real_fat_geral = real_fat_fl2 + real_fat_fl6

# --- FUNÇÃO DE RENDERIZAÇÃO DO CABEÇALHO ---
def exibir_kpi_linha(label, meta, realizado, eh_faturamento=False):
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    col1.write(f"**{label}**")
    col2.write(f"Meta: {f'R$ {meta:,.0f}' if eh_faturamento else meta}")
    col3.write(f"Real: {f'R$ {realizado:,.0f}' if eh_faturamento else realizado}")
    
    perc = (realizado / meta * 100) if meta > 0 else 0
    cor = "#00875A" if perc >= 100 else "#DE350B"
    col4.markdown(f'<div style="background-color:{cor}; color:white; text-align:center; border-radius:4px; font-weight:bold;">{perc:.1f}%</div>', unsafe_allow_html=True)

# --- EXIBIÇÃO DE METAS NA TELA ---
st.subheader("📊 Painel de Metas")
if st.button("✏️ Editar Metas do Mês"):
    st.session_state.editar_aberto = True

if st.session_state.get('editar_aberto', False):
    with st.expander("Configurar Metas", expanded=True):
        m = st.session_state.metas_config
        with st.form("form_metas"):
            st.write("Positivação (Qtd Clientes)")
            c1, c2, c3 = st.columns(3)
            m['pos_geral'] = c1.number_input("Geral", value=m['pos_geral'])
            m['pos_fl2'] = c2.number_input("FL2", value=m['pos_fl2'])
            m['pos_fl6'] = c3.number_input("FL6", value=m['pos_fl6'])
            
            st.write("Faturamento (R$)")
            c4, c5, c6 = st.columns(3)
            m['fat_geral'] = c4.number_input("Geral", value=m['fat_geral'])
            m['fat_fl2'] = c5.number_input("FL2", value=m['fat_fl2'])
            m['fat_fl6'] = c6.number_input("FL6", value=m['fat_fl6'])
            
            if st.form_submit_button("Salvar Metas"):
                st.session_state.metas_config = m
                salvar_progresso_atual()
                st.session_state.editar_aberto = False
                st.rerun()

# --- RENDERIZAÇÃO DO CABEÇALHO ---
st.markdown("### Positivação")
m = st.session_state.metas_config
exibir_kpi_linha("Geral", m['pos_geral'], real_pos_geral)
exibir_kpi_linha("FL2", m['pos_fl2'], real_pos_fl2)
exibir_kpi_linha("FL6", m['pos_fl6'], real_pos_fl6)

st.write("---")

st.markdown("### ROB FATURAMENTO")
exibir_kpi_linha("Geral", m['fat_geral'], real_fat_geral, eh_faturamento=True)
exibir_kpi_linha("FL2", m['fat_fl2'], real_fat_fl2, eh_faturamento=True)
exibir_kpi_linha("FL6", m['fat_fl6'], real_fat_fl6, eh_faturamento=True)

# --- BOTÕES DE NAVEGAÇÃO ---
st.write("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🟢 Ofertas", type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"):
        st.session_state.aba_atual = "🟢 Ofertas"
        st.rerun()

with col2:
    if st.button("🚨 Alertas", type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"):
        st.session_state.aba_atual = "🚨 Alertas"
        st.rerun()

with col3:
    if st.button("🔍 Consulta", type="primary" if st.session_state.aba_atual == "🔍 Consulta" else "secondary"):
        st.session_state.aba_atual = "🔍 Consulta"
        st.rerun()

st.write("---")

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
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:4px 6px; border-radius:4px; font-weight:bold; font-size:12px; margin-right:4px;">⚠️ SUMIDO</span>'
    return html

# ==============================================================================
# --- ABA 1: OFERTAS ---
# ==============================================================================
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão c/ IA 🧠")
    st.markdown(f"📊 Envia hoje: **{st.session_state.envios_hoje}** listas")
    
    tipo_lista = st.radio("Canal:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_memoria = "memoria_ofertas_cruas_dia" if "☀️" in tipo_lista else "memoria_ofertas_cruas_rel"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    
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
                            if cli in clientes_com_compra_mes_atual:
                                st.session_state.excluidos_permanente.remove(cli)
                            else: continue
                                
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.success("Fila vinculada e cruzada com sucesso!")
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info("Nenhum cliente na fila de transmissão pendente.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Pendentes na Fila: **{len(clientes_restantes)}**")
        
        # --- 🔍 CAMPO DE BUSCA / ANTECIPAÇÃO DE CLIENTE ---
        busca_cliente_fila = st.text_input(
            "🔍 Buscar / Antecipar Cliente na Fila (Nome ou Código):", 
            key=f"busca_fila_{id_fila}", 
            placeholder="Digite parte do nome ou código do cliente..."
        ).strip()
        
        if busca_cliente_fila:
            termo_busca = limpar_texto(busca_cliente_fila)
            clientes_filtrados = [c for c in clientes_restantes if termo_busca in limpar_texto(c)]
            
            if clientes_filtrados:
                cliente_atual = clientes_filtrados[0]
                st.toast(f"Exibindo cliente encontrado: {cliente_atual}", icon="🎯")
            else:
                st.warning("Nenhum cliente com esse nome/código encontrado na fila ativa. Exibindo o próximo da fila padrão.")
                cliente_atual = clientes_restantes[0]
        else:
            cliente_atual = clientes_restantes[0]
        
        ofertas_cliente = fila_ativa[cliente_atual]
        
        st.markdown(f"**🏢 {cliente_atual}**")
        st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
        st.write("")
        
        # --- GERAÇÃO DA MENSAGEM VIA IA ---
        if st.session_state.cliente_ia_atual != cliente_atual:
            st.session_state.cliente_ia_atual = cliente_atual
            historico = df_total[df_total['Cliente'] == cliente_atual].groupby('Produto')['Faturamento Brut'].sum().nlargest(5).index.tolist()
            
            with st.spinner("🧠 Gemini analisando o histórico e escrevendo a mensagem..."):
                st.session_state.msg_ia_atual = gerar_mensagem_ia(cliente_atual, ofertas_cliente, historico)
        
        st.code(st.session_state.msg_ia_atual, language=None)
        
        if st.button("✅ Enviado", type="primary", key=f"env_{str(cliente_atual)[:5]}"):
            st.session_state.envios_hoje += 1
            st.session_state[id_excluidos].add(cliente_atual)
            del st.session_state[id_fila][cliente_atual]
            st.session_state.cliente_ia_atual = "" 
            salvar_progresso_atual()
            st.rerun()
            
        if st.button("❌ Excluir da Fila", key=f"ex_{str(cliente_atual)[:5]}"):
            st.session_state.excluidos_permanente.add(cliente_atual)
            del st.session_state[id_fila][cliente_atual]
            st.session_state.cliente_ia_atual = ""
            salvar_progresso_atual()
            st.rerun()

# ==============================================================================
# --- ABA 2: ALERTAS ---
# ==============================================================================
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    if st.session_state.texto_supervisor_gerado:
        with st.expander("📋 RELATÓRIO DO SUPERVISOR GERADO", expanded=True):
            st.text_area("Texto estruturado:", value=st.session_state.texto_supervisor_gerado, height=200, key="txt_sup_area_fix")
            texto_js_safe = json.dumps(st.session_state.texto_supervisor_gerado)
            html_button_js = f"""
            <button id=\"copyBtn\" style=\"width: 100%; background-color: #00875A; color: white; border: none; padding: 14px; border-radius: 6px; font-weight: bold; font-size: 16px; cursor: pointer;\">📋 Copiar Relatório</button>
            <script>
            document.getElementById('copyBtn').addEventListener('click', function() {{
                navigator.clipboard.writeText({texto_js_safe});
                this.innerText = '✅ Copiado com sucesso!';
                setTimeout(() => {{ this.innerText = '📋 Copiar Relatório'; }}, 2000);
            }});
            </script>
            """
            components.html(html_button_js, height=55)
            
            if st.button("💾 Marcar Selecionados como Reportados"):
                for c_nome in st.session_state.clientes_processados_aguardando:
                    st.session_state.enviados_supervisor_mes.add(c_nome)
                    if f"chk_{c_nome}" in st.session_state: st.session_state[f"chk_{c_nome}"] = False
                st.session_state.clientes_processados_aguardando = []
                st.session_state.texto_supervisor_gerado = ""
                salvar_progresso_atual()
                st.toast("Clientes marcados como reportados com sucesso!", icon="💾")
                st.rerun()
            st.write("---")

    st.markdown("### Filtros da Lista")
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
        termo_limpo = limpar_texto(busca_alerta)
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: termo_limpo in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info("Nenhum cliente localizado para os filtros selecionados.")
    else:
        st.markdown(f"📊 Exibindo **{len(df_alertas_visuais)}** clientes nesta lista:")
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            if f"chk_{c_nome}" not in st.session_state: st.session_state[f"chk_{c_nome}"] = False
            
            with st.container():
                st.checkbox(f"📍 {c_nome} ({row['Dias']} dias sem comprar)", key=f"chk_{c_nome}")
                html_badges = obter_badges_html(c_nome)
                if row["Reportado"]: html_badges += '<span style="background-color:#FFC400; color:#111; padding:3px 5px; border-radius:4px; font-weight:bold; font-size:11px; margin-right:4px;">📅 JÁ REPORTADO</span>'
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
            
            for idx, row in df_alertas_visuais.iterrows():
                c_nome = row["Cliente"]
                if st.session_state.get(f"chk_{c_nome}", False):
                    clientes_selecionados_na_rodada.append(c_nome)
                    status_txt = "Sumido" if row["Dias"] > 30 else "Pendente"
                    novo_texto_acumulado += f"📌 {c_nome} ({status_txt} - {row['Dias']} dias sem comprar)\n"
                    
                    df_cli_h = df_total[df_total['Cliente'] == c_nome]
                    if not df_cli_h.empty:
                        top_itens = df_cli_h.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                        novo_texto_acumulado += "   🔹 Mais Comprados pelo Cliente:\n"
                        for item in top_itens: novo_texto_acumulado += f"     ▪️ {item}\n"
                    else:
                        novo_texto_acumulado += "   🔹 Sem histórico recente registrado\n"
                    
                    nome_limpo_cli = limpar_texto(c_nome)
                    sugestoes_seg = []
                    regras_segmento = {
    "acai": ["Açaí", "Granola", "Leite Condensado", "Morango", "Banana", "Leite em pó"],
    "açougue": ["Carnes", "Bandejas", "Papel Filme", "Facas", "Sacos plásticos"],
    "bar": ["Cerveja", "Gelo", "Energético", "Destilados", "Amendoim", "Batata Frita"],
    "buffet": ["Descartáveis Premium", "Guardanapos", "Bebidas", "Artigos de festa"],
    "burguer": ["Hambúrguer", "Cheddar", "Bacon", "Pão de Hambúrguer", "Maionese Artesanal"],
    "cafeteria": ["Café em grão", "Leite", "Açúcar", "Adoçante", "Copos descartáveis", "Xaropes"],
    "cantina": ["Massas", "Molho de Tomate", "Queijo Ralado", "Embalagens"],
    "churrascaria": ["Linguiça", "Picanha", "Alcatra", "Carvão", "Sal Grosso", "Espetos", "Costela", "Fraldinha"],
    "churrasco": ["Linguiça", "Picanha", "Alcatra", "Carvão", "Sal Grosso"],
    "confeitaria": ["Farinha", "Açúcar", "Ovos", "Leite Condensado", "Chocolate", "Manteiga", "Fermento"],
    "conveniencia": ["Cerveja", "Refrigerante", "Salgadinhos", "Gelo", "Carvão"],
    "distribuidora": ["Cerveja", "Refrigerante", "Gelo", "Água", "Carvão"],
    "doceria": ["Chantilly", "Leite Condensado", "Chocolate", "Confeitos", "Formas", "Açúcar"],
    "espetinho": ["Linguiça", "Carne", "Frango", "Carvão", "Sal Grosso"],
    "fitness": ["Mix de folhas", "Molhos prontos", "Proteína grelhada", "Embalagens biodegradáveis"],
    "food truck": ["Embalagens take-away", "Guardanapos", "Descartáveis", "Molhos"],
    "hamburguer": ["Hambúrguer", "Cheddar", "Bacon", "Pão de Hambúrguer", "Maionese Artesanal"],
    "hotel": ["Café", "Açúcar", "Adoçante", "Produtos de Limpeza", "Descartáveis", "Amenities"],
    "italiano": ["Macarrão", "Molho", "Azeite", "Queijo Parmesão", "Manjericão", "Vinho"],
    "japones": ["Salmão", "Cream Cheese", "Shoyu", "Wasabi", "Gengibre", "Arroz Japonês", "Alga Nori"],
    "lanches": ["Hambúrguer", "Batata Frita", "Cheddar", "Maionese", "Ketchup", "Pão de Hambúrguer", "Bacon"],
    "massa": ["Farinha", "Ovos", "Molho de Tomate", "Parmesão", "Manjericão"],
    "mexicano": ["Tortilha", "Guacamole", "Pimenta", "Nachos", "Feijão Mexicano", "Carne Moída"],
    "padaria": ["Pão Francês", "Leite", "Manteiga", "Presunto", "Queijo", "Café", "Farinha"],
    "panificadora": ["Farinha", "Fermento", "Ovos", "Leite", "Margarina", "Embalagens de Pão"],
    "pastel": ["Massa de Pastel", "Carne Moída", "Queijo", "Caldo de Cana", "Óleo"],
    "pastelaria": ["Massa de Pastel", "Carne Moída", "Queijo", "Caldo de Cana", "Óleo", "Embalagens"],
    "peixaria": ["Peixe Fresco", "Gelo", "Limão", "Embalagens", "Sacos de Gelo"],
    "pizza": ["Calabresa", "Muçarela", "Presunto", "Molho de Tomate", "Manjericão"],
    "pizzaria": ["Calabresa", "Muçarela", "Presunto", "Molho de Tomate", "Azeitona", "Orégano", "Farinha", "Fermento"],
    "pousada": ["Café", "Leite", "Pão", "Produtos de Limpeza", "Lençóis", "Descartáveis"],
    "produtos naturais": ["Grãos", "Castanhas", "Farinha Integral", "Temperos", "Frutas Secas"],
    "pub": ["Cerveja Artesanal", "Gelo", "Amendoim", "Batata Frita", "Hambúrguer"],
    "restaurante": ["Arroz", "Feijão", "Óleo", "Tempero", "Embalagens", "Descartáveis"],
    "sorveteria": ["Sorvete", "Calda", "Casquinha", "Granulado", "Marshmallow"],
    "sushi": ["Salmão", "Cream Cheese", "Shoyu", "Wasabi", "Gengibre", "Arroz Japonês", "Alga Nori"],
    "taco": ["Tortilha", "Queijo", "Pimenta", "Carne Moída"],
    "temaki": ["Salmão", "Cream Cheese", "Shoyu", "Alga Nori"]
}
                    for chave, itens_sugeridos in regras_segmento.items():
                        if chave in nome_limpo_cli: sugestoes_seg.extend(itens_sugeridos)
                    
                    if congest := list(set(sugestoes_seg)):
                        novo_texto_acumulado += "   💡 Oportunidades de Venda Cruzada:\n"
                        for sug in congest: novo_texto_acumulado += f"     ▪️ {sug}\n"
                    novo_texto_acumulado += "\n"
            
            if len(clientes_selecionados_na_rodada) > 0:
                st.session_state.texto_supervisor_gerado = novo_texto_acumulado
                st.session_state.clientes_processados_aguardando = clientes_selecionados_na_rodada
                st.toast(f"✅ Relatório pronto para conferência!", icon="🚀")
                st.rerun()
            else:
                st.warning("⚠️ Por favor, marque pelo menos um Checkbox na lista acima para poder gerar o texto!")

# ==============================================================================
# --- ABA 3: CONSULTA E VENDA CRUZADA ---
# ==============================================================================
elif st.session_state.aba_atual == "🔍 Consulta":
    st.session_state.sub_aba_consulta = st.radio("Filtro de Pesquisa:", ["👤 Por Cliente", "📦 Por Produto"], horizontal=True)
    st.write("---")
    
    if st.session_state.sub_aba_consulta == "👤 Por Cliente":
        st.subheader("Raio-X do Cliente")
        input_busca = st.text_input("Nome ou Código:", value=st.session_state.busca_direta_cliente).strip()
        
        if input_busca:
            filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', input_busca)
            nomes_encontrados = filtrados['Cliente'].unique()
            
            if len(nomes_encontrados) > 0:
                c_sel = st.selectbox("Selecione o Cliente:", nomes_encontrados)
                st.markdown(f"### Ficha: {c_sel}")
                st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
                
                df_cli = df_total[df_total['Cliente'] == c_sel]
                st.write("**Mix de Itens Históricos:**")
                rank_p = df_cli.groupby('Produto')['Faturamento Brut'].sum().nlargest(10).reset_index()
                for i, r in rank_p.iterrows():
                    st.markdown(f"· {r['Produto']} (R$ {r['Faturamento Brut']:,.2f})")
                
                st.write("---")
                st.markdown("### 💡 Venda Cruzada Inteligente")
                
                sugestoes_segmento = []
                nome_limpo_cli = limpar_texto(c_sel)
                
                regras_segmento = {
                    "acai": ["Açaí", "Granola", "Leite Condensado", "Morango", "Banana", "Leite em pó"],
    "açougue": ["Carnes", "Bandejas", "Papel Filme", "Facas", "Sacos plásticos"],
    "bar": ["Cerveja", "Gelo", "Energético", "Destilados", "Amendoim", "Batata Frita"],
    "buffet": ["Descartáveis Premium", "Guardanapos", "Bebidas", "Artigos de festa"],
    "burguer": ["Hambúrguer", "Cheddar", "Bacon", "Pão de Hambúrguer", "Maionese Artesanal"],
    "cafeteria": ["Café em grão", "Leite", "Açúcar", "Adoçante", "Copos descartáveis", "Xaropes"],
    "cantina": ["Massas", "Molho de Tomate", "Queijo Ralado", "Embalagens"],
    "churrascaria": ["Linguiça", "Picanha", "Alcatra", "Carvão", "Sal Grosso", "Espetos", "Costela", "Fraldinha"],
    "churrasco": ["Linguiça", "Picanha", "Alcatra", "Carvão", "Sal Grosso"],
    "confeitaria": ["Farinha", "Açúcar", "Ovos", "Leite Condensado", "Chocolate", "Manteiga", "Fermento"],
    "conveniencia": ["Cerveja", "Refrigerante", "Salgadinhos", "Gelo", "Carvão"],
    "distribuidora": ["Cerveja", "Refrigerante", "Gelo", "Água", "Carvão"],
    "doceria": ["Chantilly", "Leite Condensado", "Chocolate", "Confeitos", "Formas", "Açúcar"],
    "espetinho": ["Linguiça", "Carne", "Frango", "Carvão", "Sal Grosso"],
    "fitness": ["Mix de folhas", "Molhos prontos", "Proteína grelhada", "Embalagens biodegradáveis"],
    "food truck": ["Embalagens take-away", "Guardanapos", "Descartáveis", "Molhos"],
    "hamburguer": ["Hambúrguer", "Cheddar", "Bacon", "Pão de Hambúrguer", "Maionese Artesanal"],
    "hotel": ["Café", "Açúcar", "Adoçante", "Produtos de Limpeza", "Descartáveis", "Amenities"],
    "italiano": ["Macarrão", "Molho", "Azeite", "Queijo Parmesão", "Manjericão", "Vinho"],
    "japones": ["Salmão", "Cream Cheese", "Shoyu", "Wasabi", "Gengibre", "Arroz Japonês", "Alga Nori"],
    "lanches": ["Hambúrguer", "Batata Frita", "Cheddar", "Maionese", "Ketchup", "Pão de Hambúrguer", "Bacon"],
    "massa": ["Farinha", "Ovos", "Molho de Tomate", "Parmesão", "Manjericão"],
    "mexicano": ["Tortilha", "Guacamole", "Pimenta", "Nachos", "Feijão Mexicano", "Carne Moída"],
    "padaria": ["Pão Francês", "Leite", "Manteiga", "Presunto", "Queijo", "Café", "Farinha"],
    "panificadora": ["Farinha", "Fermento", "Ovos", "Leite", "Margarina", "Embalagens de Pão"],
    "pastel": ["Massa de Pastel", "Carne Moída", "Queijo", "Caldo de Cana", "Óleo"],
    "pastelaria": ["Massa de Pastel", "Carne Moída", "Queijo", "Caldo de Cana", "Óleo", "Embalagens"],
    "peixaria": ["Peixe Fresco", "Gelo", "Limão", "Embalagens", "Sacos de Gelo"],
    "pizza": ["Calabresa", "Muçarela", "Presunto", "Molho de Tomate", "Manjericão"],
    "pizzaria": ["Calabresa", "Muçarela", "Presunto", "Molho de Tomate", "Azeitona", "Orégano", "Farinha", "Fermento"],
    "pousada": ["Café", "Leite", "Pão", "Produtos de Limpeza", "Lençóis", "Descartáveis"],
    "produtos naturais": ["Grãos", "Castanhas", "Farinha Integral", "Temperos", "Frutas Secas"],
    "pub": ["Cerveja Artesanal", "Gelo", "Amendoim", "Batata Frita", "Hambúrguer"],
    "restaurante": ["Arroz", "Feijão", "Óleo", "Tempero", "Embalagens", "Descartáveis"],
    "sorveteria": ["Sorvete", "Calda", "Casquinha", "Granulado", "Marshmallow"],
    "sushi": ["Salmão", "Cream Cheese", "Shoyu", "Wasabi", "Gengibre", "Arroz Japonês", "Alga Nori"],
    "taco": ["Tortilha", "Queijo", "Pimenta", "Carne Moída"],
    "temaki": ["Salmão", "Cream Cheese", "Shoyu", "Alga Nori"]
                }
                
                for chave, itens_sugeridos in regras_segmento.items():
                    if chave in nome_limpo_cli: sugestoes_segmento.extend(itens_sugeridos)
                
                produtos_ja_comprados = set(df_cli['Produto'].unique())
                produto_campeao = rank_p.iloc[0]['Produto'] if not rank_p.empty else None
                sugestoes_similaridade = []
                
                if produto_campeao:
                    compradores_mesmo_item = df_total[(df_total['Produto'] == produto_campeao) & (df_total['Cliente'] != c_sel)]['Cliente'].unique()
                    if len(compradores_mesmo_item) > 0:
                        df_parecidos = df_total[(df_total['Cliente'].isin(compradores_mesmo_item)) & (~df_total['Produto'].isin(produtos_ja_comprados))]
                        if not df_parecidos.empty:
                            sugestoes_similaridade = df_parecidos.groupby('Produto')['Faturamento Brut'].sum().nlargest(5).index.tolist()
                
                todas_sugestoes_brutas = list(set(sugestoes_segmento + sugestoes_similaridade))
                ofertas_memoria = st.session_state.memoria_ofertas_cruas_dia + st.session_state.memoria_ofertas_cruas_rel
                
                lista_venda_final = []
                
                for item in todas_sugestoes_brutas:
                    item_limpo = limpar_texto(item)
                    achou_oferta = False
                    for of_linha in ofertas_memoria:
                        if all(p in limpar_texto(of_linha) for p in extrair_palavras_produto(item)):
                            lista_venda_final.append(f"▪️ {of_linha} (Oferta do Dia)")
                            achou_oferta = True
                            break
                    if not achou_oferta and item not in produtos_ja_comprados:
                        lista_venda_final.append(f"▪️ {item}")
                        
                if not lista_venda_final and ofertas_memoria:
                    for of_linha in ofertas_memoria[:4]:
                        lista_venda_final.append(f"▪️ {of_linha} (Oferta do Dia)")
                
                msg_cross = f"Separei essas sugestões ideais para complementar seu pedido hoje:\n\n"
                for item_final in lista_venda_final:
                    msg_cross += f"{item_final}\n"
                
                st.text_area("Mensagem Enxuta para Whatsapp:", value=msg_cross, height=180)
            else:
                st.warning("Cliente não encontrado.")
                
    elif st.session_state.sub_aba_consulta == "📦 Por Produto":
        st.subheader("Análise por Produto")
        input_prod = st.text_input("Nome do produto:").strip()
        
        if input_prod:
            filtrados_p = filtrar_por_palavras(df_total, 'Produto_Busca', input_prod)
            
            if not filtrados_p.empty:
                st.write(f"✅ Encontrados **{len(filtrados_p['Produto'].unique())}** produtos semelhantes.")
                
                st.markdown("### Top 10 Compradores deste Item")
                top_compradores = filtrados_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).reset_index()
                
                for idx, row in top_compradores.iterrows():
                    st.markdown(f"**{row['Cliente']}** - R$ {row['Faturamento Brut']:,.2f}")
            else:
                st.warning("Nenhum produto encontrado com este nome.")
