from datetime import date
from flask import Blueprint, render_template, request, redirect, flash, jsonify, session
from db import db
from models import Aluno, Curso, Mensalidade, Matricula
from security import login_required, verificar_senha
from sqlalchemy import func


aluno_bp = Blueprint("aluno", __name__)


def _cpf_limpo(cpf: str) -> str:
    return (cpf or "").replace(".", "").replace("-", "").replace(" ", "").strip()


@aluno_bp.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    if request.method == "POST":
        f   = request.form
        cpf = _cpf_limpo(f.get("cpf", ""))

        if cpf:
            existente = Aluno.query.filter(
                func.replace(func.replace(func.replace(Aluno.cpf, ".", ""), "-", ""), " ", "") == cpf
            ).first()
            if existente:
                flash(f"CPF já cadastrado para o aluno \u201c{existente.nome}\u201d.", "erro")
                cursos    = Curso.query.order_by(Curso.nome).all()
                paginacao = Aluno.query.order_by(Aluno.nome).paginate(page=1, per_page=20, error_out=False)
                hoje = date.today().isoformat()
                inadimplentes_ids = {
                    r[0] for r in db.session.query(Mensalidade.aluno_id.distinct())
                    .filter(Mensalidade.status == "Pendente", Mensalidade.vencimento < hoje).all()
                }
                for a in paginacao.items:
                    a.inadimplente = "true" if a.id in inadimplentes_ids else "false"
                return render_template("cadastro.html",
                                       alunos=paginacao.items,
                                       cursos=cursos,
                                       inadimplentes=len(inadimplentes_ids),
                                       paginacao=paginacao,
                                       busca="")

        a = Aluno(
            nome                   = f.get("nome"),
            cpf                    = f.get("cpf"),
            rg                     = f.get("rg"),
            data_nascimento        = f.get("data_nascimento") or None,
            telefone               = f.get("telefone"),
            whatsapp               = f.get("whatsapp"),
            telefone_contato       = f.get("telefone_contato"),
            email                  = f.get("email"),
            endereco               = f.get("endereco"),
            status                 = f.get("status", "Ativo"),
            curso_id               = f.get("curso_id") or None,
            responsavel_nome       = f.get("responsavel_nome"),
            responsavel_cpf        = f.get("responsavel_cpf"),
            responsavel_telefone   = f.get("responsavel_telefone"),
            responsavel_parentesco = f.get("responsavel_parentesco"),
        )
        db.session.add(a)
        db.session.commit()
        flash("Aluno cadastrado com sucesso.", "sucesso")
        return redirect("/cadastro")

    page      = request.args.get("page", 1, type=int)
    busca     = request.args.get("q", "").strip()
    query     = Aluno.query.order_by(Aluno.nome)
    if busca:
        query = query.filter(Aluno.nome.ilike(f"%{busca}%"))
    paginacao = query.paginate(page=page, per_page=20, error_out=False)
    alunos    = paginacao.items

    cursos = Curso.query.order_by(Curso.nome).all()

    hoje = date.today().isoformat()
    inadimplentes_ids = {
        r[0] for r in db.session.query(Mensalidade.aluno_id.distinct())
        .filter(Mensalidade.status == "Pendente", Mensalidade.vencimento < hoje)
        .all()
    }
    for a in alunos:
        a.inadimplente = "true" if a.id in inadimplentes_ids else "false"

    return render_template("cadastro.html",
                           alunos=alunos,
                           cursos=cursos,
                           inadimplentes=len(inadimplentes_ids),
                           paginacao=paginacao,
                           busca=busca)


@aluno_bp.route("/aluno/<int:id>/pendencias")
@login_required
def pendencias_aluno(id):
    pendentes = Mensalidade.query.filter_by(aluno_id=id, status="Pendente").all()
    total     = sum(m.valor or 0 for m in pendentes)
    return jsonify({"total_parcelas": len(pendentes), "total_valor": float(total)})


@aluno_bp.route("/excluir_aluno/<int:id>", methods=["POST"])
@login_required
def excluir_aluno(id):
    from models import Usuario
    senha = request.form.get("senha", "")
    user  = Usuario.query.get(session.get("usuario_id"))
    if not user or not verificar_senha(senha, user.senha):
        flash("Senha incorreta. Exclusão cancelada.", "erro")
        return redirect("/cadastro")
    a = Aluno.query.get_or_404(id)
    nome = a.nome
    Mensalidade.query.filter_by(aluno_id=id).delete()
    Matricula.query.filter_by(aluno_id=id).delete()
    db.session.delete(a)
    db.session.commit()
    flash(f"Aluno \u201c{nome}\u201d excluído com sucesso.", "sucesso")
    return redirect("/cadastro")


@aluno_bp.route("/editar_aluno/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    a = Aluno.query.get_or_404(id)
    if request.method == "POST":
        f   = request.form
        cpf = _cpf_limpo(f.get("cpf", ""))

        if cpf:
            existente = Aluno.query.filter(
                func.replace(func.replace(func.replace(Aluno.cpf, ".", ""), "-", ""), " ", "") == cpf,
                Aluno.id != id
            ).first()
            if existente:
                flash(f"CPF já cadastrado para o aluno \u201c{existente.nome}\u201d.", "erro")
                cursos = Curso.query.order_by(Curso.nome).all()
                return render_template("editar_aluno.html", aluno=a, cursos=cursos)

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


@aluno_bp.route("/aluno/<int:aluno_id>")
@login_required
def ficha_aluno(aluno_id):
    aluno      = Aluno.query.get_or_404(aluno_id)
    matriculas = Matricula.query.filter_by(aluno_id=aluno_id).all()
    for m in matriculas:
        curso        = Curso.query.get(m.curso_id)
        m.curso_nome = curso.nome if curso else "—"
    return render_template("ficha_aluno.html", aluno=aluno, matriculas=matriculas)
