import streamlit as st
import pandas as pd
import datetime
import urllib.parse

# Configuração da página para formato responsivo (Mobile & Desktop)
st.set_page_config(page_title="Inteligência de Vendas - Delly's", layout="wide", page_icon="🚀")

# --- 1. PERSISTÊNCIA DE DADOS NA MEMÓRIA (SESSION STATE) ---
if 'df_matriz' not in st.session_state:
    # Matriz de cruzamento inicial: Cidades x Dias da Semana (Modificável na tela)
    st.session_state.df_matriz = pd.DataFrame({
        "Cidade": ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Salvador"],
        "Segunda": [True, False, True, False, True],
        "Terça": [False, True, True, False, False],
        "Quarta": [True, False, True, True, False],
        "Quinta": [False, True, False, True, True],
        "Sexta": [True, False, True, False, True]
    })

if 'df_clientes' not in st.session_state:
    # Simulação da base de carteira de clientes vinculados às cidades
    st.session_state.df_clientes = pd.DataFrame({
        "ID": [101, 102, 103, 104, 105, 106, 107, 108],
        "Nome": ["Pizzaria do Nonno", "Burguer Mania", "Restaurante Central", "Panificadora Alfa", "Lanches Express", "Cantina Bella", "Sushi Prime", "Supermercado Real"],
        "Cidade": ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "São Paulo", "Curitiba", "Salvador", "Belo Horizonte", "Rio de Janeiro"],
        "Segmento": ["Pizzaria", "Lanches", "Restaurante", "Lanches", "Lanches", "Pizzaria", "Restaurante", "Supermercado"],
        "Status": ["Ativo", "Inativo", "Ativo", "Inativo", "Ativo", "Ativo", "Inativo", "Ativo"],
        "Telefone": ["5511999999999", "5521999999999", "5531999999999", "5511988888888", "5541999999999", "5571999999999", "5531988888888", "5521988888888"]
    })

if 'df_ofertas' not in st.session_state:
    # Tabela de ofertas vigentes e regras de segmentação (Venda Cruzada)
    st.session_state.df_ofertas = pd.DataFrame({
        "Código": ["PROT-01", "QUEI-02", "BEB-03", "MOL-04"],
        "Produto": ["Hambúrguer Bovino Interfolhado 120g", "Queijo Muçarela Barra Rancheiro", "Refrigerante Lata 350ml Caixa c/ 24", "Molho de Tomate Bag 2kg Bonare"],
        "Preço": [189.90, 34.50, 68.00, 14.20],
        "Tipo": ["Diária", "Relâmpago", "Diária", "Relâmpago"],
        "Segmento_Alvo": ["Lanches", "Pizzaria", "Todos", "Pizzaria"]
    })

# --- 2. MOTOR DE DETECÇÃO AUTOMÁTICA DO DIA DA SEMANA ---
DIAS_MAP = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo"
}

# Coleta o dia da semana atual baseado no relógio do sistema/servidor
dia_atual_num = datetime.date.today().weekday()
nome_dia_atual = DIAS_MAP.get(dia_atual_num, "Segunda")

# --- 3. EXECUÇÃO DO CRUZAMENTO EM MEMÓRIA ---
df_matriz_atual = st.session_state.df_matriz

# Captura apenas as cidades marcadas como True (X) na coluna do dia de hoje
if nome_dia_atual in df_matriz_atual.columns:
    cidades_ativas_hoje = df_matriz_atual[df_matriz_atual[nome_dia_atual] == True]["Cidade"].tolist()
else:
    # Fallback para fins de semana (mostra todas as cidades para evitar travamento)
    cidades_ativas_hoje = df_matriz_atual["Cidade"].tolist()

# --- 4. INTERFACE VISUAL DO SISTEMA ---
st.title("📊 Painel Inteligente de Vendas & Rotas")

# Banner dinâmico informando o estado da memória do sistema
st.info(f"📅 **Hoje é {nome_dia_atual}-feira.** O sistema filtrou automaticamente as rotas ativas para: **{', '.join(cidades_ativas_hoje) if cidades_ativas_hoje else 'Nenhuma cidade marcada'}**")

# Divisão das funcionalidades em Abas (Tabs) para melhor scannability
tab_ofertas, tab_carteira, tab_config = st.tabs([
    "💬 Motor de Ofertas (WhatsApp)", 
    "👥 Carteira Filtrada do Dia", 
    "⚙️ Configuração da Matriz"
])

# =========================================================
# ABA 1: MOTOR DE OFERTAS & INTEGRAÇÃO WHATSAPP
# =========================================================
with tab_ofertas:
    st.header("🎯 Geração de Ofertas Direcionadas")
    
    # Filtra os clientes que pertencem APENAS às cidades ativas de hoje
    df_clientes_do_dia = st.session_state.df_clientes[st.session_state.df_clientes["Cidade"].isin(cidades_ativas_hoje)]
    
    if df_clientes_do_dia.empty:
        st.warning("⚠️ Não existem clientes elegíveis para as cidades ativas de hoje. Altere a matriz na aba de Configurações.")
    else:
        # Seleção do cliente
        lista_nomes = df_clientes_do_dia["Nome"].tolist()
        cliente_selecionado = st.selectbox("Selecione o Cliente para atendimento:", lista_nomes)
        
        # Extração dos dados do cliente selecionado para o cruzamento de ofertas
        dados_cliente = df_clientes_do_dia[df_clientes_do_dia["Nome"] == cliente_selecionado].iloc[0]
        segmento = dados_cliente["Segmento"]
        cidade = dados_cliente["Cidade"]
        telefone = dados_cliente["Telefone"]
        
        st.write(f"📍 **Cidade:** {cidade} | 🏷️ **Segmento:** {segmento}")
        
        st.markdown("---")
        st.subheader("📦 Sugestões de Venda Cruzada para este Perfil")
        
        # Filtragem das ofertas: traz o que é do segmento do cliente OU o que serve para "Todos"
        ofertas_sugeridas = st.session_state.df_ofertas[
            (st.session_state.df_ofertas["Segmento_Alvo"] == segmento) | 
            (st.session_state.df_ofertas["Segmento_Alvo"] == "Todos")
        ]
        
        # Checkboxes dinâmicos para o vendedor montar o carrinho de ofertas
        ofertas_escolhidas = []
        for idx, row in ofertas_sugeridas.iterrows():
            tipo_tag = "🔥 [RELÂMPAGO]" if row["Tipo"] == "Relâmpago" else "☀️ [DIÁRIA]"
            label = f"{tipo_tag} {row['Produto']} - Preço: R$ {row['Preço']:.2f}"
            if st.checkbox(label, key=f"oferta_{row['Código']}"):
                ofertas_escolhidas.append(row)
                
        st.markdown("---")
        st.subheader("📝 Mensagem Pronta para Cópia/Envio")
        
        if ofertas_escolhidas:
            # Construção dinâmica do texto com base no dia e escolhas
            texto_base = f"Olá, *{cliente_selecionado}*! Tudo bem?\n\n"
            texto_base += f"Como hoje é *{nome_dia_atual}-feira*, nossa equipe de logística separou ofertas exclusivas com frete garantido para *{cidade}*! 🚀\n\n"
            texto_base += "Confira os destaques que separamos para o seu negócio:\n\n"
            
            for item in ofertas_escolhidas:
                texto_base += f"▪️ *{item['Produto']}*\n"
                texto_base += f"    👉 Por apenas: *R$ {item['Preço']:.2f}*\n\n"
                
            texto_base += "⚠️ _Condições válidas apenas para pedidos fechados hoje enquanto durar o estoque._\n\n"
            texto_base += "Podemos incluir algum destes itens na sua carga de amanhã?"
            
            # Campo de texto editável para ajustes manuais de última hora
            mensagem_final = st.text_area("Edite o texto se achar necessário:", value=texto_base, height=200)
            
            # Geração do link direto do WhatsApp
            texto_codificado = urllib.parse.quote(mensagem_final)
            link_whatsapp = f"https://api.whatsapp.com/send?phone={telefone}&text={texto_codificado}"
            
            st.link_button("📲 Disparar via WhatsApp Web", link_whatsapp, type="primary", use_container_width=True)
        else:
            st.caption("Marque pelo menos uma oferta acima para estruturar o texto da mensagem.")

# =========================================================
# ABA 2: CARTEIRA FILTRADA DO DIA (VISÃO GERAL DO SUPERVISOR)
# =========================================================
with tab_carteira:
    st.header(f"👥 Clientes Atendidos Hoje ({nome_dia_atual}-feira)")
    st.markdown("Esta lista mostra todos os clientes que estão na rota do dia atual de acordo com o cruzamento da memória.")
    
    # Exibe a tabela tratada e limpa
    if not df_clientes_do_dia.empty:
        st.dataframe(
            df_clientes_do_dia[["ID", "Nome", "Cidade", "Segmento", "Status"]], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Nenhum cliente ativo para as rotas mapeadas de hoje.")

# =========================================================
# ABA 3: CONFIGURAÇÃO DA MATRIZ (ONDE A SELEÇÃO ACONTECE)
# =========================================================
with tab_config:
    st.header("⚙️ Matriz de Distribuição Semanal")
    st.markdown("Marque ou desmarque as caixas para definir quais cidades são atendidas em quais dias da semana:")
    
    # Aplicação do Componente Data Editor para edição direta da tabela em formato de matriz
    matriz_editada = st.data_editor(
        st.session_state.df_matriz,
        column_config={
            "Cidade": st.column_config.TextColumn("Cidade", disabled=True),
            "Segunda": st.column_config.CheckboxColumn("Segunda-feira", default=False),
            "Terça": st.column_config.CheckboxColumn("Terça-feira", default=False),
            "Quarta": st.column_config.CheckboxColumn("Quarta-feira", default=False),
            "Quinta": st.column_config.CheckboxColumn("Quinta-feira", default=False),
            "Sexta": st.column_config.CheckboxColumn("Sexta-feira", default=False),
        },
        disabled=["Cidade"],
        key="editor_grade_semanal",
        use_container_width=True
    )
    
    # Botão para commitar as alterações na memória do sistema
    if st.button("💾 Aplicar e Atualizar Regras de Oferta", type="secondary"):
        st.session_state.df_matriz = matriz_editada
        st.success("A nova grade foi injetada na memória! Os filtros de ofertas já foram recalculados.")
        st.rerun()
