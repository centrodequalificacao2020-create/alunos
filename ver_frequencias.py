import sqlite3

conn = sqlite3.connect("cqp.db")
c = conn.cursor()

c.execute("PRAGMA table_info(frequencias)")

for coluna in c.fetchall():
    print(coluna)

conn.close()