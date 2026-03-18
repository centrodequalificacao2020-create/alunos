from flask import Blueprint, render_template, request, redirect, flash
from db import db
from models import Curso, Matricula
from security import login_required, admin_required

cursos_bp = Blueprint("cursos", __name__)

@cursos_bp.route("/cursos")
@login_required
def listar_cursos():
    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("cursos.html", cursos=cursos)

@cursos_bp.route("/salvar_curso", methods=["POST"])
@login_required
def salvar_curso():
    f = request.form
    curso = Curso(
        nome            = f["nome"],
        valor_mensal    = float(f.get("valor_mensal") or 0),
        valor_matricula = float(f.get("valor_matricula") or 0),
        parcelas        = int(f.get("parcelas") or 1),
        tipo            = f.get("tipo", ""),
    )
    db.session.add(curso)
    db.session.commit()
    flash("Curso salvo com sucesso.", "sucesso")
    return redirect("/cursos")

@cursos_bp.route("/editar_curso/<int:id>", methods=["GET", "POST"])
@login_required
def editar_curso(id):
    curso = Curso.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        curso.nome            = f["nome"]
        curso.valor_mensal    = float(f.get("valor_mensal") or 0)
        curso.valor_matricula = float(f.get("valor_matricula") or 0)
        curso.parcelas        = int(f.get("parcelas") or 1)
        db.session.commit()
        flash("Curso atualizado.", "sucesso")
        return redirect("/cursos")
    return render_template("editar_curso.html", curso=curso)

@cursos_bp.route("/excluir_curso/<int:id>", methods=["POST"])
@admin_required
def excluir_curso(id):
    curso = Curso.query.get_or_404(id)
    db.session.delete(curso)
    db.session.commit()
    flash("Curso excluído.", "sucesso")
    return redirect("/cursos")