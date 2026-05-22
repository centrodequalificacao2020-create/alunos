"""
Migration de backfill — executar UMA única vez após o deploy que adicionou
a coluna pontos_obtidos_total em RespostaExercicio.

O que faz:
  Percorre todas as RespostaExercicio que ainda têm pontos_obtidos_total = NULL
  e preenche o valor somando rq.pontos_obtidos de cada RespostaExercicioQuestao
  vinculada, exatamente como a função recalcular_pontos_todos() de exercicios.py.

Como executar (uma vez, na raiz do projeto):
  python migrations/backfill_pontos_obtidos_total.py
"""

import sys
import os

# Garante que o diretório raiz do projeto está no PATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app          # ajuste se o factory tiver outro nome
from routes.exercicios import recalcular_pontos_todos

app = create_app()

with app.app_context():
    total = recalcular_pontos_todos()
    print(f"[backfill] {total} registro(s) atualizado(s) com pontos_obtidos_total.")
