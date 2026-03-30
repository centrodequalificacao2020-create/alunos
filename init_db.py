"""
init_db.py — fallback para ambientes sem Flask-Migrate
=======================================================
Chama db.create_all() dentro do contexto da aplicacao.
Cria TODAS as tabelas definidas em models.py que ainda nao existem.

Uso:
    python init_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from db import db
import models  # garante que todos os models sao importados antes do create_all

app = create_app()

with app.app_context():
    db.create_all()
    print("[init_db] db.create_all() executado — todas as tabelas verificadas.")
