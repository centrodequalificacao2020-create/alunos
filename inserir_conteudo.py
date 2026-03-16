import sqlite3
from datetime import datetime

conn = sqlite3.connect("cqp.db")
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