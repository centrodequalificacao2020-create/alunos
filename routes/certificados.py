"""Emissão, download e cancelamento de certificados de conclusão.

Fluxo:
    GET  /aluno/<id>/certificados          histórico + formulário de emissão
    POST /aluno/<id>/certificados          emite (gera PDF, persiste snapshot)
    GET  /certificados/<id>/pdf            baixa/renderiza o PDF
    POST /certificados/<id>/cancelar       cancelamento lógico

O upload para o Cloudinary é opcional: sem credenciais configuradas o PDF é
re-renderizado a partir do snapshot a cada download. Como o renderer é
determinístico (``invariant=1``), o hash gravado continua válido.
"""
from __future__ import annotations

import logging

from flask import (
    Blueprint, Response, current_app, flash, redirect, render_template,
    request, send_file, session,
)

from db import db
from models import Aluno, Certificado, Curso, Matricula
from security import login_required
from services.certificado_service import (
    ErroEmissao,
    cancelar_certificado,
    certificados_do_aluno,
    emitir_certificado,
    pdf_do_certificado,
    validar_emissao,
)

logger = logging.getLogger(__name__)

certificados_bp = Blueprint("certificados", __name__)


def _usuario() -> str:
    return session.get("usuario_nome") or session.get("usuario") or "Sistema"


def _matriculas_do_aluno(aluno_id: int) -> list[Matricula]:
    return (
        Matricula.query
        .filter_by(aluno_id=aluno_id)
        .order_by(Matricula.data_matricula.desc())
        .all()
    )


def _nome_arquivo(certificado: Certificado) -> str:
    """Nome de download legível: certificado_maria_silva_ABCD123456.pdf"""
    primeiro = (certificado.nome_aluno or "aluno").split()[0]
    seguro = "".join(c for c in primeiro.lower() if c.isalnum()) or "aluno"
    return f"certificado_{seguro}_{certificado.codigo_verificacao}.pdf"


def _enviar_pdf(pdf_bytes: bytes, nome_arquivo: str) -> Response:
    import io

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nome_arquivo,
    )


@certificados_bp.route("/aluno/<int:aluno_id>/certificados", methods=["GET", "POST"])
@login_required
def certificados_do_aluno_view(aluno_id):
    """Histórico de certificados do aluno e formulário de emissão."""
    aluno = db.get_or_404(Aluno, aluno_id)
    matriculas = _matriculas_do_aluno(aluno_id)

    if request.method == "POST":
        try:
            valores = validar_emissao(request.form)
            matricula_id = request.form.get("matricula_id", type=int)
            certificado, pdf_bytes = emitir_certificado(
                aluno_id=aluno.id,
                matricula_id=matricula_id,
                emitido_por=_usuario(),
                **valores,
            )
        except ErroEmissao as exc:
            flash(str(exc), "erro")
            return redirect(f"/aluno/{aluno_id}/certificados")

        _tentar_upload(certificado, pdf_bytes)
        flash(
            f"Certificado emitido. Código de verificação: "
            f"{certificado.codigo_verificacao}",
            "sucesso",
        )
        return redirect(f"/aluno/{aluno_id}/certificados")

    # ── GET ────────────────────────────────────────────────────────────
    cursos = {c.id: c for c in Curso.query.all()}
    return render_template(
        "certificados.html",
        aluno=aluno,
        matriculas=matriculas,
        cursos=cursos,
        certificados=certificados_do_aluno(aluno_id),
    )


def _tentar_upload(certificado: Certificado, pdf_bytes: bytes) -> None:
    """Envia o PDF ao Cloudinary. Falha de upload não invalida a emissão.

    O snapshot já está no banco e o PDF é reproduzível, então o certificado
    continua baixável mesmo sem armazenamento externo.
    """
    import io

    if not current_app.config.get("CLOUDINARY_CLOUD_NAME"):
        # Sem credenciais o download re-renderiza a partir do snapshot.
        return

    try:
        from services.storage_service import upload_arquivo

        resultado = upload_arquivo(
            io.BytesIO(pdf_bytes),
            pasta="certificados",
            nome_publico=f"certificado_{certificado.codigo_verificacao}",
        )
    except Exception as exc:  # credenciais ausentes, rede, limite de plano…
        logger.warning(
            "[certificados] upload do certificado %s falhou: %s",
            certificado.codigo_verificacao, exc,
        )
        return

    certificado.arquivo_url = resultado.get("url")
    certificado.arquivo_public_id = resultado.get("public_id")
    db.session.commit()


@certificados_bp.route("/certificados/<int:certificado_id>/pdf")
@login_required
def baixar_certificado(certificado_id):
    """Baixa o PDF. Re-renderiza a partir do snapshot quando não há arquivo."""
    certificado = db.get_or_404(Certificado, certificado_id)
    nome_arquivo = _nome_arquivo(certificado)

    if certificado.arquivo_url:
        try:
            from services.file_service import proxy_remote_file

            return proxy_remote_file(certificado.arquivo_url)
        except Exception as exc:
            logger.warning(
                "[certificados] proxy do arquivo %s falhou, re-renderizando: %s",
                certificado.codigo_verificacao, exc,
            )

    return _enviar_pdf(pdf_do_certificado(certificado), nome_arquivo)


@certificados_bp.route("/certificados/<int:certificado_id>/cancelar", methods=["POST"])
@login_required
def cancelar(certificado_id):
    """Cancelamento lógico — preserva o código de verificação para auditoria."""
    certificado = db.get_or_404(Certificado, certificado_id)
    # aluno_id pode ser NULL se o aluno foi excluído (FK ondelete=SET NULL).
    destino = (
        f"/aluno/{certificado.aluno_id}/certificados"
        if certificado.aluno_id else "/cadastro"
    )

    try:
        cancelar_certificado(
            certificado_id,
            motivo=request.form.get("motivo", ""),
            cancelado_por=_usuario(),
        )
    except ErroEmissao as exc:
        flash(str(exc), "erro")
        return redirect(destino)

    flash("Certificado cancelado.", "sucesso")
    return redirect(destino)
