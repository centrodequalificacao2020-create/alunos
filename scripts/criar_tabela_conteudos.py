"""Cria a tabela conteudos se não existir (schema legado).
Nota: com SQLAlchemy/Flask-Migrate ativo, este script é dispensável.
Execute da raiz do projeto: py scripts/criar_tabela_conteudos.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS conteudos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT,
    arquivo TEXT,
    tipo TEXT,
    curso_id INTEGER,
    data TEXT
)
""")

conn.commit()
conn.close()
print("Tabela conteudos criada!")
