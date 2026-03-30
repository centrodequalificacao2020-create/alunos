"""
migrate_novos_modelos.py
────────────────────────
Adiciona ao banco as tabelas e colunas novas:
  - materias_liberadas   (liberação individual de matéria por aluno)
  - provas_liberadas     (liberação individual de prova por aluno)
  - atividades           (enunciados + entregas)
  - atividade_questoes
  - entregas_atividade
  - mensalidades.curso_id  (vincula parcela ao curso correto)
  - notas.publicada        (controla visibilidade no portal do aluno)

Executar UMA vez após git pull:
    python migrate_novos_modelos.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from db import db

DDL = [
    # Coluna curso_id em mensalidades (parcelas por curso)
    """
    ALTER TABLE mensalidades
    ADD COLUMN IF NOT EXISTS curso_id INTEGER REFERENCES cursos(id);
    """,
    # Coluna publicada em notas (controla visibilidade do aluno)
    """
    ALTER TABLE notas
    ADD COLUMN IF NOT EXISTS publicada INTEGER NOT NULL DEFAULT 0;
    """,
    # Tabela de liberação individual de matérias
    """
    CREATE TABLE IF NOT EXISTS materias_liberadas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        materia_id   INTEGER NOT NULL REFERENCES materias(id),
        liberado     INTEGER NOT NULL DEFAULT 1,
        liberado_por TEXT,
        liberado_em  TEXT,
        UNIQUE(aluno_id, materia_id)
    );
    """,
    # Tabela de liberação individual de provas
    """
    CREATE TABLE IF NOT EXISTS provas_liberadas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        prova_id     INTEGER NOT NULL REFERENCES provas(id),
        liberado     INTEGER NOT NULL DEFAULT 1,
        liberado_por TEXT,
        liberado_em  TEXT,
        UNIQUE(aluno_id, prova_id)
    );
    """,
    # Atividades
    """
    CREATE TABLE IF NOT EXISTS atividades (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo     TEXT    NOT NULL,
        descricao  TEXT,
        curso_id   INTEGER NOT NULL REFERENCES cursos(id),
        materia_id INTEGER REFERENCES materias(id),
        ativa      INTEGER NOT NULL DEFAULT 1,
        criado_em  TEXT,
        criado_por TEXT
    );
    """,
    # Questões/enunciados de atividade
    """
    CREATE TABLE IF NOT EXISTS atividade_questoes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        atividade_id INTEGER NOT NULL REFERENCES atividades(id) ON DELETE CASCADE,
        enunciado    TEXT    NOT NULL,
        ordem        INTEGER DEFAULT 1
    );
    """,
    # Entregas do aluno (até 3 arquivos)
    """
    CREATE TABLE IF NOT EXISTS entregas_atividade (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id     INTEGER NOT NULL REFERENCES alunos(id),
        atividade_id INTEGER NOT NULL REFERENCES atividades(id) ON DELETE CASCADE,
        arquivo1     TEXT,
        arquivo2     TEXT,
        arquivo3     TEXT,
        entregue_em  TEXT,
        status       TEXT DEFAULT 'entregue',
        nota         REAL,
        feedback     TEXT,
        UNIQUE(aluno_id, atividade_id)
    );
    """,
]

def main():
    app = create_app()
    with app.app_context():
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        erros = 0
        for sql in DDL:
            sql = sql.strip()
            if not sql:
                continue
            try:
                cur.execute(sql)
                print(f"OK: {sql[:60].replace(chr(10),' ')}...")
            except Exception as e:
                print(f"AVISO: {e}  →  {sql[:60].replace(chr(10),' ')}...")
                erros += 1
        conn.commit()
        cur.close()
        conn.close()
        if erros:
            print(f"\n{erros} aviso(s) — geralmente significa que a coluna/tabela já existe (OK).")
        print("\nMigração concluída.")

if __name__ == "__main__":
    main()
