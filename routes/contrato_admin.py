"""Endpoints administrativos para auditoria e gestão de aceite de contrato.

Registrado em app.py com url_prefix='/admin'.
Acesso restrito a perfil ADMIN ou SECRETARIA.
"""
from flask import Blueprint, jsonify, session, abort, redirect, flash, url_for, request
from models import Aluno, ContratoAceite
from db import db
from security import login_required
from datetime import datetime

contrato_admin_bp = Blueprint("contrato_admin", __name__)


def _requer_admin_ou_secretaria():
    """Aborta com 403 se o usuario nao tiver perfil admin ou secretaria."""
    perfil = (session.get("perfil") or "").lower()
    if perfil not in ("admin", "secretaria"):
        abort(403)


@contrato_admin_bp.route("/alunos/<int:aluno_id>/contrato/aceites", methods=["GET"])
@login_required
def listar_aceites_contrato(aluno_id):
    """Lista todos os aceites de contrato de um aluno (JSON).

    Retorna historico completo incluindo versao, hash SHA-256,
    timestamp, IP e user-agent para fins de auditoria.
    """
    _requer_admin_ou_secretaria()
    aluno  = db.get_or_404(Aluno, aluno_id)
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


@contrato_admin_bp.route("/alunos/<int:aluno_id>/contrato/reset", methods=["POST"])
@login_required
def resetar_contrato(aluno_id):
    """Reseta o status de aceite do contrato de um aluno.

    Marca contrato_assinado=False e limpa contrato_assinado_em.
    O historico de ContratoAceite e PRESERVADO integralmente.
    No proximo login, o aluno sera redirecionado para /aluno/contrato.

    Util para:
    - Forcar alunos antigos (pre-implantacao) a assinarem o contrato digital.
    - Solicitar nova assinatura apos atualizacao do texto do contrato.
    """
    _requer_admin_ou_secretaria()
    aluno = db.get_or_404(Aluno, aluno_id)
    aluno.contrato_assinado    = False
    aluno.contrato_assinado_em = None
    db.session.commit()
    flash(
        f"Contrato de {aluno.nome} marcado como pendente. "
        "O aluno deverá assinar novamente ao acessar o portal.",
        "sucesso"
    )
    return redirect(f"/aluno/{aluno_id}")
