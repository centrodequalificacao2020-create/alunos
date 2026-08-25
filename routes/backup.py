import os
import sqlite3
import tempfile
from datetime import datetime
from flask import Blueprint, current_app, send_file, after_this_request
from security import admin_required

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup')
@admin_required
def baixar_backup():
    # Caminho do banco derivado de SQLALCHEMY_DATABASE_URI (fonte única de verdade).
    # A config expõe a URI "sqlite:///<path>"; extraímos o caminho do arquivo.
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_path = uri.replace('sqlite:///', '', 1) if uri.startswith('sqlite:///') else ''
    if not db_path:
        # Fallback para o caminho histórico (mesma resolução do código original)
        db_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'cqp.db')
        )
    db_path = os.path.abspath(db_path)

    if not os.path.exists(db_path):
        from flask import abort
        abort(404, description="Banco de dados não encontrado.")

    # Cria cópia consistente com sqlite3.backup() — segura mesmo com WAL.
    # Um simple send_file do arquivo aberto poderia capturar o banco no meio
    # de uma transação, produzindo um dump corrompido/inconsistente.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(tmp_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
    except Exception:
        # Garante a limpeza do arquivo temporário em caso de falha
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

    # Remove o arquivo temporário assim que o Flask terminar de enviá-lo
    @after_this_request
    def _cleanup(response):
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        finally:
            return response

    nome = f"backup_cqp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(tmp_path, as_attachment=True, download_name=nome)
