import sqlite3

conn = sqlite3.connect("cqp.db")
c = conn.cursor()

# tentar adicionar coluna tipo
try:
    c.execute("ALTER TABLE conteudos ADD COLUMN tipo TEXT")
    print("coluna tipo criada")
except:
    print("coluna tipo já existe")

# tentar adicionar coluna modulo
try:
    c.execute("ALTER TABLE conteudos ADD COLUMN modulo INTEGER")
    print("coluna modulo criada")
except:
    print("coluna modulo já existe")

conn.commit()
conn.close()

print("tabela atualizada")