import os
import json
import csv
import shutil
import requests
from dotenv import load_dotenv
from supabase import create_client
from fastapi import FastAPI, BackgroundTasks
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
os.makedirs(PASTA_BACKUP, exist_ok=True)
PASTA_FOTOS = f"{PASTA_BACKUP}/fotos"

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
# PREPARAR PASTAS
# =========================

os.makedirs(PASTA_BACKUP, exist_ok=True)
os.makedirs(PASTA_FOTOS, exist_ok=True)

# =========================
# BACKUP JSON
# =========================

def backup_tabela(nome_tabela="Colecoes_Leandra"):

    print("📦 Buscando dados da tabela...")

    try:
        response = supabase.table(nome_tabela).select("*").execute()
        dados = response.data

        if not dados:
            print("⚠️ Nenhum dado encontrado.")
            return

        arquivo_json = f"{PASTA_BACKUP}/{nome_tabela}_backup.json"

        with open(arquivo_json, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        print(f"✅ JSON salvo em: {arquivo_json}")

    except Exception as e:
        print("❌ Erro ao salvar JSON:", str(e))

# =========================
# BACKUP CSV
# =========================

def backup_csv(nome_tabela):

    print(f"📄 Gerando CSV: {nome_tabela}")

    try:
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

    except Exception as e:
        print("❌ Erro ao gerar CSV:", str(e))

# =========================
# BAIXAR IMAGENS
# =========================

def baixar_imagens():

    print("📸 Buscando imagens do Storage...")

    try:
        arquivos = supabase.storage.from_(BUCKET).list(PASTA)

        if not arquivos:
            print("⚠️ Nenhuma imagem encontrada")
            return

        total = len(arquivos)

        for i, file in enumerate(arquivos, start=1):

            nome = file["name"]

            caminho_storage = f"{PASTA}/{nome}"

            url = supabase.storage.from_(BUCKET).get_public_url(caminho_storage)

            img_data = requests.get(url).content

            caminho_local = f"{PASTA_FOTOS}/{nome}"

            with open(caminho_local, "wb") as f:
                f.write(img_data)

            print(f"⬇️ ({i}/{total}) {nome}")

        print("✅ Imagens salvas")

    except Exception as e:
        print("❌ Erro ao baixar imagens:", str(e))

# =========================
# GERAR ZIP
# =========================

def gerar_zip():

    print("🗜️ Gerando ZIP...")

    nome_zip = "/tmp/colecoes_supabase_bkp"

    shutil.make_archive(nome_zip, "zip", PASTA_BACKUP)

    print(f"✅ ZIP criado em: {nome_zip}.zip")
# =========================
# EXECUTAR BACKUP COMPLETO
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
        #backup_csv("listapaises")
        print("✔ listapaises OK")
        print("-------------")

        # print("➡️ ETAPA 4: baixar_imagens (DESATIVADO)")
        # baixar_imagens()
        # print("✔ imagens OK")
        print("-------------")

        print("➡️ ETAPA 5: gerar_zip")
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
def executar_backup(background_tasks: BackgroundTasks):

    try:

        background_tasks.add_task(executar_backup_completo)

        return {
            "success": True,
            "message": "Backup iniciado com sucesso"
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