import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect,
    flash, session, abort, Response, current_app
)
from werkzeug.utils import secure_filename
from db import db
from models import Materia, Exercicio, Curso, CursoMateria
from security import login_required

exercicios_bp = Blueprint("exercicios", __name__)

ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "docx", "doc"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _upload_folder():
    return os.path.join(current_app.root_path, "static", "uploads", "exercicios")


# ─── LISTA / CRUD de exercícios de uma matéria ─────────────────────────────

@exercicios_bp.route("/materias/<int:materia_id>/exercicios")
@login_required
def lista_exercicios(materia_id):
    materia    = db.get_or_404(Materia, materia_id)
    exercicios = Exercicio.query.filter_by(materia_id=materia_id, ativo=1)\
                                .order_by(Exercicio.ordem).all()
    cursos = (
        db.session.query(Curso)
        .join(CursoMateria, CursoMateria.curso_id == Curso.id)
        .filter(CursoMateria.materia_id == materia_id)
        .all()
    )
    return render_template(
        "exercicios.html",
        materia=materia, exercicios=exercicios, cursos=cursos
    )


@exercicios_bp.route("/materias/<int:materia_id>/exercicios/criar", methods=["POST"])
@login_required
def criar_exercicio(materia_id):
    db.get_or_404(Materia, materia_id)
    titulo   = request.form.get("titulo", "").strip()
    descricao = request.form.get("descricao", "").strip()
    ordem    = request.form.get("ordem", 1, type=int)
    if not titulo:
        flash("Título é obrigatório.", "erro")
        return redirect(f"/materias/{materia_id}/exercicios")

    arquivo_nome = None
    f = request.files.get("arquivo")
    if f and f.filename and _allowed(f.filename):
        pasta = _upload_folder()
        os.makedirs(pasta, exist_ok=True)
        nome_seguro = secure_filename(f"{materia_id}_{int(datetime.now().timestamp())}_{f.filename}")
        f.save(os.path.join(pasta, nome_seguro))
        arquivo_nome = f"exercicios/{nome_seguro}"

    ex = Exercicio(
        materia_id = materia_id,
        titulo     = titulo,
        descricao  = descricao or None,
        arquivo    = arquivo_nome,
        ordem      = ordem,
        ativo      = 1,
        criado_em  = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        criado_por = session.get("usuario") or "",
    )
    db.session.add(ex)
    db.session.commit()
    flash(f"Exercício '{titulo}' criado!", "sucesso")
    return redirect(f"/materias/{materia_id}/exercicios")


@exercicios_bp.route("/exercicios/<int:ex_id>/editar", methods=["POST"])
@login_required
def editar_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    ex.titulo   = request.form.get("titulo", ex.titulo).strip()
    ex.descricao = request.form.get("descricao", ex.descricao or "").strip() or None
    ex.ordem    = request.form.get("ordem", ex.ordem, type=int)

    f = request.files.get("arquivo")
    if f and f.filename and _allowed(f.filename):
        pasta = _upload_folder()
        os.makedirs(pasta, exist_ok=True)
        nome_seguro = secure_filename(f"{ex.materia_id}_{int(datetime.now().timestamp())}_{f.filename}")
        f.save(os.path.join(pasta, nome_seguro))
        ex.arquivo = f"exercicios/{nome_seguro}"

    db.session.commit()
    flash("Exercício atualizado!", "sucesso")
    return redirect(f"/materias/{ex.materia_id}/exercicios")


@exercicios_bp.route("/exercicios/<int:ex_id>/excluir", methods=["POST"])
@login_required
def excluir_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    mid = ex.materia_id
    ex.ativo = 0
    db.session.commit()
    flash("Exercício removido.", "sucesso")
    return redirect(f"/materias/{mid}/exercicios")


# ─── Servir arquivo do exercício (somente admin/instrutor) ─────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/arquivo")
@login_required
def ver_arquivo_exercicio(ex_id):
    import mimetypes
    ex = db.get_or_404(Exercicio, ex_id)
    if not ex.arquivo:
        abort(404)
    caminho = os.path.join(current_app.root_path, "static", "uploads", ex.arquivo)
    if not os.path.isfile(caminho):
        abort(404)
    mime, _ = mimetypes.guess_type(caminho)
    with open(caminho, "rb") as fp:
        dados = fp.read()
    resp = Response(dados, mimetype=mime or "application/octet-stream")
    resp.headers["Content-Disposition"] = "inline"
    return resp
