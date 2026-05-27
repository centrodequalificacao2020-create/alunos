"""Endpoints administrativos para auditoria de aceite de contrato.

Registrado no app com prefixo /admin (ou via blueprint).
Acesso restrito a perfil ADMIN ou SECRETARIA.
"""
from flask import Blueprint, jsonify, session, abort
from models import Aluno, ContratoAceite
from db import db
from security import login_required  # decorador existente no projeto

contrato_admin_bp = Blueprint("contrato_admin", __name__)


def _requer_admin_ou_secretaria():
    """Aborta com 403 se o usuario nao tiver perfil admin ou secretaria."""
    perfil = (session.get("perfil") or "").lower()
    if perfil not in ("admin", "secretaria"):
        abort(403)


@contrato_admin_bp.route("/alunos/<int:aluno_id>/contrato/aceites", methods=["GET"])
@login_required
def listar_aceites_contrato(aluno_id):
    """Lista todos os aceites de contrato de um aluno.

    Retorna JSON com o historico completo de aceites, incluindo
    versao, hash SHA-256, timestamp, IP e user-agent.
    Util para comprovar aceite em caso de contestacao.

    Resposta de exemplo::

        {
            "aluno_id": 42,
            "aluno_nome": "Maria Silva",
            "total": 1,
            "aceites": [
                {
                    "id": 1,
                    "versao": "v1.0",
                    "hash_contrato": "<sha256hex>",
                    "aceito_em": "2026-05-27 18:00:00",
                    "ip": "177.10.20.30",
                    "user_agent": "Mozilla/5.0 ..."
                }
            ]
        }
    """
    _requer_admin_ou_secretaria()

    aluno = db.get_or_404(Aluno, aluno_id)

    aceites = (
        ContratoAceite.query
        .filter_by(aluno_id=aluno_id)
        .order_by(ContratoAceite.aceito_em.desc())
        .all()
    )

    return jsonify({
        "aluno_id":   aluno.id,
        "aluno_nome": aluno.nome,
        "total":      len(aceites),
        "aceites": [
            {
                "id":            a.id,
                "versao":        a.versao,
                "hash_contrato": a.hash_contrato,
                "aceito_em":     a.aceito_em,
                "ip":            a.ip,
                "user_agent":    a.user_agent,
            }
            for a in aceites
        ],
    })
