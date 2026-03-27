from flask import Blueprint, render_template, request, redirect, flash
from db import db
from models import Usuario
from security import login_required, admin_required, hash_senha

funcionario_bp = Blueprint("funcionario", __name__)


@funcionario_bp.route("/funcionario")
@funcionario_bp.route("/funcionarios")
@login_required
def listar_funcionarios():
    page   = request.args.get("page", 1, type=int)
    busca  = request.args.get("q", "").strip()
    perfil = request.args.get("perfil", "").strip()

    q = Usuario.query
    if busca:
        q = q.filter(Usuario.nome.ilike(f"%{busca}%"))
    if perfil:
        q = q.filter(Usuario.perfil == perfil)

    paginacao    = q.order_by(Usuario.nome).paginate(page=page, per_page=20, error_out=False)
    funcionarios = paginacao.items
    perfis       = ["administrador", "financeiro", "secretaria", "instrutor"]

    return render_template(
        "funcionario.html",
        funcionarios=funcionarios,
        paginacao=paginacao,
        busca=busca,
        perfil_filtro=perfil,
        perfis=perfis,
    )


@funcionario_bp.route("/salvar_funcionario", methods=["POST"])
@admin_required
def salvar_funcionario():
    f = request.form
    u = Usuario(
        nome     = f.get("nome"),
        usuario  = f.get("usuario"),
        senha    = hash_senha(f.get("senha", "")),
        perfil   = f.get("perfil", "secretaria"),
        cpf      = f.get("cpf"),
        telefone = f.get("telefone"),
        email    = f.get("email"),
    )
    db.session.add(u)
    db.session.commit()
    flash("Funcionário cadastrado.", "sucesso")
    return redirect("/funcionarios")


@funcionario_bp.route("/editar_funcionario/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_funcionario(id):
    u = Usuario.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        u.nome    = f.get("nome")
        u.usuario = f.get("usuario")
        u.perfil  = f.get("perfil")
        u.email   = f.get("email")
        nova_senha = f.get("senha", "").strip()
        if nova_senha:
            u.senha = hash_senha(nova_senha)
        db.session.commit()
        flash("Funcionário atualizado.", "sucesso")
        return redirect("/funcionarios")
    return render_template("editar_funcionario.html", funcionario=u)


@funcionario_bp.route("/excluir_funcionario/<int:id>", methods=["POST"])
@admin_required
def excluir_funcionario(id):
    u = Usuario.query.get_or_404(id)
    db.session.delete(u)
    db.session.commit()
    flash("Funcionário excluído.", "sucesso")
    return redirect("/funcionarios")


@funcionario_bp.route("/ver_funcionario/<int:id>")
@login_required
def ver_funcionario(id):
    u = Usuario.query.get_or_404(id)
    return render_template("ver_funcionario.html", funcionario=u)
