import os
import json
import csv
import shutil
import requests
import time

from dotenv import load_dotenv
from supabase import create_client

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# =========================
# CONFIG
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "fotos"
PASTA = "removidas"

PASTA_BACKUP = "/tmp/backup"
PASTA_FOTOS = f"{PASTA_BACKUP}/fotos"

os.makedirs(PASTA_BACKUP, exist_ok=True)
os.makedirs(PASTA_FOTOS, exist_ok=True)

ZIP_PATH = "/tmp/backup_supabase.zip"

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
# BACKUP HELPERS
# =========================

def limpar_backup_antigo():
    if os.path.exists(PASTA_BACKUP):
        shutil.rmtree(PASTA_BACKUP)

    os.makedirs(PASTA_BACKUP, exist_ok=True)
    os.makedirs(PASTA_FOTOS, exist_ok=True)


def backup_tabela(nome_tabela="Colecoes_Leandra"):
    response = supabase.table(nome_tabela).select("*").execute()
    dados = response.data

    if not dados:
        return

    arquivo_json = f"{PASTA_BACKUP}/{nome_tabela}_backup.json"

    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def backup_csv(nome_tabela):
    response = supabase.table(nome_tabela).select("*").execute()
    dados = response.data

    if not dados:
        return

    arquivo_csv = f"{PASTA_BACKUP}/{nome_tabela}_backup.csv"
    colunas = dados[0].keys()

    with open(arquivo_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(dados)


def baixar_imagens():
    arquivos = supabase.storage.from_(BUCKET).list(PASTA)

    if not arquivos:
        return

    for file in arquivos:

        nome = file["name"]
        caminho = f"{PASTA}/{nome}"

        url = supabase.storage.from_(BUCKET).get_public_url(caminho)
        resposta = requests.get(url)

        if resposta.status_code != 200:
            continue

        with open(f"{PASTA_FOTOS}/{nome}", "wb") as f:
            f.write(resposta.content)


def gerar_zip():
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    shutil.make_archive("/tmp/backup_supabase", "zip", PASTA_BACKUP)

    time.sleep(0.5)

    return ZIP_PATH


def executar_backup_completo():

    global STATUS_BACKUP

    try:
        STATUS_BACKUP = "rodando"

        limpar_backup_antigo()

        backup_tabela("Colecoes_Leandra")
        backup_csv("Colecoes_Leandra")
        backup_csv("listapaises")

        baixar_imagens()

        zip_path = gerar_zip()

        # =========================
        # ENVIA PARA SUPABASE STORAGE
        # =========================

        with open(zip_path, "rb") as f:
            supabase.storage.from_("backup").upload(
                "backup_supabase.zip",
                f,
                file_options={"content-type": "application/zip", "upsert": "true"}
            )

        url = supabase.storage.from_("backup").get_public_url("backup_supabase.zip")

        STATUS_BACKUP = "concluido"

        return url

    except Exception as e:
        STATUS_BACKUP = "erro"
        print("❌ ERRO:", str(e))
        return None

def deletar_zip_storage():

    try:
        supabase.storage.from_("backup").remove(
            ["backup_supabase.zip"]
        )

        print("🗑️ ZIP removido do storage")

    except Exception as e:
        print("❌ ERRO AO REMOVER ZIP:", str(e))

# =========================
# ROTAS
# =========================

@app.get("/")
def home():
    return {"status": "API ONLINE"}


@app.get("/status")
def status():
    return {"status": STATUS_BACKUP}


@app.get("/backup")
def backup():

    try:
        url = executar_backup_completo()

        if not url:
            return JSONResponse(
                status_code=500,
                content={"error": "Falha ao gerar backup"}
            )

        return {
            "success": True,
            "download_url": url
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/deletar_backup")
def deletar_backup():

    try:
        deletar_zip_storage()

        return {
            "success": True
        }

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )