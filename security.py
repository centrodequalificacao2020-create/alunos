from functools import wraps
from flask import session, redirect, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash

# Perfis reconhecidos pelo sistema
PERFIS_VALIDOS = {"admin", "administrador", "secretaria", "financeiro", "instrutor"}
ADMIN_PERFIS   = {"administrador", "admin"}
FINAN_PERFIS   = {"administrador", "admin", "financeiro"}


def hash_senha(senha: str) -> str:
    return generate_password_hash(senha)


def verificar_senha(senha: str, hashed: str) -> bool:
    return check_password_hash(hashed, senha)


def extensao_permitida(filename: str) -> bool:
    """Valida extensão usando a lista definida em config.py."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("EXTENSOES_PERMITIDAS", set())


def login_required(f):
    """Exige sessão admin ativa. Bloqueia alunos."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para continuar.", "erro")
            return redirect("/login")
        if session.get("perfil") == "aluno":
            return redirect("/aluno/dashboard")
        return f(*args, **kwargs)
    return decorated


def financeiro_required(f):
    """Exige perfil admin ou financeiro."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect("/login")
        if session.get("perfil", "").lower() not in FINAN_PERFIS:
            flash("Acesso restrito ao setor financeiro.", "erro")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Exige que o perfil do usuário seja administrador."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect("/login")
        if session.get("perfil", "").lower() not in ADMIN_PERFIS:
            flash("Acesso restrito a administradores.", "erro")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


def aluno_login_required(f):
    """Exige sessão de aluno ativa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "aluno_id" not in session:
            return redirect("/aluno/login")
        # Garante que não é uma sessão admin infiltrada
        if session.get("perfil") not in ("aluno", None):
            return redirect("/aluno/login")
        return f(*args, **kwargs)
    return decorated
