import sqlite3

conn = sqlite3.connect("cqp.db")
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM matriculas")
for m in c.fetchall():
    print(dict(m))

conn.close()