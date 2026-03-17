"""Lista todas as tabelas existentes no banco SQLite.
Execute da raiz do projeto: py scripts/ver_tabelas.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for tabela in c.fetchall():
    print(tabela)

conn.close()
