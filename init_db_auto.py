"""
init_db_auto.py
---------------
Cria TODAS as tabelas definidas nos models (incluindo provas) de uma vez.
Usar apenas em ambiente de desenvolvimento ou primeiro deploy.

    python init_db_auto.py
    docker compose exec web python init_db_auto.py
"""
from app import create_app
from db import db
import models  # garante que todos os models estao importados antes do create_all

def run():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("[init_db_auto] Todas as tabelas criadas/verificadas com sucesso.")

if __name__ == "__main__":
    run()
