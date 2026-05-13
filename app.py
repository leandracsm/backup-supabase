import os
import json
import csv
import shutil
from dotenv import load_dotenv
from supabase import create_client
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io

# =========================
# CONFIG
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL:", SUPABASE_URL)
print("SUPABASE_KEY EXISTS:", bool(SUPABASE_KEY))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

PASTA_BACKUP = "/tmp/backup"
os.makedirs(PASTA_BACKUP, exist_ok=True)

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
# BACKUP TABELA (JSON)
# =========================

def backup_tabela(nome_tabela="Colecoes_Leandra"):

    print(f"📦 Backup tabela: {nome_tabela}")

    response = supabase.table(nome_tabela).select("*").execute()
    dados = response.data

    if not dados:
        print("⚠️ Nenhum dado encontrado.")
        return

    path = f"{PASTA_BACKUP}/{nome_tabela}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON salvo: {path}")


# =========================
# BACKUP CSV
# =========================

def backup_csv(nome_tabela):

    print(f"📄 Backup CSV: {nome_tabela}")

    response = supabase.table(nome_tabela).select("*").execute()
    dados = response.data

    if not dados:
        print("⚠️ Nenhum dado encontrado.")
        return

    path = f"{PASTA_BACKUP}/{nome_tabela}.csv"

    colunas = dados[0].keys()

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(dados)

    print(f"✅ CSV salvo: {path}")


# =========================
# ZIP
# =========================

def gerar_zip():

    print("🗜️ Gerando ZIP...")

    nome_zip = "/tmp/backup_supabase"

    shutil.make_archive(nome_zip, "zip", PASTA_BACKUP)

    zip_path = f"{nome_zip}.zip"

    print("📦 ZIP criado:", zip_path)
    print("EXISTS:", os.path.exists(zip_path))

    return zip_path


# =========================
# BACKUP COMPLETO
# =========================

def executar_backup_completo():

    global STATUS_BACKUP

    STATUS_BACKUP = "rodando"

    try:

        print("🔵 INICIO BACKUP")

        backup_tabela("Colecoes_Leandra")
        backup_csv("Colecoes_Leandra")
        backup_csv("listapaises")

        zip_path = gerar_zip()

        STATUS_BACKUP = "concluido"

        print("🎉 BACKUP FINALIZADO")

        return zip_path

    except Exception as e:

        STATUS_BACKUP = "erro"
        print("❌ ERRO BACKUP:", str(e))
        return None


# =========================
# API BACKUP (DOWNLOAD)
# =========================

@app.get("/backup")
def executar_backup():

    try:

        zip_path = executar_backup_completo()

        if not zip_path or not os.path.exists(zip_path):
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "ZIP não encontrado"}
            )

        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=backup_supabase.zip"
            }
        )

    except Exception as e:

        print("ERRO API:", str(e))

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


# =========================
# STATUS
# =========================

@app.get("/status")
def status_backup():

    return {
        "status": STATUS_BACKUP
    }