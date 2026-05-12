import os
import json
import csv
import shutil
import requests
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

print("SUPABASE_URL:", SUPABASE_URL)
print("SUPABASE_KEY EXISTS:", bool(SUPABASE_KEY))

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "fotos"
PASTA = "removidas"

PASTA_BACKUP = "/tmp/backup"
PASTA_FOTOS = f"{PASTA_BACKUP}/fotos"

os.makedirs(PASTA_BACKUP, exist_ok=True)
os.makedirs(PASTA_FOTOS, exist_ok=True)

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
# BACKUP JSON
# =========================

def backup_tabela(nome_tabela="Colecoes_Leandra"):

    print("📦 Buscando dados da tabela...")

    response = supabase.table(nome_tabela).select("*").execute()
    print("RESPOSTA:", response)
    
    dados = response.data

    if not dados:
        print("⚠️ Nenhum dado encontrado.")
        return

    arquivo_json = f"{PASTA_BACKUP}/{nome_tabela}_backup.json"

    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON salvo em: {arquivo_json}")


# =========================
# BACKUP CSV
# =========================

def backup_csv(nome_tabela):

    print(f"📄 Gerando CSV: {nome_tabela}")

    response = supabase.table(nome_tabela).select("*").execute()
    dados = response.data

    if not dados:
        print("⚠️ Nenhum dado encontrado.")
        return

    arquivo_csv = f"{PASTA_BACKUP}/{nome_tabela}_backup.csv"

    colunas = dados[0].keys()

    with open(arquivo_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(dados)

    print(f"✅ CSV salvo em: {arquivo_csv}")


# =========================
# GERAR ZIP
# =========================

def gerar_zip():

    print("🗜️ Gerando ZIP...")

    nome_zip = "/tmp/colecoes_supabase_bkp"

    shutil.make_archive(nome_zip, "zip", PASTA_BACKUP)

    print(f"✅ ZIP criado em: {nome_zip}.zip")


# =========================
# BACKUP COMPLETO
# =========================

def executar_backup_completo():

    global STATUS_BACKUP

    try:

        print("🔵 INICIO BACKUP")
        STATUS_BACKUP = "rodando"

        print("➡️ ETAPA 1: backup_tabela")
        backup_tabela()
        print("✔ backup_tabela OK")
        print("-------------")

        print("➡️ ETAPA 2: backup_csv Colecoes_Leandra")
        backup_csv("Colecoes_Leandra")
        print("✔ Colecoes_Leandra OK")
        print("-------------")

        print("➡️ ETAPA 3: backup_csv listapaises")
        backup_csv("listapaises")
        print("✔ listapaises OK")
        print("-------------")

        print("➡️ ETAPA 4: gerar_zip")
        gerar_zip()
        print("✔ ZIP OK")
        print("-------------")

        STATUS_BACKUP = "concluido"
        print("🎉 BACKUP FINALIZADO COM SUCESSO")

    except Exception as e:

        STATUS_BACKUP = "erro"
        print("❌ ERRO BACKUP:", str(e))


# =========================
# API
# =========================

@app.get("/backup")
def executar_backup():

    try:

        executar_backup_completo()

        return {
            "success": True,
            "message": "Backup executado com sucesso"
        }

    except Exception as e:

        print("ERRO API:", str(e))

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


@app.get("/status")
def status_backup():

    return {
        "status": STATUS_BACKUP
    }