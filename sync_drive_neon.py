import os
import gdown

# Conexões via variáveis de ambiente (URLs e senhas ficam ocultas no GitHub)
NEON_DB_URL = os.environ.get("NEON_DB_URL")
DRIVE_VENDAS = os.environ.get("DRIVE_VENDAS")
DRIVE_CADASTRO = os.environ.get("DRIVE_CADASTRO")

# Diretórios locais onde os arquivos serão salvos temporariamente na nuvem
PASTA_VENDAS_LOCAL = "./dados_vendas"
PASTA_CADASTRO_LOCAL = "./dados_cadastro"

def sincronizar_drive():
    # Sincroniza a pasta de Vendas
    if DRIVE_VENDAS:
        print("Sincronizando pasta de Vendas do Google Drive...")
        gdown.download_folder(
            url=DRIVE_VENDAS,
            output=PASTA_VENDAS_LOCAL,
            quiet=False
        )
    else:
        print("Erro: Variável de ambiente DRIVE_VENDAS não encontrada.")

    # Sincroniza a pasta de Cadastro
    if DRIVE_CADASTRO:
        print("Sincronizando pasta de Cadastro do Google Drive...")
        gdown.download_folder(
            url=DRIVE_CADASTRO,
            output=PASTA_CADASTRO_LOCAL,
            quiet=False
        )
    else:
        print("Erro: Variável de ambiente DRIVE_CADASTRO não encontrada.")

if __name__ == "__main__":
    sincronizar_drive()
