"""
migrate_provas.py  —  cria todas as tabelas de provas/atividades/liberacoes
usando CREATE TABLE IF NOT EXISTS via SQLAlchemy + texto puro.
Executar UMA VEZ no console do PythonAnywhere:

    cd ~/alunos && python migrate_provas.py
"""
from app import create_app
from db import db

DDL = [
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
    """
    CREATE TABLE IF NOT EXISTS questoes (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        prova_id  INTEGER NOT NULL REFERENCES provas(id),
        enunciado TEXT    NOT NULL,
        tipo      VARCHAR(30) NOT NULL DEFAULT 'multipla_escolha',
        ordem     INTEGER DEFAULT 1,
        pontos    REAL    DEFAULT 1.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alternativas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        questao_id INTEGER NOT NULL REFERENCES questoes(id),
        texto      TEXT    NOT NULL,
        correta    INTEGER DEFAULT 0,
        ordem      INTEGER DEFAULT 1
    )
    """,
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
    """
    CREATE TABLE IF NOT EXISTS respostas_questao (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        resposta_prova_id INTEGER NOT NULL REFERENCES respostas_prova(id),
        questao_id        INTEGER NOT NULL REFERENCES questoes(id),
        alternativa_id    INTEGER REFERENCES alternativas(id),
        texto_resposta    TEXT,
        pontos_obtidos    REAL,
        corrigida         INTEGER DEFAULT 0,
        UNIQUE(resposta_prova_id, questao_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provas_liberadas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        prova_id     INTEGER NOT NULL REFERENCES provas(id),
        liberado     INTEGER NOT NULL DEFAULT 1,
        liberado_por VARCHAR(120),
        liberado_em  VARCHAR(19),
        UNIQUE(aluno_id, prova_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS materias_liberadas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        materia_id   INTEGER NOT NULL REFERENCES materias(id),
        liberado     INTEGER NOT NULL DEFAULT 1,
        liberado_por VARCHAR(120),
        liberado_em  VARCHAR(19),
        UNIQUE(aluno_id, materia_id)
    )
    """,
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
    """
    CREATE TABLE IF NOT EXISTS atividade_questoes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        atividade_id INTEGER NOT NULL REFERENCES atividades(id),
        enunciado    TEXT    NOT NULL,
        ordem        INTEGER DEFAULT 1
    )
    """,
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
        UNIQUE(aluno_id, atividade_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS acesso_conteudo_curso (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        curso_id     INTEGER NOT NULL REFERENCES cursos(id),
        liberado     INTEGER NOT NULL DEFAULT 0,
        liberado_por VARCHAR(120),
        liberado_em  VARCHAR(19),
        UNIQUE(aluno_id, curso_id)
    )
    """,
    # indexes
    "CREATE INDEX IF NOT EXISTS ix_provas_curso_id    ON provas(curso_id)",
    "CREATE INDEX IF NOT EXISTS ix_provas_materia_id  ON provas(materia_id)",
    "CREATE INDEX IF NOT EXISTS ix_questoes_prova_id  ON questoes(prova_id)",
    "CREATE INDEX IF NOT EXISTS ix_alt_questao_id     ON alternativas(questao_id)",
    "CREATE INDEX IF NOT EXISTS ix_resp_prova_aluno   ON respostas_prova(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_resp_prova_prova   ON respostas_prova(prova_id)",
    "CREATE INDEX IF NOT EXISTS ix_resp_q_rp_id       ON respostas_questao(resposta_prova_id)",
    "CREATE INDEX IF NOT EXISTS ix_prova_lib_aluno    ON provas_liberadas(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_prova_lib_prova    ON provas_liberadas(prova_id)",
    "CREATE INDEX IF NOT EXISTS ix_mat_lib_aluno      ON materias_liberadas(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_mat_lib_materia    ON materias_liberadas(materia_id)",
    "CREATE INDEX IF NOT EXISTS ix_entrega_aluno      ON entregas_atividade(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_entrega_atv        ON entregas_atividade(atividade_id)",
    "CREATE INDEX IF NOT EXISTS ix_acesso_aluno       ON acesso_conteudo_curso(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_acesso_curso       ON acesso_conteudo_curso(curso_id)",
    "CREATE INDEX IF NOT EXISTS ix_login_hist_aluno   ON login_historico_aluno(aluno_id)",
]


def main():
    app = create_app()
    with app.app_context():
        conn = db.engine.connect()
        for sql in DDL:
            sql = sql.strip()
            if sql:
                try:
                    conn.execute(db.text(sql))
                    print(f"OK: {sql[:60].strip()}...")
                except Exception as e:
                    print(f"SKIP ({e}): {sql[:60].strip()}...")
        conn.commit()
        conn.close()
        print("\n✅ Migration concluida com sucesso!")


if __name__ == "__main__":
    main()
