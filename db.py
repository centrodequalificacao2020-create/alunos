from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        db.engine.execute("PRAGMA journal_mode=WAL")  
        db.engine.execute("PRAGMA foreign_keys=ON")
        db.create_all()