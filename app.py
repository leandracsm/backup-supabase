import os
import json
import csv
import shutil
import requests

from dotenv import load_dotenv
from supabase import create_client

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# =========================
# CONFIG
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL:", SUPABASE_URL)
print("SUPABASE_KEY EXISTS:", bool(SUPABASE_KEY))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "fotos"
PASTA = "removidas"

PASTA_BACKUP = "/tmp/backup"
PASTA_FOTOS = f"{PASTA_BACKUP}/fotos"

os.makedirs(PASTA_BACKUP, exist_ok=True)
os.makedirs(PASTA_FOTOS, exist_ok=True)

# =========================
# APP
# =========================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATUS_BACKUP = "parado"

# =========================
# LIMPAR BACKUP ANTIGO
# =========================

def limpar_backup_antigo():

    print("🧹 Limpando backup antigo...")

    if os.path.exists(PASTA_BACKUP):
        shutil.rmtree(PASTA_BACKUP)

    os.makedirs(PASTA_BACKUP, exist_ok=True)
    os.makedirs(PASTA_FOTOS, exist_ok=True)

# =========================
# BACKUP JSON
# =========================

def backup_tabela(nome_tabela="Colecoes_Leandra"):

    print(f"📦 Backup JSON: {nome_tabela}")

    response = supabase.table(nome_tabela).select("*").execute()

    dados = response.data

    if not dados:
        print("⚠️ Nenhum dado encontrado")
        return

    arquivo_json = f"{PASTA_BACKUP}/{nome_tabela}_backup.json"

    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON salvo: {arquivo_json}")

# =========================
# BACKUP CSV
# =========================

def backup_csv(nome_tabela):

    print(f"📄 Backup CSV: {nome_tabela}")

    response = supabase.table(nome_tabela).select("*").execute()

    dados = response.data

    if not dados:
        print("⚠️ Nenhum dado encontrado")
        return

    arquivo_csv = f"{PASTA_BACKUP}/{nome_tabela}_backup.csv"

    colunas = dados[0].keys()

    with open(arquivo_csv, "w", newline="", encoding="utf-8-sig") as f:

        writer = csv.DictWriter(f, fieldnames=colunas)

        writer.writeheader()
        writer.writerows(dados)

    print(f"✅ CSV salvo: {arquivo_csv}")

# =========================
# BAIXAR IMAGENS
# =========================

def baixar_imagens():

    print("📸 Baixando imagens...")

    try:

        arquivos = supabase.storage.from_(BUCKET).list(PASTA)

        if not arquivos:
            print("⚠️ Nenhuma imagem encontrada")
            return

        total = len(arquivos)

        for i, file in enumerate(arquivos, start=1):

            nome = file["name"]

            caminho_storage = f"{PASTA}/{nome}"

            print(f"⬇️ ({i}/{total}) {caminho_storage}")

            url = supabase.storage.from_(BUCKET).get_public_url(caminho_storage)

            resposta = requests.get(url)

            if resposta.status_code != 200:
                print(f"❌ Erro download: {nome}")
                continue

            caminho_local = f"{PASTA_FOTOS}/{nome}"

            with open(caminho_local, "wb") as f:
                f.write(resposta.content)

        print("✅ Imagens baixadas")

    except Exception as e:

        print("❌ ERRO IMAGENS:", str(e))

# =========================
# GERAR ZIP
# =========================

def gerar_zip():

    print("🗜️ Gerando ZIP...")

    nome_zip = "/tmp/colecoes_supabase_bkp"

    shutil.make_archive(nome_zip, "zip", PASTA_BACKUP)

    zip_path = f"{nome_zip}.zip"

    print("ZIP PATH:", zip_path)
    print("ZIP EXISTS:", os.path.exists(zip_path))

    return zip_path

# =========================
# BACKUP COMPLETO
# =========================

def executar_backup_completo():

    global STATUS_BACKUP

    try:

        STATUS_BACKUP = "rodando"

        print("🔵 INICIO BACKUP")

        limpar_backup_antigo()

        print("-------------")

        backup_tabela("Colecoes_Leandra")

        print("-------------")

        backup_csv("Colecoes_Leandra")

        print("-------------")

        backup_csv("listapaises")

        print("-------------")

        baixar_imagens()

        print("-------------")

        zip_path = gerar_zip()

        print("-------------")

        STATUS_BACKUP = "concluido"

        print("🎉 BACKUP FINALIZADO")

        return zip_path

    except Exception as e:

        STATUS_BACKUP = "erro"

        print("❌ ERRO BACKUP:", str(e))

        return None

# =========================
# API
# =========================

@app.get("/")
def home():

    return {
        "status": "API ONLINE"
    }

@app.get("/status")
def status_backup():

    return {
        "status": STATUS_BACKUP
    }

@app.get("/backup")
def executar_backup():

    global STATUS_BACKUP

    try:

        zip_path = executar_backup_completo()

        if not zip_path:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Falha ao gerar ZIP"
                }
            )

        if not os.path.exists(zip_path):
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "ZIP não encontrado"
                }
            )

        return FileResponse(
            path=zip_path,
            filename="backup_supabase.zip",
            media_type="application/zip"
        )

    except Exception as e:

        STATUS_BACKUP = "erro"

        print("❌ ERRO API:", str(e))

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )