import os
from dotenv import load_dotenv

load_dotenv()

BASEDIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASEDIR, "cqp.db")


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", os.urandom(32))
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False, "timeout": 30},
    }
    UPLOAD_FOLDER = os.path.join("static", "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    EXTENSOES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "docx", "mp4"}
    DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
