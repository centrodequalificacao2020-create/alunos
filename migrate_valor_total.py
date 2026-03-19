"""Script de migração: adiciona coluna valor_total à tabela cursos
e recalcula o valor para todos os cursos já cadastrados.
Execute uma única vez: python migrate_valor_total.py
"""
import sqlite3, os

DB_PATH = os.environ.get("DATABASE_URL", "cqp.db").replace("sqlite:///", "")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

colunas = [row[1] for row in cur.execute("PRAGMA table_info(cursos)")]
if "valor_total" not in colunas:
    cur.execute("ALTER TABLE cursos ADD COLUMN valor_total REAL DEFAULT 0")
    print("Coluna valor_total criada.")
else:
    print("Coluna valor_total já existe.")

# valor_total = valor_matricula + (valor_mensal x parcelas)
cur.execute("""
    UPDATE cursos
    SET valor_total = ROUND(
        COALESCE(valor_matricula, 0) + COALESCE(valor_mensal, 0) * COALESCE(parcelas, 1),
    2)
""")
print(f"{cur.rowcount} curso(s) recalculado(s).")

conn.commit()
conn.close()
print("Migração concluída.")
