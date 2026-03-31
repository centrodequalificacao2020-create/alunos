"""
migrate_login_historico.py
==========================
Cria a tabela login_historico_aluno se ela nao existir.
Execute uma unica vez no servidor:

    python migrate_login_historico.py
"""
from app import create_app
from db import db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    tabelas   = inspector.get_table_names()

    if "login_historico_aluno" in tabelas:
        print("[OK] Tabela login_historico_aluno ja existe. Nada a fazer.")
    else:
        db.session.execute(text("""
            CREATE TABLE login_historico_aluno (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                aluno_id   INTEGER NOT NULL REFERENCES alunos(id),
                login_em   VARCHAR(19) NOT NULL,
                ip         VARCHAR(45),
                user_agent VARCHAR(300)
            )
        """))
        db.session.execute(text(
            "CREATE INDEX ix_login_hist_aluno_id ON login_historico_aluno (aluno_id)"
        ))
        db.session.execute(text(
            "CREATE INDEX ix_login_hist_login_em ON login_historico_aluno (login_em)"
        ))
        db.session.commit()
        print("[OK] Tabela login_historico_aluno criada com sucesso!")

    # Verifica se as demais tabelas novas tambem existem
    novas = [
        "acesso_conteudo_curso", "materias_liberadas", "provas_liberadas",
        "provas", "questoes", "alternativas", "respostas_prova",
        "respostas_questao", "atividades", "atividade_questoes",
        "entregas_atividade", "progresso_aulas", "turma_alunos",
        "cursos_materias",
    ]
    for t in novas:
        if t not in tabelas:
            print(f"[AVISO] Tabela '{t}' nao existe — execute: python migrate_b2.py")
        else:
            print(f"[OK] {t}")
