"""
migrate_login_historico.py
--------------------------
Cria a tabela `login_historico_aluno` e adiciona a coluna
`data_cadastro` na tabela `matriculas` (se ainda nao existirem).

Uso:  python migrate_login_historico.py
"""
from app import app
from db import db

with app.app_context():
    # 1. Tabela de historico de login
    db.engine.execute("""
        CREATE TABLE IF NOT EXISTS login_historico_aluno (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id   INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
            login_em   TEXT    NOT NULL,
            ip         TEXT,
            user_agent TEXT
        )
    """)

    # 2. Coluna data_cadastro na tabela matriculas
    try:
        db.engine.execute("ALTER TABLE matriculas ADD COLUMN data_cadastro TEXT")
        print("Coluna data_cadastro adicionada em matriculas.")
    except Exception:
        print("Coluna data_cadastro ja existe em matriculas — OK.")

    print("Migracao concluida.")
