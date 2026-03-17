"""Migração manual: adiciona colunas 'tipo' e 'modulo' na tabela conteudos.
Execute da raiz do projeto: py scripts/corrigir_conteudos.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

try:
    c.execute("ALTER TABLE conteudos ADD COLUMN tipo TEXT")
    print("coluna tipo criada")
except Exception:
    print("coluna tipo já existe")

try:
    c.execute("ALTER TABLE conteudos ADD COLUMN modulo INTEGER")
    print("coluna modulo criada")
except Exception:
    print("coluna modulo já existe")

conn.commit()
conn.close()
print("tabela atualizada")
