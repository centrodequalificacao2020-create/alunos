import os
from flask import Blueprint, render_template, request, redirect, flash, session, current_app
from db import db
from models import Atividade, AtividadeQuestao, Curso, Materia, EntregaAtividade, Aluno
from security import login_required
from datetime import datetime

atividades_bp = Blueprint("atividades", __name__)

PERFIS_ADMIN = {"ADMIN", "SECRETARIA", "INSTRUTOR"}

PER_PAGE = 20


def _operador():
    return session.get("usuario") or session.get("nome") or "sistema"


# ─── LISTAGEM + CRIAÇÃO ──────────────────────────────────────────────────────

@atividades_bp.route("/atividades", methods=["GET", "POST"])
@login_required
def atividades():
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.order_by(Materia.nome).all()
    lista    = Atividade.query.order_by(Atividade.id.desc()).all()

    if request.method == "POST":
        titulo     = request.form.get("titulo", "").strip()
        descricao  = request.form.get("descricao", "").strip() or None
        curso_id   = request.form.get("curso_id", type=int)
        materia_id = request.form.get("materia_id", type=int) or None

        if not titulo or not curso_id:
            flash("Título e curso são obrigatórios.", "erro")
            return redirect("/atividades")

        enunciados = request.form.getlist("enunciado[]")
        enunciados = [e.strip() for e in enunciados if e.strip()]
        if not enunciados:
            flash("Adicione pelo menos um enunciado.", "erro")
            return redirect("/atividades")

        atv = Atividade(
            titulo     = titulo,
            descricao  = descricao,
            curso_id   = curso_id,
            materia_id = materia_id,
            ativa      = 1,
            criado_em  = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            criado_por = _operador(),
        )
        db.session.add(atv)
        db.session.flush()

        for i, texto in enumerate(enunciados, 1):
            db.session.add(AtividadeQuestao(
                atividade_id = atv.id,
                enunciado    = texto,
                ordem        = i,
            ))

        db.session.commit()
        flash(f"Atividade '{titulo}' criada com {len(enunciados)} enunciado(s).", "sucesso")
        return redirect("/atividades")

    materias_json = [{"id": m.id, "nome": m.nome, "curso_id": m.curso_id} for m in materias]
    return render_template(
        "atividades.html",
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        atividades    = lista,
    )


# ─── EDITAR ATIVIDADE ────────────────────────────────────────────────────────

@atividades_bp.route("/atividades/<int:atv_id>/editar", methods=["GET", "POST"])
@login_required
def editar_atividade(atv_id):
    atv      = db.get_or_404(Atividade, atv_id)
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.order_by(Materia.nome).all()

    if request.method == "POST":
        titulo     = request.form.get("titulo", "").strip()
        descricao  = request.form.get("descricao", "").strip() or None
        curso_id   = request.form.get("curso_id", type=int)
        materia_id = request.form.get("materia_id", type=int) or None

        if not titulo or not curso_id:
            flash("Título e curso são obrigatórios.", "erro")
            return redirect(f"/atividades/{atv_id}/editar")

        enunciados = request.form.getlist("enunciado[]")
        enunciados = [e.strip() for e in enunciados if e.strip()]
        if not enunciados:
            flash("Adicione pelo menos um enunciado.", "erro")
            return redirect(f"/atividades/{atv_id}/editar")

        atv.titulo     = titulo
        atv.descricao  = descricao
        atv.curso_id   = curso_id
        atv.materia_id = materia_id

        AtividadeQuestao.query.filter_by(atividade_id=atv_id).delete(
            synchronize_session=False
        )
        for i, texto in enumerate(enunciados, 1):
            db.session.add(AtividadeQuestao(
                atividade_id = atv_id,
                enunciado    = texto,
                ordem        = i,
            ))

        db.session.commit()
        flash(f"Atividade '{titulo}' atualizada.", "sucesso")
        return redirect("/atividades")

    materias_json = [{"id": m.id, "nome": m.nome, "curso_id": m.curso_id} for m in materias]
    return render_template(
        "editar_atividade.html",
        atv           = atv,
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
    )


# ─── EXCLUIR ATIVIDADE ───────────────────────────────────────────────────

@atividades_bp.route("/atividades/excluir/<int:atv_id>", methods=["POST"])
@login_required
def excluir_atividade(atv_id):
    from models import AtividadeLiberada
    atv = db.get_or_404(Atividade, atv_id)

    AtividadeLiberada.query.filter_by(atividade_id=atv_id).delete(
        synchronize_session="fetch"
    )

    db.session.delete(atv)
    db.session.commit()
    flash(f"Atividade '{atv.titulo}' excluída.", "sucesso")
    return redirect("/atividades")


# ─── ENTREGAS (visão admin) ────────────────────────────────────────────────

@atividades_bp.route("/atividades/<int:atv_id>/entregas")
@login_required
def ver_entregas(atv_id):
    atv   = db.get_or_404(Atividade, atv_id)
    termo = request.args.get("q", "").strip()
    page  = request.args.get("page", 1, type=int)

    query = (
        EntregaAtividade.query
        .join(Aluno, Aluno.id == EntregaAtividade.aluno_id)
        .filter(EntregaAtividade.atividade_id == atv_id)
    )

    if termo:
        query = query.filter(Aluno.nome.ilike(f"%{termo}%"))

    paginacao = query.order_by(EntregaAtividade.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )

    return render_template(
        "atividades_entregas.html",
        atividade = atv,
        paginacao = paginacao,
        entregas  = paginacao.items,
        termo     = termo,
    )


@atividades_bp.route("/atividades/<int:atv_id>/entregas/<int:entrega_id>/avaliar",
                     methods=["POST"])
@login_required
def avaliar_entrega(atv_id, entrega_id):
    entrega  = db.get_or_404(EntregaAtividade, entrega_id)
    nota     = request.form.get("nota",     type=float)
    feedback = request.form.get("feedback", "").strip() or None
    if nota is not None:
        entrega.nota     = nota
        entrega.feedback = feedback
        entrega.status   = "corrigida"
        db.session.commit()
        flash("Avaliação salva.", "sucesso")
    return redirect(f"/atividades/{atv_id}/entregas")


# ─── DOWNLOAD / VISUALIZAÇÃO DE ENTREGA (admin) ──────────────────────────
# Os arquivos agora são URLs do Cloudinary; o admin acessa diretamente pelo link.

@atividades_bp.route("/atividades/download/<path:filename>")
@login_required
def download_entrega(filename):
    """Mantido por compatibilidade com entregas legacy salvas em disco.
    Novas entregas usam Cloudinary e não passam por esta rota.
    """
    from flask import send_from_directory, abort
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    safe = os.path.basename(filename)
    full = os.path.join(upload_folder, safe)
    if not os.path.isfile(full):
        abort(404)
    return send_from_directory(upload_folder, safe, as_attachment=True)
