"""
migrate_acesso_conteudo.py
--------------------------
Cria a tabela `acesso_conteudo_curso` que controla se um aluno
tem acesso liberado ao conteudo de determinado curso.

Uso:  python migrate_acesso_conteudo.py
"""
from app import create_app
from db import db

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(db.text("""
            CREATE TABLE IF NOT EXISTS acesso_conteudo_curso (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                aluno_id        INTEGER NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
                curso_id        INTEGER NOT NULL REFERENCES cursos(id) ON DELETE CASCADE,
                liberado        INTEGER NOT NULL DEFAULT 0,
                liberado_por    TEXT,
                liberado_em     TEXT,
                UNIQUE (aluno_id, curso_id)
            )
        """))
        conn.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_acesso_cont_aluno
            ON acesso_conteudo_curso (aluno_id)
        """))
        conn.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_acesso_cont_curso
            ON acesso_conteudo_curso (curso_id)
        """))
        conn.commit()
    print("Tabela acesso_conteudo_curso criada/verificada com sucesso!")
