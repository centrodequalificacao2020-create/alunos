import os
from flask import Blueprint, render_template, request, redirect, flash, current_app
from db import db
from models import Conteudo, Materia, CursoMateria, Curso
from security import login_required, extensao_permitida

conteudos_bp = Blueprint("conteudos", __name__)

def _limpar(nome):
    import re
    return re.sub(r"[^a-z0-9_.-]", "", nome.lower().replace(" ", "_"))


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
        video      = request.form.get("video")
        arquivo    = request.files.get("arquivo")
        caminho_db = None

        if arquivo and arquivo.filename:
            if not extensao_permitida(arquivo.filename):
                flash("Tipo de arquivo não permitido.", "erro")
                return redirect("/conteudos")

            nome_seg = _limpar(arquivo.filename)

            # Caminho absoluto para salvar fisicamente o arquivo
            pasta_abs = os.path.join(current_app.root_path, "static", "uploads")
            os.makedirs(pasta_abs, exist_ok=True)
            caminho_abs = os.path.join(pasta_abs, nome_seg)
            arquivo.save(caminho_abs)

            # Caminho relativo salvo no banco (sempre a partir da raiz do projeto)
            caminho_db = os.path.join("static", "uploads", nome_seg)

        c = Conteudo(
            titulo     = titulo,
            materia_id = materia_id,
            modulo     = modulo,
            arquivo    = caminho_db or video
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
    if c.arquivo and not c.arquivo.startswith("http"):
        # Resolve caminho absoluto para deletar o arquivo físico
        caminho_abs = os.path.join(current_app.root_path, c.arquivo)
        if os.path.isfile(caminho_abs):
            os.remove(caminho_abs)
    db.session.delete(c)
    db.session.commit()
    flash("Conteúdo excluído.", "sucesso")
    return redirect("/conteudos")
