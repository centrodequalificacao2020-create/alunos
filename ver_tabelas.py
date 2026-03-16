import sqlite3

conn = sqlite3.connect("cqp.db")
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")

for tabela in c.fetchall():
    print(tabela)

conn.close()