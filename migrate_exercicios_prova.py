"""
migrate_exercicios_prova.py
===========================
Etapa 3 — Migra banco para suportar:
  - exercicio_questoes        (questoes do exercicio, como mini-prova)
  - exercicio_alternativas    (alternativas das questoes de exercicio)
  - respostas_exercicio       (resultado por tentativa, sem lancar nota no boletim)
  - atividades_liberadas      (extra_tentativas para atividades)
  - exercicios.tentativas     (max tentativas padrao)
  - exercicios.tempo_limite   (minutos; None = sem limite)
  - exercicios_liberados.extra_tentativas
  - provas_liberadas.extra_tentativas

Rodar UMA VEZ apos o deploy:
    python migrate_exercicios_prova.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from db import db

DDL = [
    # ── novas colunas em tabelas existentes ───────────────────────────────
    "ALTER TABLE exercicios ADD COLUMN tentativas   INTEGER DEFAULT 1",
    "ALTER TABLE exercicios ADD COLUMN tempo_limite INTEGER",
    "ALTER TABLE exercicios_liberados ADD COLUMN extra_tentativas INTEGER DEFAULT 0",
    "ALTER TABLE provas_liberadas     ADD COLUMN extra_tentativas INTEGER DEFAULT 0",

    # ── tabela de questoes de exercicio ───────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS exercicio_questoes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        exercicio_id INTEGER NOT NULL REFERENCES exercicios(id) ON DELETE CASCADE,
        enunciado    TEXT    NOT NULL,
        tipo         VARCHAR(30) NOT NULL DEFAULT 'multipla_escolha',
        ordem        INTEGER DEFAULT 1,
        pontos       FLOAT   DEFAULT 1.0
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ex_questao_exercicio_id ON exercicio_questoes(exercicio_id)",

    # ── alternativas das questoes de exercicio ────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS exercicio_alternativas (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        questao_id INTEGER NOT NULL REFERENCES exercicio_questoes(id) ON DELETE CASCADE,
        texto      TEXT    NOT NULL,
        correta    INTEGER DEFAULT 0,
        ordem      INTEGER DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ex_alt_questao_id ON exercicio_alternativas(questao_id)",

    # ── resultado por tentativa de exercicio (nao vai ao boletim) ─────────
    """
    CREATE TABLE IF NOT EXISTS respostas_exercicio (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id       INTEGER NOT NULL REFERENCES alunos(id)    ON DELETE CASCADE,
        exercicio_id   INTEGER NOT NULL REFERENCES exercicios(id) ON DELETE CASCADE,
        tentativa_num  INTEGER DEFAULT 1,
        iniciado_em    VARCHAR(19),
        finalizado_em  VARCHAR(19),
        total_questoes INTEGER DEFAULT 0,
        acertos        INTEGER DEFAULT 0,
        percentual     FLOAT   DEFAULT 0.0
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_resp_ex_aluno_id    ON respostas_exercicio(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_resp_ex_exercicio_id ON respostas_exercicio(exercicio_id)",

    # ── tentativas extras para atividades ─────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS atividades_liberadas (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id         INTEGER NOT NULL REFERENCES alunos(id)     ON DELETE CASCADE,
        atividade_id     INTEGER NOT NULL REFERENCES atividades(id) ON DELETE CASCADE,
        liberado_por     VARCHAR(120),
        liberado_em      VARCHAR(19),
        extra_tentativas INTEGER DEFAULT 0,
        UNIQUE(aluno_id, atividade_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_atv_lib_aluno     ON atividades_liberadas(aluno_id)",
    "CREATE INDEX IF NOT EXISTS ix_atv_lib_atividade ON atividades_liberadas(atividade_id)",
]


def executar(app):
    with app.app_context():
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        ok = erros = 0
        for sql in DDL:
            sql = sql.strip()
            if not sql:
                continue
            try:
                cur.execute(sql)
                ok += 1
                print(f"  OK: {sql[:60].replace(chr(10),' ')}...")
            except Exception as e:
                erros += 1
                msg = str(e)
                if "duplicate column" in msg.lower() or "already exists" in msg.lower():
                    print(f"  JA EXISTE (ignorado): {sql[:60].replace(chr(10),' ')}...")
                else:
                    print(f"  ERRO: {e}")
                    print(f"    SQL: {sql[:120]}")
        conn.commit()
        conn.close()
        print(f"\nMigracao concluida — {ok} comandos OK, {erros} com aviso/erro.")


if __name__ == "__main__":
    app = create_app()
    executar(app)
    print("Pronto! Reinicie o servidor para ativar os novos modelos.")
