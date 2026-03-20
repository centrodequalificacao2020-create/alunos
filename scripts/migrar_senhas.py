"""
Script de migração: gera senha inicial para alunos sem senha cadastrada.

Regra de prioridade:
  1. CPF (sem pontos e traços) se existir
  2. E-mail (sem espaços) se existir
  3. 'aluno' + id do aluno (ex: aluno42) como último recurso

Como executar no PythonAnywhere (console bash):
    cd /home/<usuario>/<projeto>
    python scripts/migrar_senhas.py

O script imprime um relatório de tudo que foi feito.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from db import db
from models import Aluno
from security import hash_senha

app = create_app()

with app.app_context():
    alunos_sem_senha = Aluno.query.filter(
        (Aluno.senha == None) | (Aluno.senha == "")
    ).all()

    if not alunos_sem_senha:
        print("Nenhum aluno sem senha encontrado. Nada a fazer.")
        sys.exit(0)

    print(f"Encontrados {len(alunos_sem_senha)} alunos sem senha.\n")
    print(f"{'ID':<6} {'Nome':<40} {'Senha gerada'}")
    print("-" * 70)

    for aluno in alunos_sem_senha:
        cpf_limpo = "".join(filter(str.isdigit, aluno.cpf or ""))
        email_limpo = (aluno.email or "").strip()

        if cpf_limpo:
            senha_raw = cpf_limpo
            origem = "cpf"
        elif email_limpo:
            senha_raw = email_limpo
            origem = "email"
        else:
            senha_raw = f"aluno{aluno.id}"
            origem = "padrao"

        aluno.senha = hash_senha(senha_raw)
        print(f"{aluno.id:<6} {aluno.nome:<40} {senha_raw}  [{origem}]")

    db.session.commit()
    print(f"\nMigracao concluida. {len(alunos_sem_senha)} aluno(s) atualizados.")
    print("Comunique aos alunos a senha inicial e oriente a trocar pelo portal.")
