import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(app):
    os.makedirs("logs", exist_ok=True)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(module)s: %(message)s"
    )
    file_handler = RotatingFileHandler(
        "logs/app.log", maxBytes=5_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    error_handler = RotatingFileHandler(
        "logs/errors.log", maxBytes=2_000_000, backupCount=3
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Aplicação iniciada.")
