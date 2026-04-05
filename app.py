import os
import re
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from config import Config
from db import init_db
from logging_config import configure_logging

# Instância global — blueprints importam este objeto para usar @limiter.limit()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)

csrf = CSRFProtect()


def limpar_nome_arquivo(nome):
    nome = nome.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_.-]", "", nome)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    init_db(app)
    limiter.init_app(app)
    csrf.init_app(app)
    configure_logging(app)

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
    from routes.provas       import provas_bp
    from routes.provas_aluno import provas_aluno_bp
    from routes.atividades   import atividades_bp
    from routes.liberacoes   import liberacoes_bp
    from routes.admin_utils  import admin_utils_bp
    from routes.exercicios   import exercicios_bp

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
    app.register_blueprint(provas_bp)
    app.register_blueprint(atividades_bp)
    app.register_blueprint(liberacoes_bp)
    app.register_blueprint(admin_utils_bp)
    app.register_blueprint(exercicios_bp)
    app.register_blueprint(portal_aluno_bp, url_prefix="/aluno")
    app.register_blueprint(provas_aluno_bp, url_prefix="/aluno")

    # BUG-19: filtro moeda corrigido — formato brasileiro R$ 1.234,56
    @app.template_filter("moeda")
    def filtro_moeda(valor):
        """Formata valor float como moeda brasileira: R$ 1.234,56"""
        try:
            v = float(valor or 0)
        except (TypeError, ValueError):
            v = 0.0
        # Formata com separador de milhar e 2 casas decimais no padrão pt-BR
        # Estratégia: formata em en-US primeiro (1,234.56) e depois converte
        formatado = f"{v:,.2f}"          # "1,234.56"
        formatado = formatado.replace(",", "X")  # "1X234.56"
        formatado = formatado.replace(".", ",")  # "1X234,56"
        formatado = formatado.replace("X", ".")  # "1.234,56"
        return f"R$ {formatado}"

    # ── Erro 413: arquivo maior que MAX_CONTENT_LENGTH ──────────────────────
    @app.errorhandler(413)
    def arquivo_muito_grande(e):
        limite_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        mensagem  = f"Arquivo muito grande. O limite máximo permitido é {limite_mb} MB."
        # Responde JSON para requisições AJAX / fetch
        if request.accept_mimetypes.best == "application/json" or request.is_json:
            return jsonify(erro=mensagem), 413
        # Resposta HTML simples para envios de formulário normais
        html = f"""
        <!doctype html><html lang="pt-BR"><head>
        <meta charset="utf-8">
        <meta http-equiv="refresh" content="4;url={request.referrer or '/'}"´>
        <title>Arquivo muito grande</title>
        <style>
          body{{font-family:sans-serif;display:flex;align-items:center;
               justify-content:center;height:100vh;margin:0;background:#f5f5f5;}}
          .box{{background:#fff;padding:2rem 2.5rem;border-radius:10px;
                box-shadow:0 2px 12px rgba(0,0,0,.1);text-align:center;max-width:420px;}}
          h2{{color:#c0392b;margin-bottom:.5rem;}} p{{color:#555;}}
          a{{color:#01696f;text-decoration:none;font-weight:600;}}
        </style>
        </head><body><div class="box">
          <h2>⚠️ Arquivo muito grande</h2>
          <p>{mensagem}</p>
          <p>Você será redirecionado em instantes.<br>
             <a href="{request.referrer or '/'}">Voltar agora</a></p>
        </div></body></html>
        """
        return html, 413

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config["DEBUG"])
