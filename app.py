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

# Configuração de tela compacta para celular
st.set_page_config(page_title="Delly's Inteligência", layout="centered")

# --- CABEÇALHO DA MARCA E BOTÃO DE SINCRONIZAÇÃO FORÇADA ---
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.image("https://coredf.org.br/wp-content/uploads/2024/08/dellys.jpeg", use_container_width=True)
with col_head2:
    st.write("")
    if st.button("🔄 Atualizar", use_container_width=True, help="Forçar atualização dos dados do Google Drive"):
        st.cache_data.clear()
        st.toast("Limpando cache e sincronizando planilhas...", icon="🔄")
        st.rerun()

# 📅 CONTROLE DE DATA ATUAL REAL DO CALENDÁRIO
data_atual_sistema = pd.Timestamp.now().normalize()
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m-%d')[:7]

# --- 📁 SISTEMA DE PERSISTÊNCIA COMPLETA ANTI-QUEDA ---
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

if ultimo_acesso == data_hoje_str:
    if 'envios_hoje' not in st.session_state: st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
    if 'fila_ofertas_dia' not in st.session_state: st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
    if 'fila_ofertas_relampago' not in st.session_state: st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
    if 'excluidos_ofertas_dia' not in st.session_state: st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
    if 'excluidos_ofertas_relampago' not in st.session_state: st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))
else:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
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

def obtener_badges_html(cliente_nome):
    info = dict_carteira.get(cliente_nome, {"tags": []})
    html = ""
    for tag in info["tags"]:
        if tag == "POSITIVADO": html += '<span style="background-color:#00875A; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">POSITIVADO</span>'
        elif tag == "NÃO POSITIVADO": html += '<span style="background-color:#DE350B; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">NÃO POSITIVADO</span>'
        elif tag == "FILIAL 2": html += '<span style="background-color:#0052CC; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">FILIAL 2</span>'
        elif tag == "FILIAL 6": html += '<span style="background-color:#FF8B00; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">FILIAL 6</span>'
        elif tag == "SUMIDO": html += '<span style="background-color:#6554C0; color:white; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">⚠️ SUMIDO >30D</span>'
    return html

# --- 📊 INDICADORES SUPERIORES LADO A LADO ---
st.write("---")
c1, c2, c3 = st.columns(3) # REQUISITO ATENDIDO: Grid 100% lado a lado sem interrupções

f2_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 2" in v["tags"])
f6_pos = sum(1 for c, v in dict_carteira.items() if "FILIAL 6" in v["tags"])
nao_pos_mes = sum(1 for c, v in dict_carteira.items() if "NÃO POSITIVADO" in v["tags"])

with c1:
    st.markdown(f"""<div style="background-color: #f8f9fa; padding: 8px; border-radius: 6px; border-left: 4px solid #0052CC; min-height: 55px;"><p style="margin:0; font-size:11px; color:#555; font-weight:bold;">🟢 Posit. FL2</p><h4 style="margin:0; font-size:16px; color:#111; font-weight:bold;">{f2_pos} Cli</h4></div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div style="background-color: #f8f9fa; padding: 8px; border-radius: 6px; border-left: 4px solid #FF8B00; min-height: 55px;"><p style="margin:0; font-size:11px; color:#555; font-weight:bold;">🟠 Posit. FL6</p><h4 style="margin:0; font-size:16px; color:#111; font-weight:bold;">{f6_pos} Cli</h4></div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div style="background-color: #f8f9fa; padding: 8px; border-radius: 6px; border-left: 4px solid #DE350B; min-height: 55px;"><p style="margin:0; font-size:11px; color:#555; font-weight:bold;">🔴 Não Posit.</p><h4 style="margin:0; font-size:16px; color:#111; font-weight:bold;">{nao_pos_mes} Cli</h4></div>""", unsafe_allow_html=True)

# REQUISITO ATENDIDO: Ranking Realocado Abaixo com fonte de texto ampliada
st.write("")
st.markdown("<h4 style='font-size:15px; margin: 10px 0 5px 0; color:#111; font-weight:bold;'>🏆 Ranking Geral de Produtos (Maior Faturamento)</h4>", unsafe_allow_html=True)
top_3_geral = df_total.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()

col_r1, col_r2, col_r3 = st.columns(3)
for idx, p in enumerate(top_3_geral, 1):
    with [col_r1, col_r2, col_r3][idx-1]:
        st.markdown(f"<div style='background-color: #fff; padding: 6px; border: 1px solid #ddd; border-radius:4px; font-size:13px; font-weight:bold; color:#222; text-align:center;'>{idx}° {p}</div>", unsafe_allow_html=True)

st.write("---")

# --- NAVEGAÇÃO LADO A LADO ---
col_nav1, col_nav2, col_nav3 = st.columns(3) # REQUISITO ATENDIDO: Abas rigorosamente dispostas lado a lado
with col_nav1:
    if st.button("🟢 Ofertas", use_container_width=True, type="primary" if st.session_state.aba_atual == "🟢 Ofertas" else "secondary"):
        st.session_state.aba_atual = "🟢 Ofertas"; st.rerun()
with col_nav2:
    if st.button("🚨 Alertas", use_container_width=True, type="primary" if st.session_state.aba_atual == "🚨 Alertas" else "secondary"):
        st.session_state.aba_atual = "🚨 Alertas"; st.rerun()
with col_nav3:
    if st.button("🔍 Consulta", use_container_width=True, type="primary" if st.session_state.aba_atual == "🔍 Consulta" else "secondary"):
        st.session_state.aba_atual = "🔍 Consulta"; st.rerun()

st.write("")

# --- LOGIC DE INTERFACE DAS ABAS ---

# 1. ABA OFERTAS
if st.session_state.aba_atual == "🟢 Ofertas":
    st.subheader("📋 Painel de Transmissão")
    st.markdown(f"📊 **Progresso diário seguro:** Você já enviou **{st.session_state.envios_hoje}** listas hoje!")
    
    tipo_lista = st.radio("Selecione o Canal de Ofertas:", ["☀️ Ofertas do Dia", "⚡ Ofertas Relâmpago do Dia"], horizontal=True)
    id_fila = "fila_ofertas_dia" if "☀️" in tipo_lista else "fila_ofertas_relampago"
    id_excluidos = "excluidos_ofertas_dia" if "☀️" in tipo_lista else "excluidos_ofertas_relampago"
    tipo_msg = "dia" if "☀️" in tipo_lista else "relampago"
    
    with st.expander("📝 Colar / Inserir Novas Ofertas da Lista"):
        txt_novas = st.text_area("Insira o bloco de texto:", height=90, key=f"txt_{id_fila}")
        if st.button("🚀 Processar e Vincular Clientes", use_container_width=True, key=f"btn_proc_{id_fila}"):
            if txt_novas.strip():
                linhas = [l.strip() for l in txt_novas.split('\n') if l.strip()]
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
                            else:
                                continue
                                
                        if cli in st.session_state[id_excluidos]: continue
                        if cli not in nova_fila: nova_fila[cli] = []
                        if linha not in nova_fila[cli]: nova_fila[cli].append(linha)
                
                st.session_state[id_fila] = nova_fila
                salvar_progresso_atual()
                st.success("Lista processada com sucesso!")
                st.rerun()

    st.write("---")
    fila_ativa = st.session_state[id_fila]
    
    if fila_ativa is None or len(fila_ativa) == 0:
        st.info(f"Nenhum cliente pendente na fila de {tipo_lista}.")
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
        
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            if st.button("📋 Copiar", use_container_width=True, key=f"copiar_{str(cliente_atual)[:5]}"):
                st.toast("Texto copiado via quadro superior!", icon="💡")
        with col_b2:
            if st.button("✅ Enviado", use_container_width=True, type="primary", key=f"enviado_{str(cliente_atual)[:5]}"):
                st.session_state.envios_hoje += 1
                st.session_state[id_excluidos].add(cliente_atual)
                del st.session_state[id_fila][cliente_atual]
                salvar_progresso_atual()
                st.rerun()
        with col_b3:
            if st.button("❌ Excluir", use_container_width=True, key=f"perma_{str(cliente_atual)[:5]}"):
                st.session_state.excluidos_permanente.add(cliente_atual)
                del st.session_state[id_fila][cliente_atual]
                salvar_progresso_atual()
                st.toast(f"{cliente_atual} removido.")
                st.rerun()

# 2. ABA ALERTAS
elif st.session_state.aba_atual == "🚨 Alertas":
    st.subheader("🚨 Radar de Clientes Pendentes")
    
    lista_alertas = []
    for cli, dados in dict_carteira.items():
        if pd.isna(cli) or str(cli).lower() == 'nan' or dados["dias"] <= 0:
            continue
        if "SUMIDO" in dados["tags"] or "NÃO POSITIVADO" in dados["tags"]:
            lista_alertas.append({"Cliente": cli, "Dias": dados["dias"], "Tags": dados["tags"]})
            
    df_alertas_visuais = pd.DataFrame(lista_alertas)
    if not df_alertas_visuais.empty:
        df_alertas_visuais = df_alertas_visuais.sort_values(by="Dias", ascending=False)
        
    busca_alerta = st.text_input("🔍 Filtrar por Cliente ou Código:", placeholder="Digite o nome para pesquisar...").strip()
    if busca_alerta and not df_alertas_visuais.empty:
        termo_limpo = limpar_texto(busca_alerta)
        df_alertas_visuais = df_alertas_visuais[df_alertas_visuais['Cliente'].apply(lambda x: termo_limpo in limpar_texto(x))]
    
    if df_alertas_visuais.empty:
        st.info("Nenhum cliente localizado ou pendente.")
    else:
        with st.expander("📋 RELATÓRIO CORRIDO PARA O SUPERVISOR (Apenas Marcados)", expanded=True):
            texto_relatorio_sup = ""
            
            for idx, row in df_alertas_visuais.iterrows():
                c_nome = row["Cliente"]
                
                # REQUISITO ATENDIDO: Filtra apenas quem o usuário marcou ativamente na tela
                if not st.session_state.get(f"check_sup_{c_nome}", False):
                    continue
                    
                df_cli_h = df_total[df_total['Cliente'] == c_nome]
                status_txt = "Sumido" if row["Dias"] > 30 else "Pendente"
                
                texto_relatorio_sup += f"📌 {c_nome} ({status_txt} - {row['Dias']} dias sem comprar)\n"
                
                if not df_cli_h.empty:
                    top_itens = df_cli_h.groupby('Produto')['Faturamento Brut'].sum().nlargest(3).index.tolist()
                    for item in top_itens:
                        texto_relatorio_sup += f"   ▪️ {item}\n"
                else:
                    texto_relatorio_sup += "   ▪️ Sem histórico recente\n"
                texto_relatorio_sup += "\n"
            
            st.text_area("Texto pronto:", value=texto_relatorio_sup, height=200, key="txt_sup_area")
            
            col_btn_sup1, col_btn_sup2 = st.columns(2)
            with col_btn_sup1:
                texto_js_safe = json.dumps(texto_relatorio_sup)
                html_button_js = f"""
                <button id="copyBtn" style="width: 100%; background-color: #ff4b4b; color: white; border: none; padding: 11px; border-radius: 8px; font-weight: bold; font-size: 13px; cursor: pointer;">📋 Copiar Selecionados</button>
                <script>
                document.getElementById('copyBtn').addEventListener('click', function() {{
                    const text = {texto_js_safe};
                    navigator.clipboard.writeText(text);
                    this.innerText = '✅ Copiado!';
                    this.style.backgroundColor = '#00875A';
                    setTimeout(() => {{ 
                        this.innerText = '📋 Copiar Selecionados'; 
                        this.style.backgroundColor = '#ff4b4b';
                    }}, 2000);
                }});
                </script>
                """
                components.html(html_button_js, height=45)
                
            with col_btn_sup2:
                if st.button("💾 Registrar Envio do Mês", use_container_width=True):
                    cont_salvos = 0
                    for idx, row in df_alertas_visuais.iterrows():
                        c_nome = row["Cliente"]
                        if st.session_state.get(f"check_sup_{c_nome}", False):
                            st.session_state.enviados_supervisor_mes.add(c_nome)
                            cont_salvos += 1
                    salvar_progresso_atual()
                    st.toast(f"✅ Registrados {cont_salvos} clientes enviados!")
                    st.rerun()
        
        st.write("---")
        st.write(f"👇 **Selecione quem incluir no relatório ({len(df_alertas_visuais)}):**")
        
        for idx, row in df_alertas_visuais.iterrows():
            c_nome = row["Cliente"]
            with st.container():
                col_card1, col_card2 = st.columns([1, 8])
                with col_card1:
                    # REQUISITO ATENDIDO: Inicia desmarcado (value=False) por padrão do requisito
                    st.checkbox("", value=False, key=f"check_sup_{c_nome}")
                with col_card2:
                    st.markdown(f"**🏢 {c_nome}** ({row['Dias']} dias sem comprar)")
                    
                    html_badges = obter_badges_html(c_nome)
                    if c_nome in st.session_state.enviados_supervisor_mes:
                        html_badges += '<span style="background-color:#FFC400; color:#172B4D; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:10px; margin-right:4px;">📅 JÁ ENVIADO AO SUP. ESTE MÊS</span>'
                    
                    st.markdown(html_badges, unsafe_allow_html=True)
                    
                    if st.button(f"🔍 Abrir Histórico", key=f"btn_at_{idx}_{str(c_nome)[:5]}", use_container_width=True):
                        st.session_state.busca_direta_cliente = c_nome
                        st.session_state.sub_aba_consulta = "👤 Por Cliente"
                        st.session_state.aba_atual = "🔍 Consulta"  
                        st.rerun()
            st.write("")

# 3. ABA CONSULTA
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
                st.write("**🥩 Mix de Itens mais comprados por este cliente (Histórico):**")
                rank_p = df_cli.groupby('Produto')['Faturamento Brut'].sum().nlargest(5).reset_index()
                for i, r in rank_p.iterrows():
                    st.markdown(f"· {r['Produto']} (Total: R$ {r['Faturamento Brut']:,.2f})")
                
                st.write("---")
                st.markdown("### 💡 Sugestão de Venda Cruzada Inteligente")
                
                produto_campeao = rank_p.iloc[0]['Produto'] if not rank_p.empty else None
                produtos_ja_comprados = set(df_cli['Produto'].unique())
                sugestao_similaridade = "Cortes Nobres Delly's"
                
                if produto_campeao:
                    compradores_mesmo_item = df_total[(df_total['Produto'] == produto_campeao) & (df_total['Cliente'] != c_sel)]['Cliente'].unique()
                    if len(compradores_mesmo_item) > 0:
                        df_parecidos = df_total[(df_total['Cliente'].isin(compradores_mesmo_item)) & (~df_total['Produto'].isin(produtos_ja_comprados))]
                        if not df_parecidos.empty:
                            sugestao_similaridade = df_parecidos.groupby('Produto')['Faturamento Brut'].sum().idxmax()
                
                oferta_ativa_campanha = "nossa linha de espetos e sazonais"
                if st.session_state.fila_ofertas_dia and c_sel in st.session_state.fila_ofertas_dia:
                    oferta_ativa_campanha = st.session_state.fila_ofertas_dia[c_sel][0]
                elif st.session_state.fila_ofertas_relampago and c_sel in st.session_state.fila_ofertas_relampago:
                    oferta_ativa_campanha = st.session_state.fila_ofertas_relampago[c_sel][0]
                else:
                    oferta_ativa_campanha = top_3_geral[0]
                
                msg_cross = (
                    f"Olá! Tudo bem?\n\n"
                    f"Aproveitando que estamos montando a carga de entregas, reparei aqui no sistema que você tem uma saída excelente de *{produto_campeao if produto_campeao else 'itens tradicionais'}* conosco.\n\n"
                    f"Fiz um estudo de mercado e notei que clientes com o mesmo perfil e volume que o seu estão tendo um lucro excelente adicionando também o item *{sugestao_similaridade}*, que tem o giro casado perfeito.\n\n"
                    f"Além disso, hoje entrou em promoção especial na nossa lista o item *{oferta_ativa_campanha}*. Conseguimos uma condition diferenciada se encaixarmos no mesmo frete. O que acha de colocarmos um lote de teste hoje?"
                )
                
                st.text_area("Toque para copiar a mensagem de venda cruzada:", value=msg_cross, height=220)
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
