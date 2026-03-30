"""Migração: cria as tabelas do módulo de provas se ainda não existirem.

Uso:
    python migrate_provas.py
"""
from app import create_app
from db import db
from models import Prova, Questao, Alternativa, RespostaProva, RespostaQuestao

app = create_app()

with app.app_context():
    tabelas = ["provas", "questoes", "alternativas",
               "respostas_prova", "respostas_questao"]

    inspector = db.inspect(db.engine)
    existentes = inspector.get_table_names()

    criadas = []
    for tabela in tabelas:
        if tabela not in existentes:
            criadas.append(tabela)

    if criadas:
        db.create_all()      # cria apenas as tabelas ausentes
        print(f"Tabelas criadas: {', '.join(criadas)}")
    else:
        print("Todas as tabelas do módulo de provas já existem. Nenhuma alteração.")
