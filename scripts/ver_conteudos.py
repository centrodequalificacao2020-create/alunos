"""Lista todos os registros da tabela conteudos.
Execute da raiz do projeto: py scripts/ver_conteudos.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM conteudos")
for d in c.fetchall():
    print(dict(d))

conn.close()
