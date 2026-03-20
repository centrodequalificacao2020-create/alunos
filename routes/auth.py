from flask import Blueprint, render_template, request, redirect, session, flash
from models import Usuario, Aluno
from security import verificar_senha

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("login", "").strip()
        s = request.form.get("senha", "")
        user = Usuario.query.filter_by(usuario=u).first()
        if user and verificar_senha(s, user.senha):
            session["usuario_id"]   = user.id
            session["usuario_nome"] = user.nome
            session["perfil"]       = user.perfil
            # Aluno não usa o sistema interno — redireciona para o portal do aluno
            if user.perfil == "aluno":
                return redirect("/aluno/dashboard")
            return redirect("/")
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@auth_bp.route("/")
def home():
    if "usuario_id" not in session:
        return redirect("/login")
    # Aluno não deve acessar a home interna
    if session.get("perfil") == "aluno":
        return redirect("/aluno/dashboard")
    total_alunos = Aluno.query.filter_by(status="Ativo").count()
    return render_template("home.html", total_alunos=total_alunos)
