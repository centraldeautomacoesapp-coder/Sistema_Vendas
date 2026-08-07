import os
import glob
import re
import gdown
import pandas as pd
from sqlalchemy import create_engine

# Conexões via variáveis de ambiente
NEON_DB_URL = os.environ.get("NEON_DB_URL")
DRIVE_VENDAS = os.environ.get("DRIVE_VENDAS")
DRIVE_CADASTRO = os.environ.get("DRIVE_CADASTRO")

# Pastas locais temporárias
PASTA_VENDAS_LOCAL = "./dados_vendas"
PASTA_CADASTRO_LOCAL = "./dados_cadastro"

def extrair_id_drive(url_ou_id):
    """Extrai o ID da pasta do Google Drive a partir da URL ou do próprio ID"""
    if not url_ou_id:
        return None
    if "folders/" in url_ou_id:
        match = re.search(r'folders/([a-zA-Z0-9_-]+)', url_ou_id)
        return match.group(1) if match else url_ou_id
    if "id=" in url_ou_id:
        match = re.search(r'id=([a-zA-Z0-9_-]+)', url_ou_id)
        return match.group(1) if match else url_ou_id
    return url_ou_id.strip()

def executar_sincronizacao():
    """Baixa os arquivos do Drive e salva no banco de dados Neon"""
    id_vendas = extrair_id_drive(DRIVE_VENDAS)
    id_cadastro = extrair_id_drive(DRIVE_CADASTRO)

    # 1. Download da pasta de Vendas
    if id_vendas:
        print("Sincronizando pasta de Vendas do Google Drive...")
        gdown.download_folder(id=id_vendas, output=PASTA_VENDAS_LOCAL, quiet=True)
    else:
        print("Aviso: DRIVE_VENDAS não configurado.")

    # 2. Download da pasta de Cadastro
    if id_cadastro:
        print("Sincronizando pasta de Cadastro do Google Drive...")
        gdown.download_folder(id=id_cadastro, output=PASTA_CADASTRO_LOCAL, quiet=True)
    else:
        print("Aviso: DRIVE_CADASTRO não configurado.")

    # 3. Enviar para o banco de dados Neon PostgreSQL
    if not NEON_DB_URL:
        print("Erro: NEON_DB_URL não configurada.")
        return

    # Corrige prefixo da URL caso esteja usando postgres:// em vez de postgresql://
    db_url = NEON_DB_URL.replace("postgres://", "postgresql://")
    engine = create_engine(db_url)

    # Processar e enviar histórico de vendas
    arquivos_vendas = glob.glob(os.path.join(PASTA_VENDAS_LOCAL, "**", "*.xlsx"), recursive=True) + \
                     glob.glob(os.path.join(PASTA_VENDAS_LOCAL, "**", "*.csv"), recursive=True)
    if arquivos_vendas:
        lista_dfs = []
        for arq in arquivos_vendas:
            df = pd.read_csv(arq) if arq.endswith('.csv') else pd.read_excel(arq)
            lista_dfs.append(df)
        df_vendas_total = pd.concat(lista_dfs, ignore_index=True)
        # Substitui a tabela 'vendas' no Neon com os dados atualizados
        df_vendas_total.to_sql('vendas', con=engine, if_exists='replace', index=False)
        print("Tabela 'vendas' atualizada no Neon.")

    # Processar e enviar cadastro de clientes
    arquivos_cadastro = glob.glob(os.path.join(PASTA_CADASTRO_LOCAL, "**", "*.xlsx"), recursive=True) + \
                        glob.glob(os.path.join(PASTA_CADASTRO_LOCAL, "**", "*.csv"), recursive=True)
    if arquivos_cadastro:
        lista_dfs_cad = []
        for arq in arquivos_cadastro:
            df = pd.read_csv(arq) if arq.endswith('.csv') else pd.read_excel(arq)
            lista_dfs_cad.append(df)
        df_cadastro_total = pd.concat(lista_dfs_cad, ignore_index=True)
        # Substitui a tabela 'clientes' no Neon
        df_cadastro_total.to_sql('clientes', con=engine, if_exists='replace', index=False)
        print("Tabela 'clientes' atualizada no Neon.")

if __name__ == "__main__":
    executar_sincronizacao()
