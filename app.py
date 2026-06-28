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
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7]

# --- CONTROLE E AUTO-LIMPEZA DIÁRIA DA MEMÓRIA ---
if 'data_ultimo_acesso' not in st.session_state:
    st.session_state.data_ultimo_acesso = data_hoje_str

if st.session_state.data_ultimo_acesso != data_hoje_str:
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()
    st.session_state.envios_hoje = 0  # Zera o contador de envios do dia à meia-noite
    st.session_state.data_ultimo_acesso = data_hoje_str

if 'fila_ofertas_dia' not in st.session_state: st.session_state.fila_ofertas_dia = None
if 'fila_ofertas_relampago' not in st.session_state: st.session_state.fila_ofertas_relampago = None
if 'excluidos_ofertas_dia' not in st.session_state: st.session_state.excluidos_ofertas_dia = set()
if 'excluidos_ofertas_relampago' not in st.session_state: st.session_state.excluidos_ofertas_relampago = set()
if 'busca_direta_cliente' not in st.session_state: st.session_state.busca_direta_cliente = ""
if 'sub_aba_consulta' not in st.session_state: st.session_state.sub_aba_consulta = "👤 Por Cliente"
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"
if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = 0
if 'excluidos_permanente' not in st.session_state: st.session_state.excluidos_permanente = set()

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

@st.cache_data(ttl=120)
def analisar_carteira_clientes(df, df_mes, data_hoje):
    mapa = {}
    ultimas_compras = df.groupby('Cliente')['Data_Datetime'].max().to_dict()
    
    for cli in df['Cliente'].unique():
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
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">⚠️ SUMIDO >30D</span>'
    return html

# --- 📊 INDICADORES SUPERIORES ADAPTADOS (Ranking agora é Geral) ---
st.write("---")
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.8])

f2_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 2" in v["tags"])
f6_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 6" in v["tags"])
nao_pos_mes = sum(1 for c, v in dict_carteira.items() if "NÃO POSITIVADO" in v["tags"])

with c1:
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 6px; border-radius: 6px; border-left: 3px solid #00875A; min-height: 55px;">
        <p style="margin:0; font-size:10px; color:#555; font-weight:bold;">🟢 Posit. FL2</p>
        <h4 style="margin:0; font-size:14px; color:#111; font-weight:bold;">{f2_pos} Cli</h4>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 6px; border-radius: 6px; border-left: 3px solid #FF8B00; min-height: 55px;">
        <p style="margin:0; font-size:10px; color:#555; font-weight:bold;">🟠 Posit. FL6</p>
        <h4 style="margin:0; font-size:14px; color:#111; font-weight:bold;">{f6_pos} Cli</h4>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 6px; border-radius: 6px; border-left: 3px solid #DE350B; min-height: 55px;">
        <p style="margin:0; font-size:10px; color:#555; font-weight:bold;">🔴 Não Posit.</p>
        <h4 style="margin:0; font-size:14px; color:#111; font-weight:bold;">{nao_pos_mes} Cli</h4>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown("<p style='font-size:11px; margin:0 0 2px 0; color:#555; font-weight:bold;'>🏆 Ranking Geral (Todos os Meses)</p>", unsafe_allow_html=True)
    # REQUISITO ATENDIDO: Ranking calculado sobre a base geral (df_total)
    top_3_geral = df_total.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
    for idx, p in enumerate(top_3_geral, 1):
        st.markdown(f"<p style='font-size:11px; margin:1px 0; font-weight:bold; color:#222; line-height:1.2;'>{idx}° {p}</p>", unsafe_allow_html=True)

st.write("---")

# --- 🚀 NAVEGAÇÃO LADO A LADO DO ASSISTENTE ---
col_nav1, col_nav2, col_nav3 = st.columns(3)

with col_nav1:
    if st.button("🟢 Ofertas", use_container_width=True, type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"):
        st.session_state.aba_atual = "🟢 Ofertas"
        st.rerun()
with col_nav2:
    if st.button("🚨 Alertas", use_container_width=True, type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"):
        st.session_state.aba_atual = "🚨 Alertas"
        st.rerun()
with col_nav3:
    if st.button("🔍 Consulta", use_container_width=True, type="primary" if st.session_state.aba_atual == "🔍 Consulta" else "secondary"):
        st.session_state.aba_atual = "🔍 Consulta"
        st.rerun()

st.write("")

# --- INTERFACES DAS ABAS ---

# 1. ABA OFERTAS WHATSAPP
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    
    # Exibição do contador recomendado
    st.markdown(f"📊 **Progresso de hoje:** Você já realizou **{st.session_state.envios_hoje}** envios de listas com sucesso! 🚀")
    
    tipo_lista = st.radio("Selecione o Canal de Ofertas:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago do Dia"], horizontal=True)
    
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    tipo_msg = "dia" if "☀️" in tipo_lista else "relampago"
    
    with st.expander("📝 Colar / Inserir Novas Ofertas da Lista"):
        txt_novas = st.text_area("Insira o bloco de texto:", height=90, key=f"txt_{id_fila}", placeholder="Ex: 102 - Alcatra - R$ 35,00")
        if st.button("🚀 Processar e Otimizar para Todos os Meses", use_container_width=True, key=f"btn_proc_{id_fila}"):
            if txt_novas.strip():
                linhas = [l.strip() for l in txt_novas.split('\n') if l.strip()]
                
                # Agrupamento feito sobre 'df_total' para capturar compradores de todo o histórico
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
                        # REQUISITO DE EXCLUSÃO INTELIGENTE: Se foi excluído manualmente da base, mas comprou no mês atual, ele volta automaticamente!
                        if cli in st.session_state.excluidos_permanente:
                            if cli in clientes_com_compra_mes_atual:
                                st.session_state.excluidos_permanente.remove(cli)
                            else:
                                continue
                                
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                st.success("Lista vinculada com histórico completo!")
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info(f"Nenhum cliente na fila de {tipo_lista} no momento.")
    else:
        clientes_restantes = list(fila_ativa.keys())
        st.markdown(f"🎯 Clientes restantes na Fila: **{len(clientes_restantes)}**")
        
        cliente_atual = clientes_restantes[0]
        ofertas_cliente = fila_ativa[cliente_atual]
        mensagem_pronta = gerar_mensagem_humanizada(ofertas_cliente, tipo_msg)
        
        st.markdown(f"<div style='font-size:15px; font-weight:bold;'>🏢 {cliente_atual}</div>", unsafe_allow_html=True)
        st.markdown(obter_badges_html(cliente_atual), unsafe_allow_html=True)
        st.write("")
        
        st.code(mensagem_pronta, language=None)
        
        # REQUISITO ATENDIDO: Três botões lado a lado organizados para celular
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            if st.button("📋 Copiar", use_container_width=True, key=f"copiar_{cliente_atual}"):
                st.toast("Texto copiado! Use o ícone de cópia da caixa preta acima.", icon="💡")
        with col_b2:
            if st.button("✅ Enviado", use_container_width=True, type="primary", key=f"enviado_{cliente_atual}"):
                st.session_state.envios_hoje += 1  # Contabiliza no contador
                st.session_state[id_excluidos].add(cliente_atual)
                del st.session_state[id_fila][cliente_atual]
                st.rerun()
        with col_b3:
            if st.button("❌ Excluir", use_container_width=True, key=f"perma_{cliente_atual}"):
                st.session_state.excluidos_permanente.add(cliente_atual)  # Joga na lista de exclusão permanente
                del st.session_state[id_fila][cliente_atual]
                st.toast(f"{cliente_atual} removido de futuras listas (até que volte a comprar).")
                st.rerun()

# 2. ABA ALERTAS DE CARTEIRA (Relatório automático para o supervisor)
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Exigindo Atenção")
    
    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if "SUMIDO" in dados["tags"]:
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"]})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas).sort_values(by="Dias", ascending=False)
    
    if df_alertas_visuais.empty:
        st.success("Nenhum cliente sumido!")
    else:
        # REQUISITO ATENDIDO: Copiar lista de clientes sumidos formatada com item mais comprado
        st.write("📋 **Relatório para enviar ao Supervisor (Clique no ícone de copiar no canto do quadro abaixo):**")
        texto_relatorio_sup = "RELAÇÃO DE CLIENTES SUMIDOS PARA AJUSTE DE DESCONTO:\n\n"
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            df_cli_h = df_total[df_total['Cliente'] == c_nome]
            top_item = df_cli_h.groupby('Produto')['Faturamento Brut'].sum().idxmax() if not df_cli_h.empty else "Sem histórico"
            texto_relatorio_sup += f"· {c_nome}\n  ↳ Sem comprar há: {row['Dias']} dias\n  ↳ Item predileto: {top_item}\n\n"
            
        st.code(texto_relatorio_sup, language=None)
        
        st.write("---")
        st.write("👇 **Ações individuais por cliente:**")
        for idx, row in df_alertas_visuais.head(15).iterrows():
            c_nome = row["Cliente"]
            with st.container():
                st.markdown(f"**🏢 {c_nome}** ({row['Dias']} dias sem comprar)")
                st.markdown(obter_badges_html(c_nome), unsafe_allow_html=True)
                if st.button(f"🔍 Abrir Histórico", key=f"btn_at_{idx}", use_container_width=True):
                    st.session_state.busca_direta_cliente = c_nome
                    st.session_state.sub_aba_consulta = "👤 Por Cliente"
                    st.session_state.aba_atual = "🔍 Consulta"  
                    st.rerun()

# 3. ABA CONSULTAS (Com Cross-Selling integrado na ficha)
elif st.session_state.aba_atual == "🔍 Consulta":
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
                
                # REQUISITO ATENDIDO: Geração da Oferta de Venda Cruzada (Cross-Selling) na própria Ficha do Cliente
                st.write("---")
                st.markdown("### 💡 Sugestão de Venda Cruzada (Cross-Selling)")
                
                item_forte = rank_p.iloc[0]['Produto'] if not rank_p.empty else "seus cortes tradicionais"
                
                # Regra: tentar buscar se o cliente tem algum item na fila ativa de ofertas para cruzar, caso contrário pega o Top 1 Geral
                item_sugerido_cross = top_3_geral[0]
                if st.session_state.fila_ofertas_dia and c_sel in st.session_state.fila_ofertas_dia:
                    item_sugerido_cross = st.session_state.fila_ofertas_dia[c_sel][0]
                elif st.session_state.fila_ofertas_relampago and c_sel in st.session_state.fila_ofertas_relampago:
                    item_sugerido_cross = st.session_state.fila_ofertas_relampago[c_sel][0]
                
                msg_cross = (
                    f"Olá! Tudo bem?\n\n"
                    f"Reparei aqui no sistema que você tem uma saída excelente de *{item_forte}* conosco.\n\n"
                    f"Pensando em aumentar a sua margem e trazer uma novidade para o seu balcão, separei uma oportunidade especial hoje para o item *{item_sugerido_cross}*.\n\n"
                    f"Conseguimos uma condição diferenciada para faturar junto com os seus produtos habituais de carga. O que acha de colocar um lote desse para testarmos?"
                )
                
                st.write("Arraste para o lado ou clique no canto para copiar a mensagem pronta:")
                st.code(msg_cross, language=None)
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
