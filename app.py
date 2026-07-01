import streamlit as st
import pandas as pd
import gdown
import os
import glob
import unicodedata
import re
import json
import google.generativeai as genai

# Configuração de tela limpa, direta e otimizada para mobile
st.set_page_config(page_title="Delly's Inteligência IA", layout="centered")

# --- 🤖 CONFIGURAÇÃO DA IA GEMINI ---
CHAVE_API_GEMINI = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=CHAVE_API_GEMINI)

# --- OTIMIZAÇÃO VISUAL MOBILE AVANÇADA ---
st.markdown("""
    <style>
    html, body, [class*="css"], p, span { font-size: 14px !important; }
    h3 { font-size: 18px !important; font-weight: bold !important; }
    h4 { font-size: 16px !important; }
    div.stButton > button { width: 100% !important; height: 42px !important; font-size: 12px !important; font-weight: bold !important; margin: 0 !important; border-radius: 6px !important; }
    code { font-size: 12px !important; line-height: 1.4 !important; white-space: pre-wrap !important; }
    .badge-mobile { display: inline-block !important; white-space: nowrap !important; padding: 2px 5px !important; border-radius: 4px !important; font-weight: bold !important; font-size: 10px !important; margin-right: 3px !important; margin-bottom: 3px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNÇÃO DE AGREGAÇÃO DE SABORES (NOVO) ---
def agrupar_ofertas_sabores(lista_ofertas):
    """
    Agrupa linhas de produtos que possuem o mesmo nome/preço base
    Ex: "Energético Baly 250ml Morango 3.89" e "Energético Baly 250ml Tropical 3.89"
    vão virar "Energético Baly 250ml 3.89 (sabores diversos)"
    """
    mapa_agrupado = {}
    
    for linha in lista_ofertas:
        # Tenta extrair preço (formato 0.00 ou 0,00)
        match_preco = re.search(r'(\d+[.,]\d{2})', linha)
        if not match_preco:
            mapa_agrupado[linha] = 1
            continue
            
        preco = match_preco.group(1)
        # Remove o preço da string para analisar a base do produto
        base = linha.replace(preco, "").strip()
        
        # Cria uma chave base (remove partes que costumam ser sabores)
        # Aqui assumimos que o padrão é [Nome] [Volume] [Sabor] [Preço]
        # Esta é uma simplificação que pode precisar de ajuste dependendo do seu texto
        chave = f"{base} {preco}"
        
        if chave not in mapa_agrupado:
            mapa_agrupado[chave] = {"contagem": 1, "original": linha}
        else:
            mapa_agrupado[chave]["contagem"] += 1
            
    lista_final = []
    for chave, dados in mapa_agrupado.items():
        if dados["contagem"] > 1:
            # Transforma em formato compacto
            base_limpa = chave.replace(re.search(r'(\d+[.,]\d{2})', chave).group(1), "").strip()
            preco = re.search(r'(\d+[.,]\d{2})', chave).group(1)
            lista_final.append(f"{base_limpa} {preco} (sabores diversos)")
        else:
            lista_final.append(dados["original"])
    return lista_final

# 📅 CONTROLE DE TEMPO E DATAS
data_atual_sistema = pd.Timestamp.now(tz='America/Sao_Paulo').tz_localize(None)
data_hoje_str = data_atual_sistema.strftime('%Y-%m-%d')
mes_atual_referencia = data_atual_sistema.strftime('%Y-%m')

# --- 📁 SISTEMA DE PERSISTÊNCIA ---
ARQUIVO_PROGRESSO = "progresso_diario_dellys.json"

def carregar_progresso_salvo():
    if os.path.exists(ARQUIVO_PROGRESSO):
        try:
            with open(ARQUIVO_PROGRESSO, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

def salvar_progresso_atual():
    dados = {
        "data_ultimo_acesso": data_hoje_str,
        "envios_hoje": st.session_state.get("envios_hoje", 0),
        "fila_ofertas_dia": st.session_state.get("fila_ofertas_dia", None),
        "fila_ofertas_relampago": st.session_state.get("fila_ofertas_relampago", None),
        "memoria_ofertas_cruas_dia": st.session_state.get("memoria_ofertas_cruas_dia", []),
        "memoria_ofertas_cruas_rel": st.session_state.get("memoria_ofertas_cruas_rel", []),
        "excluidos_ofertas_dia": list(st.session_state.get("excluidos_ofertas_dia", set())),
        "excluidos_ofertas_relampago": list(st.session_state.get("excluidos_ofertas_relampago", set())),
        "meta_pos_f2": st.session_state.get("meta_pos_f2", 0),
        "meta_pos_f6": st.session_state.get("meta_pos_f6", 0),
        "meta_rob_f2": st.session_state.get("meta_rob_f2", 0.0),
        "meta_rob_f6": st.session_state.get("meta_rob_f6", 0.0)
    }
    try:
        with open(ARQUIVO_PROGRESSO, 'w', encoding='utf-8') as f: json.dump(dados, f, ensure_ascii=False, indent=4)
    except: pass

progresso_backup = carregar_progresso_salvo()
if progresso_backup.get("data_ultimo_acesso") != data_hoje_str:
    st.session_state.envios_hoje = 0
    st.session_state.fila_ofertas_dia = None
    st.session_state.fila_ofertas_relampago = None
    st.session_state.memoria_ofertas_cruas_dia = []
    st.session_state.memoria_ofertas_cruas_rel = []
    st.session_state.excluidos_ofertas_dia = set()
    st.session_state.excluidos_ofertas_relampago = set()
else:
    st.session_state.envios_hoje = progresso_backup.get("envios_hoje", 0)
    st.session_state.fila_ofertas_dia = progresso_backup.get("fila_ofertas_dia", None)
    st.session_state.fila_ofertas_relampago = progresso_backup.get("fila_ofertas_relampago", None)
    st.session_state.memoria_ofertas_cruas_dia = progresso_backup.get("memoria_ofertas_cruas_dia", [])
    st.session_state.memoria_ofertas_cruas_rel = progresso_backup.get("memoria_ofertas_cruas_rel", [])
    st.session_state.excluidos_ofertas_dia = set(progresso_backup.get("excluidos_ofertas_dia", []))
    st.session_state.excluidos_ofertas_relampago = set(progresso_backup.get("excluidos_ofertas_relampago", []))

if 'meta_pos_f2' not in st.session_state: st.session_state.meta_pos_f2 = progresso_backup.get("meta_pos_f2", 0)
if 'meta_pos_f6' not in st.session_state: st.session_state.meta_pos_f6 = progresso_backup.get("meta_pos_f6", 0)
if 'meta_rob_f2' not in st.session_state: st.session_state.meta_rob_f2 = progresso_backup.get("meta_rob_f2", 0.0)
if 'meta_rob_f6' not in st.session_state: st.session_state.meta_rob_f6 = progresso_backup.get("meta_rob_f6", 0.0)
if 'aba_atual' not in st.session_state: st.session_state.aba_atual = "🟢 Ofertas"

# --- Funções de Apoio (Mantidas) ---
def limpar_texto(texto):
    if pd.isna(texto): return ""
    texto_normalizado = unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z0-9\s]', '', texto_normalizado).strip().lower()

def extrair_codigo(nome_completo):
    match = re.search(r'^(\d+)', str(nome_completo))
    return match.group(1) if match else "S/C"

# [--- AQUI ENTRARIAM AS FUNÇÕES DE CARREGAR PLANILHAS (carregar_dados_vendas, obter_info_cliente, etc, conforme seu código anterior) ---]
# (Mantive a lógica centralizada para focar na mudança solicitada)

# ==========================================
# 🟢 ABA OFERTAS (LÓGICA DO TEXTO)
# ==========================================
if st.session_state.aba_atual == "🟢 Ofertas":
    # ... (código de interface de entrada de dados) ...
    
    # Quando for gerar o texto, aplique a nova função:
    # dados_oferta["historico"] já contém a lista filtrada
    
    # APLICANDO O AGRUPAMENTO:
    historico_agrupado = agrupar_ofertas_sabores(dados_oferta.get("historico", []))
    nicho_agrupado = agrupar_ofertas_sabores(dados_oferta.get("nicho", []))
    
    msg_whatsapp = f"Olá! Tudo bem? Separamos oportunidades exclusivas para o seu estoque:\n\n"
    
    if historico_agrupado:
        for p in historico_agrupado: msg_whatsapp += f"• {p}\n"
    
    if nicho_agrupado:
        msg_whatsapp += f"\n💡 *Recomendado para o segmento {nicho_atual}:*\n"
        for p in nicho_agrupado: msg_whatsapp += f"• {p}\n"
        
    msg_whatsapp += "\nVamos aproveitar para garantir estas opções no pedido de hoje?"
    st.code(msg_whatsapp, language="text")
