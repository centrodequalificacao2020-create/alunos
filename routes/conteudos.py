import os
from flask import Blueprint, render_template, request, redirect, flash, current_app
from db import db
from models import Conteudo, Materia, CursoMateria, Curso
from security import login_required, extensao_permitida

conteudos_bp = Blueprint("conteudos", __name__)

def _limpar(nome):
    import re
    return re.sub(r"[^a-z0-9_.-]", "", nome.lower().replace(" ","_"))

@conteudos_bp.route("/conteudos", methods=["GET","POST"])
@login_required
def conteudos():
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.order_by(Materia.nome).all()
    lista    = Conteudo.query.order_by(Conteudo.id).all()

    if request.method == "POST":
        titulo    = request.form.get("titulo")
        materia_id= request.form.get("materia_id")
        modulo    = request.form.get("modulo")
        video     = request.form.get("video")
        arquivo   = request.files.get("arquivo")
        caminho   = None

        if arquivo and arquivo.filename:
            if not extensao_permitida(arquivo.filename):
                flash("Tipo de arquivo não permitido.", "erro")
                return redirect("/conteudos")
            arquivo.stream.seek(0, 2)
            if arquivo.stream.tell() > current_app.config["MAX_CONTENT_LENGTH"]:
                flash("Arquivo muito grande (máx 10 MB).", "erro")
                return redirect("/conteudos")
            arquivo.stream.seek(0)
            nome_seg = _limpar(arquivo.filename)
            caminho  = os.path.join(current_app.config["UPLOAD_FOLDER"], nome_seg)
            arquivo.save(caminho)

        c = Conteudo(titulo=titulo, materia_id=materia_id, modulo=modulo,
                     arquivo=caminho or video)
        db.session.add(c)
        db.session.commit()
        flash("Conteúdo salvo.", "sucesso")
        return redirect("/conteudos")

    return render_template("conteudos.html", cursos=cursos, materias=materias, conteudos=lista)

@conteudos_bp.route("/conteudos/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_conteudo(id):
    c = Conteudo.query.get_or_404(id)
    if c.arquivo and os.path.exists(c.arquivo):
        os.remove(c.arquivo)
    db.session.delete(c)
    db.session.commit()
    flash("Conteúdo excluído.", "sucesso")
    return redirect("/conteudos")