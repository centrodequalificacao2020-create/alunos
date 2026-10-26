"""Configuração de testes do sistema escolar.

Importante: os testes usam um SQLite em memória, nunca o ``cqp.db`` real.
"""
from __future__ import annotations

import os
import sys

import pytest

# Precisa vir antes de importar ``config``: evita RuntimeError de SECRET_KEY
# e o warning de chave temporária durante a coleta.
os.environ.setdefault("FLASK_SECRET_KEY", "chave-de-teste-nao-usar-em-producao")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("FLASK_DEBUG", "False")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def app():
    """App Flask apontando para SQLite em memória."""
    from config import Config

    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"check_same_thread": False}}
        RATELIMIT_ENABLED = False

    from app import create_app

    application = create_app(TestConfig)
    with application.app_context():
        from db import db

        db.create_all()
        yield application
        db.session.remove()


@pytest.fixture()
def db_session(app):
    """Sessão isolada por teste, com rollback ao final."""
    from db import db

    yield db.session
    db.session.rollback()
