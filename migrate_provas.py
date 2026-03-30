"""
migrate_provas.py
-----------------
Cria as tabelas do módulo de provas caso ainda não existam.

Executar UMA VEZ após o deploy:
    python migrate_provas.py

Ou dentro do container:
    docker compose exec web python migrate_provas.py
"""

from app import create_app
from db import db

# SQL compatível com SQLite e PostgreSQL
STATEMENTS = [
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
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_provas_curso_id   ON provas(curso_id);",
    "CREATE INDEX IF NOT EXISTS ix_provas_materia_id ON provas(materia_id);",

    """
    CREATE TABLE IF NOT EXISTS questoes (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        prova_id  INTEGER NOT NULL REFERENCES provas(id),
        enunciado TEXT    NOT NULL,
        tipo      VARCHAR(30) NOT NULL DEFAULT 'multipla_escolha',
        ordem     INTEGER DEFAULT 1,
        pontos    REAL    DEFAULT 1.0
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_questoes_prova_id ON questoes(prova_id);",

    """
    CREATE TABLE IF NOT EXISTS alternativas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        questao_id INTEGER NOT NULL REFERENCES questoes(id),
        texto      TEXT    NOT NULL,
        correta    INTEGER DEFAULT 0,
        ordem      INTEGER DEFAULT 1
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_alternativas_questao_id ON alternativas(questao_id);",

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
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_resp_prova_aluno_id ON respostas_prova(aluno_id);",
    "CREATE INDEX IF NOT EXISTS ix_resp_prova_prova_id ON respostas_prova(prova_id);",

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
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_resp_questao_rp_id ON respostas_questao(resposta_prova_id);",
]


def run():
    app = create_app()
    with app.app_context():
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        for sql in STATEMENTS:
            sql = sql.strip()
            if sql:
                try:
                    cur.execute(sql)
                    print(f"OK: {sql[:60].replace(chr(10),' ')}...")
                except Exception as e:
                    print(f"SKIP ({e}): {sql[:60]}...")
        conn.commit()
        cur.close()
        conn.close()
        print("\n[migrate_provas] concluído.")


if __name__ == "__main__":
    run()
