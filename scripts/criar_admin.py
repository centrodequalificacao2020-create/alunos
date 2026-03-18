"""Cria ou redefine o usuario admin no banco.
Uso: python scripts/criar_admin.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from db import db
from models import Usuario
from security import hash_senha

USUARIO  = "admin"
SENHA    = "admin123"
NOME     = "Administrador"
PERFIL   = "admin"

app = create_app()

with app.app_context():
    usuario = Usuario.query.filter_by(usuario=USUARIO).first()
    if usuario:
        usuario.senha = hash_senha(SENHA)
        usuario.perfil = PERFIL
        print(f"Senha do usuario '{USUARIO}' redefinida para '{SENHA}'.")
    else:
        novo = Usuario(
            usuario=USUARIO,
            senha=hash_senha(SENHA),
            nome=NOME,
            perfil=PERFIL,
            status="Ativo"
        )
        db.session.add(novo)
        print(f"Usuario '{USUARIO}' criado com senha '{SENHA}'.")
    db.session.commit()
    print("Pronto. Altere a senha apos o primeiro login.")
