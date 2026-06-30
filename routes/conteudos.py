import os
from flask import Blueprint, render_template, request, redirect, flash, current_app
from db import db
from models import Conteudo, Materia, CursoMateria, Curso, ProgressoAula
from security import login_required, extensao_permitida


conteudos_bp = Blueprint("conteudos", __name__)


@conteudos_bp.route("/conteudos", methods=["GET", "POST"])
@login_required
def conteudos():
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.order_by(Materia.nome).all()
    lista    = Conteudo.query.order_by(Conteudo.id).all()

    if request.method == "POST":
        titulo     = request.form.get("titulo")
        materia_id = request.form.get("materia_id")
        modulo     = request.form.get("modulo")
        video      = request.form.get("video", "").strip() or None
        arquivo    = request.files.get("arquivo")
        caminho_db = None
        public_id  = None

        if arquivo and arquivo.filename:
            if not extensao_permitida(arquivo.filename):
                flash("Tipo de arquivo não permitido.", "erro")
                return redirect("/conteudos")
            from services.storage_service import upload_arquivo
            try:
                resultado  = upload_arquivo(arquivo, pasta="conteudos")
                caminho_db = resultado["url"]
                public_id  = resultado["public_id"]
            except RuntimeError as e:
                flash(f"Erro ao enviar arquivo: {e}", "erro")
                return redirect("/conteudos")

        c = Conteudo(
            titulo            = titulo,
            materia_id        = materia_id,
            modulo            = modulo or None,
            arquivo           = caminho_db,
            arquivo_public_id = public_id,
            video             = video,
        )
        db.session.add(c)
        db.session.commit()
        flash("Conteúdo salvo.", "sucesso")
        return redirect("/conteudos")

    materias_json = [{"id": m.id, "nome": m.nome, "curso_id": m.curso_id} for m in materias]
    return render_template("conteudos.html", cursos=cursos, materias=materias,
                           materias_json=materias_json, conteudos=lista)


@conteudos_bp.route("/conteudos/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_conteudo(id):
    c = Conteudo.query.get_or_404(id)

    ProgressoAula.query.filter_by(conteudo_id=id).delete()

    if c.arquivo:
        if c.arquivo_public_id:
            from services.storage_service import deletar_arquivo
            deletar_arquivo(c.arquivo_public_id)
        elif not (c.arquivo.startswith("http://") or c.arquivo.startswith("https://")):
            # arquivo local legado
            caminho_abs = os.path.join(current_app.root_path, c.arquivo)
            if os.path.isfile(caminho_abs):
                os.remove(caminho_abs)

    db.session.delete(c)
    db.session.commit()
    flash("Conteúdo excluído.", "sucesso")
    return redirect("/conteudos")


@conteudos_bp.route("/conteudos/editar/<int:id>", methods=["POST"])
@login_required
def editar_conteudo(id):
    c      = Conteudo.query.get_or_404(id)
    f      = request.form
    titulo = f.get("titulo", "").strip()
    modulo = f.get("modulo", "").strip()
    video  = f.get("video",  "").strip()

    if titulo:
        c.titulo = titulo
    c.modulo = modulo or None
    c.video  = video  or None

    arquivo = request.files.get("arquivo")
    if arquivo and arquivo.filename:
        if not extensao_permitida(arquivo.filename):
            flash("Tipo de arquivo não permitido.", "erro")
            return redirect("/conteudos")
        from services.storage_service import upload_arquivo, deletar_arquivo
        # remove arquivo anterior do Cloudinary se houver public_id
        if c.arquivo_public_id:
            deletar_arquivo(c.arquivo_public_id)
        try:
            resultado         = upload_arquivo(arquivo, pasta="conteudos")
            c.arquivo         = resultado["url"]
            c.arquivo_public_id = resultado["public_id"]
        except RuntimeError as e:
            flash(f"Erro ao enviar arquivo: {e}", "erro")
            return redirect("/conteudos")

    db.session.commit()
    flash("Conteúdo atualizado.", "sucesso")
    return redirect("/conteudos")
