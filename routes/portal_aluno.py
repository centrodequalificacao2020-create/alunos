import os
from flask import Blueprint, render_template, request, redirect, session, flash, abort, send_file, make_response
from models import Aluno, Mensalidade, Frequencia, Conteudo, Materia, Matricula, ProgressoAula, CursoMateria, Nota
from security import verificar_senha, aluno_login_required, hash_senha
from db import db


portal_aluno_bp = Blueprint("portal_aluno", __name__)


def _matricula_ativa(aluno_id):
    """Retorna a matrícula ativa mais recente do aluno (maior id)."""
    return (
        Matricula.query
        .filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == "ATIVA"
        )
        .order_by(Matricula.id.desc())
        .first()
    )


@portal_aluno_bp.route("/login", methods=["GET", "POST"])
def login_aluno():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        aluno = Aluno.query.filter_by(email=email).first()
        if aluno and aluno.senha and verificar_senha(senha, aluno.senha):
            session.clear()
            session["aluno_id"] = aluno.id
            session["perfil"]   = "aluno"
            return redirect("/aluno/dashboard")
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("aluno/login.html")


@portal_aluno_bp.route("/logout")
def logout_aluno():
    session.clear()
    return redirect("/aluno/login")


@portal_aluno_bp.route("/dashboard")
@aluno_login_required
def dashboard_aluno():
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    matricula    = _matricula_ativa(aluno.id)
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


@portal_aluno_bp.route("/notas")
@aluno_login_required
def notas_aluno():
    aluno     = db.get_or_404(Aluno, session["aluno_id"])
    matricula = _matricula_ativa(aluno.id)
    notas     = []
    media     = None

    if matricula:
        # Busca as matérias do curso via cursos_materias e faz LEFT JOIN com notas
        # para mostrar TODAS as matérias mesmo sem nota lançada
        rows = (
            db.session.query(Materia, Nota)
            .join(CursoMateria, CursoMateria.materia_id == Materia.id)
            .outerjoin(
                Nota,
                (Nota.materia_id == Materia.id) &
                (Nota.aluno_id   == aluno.id) &
                (Nota.curso_id   == matricula.curso_id)
            )
            .filter(
                CursoMateria.curso_id == matricula.curso_id,
                Materia.ativa == 1
            )
            .order_by(Materia.nome)
            .all()
        )
        # rows = lista de (Materia, Nota|None)
        # reordena para manter compatibilidade com template que espera (Nota, Materia)
        notas = [(nota, materia) for materia, nota in rows]

        valores = [n.nota for n, m in notas if n is not None and n.nota is not None]
        if valores:
            media = round(sum(valores) / len(valores), 1)

    return render_template("aluno/notas.html", aluno=aluno,
                           matricula=matricula, notas=notas, media=media)


@portal_aluno_bp.route("/conteudo")
@aluno_login_required
def conteudo_aluno():
    aluno     = db.get_or_404(Aluno, session["aluno_id"])
    matricula = _matricula_ativa(aluno.id)
    conteudos = []

    if matricula:
        conteudos = (
            db.session.query(Conteudo, ProgressoAula)
            .outerjoin(
                ProgressoAula,
                (ProgressoAula.conteudo_id == Conteudo.id) &
                (ProgressoAula.aluno_id    == aluno.id)
            )
            .join(Materia,      Materia.id      == Conteudo.materia_id)
            .join(CursoMateria, CursoMateria.materia_id == Materia.id)
            .filter(CursoMateria.curso_id == matricula.curso_id)
            .order_by(Materia.nome, Conteudo.data)
            .all()
        )

    return render_template("aluno/conteudo.html", aluno=aluno, conteudos=conteudos)


@portal_aluno_bp.route("/arquivo/<int:conteudo_id>")
@aluno_login_required
def abrir_arquivo_conteudo(conteudo_id):
    """Serve arquivos locais de forma segura via Flask, sem permitir download."""
    import mimetypes

    conteudo = db.get_or_404(Conteudo, conteudo_id)

    if not conteudo.arquivo:
        abort(404)

    arquivo = conteudo.arquivo.strip()

    if arquivo.startswith("http://") or arquivo.startswith("https://"):
        return redirect(arquivo)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho  = arquivo.lstrip("/")

    candidatos = [
        os.path.join(base_dir, caminho),
        os.path.join(base_dir, "static", caminho.replace("static/", "", 1)),
        os.path.join(base_dir, "static", "uploads", os.path.basename(caminho)),
        os.path.join(base_dir, "uploads", os.path.basename(caminho)),
    ]

    for candidato in candidatos:
        if os.path.isfile(candidato):
            mime, _ = mimetypes.guess_type(candidato)
            mime = mime or "application/octet-stream"
            response = make_response(send_file(candidato, mimetype=mime))
            response.headers["Content-Disposition"] = "inline"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

    abort(404)


@portal_aluno_bp.route("/concluir/<int:conteudo_id>")
@aluno_login_required
def concluir_aula(conteudo_id):
    p = ProgressoAula.query.filter_by(
        aluno_id=session["aluno_id"], conteudo_id=conteudo_id).first()
    if not p:
        p = ProgressoAula(
            aluno_id    = session["aluno_id"],
            conteudo_id = conteudo_id,
            concluido   = 1
        )
        db.session.add(p)
    else:
        p.concluido = 1
    db.session.commit()
    return redirect("/aluno/conteudo")


@portal_aluno_bp.route("/senha", methods=["GET", "POST"])
@aluno_login_required
def trocar_senha():
    aluno = db.get_or_404(Aluno, session["aluno_id"])
    if request.method == "POST":
        atual    = request.form.get("senha_atual", "")
        nova     = request.form.get("nova_senha", "").strip()
        confirma = request.form.get("confirma_senha", "").strip()

        if not aluno.senha or not verificar_senha(atual, aluno.senha):
            flash("Senha atual incorreta.", "erro")
            return render_template("aluno/trocar_senha.html", aluno=aluno)

        if len(nova) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "erro")
            return render_template("aluno/trocar_senha.html", aluno=aluno)

        if nova != confirma:
            flash("As senhas não conferem.", "erro")
            return render_template("aluno/trocar_senha.html", aluno=aluno)

        aluno.senha = hash_senha(nova)
        db.session.commit()
        flash("Senha alterada com sucesso!", "sucesso")
        return redirect("/aluno/dashboard")

    return render_template("aluno/trocar_senha.html", aluno=aluno)
