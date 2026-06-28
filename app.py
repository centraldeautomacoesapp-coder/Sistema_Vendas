import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import random

# Configuração de tela compacta para celular
st.set_page_config(page_title="Delly's Inteligência", layout="centered")

# Cabeçalho da Marca
st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)

# 📅 CONTROLE DE DATA ATUAL REAL DO CALENDÁRIO
data_atual_sistema = pd.Timestamp.now().normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7] # YYYY-MM

# --- CONTROLE E AUTO-LIMPEZA DIÁRIA DA MEMÓRIA (SESSION STATE) ---
if 'data_ultimo_acesso' not in st.session_state:
    st.session_state.data_ultimo_acesso = data_hoje_str

# 🚨 REGRA DA MEIA-NOITE: Se mudou o dia atual, zera as listas automaticamente
if st.session_state.data_ultimo_acesso != data_hoje_str:
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()
    st.session_state.data_ultimo_acesso = data_hoje_str

# Inicialização das variáveis caso não existam
if 'fila_ofertas_dia' not in st.session_state: st.session_state.fila_ofertas_dia = None
if 'fila_ofertas_relampago' not in st.session_state: st.session_state.fila_ofertas_relampago = None
if 'excluidos_ofertas_dia' not in st.session_state: st.session_state.excluidos_ofertas_dia = set()
if 'excluidos_ofertas_relampago' not in st.session_state: st.session_state.excluidos_ofertas_relampago = set()
if 'busca_direta_cliente' not in st.session_state: st.session_state.busca_direta_cliente = ""
if 'sub_aba_consulta' not in st.session_state: st.session_state.sub_aba_consulta = "👤 Por Cliente"

# Funções de padronização de texto
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

# Gerador de Mensagens atemporais sem dados de robô
def gerar_mensagem_humanizada(ofertas, tipo_lista):
    saudacoes = ["Olá! Tudo bem?", "Buenas! Tudo certo por aí?", "Oi! Como estão as coisas?", "Olá! Passando para te atualizar."]
    
    termo_oferta = "ofertas relâmpago do dia" if tipo_lista == "relampago" else "ofertas do dia"
    
    introducoes = [
        f"Separei aqui com exclusividade as melhores {termo_oferta} que acabaram de sair no nosso sistema:\n\n",
        f"Olha só essas condições especiais e {termo_oferta} separadas para o seu estoque:\n\n",
        f"Dá uma olhada de primeira mão nas {termo_oferta} que temos hoje:\n\n"
    ]
    fechamentos = [
        "\n\nMe avisa aqui se posso garantir o seu pedido antes que acabe o estoque! 👍",
        "\n\nSe precisar de algum desses itens, é só me mandar as quantidades por aqui. Abraço!",
        "\n\nFico à disposição para lançar seu pedido. Qual vamos aproveitar hoje? 🚀"
    ]
    msg = f"{random.choice(saudacoes)} {random.choice(introducoes)}"
    for of in ofertas:
        msg += f"👉 {of}\n"
    msg += random.choice(fechamentos)
    return msg

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

df_mes_atual = df_total[df_total['Ano_Mes'] == mes_atual_referencia[:7]]

# --- REGRAS DE NEGÓCIO DA CARTEIRA DE CLIENTES ---
@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    
    for cli in df['Cliente'].unique():
        tags = []
        dt_ult = ultimas_compras.get(cli, data_hoje)
        dias_sem_compra = (data_hoje - dt_ult).days
        
        # Regra de Positivação Semanal/Mensal integrada
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

# Conversores Visuais em HTML Quadrado Puro
def obter_badges_html(cliente_nome):
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = ""
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">⚠️ SUMIDO >30D</span>'
    return html

# --- PAINEL DE MÉTRICAS COMPACTO MÓVEL ---
st.write("---")
c1, c2, c3 = st.columns(3)
with c1:
    f2_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 2" in v["tags"])
    st.metric("🟢 Posit. FL2", f"{f2_pos} Cli")
with c2:
    f6_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 6" in v["tags"])
    st.metric("🟠 Posit. FL6", f"{f6_pos} Cli")
with c3:
    st.markdown("<p style='font-size:14px; margin-bottom:2px; color:gray;'>🏆 Ranking de Produtos</p>", unsafe_allow_html=True)
    top_3_mes = df_mes_atual.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
    for idx, p in enumerate(top_3_mes, 1):
        st.markdown(f"<p style='font-size:11px; margin:0; font-weight:bold;'>{idx}° {str(p)[:12]}...</p>", unsafe_allow_html=True)

st.write("---")

# --- GERENCIADOR DE ABAS PRINCIPAIS (MAX 3 - CABE NO CELULAR) ---
aba1, aba2, aba3 = st.tabs(["🟢 Ofertas WhatsApp", "🚨 Alertas", "🔍 Consulta"])

# --- TAB 1: OFERTAS WHATSAPP ---
with aba1:
    st.subheader("📋 Painel de Transmissão")
    
    # Seletor Duplo Isolado (Dividido em duas listas independentes)
    tipo_lista = st.radio("Selecione o Canal de Ofertas:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago do Dia"], horizontal=True)
    
    # Define as variáveis dinamicamente baseadas na escolha do usuário
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    tipo_msg = "dia" if "☀️" in tipo_lista else "relampago"
    
    # Caixa retrátil para cadastrar/atualizar lista sem estragar o espaço útil da tela
    with st.expander("📝 Colar / Inserir Novas Ofertas da Lista"):
        txt_novas = st.text_area("Insira o bloco de texto:", height=90, key=f"txt_{id_fila}", placeholder="Ex: 102 - Alcatra - R$ 35,00")
        if st.button("🚀 Processar e Atualizar esta Lista", use_container_width=True, key=f"btn_proc_{id_fila}"):
            if txt_novas.strip():
                linhas = [l.strip() for l in txt_novas.split('\n') if l.strip()]
                prod_to_clientes = df_total.groupby('Produto')['Cliente'].unique().to_dict()
                prod_busca = {p: limpar_texto(p) for p in prod_to_clientes.keys()}
                
                nova_fila = {}
                for linha in linhas:
                    chaves = extrair_palavras_produto(linha)
                    if not chaves: continue
                    combs = [orig for orig, busca in prod_busca.items() if all(c in busca for c in chaves)]
                    
                    interessados = set()
                    for c in combs: interessados.update(prod_to_clientes[c])
                    
                    for cli in interessados:
                        # Respeita a lista de exclusão do dia corrente daquela fila específica
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                st.success("Lista processada! Fila atualizada abaixo.")
                st.rerun()

    # --- PROCESSAMENTO INDEPENDENTE DA FILA SELECIONADA ---
    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info(f"Nenhum cliente na fila de {tipo_lista} no momento.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Clientes na Fila desta lista: **{len(clientes_restantes)}**")
        
        cliente_atual = clientes_restantes[0]
        ofertas_cliente = fila_ativa[cliente_atual]
        mensagem_pronta = gerar_mensagem_humanizada(ofertas_cliente, tipo_msg)
        
        st.markdown(f"<div style='font-size:15px; font-weight:bold;'>🏢 {cliente_atual}</div>", unsafe_allow_html=True)
        st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
        st.write("")
        
        st.code(mensagem_pronta, language=None)
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("📋 Copiado!", use_container_width=True, key=f"copiar_{cliente_atual}"):
                st.toast("Texto pronto! Utilize o ícone na caixa preta acima.", icon="💡")
        with col_b2:
            # Botão excluir remove o cliente da fila ativa e guarda na exclusão daquela lista específica
            if st.button("❌ Concluído / Próximo", use_container_width=True, type="primary", key=f"excluir_{cliente_atual}"):
                st.session_state[id_excluidos].add(cliente_atual)
                del st.session_state[id_fila][cliente_atual]
                st.rerun()

# --- TAB 2: ALERTAS DE CARTEIRA ---
with aba2:
    st.subheader("🚨 Radar de Clientes Exigindo Atenção")
    
    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if "NÃO POSITIVADO" in dados["tags"] or "SUMIDO" in dados["tags"]:
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"]})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas).sort_values(by="Dias", ascending=False)
    
    if df_alertas_visuais.empty:
        st.success("Carteira 100% em dia e positivada!")
    else:
        for idx, row in df_alertas_visuais.head(15).iterrows():
            c_nome = row["Cliente"]
            with st.container():
                st.markdown(f"**🏢 {c_nome}** ({row['Dias']} dias sem comprar)")
                st.markdown(obter_badges_html(c_nome), unsafe_allow_html=True)
                
                # Atalho Direto Inteligente para a aba de Consulta (Raio-X)
                if st.button(f"🔍 Abrir Histórico de {str(c_nome)[:15]}...", key=f"btn_at_{idx}", use_container_width=True):
                    st.session_state.busca_direta_cliente = c_nome
                    st.session_state.sub_aba_consulta = "👤 Por Cliente"
                    st.toast("Gatilho carregado! Vá para a aba Consulta.")

# --- TAB 3: CONSULTAS (SUB-SELETOR INTERNO) ---
with aba3:
    st.session_state.sub_aba_consulta = st.radio("Selecione o tipo de consulta:", ["👤 Por Cliente", "📦 Por Produto"], horizontal=True)
    st.write("---")
    
    if st.session_state.sub_aba_consulta == "👤 Por Cliente":
        st.subheader("Raio-X de Compras do Cliente")
        
        input_busca = st.text_input("Digite o nome ou código do cliente:", value=st.session_state.busca_direta_cliente).strip()
        
        if input_busca:
            filtrados = filtrar_por_palavras(df_total, 'Cliente_Busca', input_busca)
            nomes_encontrados = filtrados['Cliente'].unique()
            
            if len(nomes_encontrados) > 0:
                c_sel = st.selectbox("Selecione o cliente correto:", nomes_encontrados)
                st.markdown(f"### Ficha: {c_sel}")
                st.markdown(obter_badges_html(c_sel), unsafe_allow_html=True)
                
                df_cli = df_total[df_total['Cliente'] == c_sel]
                st.write("**🥩 Mix de Itens mais comprados por este cliente:**")
                rank_p = df_cli.groupby('Produto')['Faturamento Brut'].sum().nlargest(8).reset_index()
                for i, r in rank_p.iterrows():
                    st.markdown(f"· {r['Produto']} (Total: R$ {r['Faturamento Brut']:,.2f})")
            else:
                st.warning("Nenhum cliente localizado.")
                
    elif st.session_state.sub_aba_consulta == "📦 Por Produto":
        st.subheader("Análise Geral de Venda por Produto")
        input_prod = st.text_input("Digite o nome do produto:").strip()
        
        if input_prod:
            filtrados_p = filtrar_por_palavras(df_total, 'Produto_Busca', input_prod)
            if not filtrados_p.empty:
                st.write("**🏆 Maiores Compradores deste Item:**")
                rank_c = filtrados_p.groupby('Cliente')['Faturamento Brut'].sum().nlargest(10).reset_index()
                for i, r in rank_c.iterrows():
                    st.markdown(f"👤 {r['Cliente']} (R$ {r['Faturamento Brut']:,.2f})")
                    st.markdown(obter_badges_html(r['Cliente']), unsafe_allow_html=True)
            else:
                st.warning("Nenhum produto localizado.")
