"""Migração: cria tabela respostas_exercicio_questao se ainda não existir.

Executar UMA vez após o deploy da etapa6:
    python migrate_add_resp_exercicio_questao.py
"""
import sqlite3
import os

# Caminho real do banco — mesma lógica do config.py
BASEDIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "") or os.path.join(BASEDIR, "cqp.db")

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS respostas_exercicio_questao (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    resposta_exercicio_id INTEGER NOT NULL
        REFERENCES respostas_exercicio(id) ON DELETE CASCADE,
    questao_id            INTEGER NOT NULL
        REFERENCES exercicio_questoes(id),
    alternativa_id        INTEGER
        REFERENCES exercicio_alternativas(id),
    acertou               INTEGER NOT NULL DEFAULT 0,
    UNIQUE (resposta_exercicio_id, questao_id)
);
CREATE INDEX IF NOT EXISTS ix_resp_ex_q_resp_id
    ON respostas_exercicio_questao (resposta_exercicio_id);
CREATE INDEX IF NOT EXISTS ix_resp_ex_q_questao_id
    ON respostas_exercicio_questao (questao_id);
"""

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"[ERRO] Banco não encontrado em: {DB_PATH}")
        print("Ajuste a variável DATABASE_URL ou edite DB_PATH no topo deste script.")
        raise SystemExit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(CREATE_SQL)
        conn.commit()
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='respostas_exercicio_questao'"
        )
        if cur.fetchone():
            print("[OK] Tabela respostas_exercicio_questao pronta.")
        else:
            print("[ERRO] Tabela não foi criada. Verifique o banco.")
    finally:
        conn.close()
