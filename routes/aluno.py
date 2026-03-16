from flask import Blueprint, render_template, request, redirect, flash
from db import db
from models import Aluno, Curso, Mensalidade
from security import login_required, admin_required

aluno_bp = Blueprint("aluno", __name__)

@aluno_bp.route("/cadastro")
@login_required
def cadastro():
    alunos = Aluno.query.order_by(Aluno.nome).all()
    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("cadastro.html", alunos=alunos, cursos=cursos)

@aluno_bp.route("/salvar_aluno", methods=["POST"])
@login_required
def salvar_aluno():
    f = request.form
    aluno = Aluno(
        nome                 = f.get("nome"),
        cpf                  = f.get("cpf"),
        rg                   = f.get("rg"),
        data_nascimento      = f.get("data_nascimento"),
        telefone             = f.get("telefone"),
        whatsapp             = f.get("whatsapp"),
        telefone_contato     = f.get("telefone_contato"),
        email                = f.get("email"),
        endereco             = f.get("endereco"),
        status               = f.get("status", "Ativo"),
        curso_id             = f.get("curso_id") or None,
        responsavel_nome     = f.get("responsavel_nome"),
        responsavel_cpf      = f.get("responsavel_cpf"),
        responsavel_telefone = f.get("responsavel_telefone"),
        responsavel_parentesco = f.get("responsavel_parentesco"),
    )
    db.session.add(aluno)
    db.session.commit()
    flash("Aluno cadastrado com sucesso.", "sucesso")
    return redirect("/cadastro")

@aluno_bp.route("/editar_aluno/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    aluno  = Aluno.query.get_or_404(id)
    cursos = Curso.query.all()
    if request.method == "POST":
        f = request.form
        aluno.nome                  = f.get("nome")
        aluno.cpf                   = f.get("cpf")
        aluno.rg                    = f.get("rg")
        aluno.data_nascimento       = f.get("data_nascimento")
        aluno.telefone              = f.get("telefone")
        aluno.whatsapp              = f.get("whatsapp")
        aluno.email                 = f.get("email")
        aluno.endereco              = f.get("endereco")
        aluno.status                = f.get("status")
        aluno.curso_id              = f.get("curso_id") or None
        aluno.responsavel_nome      = f.get("responsavel_nome")
        aluno.responsavel_cpf       = f.get("responsavel_cpf")
        aluno.responsavel_telefone  = f.get("responsavel_telefone")
        aluno.responsavel_parentesco= f.get("responsavel_parentesco")
        db.session.commit()
        flash("Aluno atualizado.", "sucesso")
        return redirect("/cadastro")
    return render_template("editar_aluno.html", aluno=aluno, cursos=cursos)

@aluno_bp.route("/excluir_aluno/<int:id>", methods=["POST"])
@login_required
def excluir_aluno(id):
    total = Mensalidade.query.filter_by(aluno_id=id).count()
    if total > 0:
        flash("Não é possível excluir: aluno possui registros financeiros.", "erro")
        return redirect("/cadastro")
    aluno = Aluno.query.get_or_404(id)
    db.session.delete(aluno)
    db.session.commit()
    flash("Aluno excluído.", "sucesso")
    return redirect("/cadastro")

@aluno_bp.route("/aluno/<int:aluno_id>")
@login_required
def ficha_aluno(aluno_id):
    aluno = Aluno.query.get_or_404(aluno_id)
    return render_template("ficha_aluno.html", aluno=aluno)
