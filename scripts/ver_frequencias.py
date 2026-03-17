"""Exibe o schema (colunas) da tabela frequencias.
Execute da raiz do projeto: py scripts/ver_frequencias.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("PRAGMA table_info(frequencias)")
for coluna in c.fetchall():
    print(coluna)

conn.close()
