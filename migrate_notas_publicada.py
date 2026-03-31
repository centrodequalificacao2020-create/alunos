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

# Localiza o banco de dados pelo mesmo caminho que o app usa
DB_PATH = os.environ.get("DATABASE_URL", "instance/escola.db")
if DB_PATH.startswith("sqlite:///"):
    DB_PATH = DB_PATH[len("sqlite:///"):]

if not os.path.exists(DB_PATH):
    # Tenta caminhos alternativos comuns
    for alt in ("escola.db", "instance/escola.db", "/home/CQP/alunos/instance/escola.db"):
        if os.path.exists(alt):
            DB_PATH = alt
            break
    else:
        print(f"[ERRO] Banco nao encontrado: {DB_PATH}")
        sys.exit(1)

print(f"Banco de dados: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# Verifica se a coluna ja existe
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
