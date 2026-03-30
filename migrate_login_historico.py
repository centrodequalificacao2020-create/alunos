"""
migrate_login_historico.py
--------------------------
Cria a tabela `login_historico_aluno` e adiciona a coluna
`data_cadastro` na tabela `matriculas` (se ainda nao existirem).

Uso:  python migrate_login_historico.py
"""
from app import create_app
from db import db

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # 1. Tabela de historico de login
        conn.execute(db.text("""
            CREATE TABLE IF NOT EXISTS login_historico_aluno (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                aluno_id   INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
                login_em   TEXT    NOT NULL,
                ip         TEXT,
                user_agent TEXT
            )
        """))
        conn.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_login_hist_aluno_id
            ON login_historico_aluno (aluno_id)
        """))
        conn.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_login_hist_login_em
            ON login_historico_aluno (login_em)
        """))
        print("Tabela login_historico_aluno OK.")

        # 2. Coluna data_cadastro na tabela matriculas
        try:
            conn.execute(db.text("ALTER TABLE matriculas ADD COLUMN data_cadastro TEXT"))
            print("Coluna data_cadastro adicionada em matriculas.")
        except Exception:
            print("Coluna data_cadastro ja existe em matriculas — OK.")

        conn.commit()

    print("\nMigracao concluida com sucesso!")
