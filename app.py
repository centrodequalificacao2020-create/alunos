import os
import re
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from db import init_db
from logging_config import configure_logging

# Instância global — blueprints importam este objeto para usar @limiter.limit()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # sem limite global — só nas rotas explícitas
    storage_uri="memory://",    # in-memory; trocar por Redis em produção
)


def limpar_nome_arquivo(nome):
    nome = nome.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_.-]", "", nome)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Extensões
    init_db(app)
    limiter.init_app(app)

    # Logging
    configure_logging(app)

    # Blueprints
    from routes.auth         import auth_bp
    from routes.cursos       import cursos_bp
    from routes.aluno        import aluno_bp
    from routes.financeiro   import financeiro_bp
    from routes.dashboard    import dashboard_bp
    from routes.despesas     import despesas_bp
    from routes.funcionario  import funcionario_bp
    from routes.conteudos    import conteudos_bp
    from routes.portal_aluno import portal_aluno_bp
    from routes.academico    import academico_bp
    from routes.backup       import backup_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(cursos_bp)
    app.register_blueprint(aluno_bp)
    app.register_blueprint(financeiro_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(despesas_bp)
    app.register_blueprint(funcionario_bp)
    app.register_blueprint(conteudos_bp)
    app.register_blueprint(academico_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(portal_aluno_bp, url_prefix="/aluno")

    @app.template_filter("moeda")
    def filtro_moeda(valor):
        """R$ 1.234,56"""
        try:
            v = float(valor or 0)
        except (TypeError, ValueError):
            v = 0.0
        inteiro = int(v)
        decimal = int(round((v - inteiro) * 100))
        return f"R$ {inteiro:,d},{decimal:02d}".replace(",", ".")

    # Gera pasta de uploads
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config["DEBUG"])
