"""Lista todos os registros da tabela matriculas.
Execute da raiz do projeto: py scripts/ver_matricula.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM matriculas")
for m in c.fetchall():
    print(dict(m))

conn.close()
