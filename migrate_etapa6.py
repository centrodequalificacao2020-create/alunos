"""
migrate_etapa6.py
=================
Cria todas as tabelas introduzidas nas Etapas 4-6 que podem ainda
nao existir no banco de dados em producao.

Uso:
    python migrate_etapa6.py

O script e idempotente (IF NOT EXISTS) e nao apaga dados existentes.
"""
import os
import sys

# Garante que o diretorio raiz do projeto esteja no PATH
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from db import db

app = create_app()

CREATE_STATEMENTS = [
    # ------- login historico aluno -----------------------------------------
    """
    CREATE TABLE IF NOT EXISTS login_historico_aluno (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id   INTEGER NOT NULL REFERENCES alunos(id),
        login_em   VARCHAR(19) NOT NULL,
        ip         VARCHAR(45),
        user_agent VARCHAR(300)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_login_hist_aluno_id ON login_historico_aluno(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_login_hist_login_em  ON login_historico_aluno(login_em)",

    # ------- acesso conteudo curso -----------------------------------------
    """
    CREATE TABLE IF NOT EXISTS acesso_conteudo_curso (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        curso_id     INTEGER NOT NULL REFERENCES cursos(id),
        liberado     INTEGER NOT NULL DEFAULT 0,
        liberado_por VARCHAR(120),
        liberado_em  VARCHAR(19),
        UNIQUE (aluno_id, curso_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_acesso_cont_aluno ON acesso_conteudo_curso(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_acesso_cont_curso  ON acesso_conteudo_curso(curso_id)",

    # ------- materias_liberadas --------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS materias_liberadas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        materia_id   INTEGER NOT NULL REFERENCES materias(id),
        liberado     INTEGER NOT NULL DEFAULT 1,
        liberado_por VARCHAR(120),
        liberado_em  VARCHAR(19),
        UNIQUE (aluno_id, materia_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_mat_lib_aluno   ON materias_liberadas(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_mat_lib_materia ON materias_liberadas(materia_id)",

    # ------- progresso_aulas -----------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS progresso_aulas (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id    INTEGER REFERENCES alunos(id),
        conteudo_id INTEGER REFERENCES conteudos(id),
        concluido   INTEGER DEFAULT 0,
        UNIQUE (aluno_id, conteudo_id)
    )
    """,

    # ------- provas --------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS provas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo       VARCHAR(200) NOT NULL,
        descricao    TEXT,
        curso_id     INTEGER NOT NULL REFERENCES cursos(id),
        materia_id   INTEGER REFERENCES materias(id),
        tempo_limite INTEGER,
        tentativas   INTEGER DEFAULT 1,
        nota_minima  REAL    DEFAULT 6.0,
        ativa        INTEGER DEFAULT 1,
        criado_em    VARCHAR(19),
        criado_por   VARCHAR(80)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_provas_curso_id   ON provas(curso_id)",
    "CREATE INDEX IF NOT EXISTS ix_provas_materia_id ON provas(materia_id)",

    # ------- questoes ------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS questoes (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        prova_id  INTEGER NOT NULL REFERENCES provas(id),
        enunciado TEXT NOT NULL,
        tipo      VARCHAR(30) NOT NULL DEFAULT 'multipla_escolha',
        ordem     INTEGER DEFAULT 1,
        pontos    REAL    DEFAULT 1.0
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_questoes_prova_id ON questoes(prova_id)",

    # ------- alternativas --------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS alternativas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        questao_id INTEGER NOT NULL REFERENCES questoes(id),
        texto      TEXT NOT NULL,
        correta    INTEGER DEFAULT 0,
        ordem      INTEGER DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_alternativas_questao_id ON alternativas(questao_id)",

    # ------- provas_liberadas ----------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS provas_liberadas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        prova_id     INTEGER NOT NULL REFERENCES provas(id),
        liberado     INTEGER NOT NULL DEFAULT 1,
        liberado_por VARCHAR(120),
        liberado_em  VARCHAR(19),
        UNIQUE (aluno_id, prova_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_prova_lib_aluno ON provas_liberadas(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_prova_lib_prova ON provas_liberadas(prova_id)",

    # ------- respostas_prova -----------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS respostas_prova (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id      INTEGER NOT NULL REFERENCES alunos(id),
        prova_id      INTEGER NOT NULL REFERENCES provas(id),
        tentativa_num INTEGER DEFAULT 1,
        iniciado_em   VARCHAR(19),
        finalizado_em VARCHAR(19),
        nota_obtida   REAL,
        aprovado      INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_resp_prova_aluno_id ON respostas_prova(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_resp_prova_prova_id ON respostas_prova(prova_id)",

    # ------- respostas_questao ---------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS respostas_questao (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        resposta_prova_id INTEGER NOT NULL REFERENCES respostas_prova(id),
        questao_id        INTEGER NOT NULL REFERENCES questoes(id),
        alternativa_id    INTEGER REFERENCES alternativas(id),
        texto_resposta    TEXT,
        pontos_obtidos    REAL,
        corrigida         INTEGER DEFAULT 0,
        UNIQUE (resposta_prova_id, questao_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_resp_questao_rp_id ON respostas_questao(resposta_prova_id)",

    # ------- atividades ----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS atividades (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo     VARCHAR(200) NOT NULL,
        descricao  TEXT,
        curso_id   INTEGER NOT NULL REFERENCES cursos(id),
        materia_id INTEGER REFERENCES materias(id),
        ativa      INTEGER DEFAULT 1,
        criado_em  VARCHAR(19),
        criado_por VARCHAR(80)
    )
    """,

    # ------- atividade_questoes --------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS atividade_questoes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        atividade_id INTEGER NOT NULL REFERENCES atividades(id),
        enunciado    TEXT NOT NULL,
        ordem        INTEGER DEFAULT 1
    )
    """,

    # ------- entregas_atividade --------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS entregas_atividade (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        atividade_id INTEGER NOT NULL REFERENCES atividades(id),
        arquivo1     VARCHAR(300),
        arquivo2     VARCHAR(300),
        arquivo3     VARCHAR(300),
        entregue_em  VARCHAR(19),
        status       VARCHAR(20) DEFAULT 'entregue',
        nota         REAL,
        feedback     TEXT,
        UNIQUE (aluno_id, atividade_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_entrega_aluno     ON entregas_atividade(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_entrega_atividade ON entregas_atividade(atividade_id)",
]


def run():
    with app.app_context():
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        ok = 0
        erros = []
        for sql in CREATE_STATEMENTS:
            stmt = sql.strip()
            if not stmt:
                continue
            try:
                cur.execute(stmt)
                ok += 1
            except Exception as e:
                erros.append((stmt[:60], str(e)))
        conn.commit()
        conn.close()

        print(f"\n{'='*55}")
        print(f"  migrate_etapa6.py — {ok} statements executados")
        if erros:
            print(f"  {len(erros)} erro(s):")
            for stmt_trunc, msg in erros:
                print(f"    [{stmt_trunc}...] -> {msg}")
        else:
            print("  Todas as tabelas criadas/verificadas com sucesso!")
        print(f"{'='*55}\n")


if __name__ == "__main__":
    run()
