"""
migrate_manual.py
Roda com: python migrate_manual.py

Adiciona colunas faltantes nas tabelas sem precisar de Flask-Migrate.
Idempotente: verifica se a coluna ja existe antes de tentar criar.
"""
from app import create_app
from db import db
import sqlalchemy as sa

app = create_app()

COLUNAS = [
    # (tabela, coluna, tipo_sql, default)
    ("atividades_liberadas", "liberado",          "INTEGER NOT NULL DEFAULT 1"),
    ("atividades_liberadas", "liberado_por",       "VARCHAR(120)"),
    ("atividades_liberadas", "liberado_em",        "VARCHAR(19)"),
    ("atividades_liberadas", "extra_tentativas",   "INTEGER DEFAULT 0"),
    # colunas da ExercicioLiberado (por garantia)
    ("exercicios_liberados", "liberado",           "INTEGER NOT NULL DEFAULT 1"),
    ("exercicios_liberados", "liberado_por",       "VARCHAR(120)"),
    ("exercicios_liberados", "liberado_em",        "VARCHAR(19)"),
    ("exercicios_liberados", "extra_tentativas",   "INTEGER DEFAULT 0"),
]

with app.app_context():
    conn = db.engine.connect()
    inspector = sa.inspect(db.engine)
    tabelas_existentes = inspector.get_table_names()
    print("=" * 55)
    print("MIGRATION MANUAL")
    print("=" * 55)

    for tabela, coluna, tipo_sql in COLUNAS:
        if tabela not in tabelas_existentes:
            print(f"  [SKIP]  tabela '{tabela}' nao existe — pulando")
            continue
        colunas_existentes = {c["name"] for c in inspector.get_columns(tabela)}
        if coluna in colunas_existentes:
            print(f"  [OK]    {tabela}.{coluna} — ja existe")
        else:
            sql = f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo_sql}"
            try:
                conn.execute(sa.text(sql))
                conn.commit()
                print(f"  [ADD]   {tabela}.{coluna} — criada")
            except Exception as e:
                print(f"  [ERR]   {tabela}.{coluna} — {e}")

    conn.close()
    print("=" * 55)
    print("Concluido.")
    print("=" * 55)
