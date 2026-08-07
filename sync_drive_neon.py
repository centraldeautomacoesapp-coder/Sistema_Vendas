import os
import glob
import gdown
import pandas as pd
from sqlalchemy import create_engine

# Conexões via variáveis de ambiente
NEON_DB_URL = os.environ.get("NEON_DB_URL")
DRIVE_VENDAS = os.environ.get("DRIVE_VENDAS")
DRIVE_CADASTRO = os.environ.get("DRIVE_CADASTRO")

PASTA_VENDAS_LOCAL = "./dados_vendas"
PASTA_CADASTRO_LOCAL = "./dados_cadastro"

def sincronizar_drive():
    """Baixa as pastas do Google Drive"""
    if DRIVE_VENDAS:
        print("Sincronizando pasta de Vendas do Google Drive...")
        gdown.download_folder(url=DRIVE_VENDAS, output=PASTA_VENDAS_LOCAL, quiet=False)
    else:
        print("Aviso: Variável DRIVE_VENDAS não encontrada.")

    if DRIVE_CADASTRO:
        print("Sincronizando pasta de Cadastro do Google Drive...")
        gdown.download_folder(url=DRIVE_CADASTRO, output=PASTA_CADASTRO_LOCAL, quiet=False)
    else:
        print("Aviso: Variável DRIVE_CADASTRO não encontrada.")

def carregar_dados_para_neon():
    """Lê os arquivos baixados e insere no banco de dados Neon"""
    if not NEON_DB_URL:
        print("Erro: Variável de ambiente NEON_DB_URL não configurada.")
        return

    # Cria conexão com o Neon PostgreSQL
    engine = create_engine(NEON_DB_URL)

    # 1. Processar arquivos de Vendas
    arquivos_vendas = glob.glob(f"{PASTA_VENDAS_LOCAL}/*.csv") + glob.glob(f"{PASTA_VENDAS_LOCAL}/*.xlsx")
    for arquivo in arquivos_vendas:
        print(f"Enviando vendas para o Neon: {arquivo}")
        df = pd.read_csv(arquivo) if arquivo.endswith('.csv') else pd.read_excel(arquivo)
        # Salva na tabela 'vendas'
        df.to_sql('vendas', con=engine, if_exists='replace', index=False)

    # 2. Processar arquivos de Cadastro
    arquivos_cadastro = glob.glob(f"{PASTA_CADASTRO_LOCAL}/*.csv") + glob.glob(f"{PASTA_CADASTRO_LOCAL}/*.xlsx")
    for arquivo in arquivos_cadastro:
        print(f"Enviando cadastro para o Neon: {arquivo}")
        df = pd.read_csv(arquivo) if arquivo.endswith('.csv') else pd.read_excel(arquivo)
        # Salva na tabela 'cadastro'
        df.to_sql('cadastro', con=engine, if_exists='replace', index=False)

    print("Processamento para o Neon concluído!")

if __name__ == "__main__":
    sincronizar_drive()
    carregar_dados_para_neon()
