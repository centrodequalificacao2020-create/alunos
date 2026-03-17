from flask import Blueprint, render_template, request, redirect, session, flash
from models import Aluno, Mensalidade, Frequencia, Conteudo, Matricula, ProgressoAula, CursoMateria
from security import verificar_senha, aluno_login_required
from db import db

portal_aluno_bp = Blueprint("portal_aluno", __name__)


@portal_aluno_bp.route("/login", methods=["GET", "POST"])
def login_aluno():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")
        aluno = Aluno.query.filter_by(email=email).first()
        if aluno and aluno.senha and verificar_senha(senha, aluno.senha):
            session["aluno_id"] = aluno.id
            return redirect("/aluno/dashboard")
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("aluno/login.html")


@portal_aluno_bp.route("/logout")
def logout_aluno():
    session.pop("aluno_id", None)
    return redirect("/aluno/login")


@portal_aluno_bp.route("/dashboard")
@aluno_login_required
def dashboard_aluno():
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    matricula    = Matricula.query.filter_by(aluno_id=aluno.id, status="ATIVA").first()
    mensalidades = Mensalidade.query.filter_by(aluno_id=aluno.id).order_by(Mensalidade.vencimento).all()
    pendentes    = sum(1 for m in mensalidades if m.status != "Pago")
    val_pend     = sum(m.valor for m in mensalidades if m.status != "Pago")
    return render_template("aluno/dashboard.html", aluno=aluno,
        matricula=matricula, mensalidades=mensalidades,
        pendentes=pendentes, valor_pendente=val_pend)


@portal_aluno_bp.route("/frequencia")
@aluno_login_required
def frequencia_aluno():
    aluno       = db.get_or_404(Aluno, session["aluno_id"])
    frequencias = Frequencia.query.filter_by(aluno_id=aluno.id).order_by(Frequencia.data.desc()).all()
    return render_template("aluno/frequencia.html", aluno=aluno, frequencias=frequencias)


@portal_aluno_bp.route("/conteudo")
@aluno_login_required
def conteudo_aluno():
    aluno     = db.get_or_404(Aluno, session["aluno_id"])
    matricula = Matricula.query.filter_by(aluno_id=aluno.id, status="ATIVA").first()
    conteudos = []

    if matricula:
        conteudos = (
            db.session.query(Conteudo, ProgressoAula)
            .outerjoin(
                ProgressoAula,
                (ProgressoAula.conteudo_id == Conteudo.id) &
                (ProgressoAula.aluno_id == aluno.id)
            )
            .join(CursoMateria, CursoMateria.materia_id == Conteudo.materia_id)
            .filter(CursoMateria.curso_id == matricula.curso_id)
            .order_by(Conteudo.data)
            .all()
        )

    return render_template("aluno/conteudo.html", aluno=aluno, conteudos=conteudos)


@portal_aluno_bp.route("/concluir/<int:conteudo_id>")
@aluno_login_required
def concluir_aula(conteudo_id):
    p = ProgressoAula.query.filter_by(
        aluno_id=session["aluno_id"], conteudo_id=conteudo_id).first()
    if not p:
        p = ProgressoAula(
            aluno_id=session["aluno_id"],
            conteudo_id=conteudo_id,
            concluido=1
        )
        db.session.add(p)
    else:
        p.concluido = 1
    db.session.commit()
    return redirect("/aluno/conteudo")
