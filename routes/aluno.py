from flask import Blueprint, render_template, request, redirect, flash, session
from db import db
from models import Aluno, Curso, Mensalidade
from security import login_required, admin_required

aluno_bp = Blueprint("aluno", __name__)


# ─────────────────────────── CADASTRO ───────────────────────────

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
    a = Aluno(
        nome                  = f.get("nome"),
        cpf                   = f.get("cpf"),
        rg                    = f.get("rg"),
        data_nascimento       = f.get("data_nascimento") or None,
        telefone              = f.get("telefone"),
        whatsapp              = f.get("whatsapp"),
        telefone_contato      = f.get("telefone_contato"),
        email                 = f.get("email"),
        endereco              = f.get("endereco"),
        status                = f.get("status", "Ativo"),
        curso_id              = f.get("curso_id") or None,
        responsavel_nome      = f.get("responsavel_nome"),
        responsavel_cpf       = f.get("responsavel_cpf"),
        responsavel_telefone  = f.get("responsavel_telefone"),
        responsavel_parentesco= f.get("responsavel_parentesco"),
    )
    db.session.add(a)
    db.session.commit()
    flash("Aluno cadastrado com sucesso.", "sucesso")
    return redirect("/cadastro")


@aluno_bp.route("/editar_aluno/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    a = Aluno.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        a.nome                   = f.get("nome")
        a.cpf                    = f.get("cpf")
        a.rg                     = f.get("rg")
        a.data_nascimento        = f.get("data_nascimento") or None
        a.telefone               = f.get("telefone")
        a.whatsapp               = f.get("whatsapp")
        a.email                  = f.get("email")
        a.endereco               = f.get("endereco")
        a.status                 = f.get("status")
        a.curso_id               = f.get("curso_id") or None
        a.responsavel_nome       = f.get("responsavel_nome")
        a.responsavel_cpf        = f.get("responsavel_cpf")
        a.responsavel_telefone   = f.get("responsavel_telefone")
        a.responsavel_parentesco = f.get("responsavel_parentesco")
        db.session.commit()
        flash("Aluno atualizado.", "sucesso")
        return redirect("/cadastro")
    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("editar_aluno.html", aluno=a, cursos=cursos)


@aluno_bp.route("/excluir_aluno/<int:id>", methods=["POST"])
@login_required
def excluir_aluno(id):
    a = Aluno.query.get_or_404(id)
    total = Mensalidade.query.filter_by(aluno_id=id).count()
    if total > 0:
        flash("Não é possível excluir: aluno possui registros financeiros.", "erro")
        return redirect("/cadastro")
    db.session.delete(a)
    db.session.commit()
    flash("Aluno excluído.", "sucesso")
    return redirect("/cadastro")


@aluno_bp.route("/aluno/<int:aluno_id>")
@login_required
def ficha_aluno(aluno_id):
    a = Aluno.query.get_or_404(aluno_id)
    return render_template("ficha_aluno.html", aluno=a)
