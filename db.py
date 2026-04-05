from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if type(dbapi_connection).__module__ == "sqlite3":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db(app):
    db.init_app(app)
    with app.app_context():
        try:
            import models  # noqa: F401
        except Exception as e:
            app.logger.warning(f"models import warning: {e}")
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"db.create_all() parcial: {e}")
