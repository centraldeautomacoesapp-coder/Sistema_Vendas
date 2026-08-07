import os
import glob
import gdown
import pandas as pd
from sqlalchemy import create_engine, text

# Conexões via variáveis de ambiente
NEON_DB_URL = os.environ.get("NEON_DB_URL")
DRIVE_VENDAS = os.environ.get("DRIVE_VENDAS")
DRIVE_CADASTRO = os.environ.get("DRIVE_CADASTRO")

engine = create_engine(NEON_DB_URL)

def inicializar_tabelas():
    with engine.connect() as conn:
        # Tabela para controle de arquivos já lidos
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS historico_uploads (
                nome_arquivo VARCHAR(255) PRIMARY KEY,
                data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        # Tabela unificada de faturamento
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS faturamento (
                id SERIAL PRIMARY KEY,
                dt_delivery VARCHAR(50),
                cliente VARCHAR(255),
                produto VARCHAR(255),
                faturamento_brut NUMERIC,
                filial VARCHAR(50),
                arquivo_origem VARCHAR(255)
            );
        """))

def sincronizar():
    inicializar_tabelas()
    pasta_destino = "./planilhas_temp"
    os.makedirs(pasta_destino, exist_ok=True)

    # 1. Baixar pastas do Drive
    try:
        gdown.download_folder(DRIVE_VENDAS, output=pasta_destino, quiet=True)
        gdown.download_folder(DRIVE_CADASTRO, output=pasta_destino, quiet=True)
    except Exception as e:
        print(f"Erro ao baixar do Drive: {e}")

    arquivos = glob.glob(os.path.join(pasta_destino, "**", "*.xlsx"), recursive=True)

    # 2. Consultar arquivos já importados
    with engine.connect() as conn:
        res = conn.execute(text("SELECT nome_arquivo FROM historico_uploads;")).fetchall()
        processados = {row[0] for row in res}

    # 3. Ler apenas arquivos NOVOS
    for arq in arquivos:
        nome_arq = os.path.basename(arq)
        if nome_arq in processados:
            continue

        print(f"🚀 Importando novo arquivo: {nome_arq}")
        try:
            df = pd.read_excel(arq)
            df.columns = df.columns.str.strip().str.lower()

            c_dt = next((c for c in df.columns if "dt" in c and "entrega" in c), None)
            c_cli = next((c for c in df.columns if "cliente" in c or "nome" in c), None)
            c_prod = next((c for c in df.columns if "produto" in c), None)
            c_fat = next((c for c in df.columns if "faturamento" in c and "brut" in c), None)
            c_fil = next((c for c in df.columns if "filial" in c or "empresa" in c), None)

            if c_dt and c_cli and c_prod and c_fat:
                sel = [c_dt, c_cli, c_prod, c_fat]
                heads = ['dt_delivery', 'cliente', 'produto', 'faturamento_brut']
                if c_fil:
                    sel.append(c_fil)
                    heads.append('filial')

                sub = df[sel].copy()
                sub.columns = heads
                sub['arquivo_origem'] = nome_arq

                if sub['faturamento_brut'].dtype == 'object':
                    sub['faturamento_brut'] = sub['faturamento_brut'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                sub['faturamento_brut'] = pd.to_numeric(sub['faturamento_brut'], errors='coerce')

                # Envia registros para a tabela 'faturamento' no Neon
                sub.to_sql('faturamento', con=engine, if_exists='append', index=False)

                # Marca arquivo como processado
                with engine.connect() as conn:
                    conn.execute(
                        text("INSERT INTO historico_uploads (nome_arquivo) VALUES (:n) ON CONFLICT DO NOTHING;"),
                        {"n": nome_arq}
                    )
                print(f"✅ {nome_arq} inserido no Neon com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao processar {nome_arq}: {e}")

if __name__ == "__main__":
    sincronizar()
