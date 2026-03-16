import sqlite3

conn = sqlite3.connect("cqp.db")
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