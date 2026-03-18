from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import text

# Instancias globais — URI definida exclusivamente em config.py
db = SQLAlchemy()
migrate = Migrate()


def init_db(app):
    """Inicializa SQLAlchemy e Migrate com o app Flask."""
    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()
        db.create_all()
