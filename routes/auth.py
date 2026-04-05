from flask import Blueprint, render_template, request, redirect, session, flash
from models import Usuario, Aluno
from security import verificar_senha
from app import limiter

auth_bp = Blueprint("auth", __name__)


def _vincular_aluno(user):
    """Tenta vincular session[aluno_id] cruzando Usuario com Aluno por email.

    BUG-04: fallback por nome removido — nomes não são identificadores únicos
    e causariam que alunos homônimos acessassem a conta errada.
    """
    if not user.email:
        from flask import current_app
        current_app.logger.warning(
            f"[_vincular_aluno] Usuario id={user.id} sem email — aluno não vinculado."
        )
        return
    aluno = Aluno.query.filter(
        Aluno.email.isnot(None),
        Aluno.email != "",
    ).filter(
        Aluno.email.collate("NOCASE") == user.email
    ).first()
    if aluno:
        session["aluno_id"] = aluno.id
    else:
        from flask import current_app
        current_app.logger.warning(
            f"[_vincular_aluno] Login sem aluno vinculado: {user.email}"
        )


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        u = request.form.get("login", "").strip()
        s = request.form.get("senha", "")
        user = Usuario.query.filter_by(usuario=u).first()
        if user and verificar_senha(s, user.senha):
            session.permanent = True  # S5: respeita PERMANENT_SESSION_LIFETIME
            session["usuario_id"]   = user.id
            session["usuario_nome"] = user.nome
            session["perfil"]       = user.perfil
            if user.perfil == "aluno":
                _vincular_aluno(user)
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
    if session.get("perfil") == "aluno":
        return redirect("/aluno/dashboard")
    from models import Aluno
    total_alunos = Aluno.query.filter_by(status="Ativo").count()
    return render_template("home.html", total_alunos=total_alunos)
