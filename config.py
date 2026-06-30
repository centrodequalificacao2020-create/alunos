import os
import secrets
import warnings
from datetime import timedelta
from dotenv import load_dotenv

# Caminho absoluto garante que o .env é encontrado independente de onde o CLI é chamado
BASEDIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASEDIR, ".env"))

DB_PATH = os.path.join(BASEDIR, "cqp.db")


def _secret_key() -> str:
    key = os.getenv("FLASK_SECRET_KEY")
    if key:
        return key

    # Em produção: falhar ruidosamente — chave temporária invalida todas as sessões a cada restart
    if os.getenv("FLASK_ENV") == "production":
        raise RuntimeError(
            "FLASK_SECRET_KEY não definida em produção.\n"
            "Execute: python -c \"import secrets; print(secrets.token_hex(32))\""
            " e adicione ao .env"
        )

    # Em desenvolvimento/staging: gerar chave temporária com aviso claro
    key = secrets.token_hex(32)
    warnings.warn(
        "FLASK_SECRET_KEY não definida — usando chave temporária gerada em memória. "
        "Sessões serão invalidadas a cada restart. "
        "Adicione FLASK_SECRET_KEY ao .env para desenvolvimento consistente.",
        stacklevel=2,
    )
    return key


class Config:
    SECRET_KEY                     = _secret_key()
    SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    "sqlite:///" + DB_PATH.replace("\\", "/")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS      = {
        "connect_args": {"check_same_thread": False, "timeout": 30},
    }
    UPLOAD_FOLDER                  = os.path.join(BASEDIR, "static", "uploads")
    MAX_CONTENT_LENGTH             = 50 * 1024 * 1024  # 50 MB
    EXTENSOES_PERMITIDAS           = {"pdf", "png", "jpg", "jpeg", "docx", "mp4"}
    DEBUG                          = os.getenv("FLASK_DEBUG", "False") == "True"

    # ── S1: Cookie de sessão seguro ────────────────────────────────────
    SESSION_COOKIE_HTTPONLY        = True   # JS não acessa o cookie
    SESSION_COOKIE_SAMESITE        = "Lax"  # proteção básica contra CSRF
    SESSION_COOKIE_SECURE          = os.getenv("FLASK_ENV") == "production"

    # ── S5: Expiração automática da sessão em 1 hora ──────────────
    PERMANENT_SESSION_LIFETIME     = timedelta(hours=1)

    # ── Cloudinary (armazenamento externo) ────────────────────────────
    CLOUDINARY_CLOUD_NAME    = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY       = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET    = os.environ.get('CLOUDINARY_API_SECRET')
    # Prefixo de pasta — isola arquivos por cliente em conta compartilhada
    # Ex no .env: CLOUDINARY_PASTA_PREFIXO=escola_abc
    CLOUDINARY_PASTA_PREFIXO = os.environ.get('CLOUDINARY_PASTA_PREFIXO', 'default')


import cloudinary
def configurar_cloudinary(app):
    """Configura o SDK Cloudinary se as variáveis de ambiente estiverem definidas."""
    cloud_name = app.config.get('CLOUDINARY_CLOUD_NAME')
    if cloud_name:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=app.config.get('CLOUDINARY_API_KEY'),
            api_secret=app.config.get('CLOUDINARY_API_SECRET'),
            secure=True
        )
