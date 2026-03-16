from functools import wraps
from flask import session, redirect, flash
from werkzeug.security import generate_password_hash, check_password_hash

EXTENSOES_PERMITIDAS = {"pdf", "png", "jpg", "jpeg", "docx", "mp4"}

def hash_senha(senha):
    return generate_password_hash(senha)

def verificar_senha(senha, hashed):
    return check_password_hash(hashed, senha)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Faça login para continuar.", "erro")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect("/login")
        if session.get("perfil") != "admin":
            flash("Acesso restrito a administradores.", "erro")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated

def aluno_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "aluno_id" not in session:
            return redirect("/aluno/login")
        return f(*args, **kwargs)
    return decorated

def extensao_permitida(filename):
    return "." in filename and            filename.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS