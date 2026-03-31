from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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
