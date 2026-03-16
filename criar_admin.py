import sqlite3

conn = sqlite3.connect('cqp.db')
c = conn.cursor()

# Criar tabela usuarios se não existir
c.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE,
    senha TEXT,
    nome TEXT,
    perfil TEXT
)
''')

# Inserir admin (se não existir)
c.execute('''
INSERT OR IGNORE INTO usuarios (usuario, senha, nome, perfil) 
VALUES ("admin", "admin", "Administrador", "admin")
''')

conn.commit()
conn.close()

print(' Usuário admin/admin criado!')
