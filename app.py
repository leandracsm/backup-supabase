import os
import json
import csv
import shutil
import requests
import time

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
    print("🧹 Limpando backup antigo...")

    if os.path.exists(PASTA_BACKUP):
        shutil.rmtree(PASTA_BACKUP)

    os.makedirs(PASTA_BACKUP, exist_ok=True)
    os.makedirs(PASTA_FOTOS, exist_ok=True)


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

    print("✅ JSON salvo")


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

    print("✅ CSV salvo")


def baixar_imagens():
    print("📸 Baixando imagens...")

    try:
        arquivos = supabase.storage.from_(BUCKET).list(PASTA)

        if not arquivos:
            print("⚠️ Nenhuma imagem encontrada")
            return

        for i, file in enumerate(arquivos, start=1):

            nome = file["name"]
            caminho = f"{PASTA}/{nome}"

            print(f"⬇️ {i} - {nome}")

            url = supabase.storage.from_(BUCKET).get_public_url(caminho)
            resposta = requests.get(url)

            if resposta.status_code != 200:
                print(f"❌ erro download {nome}")
                continue

            with open(f"{PASTA_FOTOS}/{nome}", "wb") as f:
                f.write(resposta.content)

        print("✅ Imagens OK")

    except Exception as e:
        print("❌ ERRO IMAGENS:", str(e))


def gerar_zip():
    print("🗜️ Gerando ZIP...")

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)

    shutil.make_archive("/tmp/backup_supabase", "zip", PASTA_BACKUP)

    time.sleep(0.5)

    print("ZIP pronto")
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

        STATUS_BACKUP = "concluido"

        return zip_path

    except Exception as e:
        STATUS_BACKUP = "erro"
        print("❌ ERRO:", str(e))
        return None

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

    global STATUS_BACKUP

    try:
        zip_path = executar_backup_completo()

        if not zip_path or not os.path.exists(zip_path):
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Falha ao gerar ZIP"}
            )

        return FileResponse(
            path=zip_path,
            filename="backup_supabase.zip",
            media_type="application/zip"
        )

    except Exception as e:
        STATUS_BACKUP = "erro"

        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )