"""
migrate_b2.py
-------------
Cria a UniqueConstraint e os índices em cursos_materias no banco SQLite existente.
Rodar UMA Única VEZ no servidor após o pull:

    python migrate_b2.py
"""
from app import create_app
from db import db
from sqlalchemy import text

app = create_app()

with app.app_context():

    # 1. Verificar duplicatas — a constraint falha se houver
    dupes = db.session.execute(text("""
        SELECT curso_id, materia_id, COUNT(*) AS n
        FROM cursos_materias
        GROUP BY curso_id, materia_id
        HAVING n > 1
    """)).fetchall()

    if dupes:
        print("\n⚠ï¸  DUPLICATAS ENCONTRADAS — remova-as antes de continuar:\n")
        for d in dupes:
            print(f"  curso_id={d.curso_id}  materia_id={d.materia_id}  ocorrências={d.n}")
        print("\nComando para remover duplicatas (mantendo o menor id):\n")
        print("  DELETE FROM cursos_materias")
        print("  WHERE id NOT IN (")
        print("    SELECT MIN(id) FROM cursos_materias")
        print("    GROUP BY curso_id, materia_id")
        print("  );")
        print("\nRode este comando no SQLite e execute migrate_b2.py novamente.")
    else:
        # 2. Criar índice único (equivale à UniqueConstraint no SQLite)
        db.session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_cursos_materias_curso_materia
            ON cursos_materias (curso_id, materia_id)
        """))
        # 3. Índices de performance
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_cursos_materias_curso_id
            ON cursos_materias (curso_id)
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_cursos_materias_materia_id
            ON cursos_materias (materia_id)
        """))
        db.session.commit()
        print("✅  Índices criados com sucesso em cursos_materias.")
        print("   - uq_cursos_materias_curso_materia  (UNIQUE)")
        print("   - ix_cursos_materias_curso_id")
        print("   - ix_cursos_materias_materia_id")
