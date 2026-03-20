import os
from functools import wraps
from datetime import datetime
from flask import Blueprint, send_file, session

backup_bp = Blueprint('backup', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('perfil') != 'admin':
            return 'Acesso negado', 403
        return f(*args, **kwargs)
    return decorated


@backup_bp.route('/backup')
@admin_required
def baixar_backup():
    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'cqp.db')
    )
    nome = f"backup_cqp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(db_path, as_attachment=True, download_name=nome)
