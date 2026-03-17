"""Insere um conteúdo de exemplo na tabela conteudos.
Execute da raiz do projeto: py scripts/inserir_conteudo.py
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cqp.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("""
INSERT INTO conteudos (titulo, arquivo, tipo, curso_id, modulo, data)
VALUES (?, ?, ?, ?, ?, ?)
""", (
    "Aula 1 - Apresentação",
    "https://www.youtube.com/watch?v=ysz5S6PUM-U",
    "video",
    1,
    1,
    datetime.now().strftime("%Y-%m-%d")
))

conn.commit()
conn.close()
print("Conteúdo inserido com sucesso")
