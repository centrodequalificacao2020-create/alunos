"""
Script de migração pontual.
Adiciona as colunas data_inicio e data_fim na tabela despesas caso não existam.
Rode UMA VEZ no bash do PythonAnywhere:

    python3 migrate_despesas.py

Após rodar com sucesso pode deletar este arquivo.
"""
from app import create_app
from db import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # Verifica colunas existentes
        result = conn.execute(text("PRAGMA table_info(despesas)"))
        colunas = {row[1] for row in result.fetchall()}

        adicionadas = []

        if "data_inicio" not in colunas:
            conn.execute(text("ALTER TABLE despesas ADD COLUMN data_inicio VARCHAR(7)"))
            adicionadas.append("data_inicio")

        if "data_fim" not in colunas:
            conn.execute(text("ALTER TABLE despesas ADD COLUMN data_fim VARCHAR(7)"))
            adicionadas.append("data_fim")

        conn.commit()

    if adicionadas:
        print(f"✅ Colunas adicionadas com sucesso: {', '.join(adicionadas)}")
    else:
        print("ℹ️  Colunas já existiam, nada foi alterado.")
