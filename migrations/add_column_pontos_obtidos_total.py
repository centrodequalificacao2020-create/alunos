"""
Migration DDL — executar UMA única vez antes do backfill.

Adiciona a coluna pontos_obtidos_total na tabela respostas_exercicio
do banco SQLite (que não suporta ALTER TABLE via Flask-Migrate).

Como executar:
  python migrations/add_column_pontos_obtidos_total.py

Se a coluna já existir o script avisa e encerra sem erro.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from db import db

app = create_app()

with app.app_context():
    try:
        db.session.execute(
            db.text("ALTER TABLE respostas_exercicio ADD COLUMN pontos_obtidos_total REAL")
        )
        db.session.commit()
        print("[migration] Coluna pontos_obtidos_total adicionada com sucesso.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("[migration] Coluna já existe — nenhuma alteração necessária.")
        else:
            print(f"[migration] ERRO: {e}")
            sys.exit(1)
