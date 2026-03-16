import sqlite3

conn = sqlite3.connect("cqp.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM conteudos")

dados = c.fetchall()

for d in dados:
    print(dict(d))

conn.close()