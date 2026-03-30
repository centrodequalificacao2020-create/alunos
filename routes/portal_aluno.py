import os
from datetime import date
from flask import Blueprint, render_template, request, redirect, session, flash, abort, send_file, make_response, Response
from models import Aluno, Mensalidade, Frequencia, Conteudo, Materia, Matricula, ProgressoAula, CursoMateria, Nota, Curso
from security import verificar_senha, aluno_login_required, hash_senha
from db import db
from app import limiter


portal_aluno_bp = Blueprint("portal_aluno", __name__)


def _matriculas_ativas(aluno_id):
    """Retorna todas as matrículas ativas do aluno, com o curso carregado."""
    return (
        Matricula.query
        .filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == "ATIVA"
        )
        .order_by(Matricula.id.desc())
        .all()
    )


def _matricula_ativa(aluno_id):
    """Retorna a matrícula ativa mais recente do aluno (retrocompatibilidade)."""
    return (
        Matricula.query
        .filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == "ATIVA"
        )
        .order_by(Matricula.id.desc())
        .first()
    )


def _aluno_pode_acessar_conteudo(aluno_id, conteudo):
    """Verifica se o aluno tem matrícula ativa em algum curso que contenha essa matéria."""
    matriculas = _matriculas_ativas(aluno_id)
    for mat in matriculas:
        vinculo = (
            db.session.query(CursoMateria)
            .filter(
                CursoMateria.materia_id == conteudo.materia_id,
                CursoMateria.curso_id   == mat.curso_id,
            )
            .first()
        )
        if vinculo:
            return True
    return False


def _contar_atrasadas(mensalidades):
    """Conta parcelas nao pagas cujo vencimento ja passou (atrasadas de verdade)."""
    hoje = date.today().strftime("%Y-%m-%d")
    count = 0
    for m in mensalidades:
        if m.status != "Pago" and m.vencimento and str(m.vencimento) < hoje:
            count += 1
    return count


@portal_aluno_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login_aluno():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        aluno = Aluno.query.filter_by(email=email).first()
        if aluno and aluno.senha and verificar_senha(senha, aluno.senha):
            session.clear()
            session.permanent = True
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
    atrasadas    = _contar_atrasadas(mensalidades)
    val_pend     = sum(m.valor for m in mensalidades if m.status != "Pago")
    return render_template("aluno/dashboard.html", aluno=aluno,
        matricula=matricula, atrasadas=atrasadas, valor_pendente=val_pend)


@portal_aluno_bp.route("/financeiro")
@aluno_login_required
def financeiro_aluno():
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    matricula    = _matricula_ativa(aluno.id)
    mensalidades = Mensalidade.query.filter_by(aluno_id=aluno.id).order_by(Mensalidade.vencimento).all()
    atrasadas    = _contar_atrasadas(mensalidades)
    val_pend     = sum(m.valor for m in mensalidades if m.status != "Pago")
    return render_template("aluno/financeiro.html", aluno=aluno,
        matricula=matricula, mensalidades=mensalidades,
        atrasadas=atrasadas, valor_pendente=val_pend)


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
        notas = [(nota, materia) for materia, nota in rows]
        valores = [n.nota for n, m in notas if n is not None and n.nota is not None]
        if valores:
            media = round(sum(valores) / len(valores), 1)

    return render_template("aluno/notas.html", aluno=aluno,
                           matricula=matricula, notas=notas, media=media)


# ── PASSO 1: selecionar o curso ────────────────────────────────────────────────
@portal_aluno_bp.route("/conteudo")
@aluno_login_required
def conteudo_cursos():
    """Exibe um card por curso em que o aluno está matriculado."""
    aluno      = db.get_or_404(Aluno, session["aluno_id"])
    matriculas = _matriculas_ativas(aluno.id)

    # Enriquece cada matrícula com o objeto Curso e o progresso geral
    cursos_info = []
    for mat in matriculas:
        curso = Curso.query.get(mat.curso_id)
        if not curso:
            continue

        # Total de conteúdos do curso
        total = (
            db.session.query(Conteudo)
            .join(Materia,      Materia.id      == Conteudo.materia_id)
            .join(CursoMateria, CursoMateria.materia_id == Materia.id)
            .filter(CursoMateria.curso_id == curso.id)
            .count()
        )
        # Conteúdos concluídos pelo aluno neste curso
        concluidos = (
            db.session.query(ProgressoAula)
            .join(Conteudo, Conteudo.id == ProgressoAula.conteudo_id)
            .join(Materia,  Materia.id  == Conteudo.materia_id)
            .join(CursoMateria, CursoMateria.materia_id == Materia.id)
            .filter(
                CursoMateria.curso_id       == curso.id,
                ProgressoAula.aluno_id      == aluno.id,
                ProgressoAula.concluido     == 1
            )
            .count()
        )
        pct = round(concluidos / total * 100) if total > 0 else 0

        cursos_info.append({
            "curso":      curso,
            "matricula":  mat,
            "total":      total,
            "concluidos": concluidos,
            "pct":        pct,
        })

    return render_template("aluno/conteudo_cursos.html", aluno=aluno, cursos_info=cursos_info)


# ── PASSO 2: player de aulas do curso selecionado ─────────────────────────────
@portal_aluno_bp.route("/conteudo/<int:curso_id>")
@aluno_login_required
def conteudo_aluno(curso_id):
    """Exibe as aulas do curso escolhido."""
    aluno = db.get_or_404(Aluno, session["aluno_id"])

    # Garante que o aluno está matriculado neste curso
    matricula = Matricula.query.filter(
        Matricula.aluno_id == aluno.id,
        Matricula.curso_id == curso_id,
        db.func.upper(Matricula.status) == "ATIVA"
    ).first()
    if not matricula:
        abort(403)

    curso = db.get_or_404(Curso, curso_id)

    conteudos = (
        db.session.query(Conteudo, ProgressoAula)
        .outerjoin(
            ProgressoAula,
            (ProgressoAula.conteudo_id == Conteudo.id) &
            (ProgressoAula.aluno_id    == aluno.id)
        )
        .join(Materia,      Materia.id      == Conteudo.materia_id)
        .join(CursoMateria, CursoMateria.materia_id == Materia.id)
        .filter(CursoMateria.curso_id == curso_id)
        .order_by(Materia.nome, Conteudo.data)
        .all()
    )

    return render_template("aluno/conteudo.html",
                           aluno=aluno, curso=curso, conteudos=conteudos)


@portal_aluno_bp.route("/arquivo/<int:conteudo_id>")
@aluno_login_required
def abrir_arquivo_conteudo(conteudo_id):
    """
    Serve o PDF em bytes para o PDF.js.
    - Verifica ownership (IDOR fix)
    - NAO expoe o caminho real do arquivo
    - Bloqueia download via Content-Disposition: inline
    - Bloqueia abertura em aba separada via X-Frame-Options: SAMEORIGIN
    - Bloqueia cache no cliente via Cache-Control
    """
    import mimetypes

    conteudo = db.get_or_404(Conteudo, conteudo_id)

    if not _aluno_pode_acessar_conteudo(session["aluno_id"], conteudo):
        abort(403)

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

            with open(candidato, "rb") as f:
                dados = f.read()

            response = Response(dados, mimetype=mime)
            response.headers["Content-Disposition"] = "inline"
            response.headers["X-Frame-Options"]     = "SAMEORIGIN"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"]        = "no-cache"
            return response

    abort(404)


@portal_aluno_bp.route("/concluir/<int:conteudo_id>")
@aluno_login_required
def concluir_aula(conteudo_id):
    conteudo = db.get_or_404(Conteudo, conteudo_id)

    # Descobre o curso_id para redirecionar de volta
    materia = Materia.query.get(conteudo.materia_id)
    curso_id = None
    if materia:
        cm = CursoMateria.query.filter_by(materia_id=materia.id).first()
        if cm:
            curso_id = cm.curso_id

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

    if curso_id:
        return redirect(f"/aluno/conteudo/{curso_id}")
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
            flash("As senhas nao conferem.", "erro")
            return render_template("aluno/trocar_senha.html", aluno=aluno)

        aluno.senha = hash_senha(nova)
        db.session.commit()
        flash("Senha alterada com sucesso!", "sucesso")
        return redirect("/aluno/dashboard")

    return render_template("aluno/trocar_senha.html", aluno=aluno)
