"""
Migracao: adiciona coluna 'publicada' na tabela notas.

Executar UMA vez no servidor:
    cd /home/CQP/alunos
    source venv/bin/activate
    python migrate_notas_publicada.py
"""
import sqlite3
import os
import sys

BASEDIR = os.path.abspath(os.path.dirname(__file__))

# Banco fica na raiz do projeto: cqp.db
# DATABASE_URL do .env tem precedencia, caso esteja configurado diferente
env_url = os.environ.get("DATABASE_URL", "")
if env_url.startswith("sqlite:///"):
    DB_PATH = env_url[len("sqlite:///"):]
else:
    DB_PATH = os.path.join(BASEDIR, "cqp.db")

if not os.path.exists(DB_PATH):
    print(f"[ERRO] Banco nao encontrado: {DB_PATH}")
    sys.exit(1)

print(f"Banco de dados: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

cur.execute("PRAGMA table_info(notas)")
colunas = [row[1] for row in cur.fetchall()]
print(f"Colunas atuais de 'notas': {colunas}")

if "publicada" in colunas:
    print("[OK] Coluna 'publicada' ja existe. Nenhuma alteracao necessaria.")
else:
    cur.execute("ALTER TABLE notas ADD COLUMN publicada INTEGER DEFAULT 0")
    conn.commit()
    print("[OK] Coluna 'publicada' adicionada com sucesso (default = 0).")

conn.close()
