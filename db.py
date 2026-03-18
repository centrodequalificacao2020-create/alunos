import sqlite3
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import text

db = SQLAlchemy()
migrate = Migrate()

BASEDIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASEDIR, "cqp.db")


def get_db_path(app=None):
    """Retorna o caminho correto do banco em qualquer ambiente."""
    azure = "/home/site/wwwroot/cqp.db"
    if os.path.exists(azure):
        return azure
    return DB_PATH


def conectar():
    """Conexao sqlite3 pura — usada por todos os blueprints."""
    path = get_db_path()
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(app):
    # Forca o SQLAlchemy a usar o mesmo arquivo que o sqlite3 puro
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH.replace("\\", "/")
    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        db.create_all()
