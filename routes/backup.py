import os
from datetime import datetime
from flask import Blueprint, send_file
from security import admin_required

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup')
@admin_required
def baixar_backup():
    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'cqp.db')
    )
    nome = f"backup_cqp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(db_path, as_attachment=True, download_name=nome)
