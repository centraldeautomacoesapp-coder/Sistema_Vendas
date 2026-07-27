import streamlit as st
import pandas as pd
import json
import re
from sqlalchemy import create_engine, text
import google.generativeai as genai

# ==========================================
# CONFIGURAÇÕES DA PÁGINA
# ==========================================
st.set_page_config(page_title="Gerador de Ofertas v1.2", layout="wide")

# Configuração do Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    st.error("Chave da API do Gemini não encontrada nos Secrets.")

# ==========================================
# DICIONÁRIO DE SEGMENTOS PADRÃO
# ==========================================
regras_segmento_padrao = {
    # --- FOODSERVICE & LANCHES ---
    "acai": ["Açaí", "Granola", "Leite Condensado", "Morango", "Banana", "Leite em pó", "Xarope de Guaraná", "Embalagens Térmicas", "Colheres Descartáveis", "Creme de Avelã", "Paçoca Rolha"],
    "burguer": ["Preparado Sabor Cheddar", "Catchup/Maionese Sachê", "Bacon Fatiado", "Batata Fininhas", "Hambúrguer", "Pão de Hambúrguer", "Anéis de Cebola", "Empanados", "Embalagem Kraft", "Papel Acoplado"],
    "hamburguer": ["Preparado Sabor Cheddar", "Catchup/Maionese Sachê", "Bacon Fatiado", "Batata Fininhas", "Hambúrguer", "Pão de Hambúrguer", "Anéis de Cebola", "Empanados", "Embalagem Kraft", "Papel Acoplado"],
    "lanches": ["Batata 9mm", "Batata Surecrisp", "Requeijão Cheddar", "Anéis de Cebola", "Frango Sassami", "Linguiça Toscana", "Pão de Cachorro Quente", "Saches de Molho", "Embalagens", "Guardanapos"],
    "pastel": ["Requeijão Bisnaga", "Energéticos", "Catchup", "Óleo de Soja", "Óleo de Algodão", "Massa de Pastel", "Carne Moída", "Bobina de Papel Toalha", "Caldo de Cana"],
    "pastelaria": ["Requeijão Bisnaga", "Energéticos", "Catchup", "Óleo de Soja", "Óleo de Algodão", "Massa de Pastel", "Carne Moída", "Bobina de Papel Toalha", "Caldo de Cana"],
    "food truck": ["Embalagens", "Guardanapos", "Descartáveis", "Molhos em Sachê", "Batata Congelada", "Bacon", "Refrigerante Lata", "Água Mineral"],

    # --- RESTAURANTES TÍPICOS ---
    "japones": ["Alga Nori", "Guioza", "Farinha Panko", "Cream Cheese", "Salmão", "Camarão", "Goiabada", "Shoyu", "Wasabi", "Gengibre", "Arroz Japonês", "Embalagens"],
    "sushi": ["Alga Nori", "Guioza", "Farinha Panko", "Cream Cheese", "Salmão", "Camarão", "Goiabada", "Shoyu", "Wasabi", "Gengibre", "Arroz Japonês", "Embalagens"],
    "temaki": ["Alga Nori", "Farinha Panko", "Cream Cheese", "Salmão", "Camarão", "Shoyu", "Cebolinha", "Embalagens"],
    "italiano": ["Mandioca Noisette", "Polenta", "Batata", "Queijo Parmesão", "Macarrão", "Molho de Tomate", "Azeite", "Manjericão", "Vinho Tinto", "Farinha de Trigo"],
    "cantina": ["Mandioca", "Polenta", "Batata", "Queijo Parmesão", "Macarrão", "Molho de Tomate", "Azeite", "Manjericão"],
    "massa": ["Farinha de Trigo", "Ovos", "Molho de Tomate", "Queijo Parmesão", "Manjericão", "Azeite", "Queijo Muçarela"],
    "mexicano": ["Tortilha", "Guacamole", "Pimenta", "Nachos", "Feijão", "Carne Moída", "Cheddar", "Sour Cream"],
    "pizza": ["Farinha de Trigo", "Carne Moída", "Presunto", "Palmito", "Molho de Tomate", "Linguiça Pepperoni", "Alho", "Muçarela", "Orégano", "Caixas para Pizza"],
    "pizzaria": ["Farinha de Trigo", "Carne Moída", "Presunto", "Palmito", "Molho de Tomate", "Linguiça Pepperoni", "Alho", "Muçarela", "Orégano", "Caixas para Pizza", "Carvão", "Lenha"],
    "restaurante": ["Frango", "Queijo Gouda", "Batata Canoa", "Catchup", "Farinha de Trigo", "Queijo Parmesão", "Arroz", "Feijão", "Óleo", "Tempero", "Marmitex"],
    "churrascaria": ["Frango", "Picanha", "Alcatra", "Linguiça Toscana", "Carvão", "Sal Grosso", "Espetos", "Costela", "Fraldinha", "Pão de Alho"],
    "churrasco": ["Linguiça", "Picanha", "Alcatra", "Carvão", "Sal Grosso", "Pão de Alho", "Faca para Carne", "Tábuas"],
    "espetinho": ["Linguiça", "Carne Bovina", "Frango", "Carvão", "Sal Grosso", "Espeto de Bambu", "Mandioca"],

    # --- COMÉRCIO E BEBIDAS ---
    "bar": ["Batata", "Bacon", "Lagarto Bovino", "Queijo Provolone", "Almôndegas", "Cerveja", "Gelo", "Amendoim", "Porções Congeladas", "Energético"],
    "pub": ["Batata", "Bacon", "Lagarto Bovino", "Queijo Provolone", "Cerveja", "Gelo", "Amendoim", "Hambúrguer", "Destilados"],
    "distribuidora": ["Vodka", "Xaropes", "Gin", "Água Tônica", "Cerveja", "Refrigerante", "Gelo", "Carvão", "Copos", "Canudos"],
    "conveniencia": ["Energéticos", "Hot Pocket", "Cerveja", "Refrigerante", "Salgadinhos", "Gelo", "Carvão", "Isqueiros", "Chocolates"],
    "buffet": ["Alcatra", "Maminha", "Frango", "Mandioca", "Requeijão", "Extrato de Tomate", "Farinha Panko", "Feijão", "Descartáveis", "Guardanapos", "Bebidas"],

    # --- PADARIA E DOCES ---
    "padaria": ["Batata", "Refrigerantes", "Patês", "Margarina", "Pão Francês", "Leite", "Café", "Farinha", "Frios", "Muçarela", "Presunto", "Bobina Plástica"],
    "panificadora": ["Batata", "Refrigerantes", "Patês", "Margarina", "Farinha", "Fermento", "Ovos", "Leite", "Embalagens", "Frios"],
    "confeitaria": ["Farinha de Trigo", "Açúcar", "Ovos", "Leite Condensado", "Chocolate", "Margarina", "Fermento", "Chantilly", "Formas"],
    "doceria": ["Chantilly", "Leite Condensado", "Chocolate", "Confeitos", "Formas", "Açúcar", "Embalagens", "Fitas"],
    "cafeteria": ["Energéticos", "Óleo Vegetal", "Café", "Leite", "Açúcar", "Adoçante", "Copos descartáveis", "Xaropes"],
    "sorveteria": ["Petit Gateau", "Muçarela", "Presunto", "Sorvete", "Calda", "Casquinha", "Granulado", "Marshmallow", "Coberturas", "Copos", "Potes"],

    # --- VAREJO E OUTROS ---
    "mercado": ["Pizza Pronta", "Batata Congelada", "Margarina", "Carne Moída", "Arroz", "Feijão", "Óleo", "Açúcar", "Café", "Macarrão", "Biscoito"],
    "mercearia": ["Pizza Pronta", "Batata Congelada", "Margarina", "Carne Moída", "Arroz", "Feijão", "Óleo", "Açúcar", "Café", "Macarrão", "Molho de Tomate"],
    "açougue": ["Bacon Manta", "Frango", "Muçarela", "Moela", "Queijo Parmesão", "Bandejas", "Papel Filme", "Facas", "Sacos plásticos"],
    "peixaria": ["Salmão", "Tilápia", "Lula", "Camarão", "Peixe Fresco", "Gelo", "Limão", "Embalagens", "Farinha para Empanar"],
    "produtos naturais": ["Grãos", "Castanhas", "Farinha Integral", "Temperos", "Frutas Secas", "Aveia", "Mel", "Óleo de Coco", "Embalagens Pouch"],
    "fitness": ["Mix de folhas", "Molhos prontos", "Proteína", "Embalagens", "Batata Doce", "Frango Desfiado", "Ovos"],
    "hotel": ["Massa Lasanha", "Presunto", "Muçarela", "Frango", "Batata", "Cream Cheese", "Café", "Açúcar", "Adoçante", "Produtos de Limpeza", "Amenities"],
    "pousada": ["Lasanha", "Frios", "Frango", "Batata", "Cream Cheese", "Café", "Leite", "Pão", "Produtos de Limpeza", "Lençóis", "Descartáveis"]
}

# ==========================================
# FUNÇÕES DO BANCO DE DADOS NEON
# ==========================================
def obter_conexao_neon():
    try:
        url = st.secrets["NEON_DATABASE_URL"]
        return create_engine(url)
    except Exception as e:
        st.warning(f"Não foi possível conectar ao Neon: {e}")
        return None

def carregar_regras_segmentos_do_neon():
    engine = obter_conexao_neon()
    regras = regras_segmento_padrao.copy()
    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT segmento, itens FROM segmentos_regras;")).fetchall()
                if res:
                    for row in res:
                        regras[row[0]] = json.loads(row[1])
                else:
                    for seg, itens in regras_segmento_padrao.items():
                        conn.execute(
                            text("INSERT INTO segmentos_regras (segmento, itens) VALUES (:s, :i) ON CONFLICT (segmento) DO NOTHING;"),
                            {"s": seg, "i": json.dumps(itens)}
                        )
                    conn.commit()
        except: pass
    return regras

def salvar_novo_item_segmento_neon(segmento, novo_item):
    engine = obter_conexao_neon()
    if engine:
        try:
            with engine.connect() as conn:
                res = conn.execute(text("SELECT itens FROM segmentos_regras WHERE segmento = :s"), {"s": segmento}).fetchone()
                if res:
                    itens = json.loads(res[0])
                    if novo_item not in itens:
                        itens.append(novo_item)
                        conn.execute(text("UPDATE segmentos_regras SET itens = :i WHERE segmento = :s"), {"i": json.dumps(itens), "s": segmento})
                        conn.commit()
        except: pass

regras_segmento = carregar_regras_segmentos_do_neon()

# ==========================================
# FUNÇÕES DE LÓGICA E GEMINI
# ==========================================
def gerar_texto_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar mensagem: {e}"

def extrair_produtos_da_oferta(texto):
    """Extrai os produtos e preços do texto, ignorando emojis e títulos."""
    linhas = texto.strip().split('\n')
    produtos_ofertados = []
    
    for linha in linhas:
        # Pula linhas muito curtas (possíveis títulos)
        if len(linha.strip()) < 5:
            continue
            
        # Limpa emojis
        linha_limpa = re.sub(r'[^\w\s.,;:R$%-/]', '', linha).strip()
        
        # Se tem R$ e números, assumimos que é um produto
        if "R$" in linha_limpa or re.search(r'\d', linha_limpa):
             produtos_ofertados.append(linha_limpa)
             
    return produtos_ofertados

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
st.title("🎯 Gerador de Ofertas Inteligentes v1.2")

# IMPORTANTE: Aqui você deve usar a SUA função que lê as planilhas do Google Drive
# Abaixo estou simulando o carregamento dos clientes. Se você já tem a função 'carregar_dados()', basta chamá-la.
@st.cache_data
def carregar_clientes_drive():
    # Substitua pelo seu código real que lê as planilhas do Drive
    # O dataframe PRECISA ter as colunas: 'Fantasia', 'Município', 'Segmento', 'Historico_Compras'
    pass

# Simulação temporária (APAGUE E USE O SEU DF REAL):
# df_clientes = carregar_clientes_drive() 
df_clientes = pd.DataFrame({
    'Fantasia': ['Pizzaria do João', 'Burger King', 'Mercadinho São José'],
    'Município': ['Criciúma', 'Içara', 'Criciúma'],
    'Segmento': ['pizzaria', 'hamburguer', 'mercado'],
    'Historico_Compras': ['Farinha, Muçarela, Calabresa', 'Bacon, Pão, Hambúrguer', 'Arroz, Feijão, Óleo']
})

# ==========================================
# FILTRO DE MUNICÍPIOS
# ==========================================
st.markdown("### 📍 Filtro de Localização")
if 'Município' in df_clientes.columns:
    municipios_disponiveis = sorted(df_clientes['Município'].dropna().unique().tolist())
    cidades_selecionadas = st.multiselect(
        "Selecione as Cidades para gerar as ofertas:", 
        options=municipios_disponiveis, 
        default=municipios_disponiveis
    )
    # Filtra o Dataframe
    df_clientes_filtrado = df_clientes[df_clientes['Município'].isin(cidades_selecionadas)]
else:
    st.warning("Coluna 'Município' não encontrada na planilha. Exibindo todos os clientes.")
    df_clientes_filtrado = df_clientes

# ==========================================
# CAIXA DE TEXTO DAS OFERTAS
# ==========================================
st.markdown("### 📝 Cole as ofertas de hoje abaixo:")
texto_colado = st.text_area("Lista do WhatsApp", height=150, help="Cole os produtos. Os títulos serão ignorados automaticamente para evitar erros.")

if st.button("Gerar Mensagens Separadas"):
    if texto_colado and not df_clientes_filtrado.empty:
        produtos_extraidos = extrair_produtos_da_oferta(texto_colado)
        
        st.success(f"✅ {len(produtos_extraidos)} produtos identificados! Gerando mensagens para {len(df_clientes_filtrado)} clientes...")
        st.divider()

        # Loop pelos clientes filtrados
        for index, row in df_clientes_filtrado.iterrows():
            nome = row.get('Fantasia', 'Cliente')
            municipio = row.get('Município', 'Sem Cidade')
            segmento = str(row.get('Segmento', '')).lower().strip()
            historico = str(row.get('Historico_Compras', '')).lower()
            
            itens_regras = regras_segmento.get(segmento, [])
            
            ofertas_recompra = []
            ofertas_novidades = []
            
            # Classificação dos produtos
            for prod in produtos_extraidos:
                prod_lower = prod.lower()
                
                # 1. Verifica se já comprou (Recompra)
                # Pega as primeiras palavras chave do produto para checar histórico
                palavras_chave_prod = prod_lower.split()[:2] 
                ja_comprou = any(palavra in historico for palavra in palavras_chave_prod if len(palavra) > 3)
                
                if ja_comprou:
                    ofertas_recompra.append(prod)
                else:
                    # 2. Verifica se encaixa no segmento (Novidade)
                    encaixa_segmento = any(item_regra.lower() in prod_lower for item_regra in itens_regras)
                    if encaixa_segmento:
                        ofertas_novidades.append(prod)
                        salvar_novo_item_segmento_neon(segmento, prod)
                        
            # Se encontrou alguma coisa, cria o bloco do cliente na tela
            if ofertas_recompra or ofertas_novidades:
                with st.expander(f"🛒 {nome} ({municipio}) - Segmento: {segmento.title()}", expanded=True):
                    
                    col1, col2 = st.columns(2)
                    
                    # CAIXA 1: RECOMPRA
                    with col1:
                        st.markdown("#### 🔄 Já Compra (Reposição)")
                        if ofertas_recompra:
                            lista_re = "\n".join([f"- {p}" for p in ofertas_recompra])
                            prompt_re = f"""
                            Aja como um vendedor simpático de atacado/distribuidora pelo WhatsApp.
                            O cliente '{nome}' já compra esses produtos com você. 
                            Crie uma mensagem curta avisando que esses itens que ele costuma usar estão em OFERTA hoje.
                            Não use títulos de sessão, apenas apresente os produtos e o preço de forma direta e chamativa.
                            Ofertas:
                            {lista_re}
                            """
                            msg_re = gerar_texto_gemini(prompt_re)
                            st.text_area("Copiar Mensagem 1", msg_re, height=250, key=f"re_{index}")
                        else:
                            st.info("Nenhuma oferta bate com o histórico.")
                            
                    # CAIXA 2: NOVIDADES / CROSS-SELL
                    with col2:
                        st.markdown("#### ✨ Novidades (Venda Cruzada)")
                        if ofertas_novidades:
                            lista_nov = "\n".join([f"- {p}" for p in ofertas_novidades])
                            prompt_nov = f"""
                            Aja como um consultor de vendas estratégico pelo WhatsApp.
                            O cliente '{nome}' é do segmento '{segmento}'. Ele NÃO compra esses produtos abaixo.
                            Crie uma mensagem separada sugerindo esses itens como uma excelente novidade ou complemento para o negócio dele, já que estão em oferta.
                            Aja de forma consultiva, dizendo "Separei essas novidades que tem tudo a ver com o seu negócio".
                            Não use títulos de sessão.
                            Ofertas:
                            {lista_nov}
                            """
                            msg_nov = gerar_texto_gemini(prompt_nov)
                            st.text_area("Copiar Mensagem 2", msg_nov, height=250, key=f"nov_{index}")
                        else:
                            st.info("Nenhuma novidade do segmento.")
    else:
        st.warning("Cole as ofertas no campo de texto e verifique se selecionou alguma cidade.")
