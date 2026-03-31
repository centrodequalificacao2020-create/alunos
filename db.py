from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    db.init_app(app)
    with app.app_context():
        # Importa todos os models para que o SQLAlchemy os registre
        # antes de chamar create_all.
        # O try/except garante que erros em tabelas novas (ex: provas)
        # nao derrubem o startup quando a tabela ainda nao existe no banco.
        try:
            import models  # noqa: F401
        except Exception:
            pass
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"db.create_all() parcial: {e}")
