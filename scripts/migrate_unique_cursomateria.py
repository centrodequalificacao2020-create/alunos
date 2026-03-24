"""Migração: adiciona UniqueConstraint em cursos_materias.

Executar uma vez após o deploy:
    python scripts/migrate_unique_cursomateria.py

Seguírá:
  1. Remove duplicatas de (curso_id, materia_id) mantendo o menor id.
  2. Tenta criar o índice UNIQUE (SQLite não suporta ADD CONSTRAINT,
     por isso usa CREATE UNIQUE INDEX).
"""
import sqlite3
import os
import sys

DB_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "cqp.db"),
    "/home/site/wwwroot/cqp.db",
]

def get_conn():
    for p in DB_PATHS:
        p = os.path.abspath(p)
        if os.path.exists(p):
            print(f"Conectando em: {p}")
            return sqlite3.connect(p)
    print("ERRO: banco nao encontrado em nenhum caminho esperado.")
    sys.exit(1)


def run():
    conn = get_conn()
    cur  = conn.cursor()

    # 1. Remove duplicatas
    cur.execute("""
        DELETE FROM cursos_materias
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM cursos_materias
            GROUP BY curso_id, materia_id
        )
    """)
    removidos = cur.rowcount
    print(f"{removidos} linha(s) duplicada(s) removida(s) de cursos_materias.")

    # 2. Cria índice UNIQUE se não existir
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND name='uq_cursos_materias'
    """)
    if not cur.fetchone():
        cur.execute("""
            CREATE UNIQUE INDEX uq_cursos_materias
            ON cursos_materias(curso_id, materia_id)
        """)
        print("Indice UNIQUE uq_cursos_materias criado.")
    else:
        print("Indice uq_cursos_materias ja existe, nada a fazer.")

    conn.commit()
    conn.close()
    print("Migracao concluida com sucesso.")


if __name__ == "__main__":
    run()
