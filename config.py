import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv

# Caminho absoluto garante que o .env é encontrado independente de onde o CLI é chamado
BASEDIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASEDIR, ".env"))

DB_PATH = os.path.join(BASEDIR, "cqp.db")


def _secret_key() -> str:
    key = os.getenv("FLASK_SECRET_KEY")
    if not key:
        if os.getenv("FLASK_DEBUG", "False") == "True":
            key = secrets.token_hex(32)
        else:
            raise RuntimeError(
                "FLASK_SECRET_KEY não definida.\n"
                "Execute: python -c \"import secrets; print(secrets.token_hex(32))\""
                " e adicione ao .env"
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
    SESSION_COOKIE_SECURE          = os.getenv("FLASK_DEBUG", "False") != "True"

    # ── S5: Expiração automática da sessão em 1 hora ──────────────
    PERMANENT_SESSION_LIFETIME     = timedelta(hours=1)
