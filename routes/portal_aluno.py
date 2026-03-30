from flask import Blueprint, render_template, session, redirect, flash, request, send_from_directory, abort
from db import db
from models import (
    Aluno, Matricula, Mensalidade, Nota, Frequencia,
    Materia, Conteudo, ProgressoAula, AcessoConteudoCurso, Curso
)
from security import aluno_login_required, hash_senha, verificar_senha
from datetime import date, datetime
import os

portal_aluno_bp = Blueprint("portal_aluno", __name__)


def _get_aluno():
    return db.get_or_404(Aluno, session["aluno_id"])


# ─── LOGIN / LOGOUT ──────────────────────────────────────────────────────────

@portal_aluno_bp.route("/login", methods=["GET", "POST"])
def aluno_login():
    if request.method == "POST":
        cpf   = request.form.get("cpf", "").strip()
        senha = request.form.get("senha", "").strip()
        aluno = Aluno.query.filter_by(cpf=cpf).first()
        if not aluno or not aluno.senha or not verificar_senha(senha, aluno.senha):
            flash("CPF ou senha incorretos.", "erro")
            return redirect("/aluno/login")
        from models import LoginHistoricoAluno
        db.session.add(LoginHistoricoAluno(
            aluno_id=aluno.id,
            login_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        db.session.commit()
        session["aluno_id"] = aluno.id
        session["perfil"]   = "aluno"
        return redirect("/aluno/dashboard")
    return render_template("aluno/login.html")


@portal_aluno_bp.route("/logout")
def aluno_logout():
    session.clear()
    return redirect("/aluno/login")


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/dashboard")
@aluno_login_required
def aluno_dashboard():
    aluno     = _get_aluno()
    matricula = aluno.matricula_ativa
    hoje      = date.today().isoformat()

    atrasadas = sum(
        1 for m in aluno.mensalidades
        if m.status.upper() in ("PENDENTE", "ATRASADO") and m.vencimento and m.vencimento < hoje
    )

    provas_disp = 0
    try:
        from models import Prova, RespostaProva
        cursos_aluno = [
            m.curso_id for m in aluno.matriculas
            if m.status.upper() == "ATIVA" and m.curso_id
        ]
        if cursos_aluno:
            provas_ativas = Prova.query.filter(
                Prova.ativa == 1,
                Prova.curso_id.in_(cursos_aluno)
            ).all()
            for p in provas_ativas:
                usadas = RespostaProva.query.filter_by(
                    prova_id=p.id, aluno_id=aluno.id
                ).count()
                if usadas < p.tentativas:
                    provas_disp += 1
    except Exception:
        provas_disp = 0

    return render_template(
        "aluno/dashboard.html",
        aluno        = aluno,
        matricula    = matricula,
        atrasadas    = atrasadas,
        provas_disp  = provas_disp,
        ultimo_login = aluno.ultimo_login,
    )


# ─── FINANCEIRO ──────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/financeiro")
@aluno_login_required
def aluno_financeiro():
    aluno = _get_aluno()
    return render_template("aluno/financeiro.html",
                           aluno=aluno,
                           mensalidades=aluno.mensalidades)


# ─── NOTAS / BOLETIM ─────────────────────────────────────────────────────────

@portal_aluno_bp.route("/notas")
@aluno_login_required
def aluno_notas():
    aluno     = _get_aluno()
    matricula = aluno.matricula_ativa
    curso_id  = matricula.curso_id if matricula else None

    notas_dict = {}
    for n in aluno.notas:
        notas_dict.setdefault(n.materia_id, []).append(n)

    materias = []
    if curso_id:
        materias = Materia.query.filter_by(curso_id=curso_id, ativa=1).all()

    provas_realizadas = []
    melhor_por_prova  = {}
    try:
        from models import Prova, RespostaProva
        if curso_id:
            provas_realizadas = (
                db.session.query(RespostaProva)
                .join(Prova, Prova.id == RespostaProva.prova_id)
                .filter(
                    RespostaProva.aluno_id == aluno.id,
                    Prova.curso_id == curso_id,
                )
                .order_by(RespostaProva.finalizado_em.desc())
                .all()
            )
            for rp in provas_realizadas:
                if rp.nota_obtida is not None:
                    ant = melhor_por_prova.get(rp.prova_id)
                    if ant is None or rp.nota_obtida > ant.nota_obtida:
                        melhor_por_prova[rp.prova_id] = rp
    except Exception:
        provas_realizadas = []
        melhor_por_prova  = {}

    return render_template(
        "aluno/notas.html",
        aluno             = aluno,
        matricula         = matricula,
        notas_dict        = notas_dict,
        materias          = materias,
        provas_realizadas = provas_realizadas,
        melhor_por_prova  = melhor_por_prova,
    )


# ─── FREQUÊNCIA ──────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/frequencia")
@aluno_login_required
def aluno_frequencia():
    aluno = _get_aluno()
    freqs = sorted(aluno.frequencias, key=lambda f: f.data or "", reverse=True)
    total    = len(freqs)
    presente = sum(1 for f in freqs if f.status == "presente")
    pct      = round(presente / total * 100) if total else 0
    return render_template("aluno/frequencia.html",
                           aluno=aluno, frequencias=freqs,
                           total=total, presente=presente, pct=pct)


# ─── CONTEÚDO ────────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/conteudo")
@aluno_login_required
def aluno_conteudo():
    aluno     = _get_aluno()
    matricula = aluno.matricula_ativa

    if not matricula:
        return render_template("aluno/conteudo_cursos.html", aluno=aluno, cursos=[])

    acesso = AcessoConteudoCurso.query.filter_by(
        aluno_id=aluno.id, curso_id=matricula.curso_id, liberado=1
    ).first()
    if not acesso:
        flash("Seu acesso ao conteúdo ainda não foi liberado. Fale com a secretaria.", "erro")
        return redirect("/aluno/dashboard")

    curso    = db.get_or_404(Curso, matricula.curso_id)
    materias = Materia.query.filter_by(curso_id=matricula.curso_id, ativa=1).all()

    # Monta lista de conteúdos ordenados por matéria/id como tuplas (conteudo, progresso)
    conteudos_raw = (
        Conteudo.query
        .filter(Conteudo.materia_id.in_([m.id for m in materias]))
        .order_by(Conteudo.materia_id, Conteudo.id)
        .all()
    )
    progressos_map = {
        p.conteudo_id: p
        for p in ProgressoAula.query.filter_by(aluno_id=aluno.id).all()
    }
    # Lista de tuplas (conteudo, progresso_ou_None) — exatamente o que o template espera
    conteudos = [(c, progressos_map.get(c.id)) for c in conteudos_raw]

    return render_template(
        "aluno/conteudo.html",
        aluno     = aluno,
        curso     = curso,
        materias  = materias,
        conteudos = conteudos,
    )


@portal_aluno_bp.route("/conteudo/concluir/<int:conteudo_id>", methods=["POST"])
@aluno_login_required
def concluir_aula(conteudo_id):
    aluno = _get_aluno()
    prog  = ProgressoAula.query.filter_by(
        aluno_id=aluno.id, conteudo_id=conteudo_id
    ).first()
    if not prog:
        db.session.add(ProgressoAula(
            aluno_id=aluno.id, conteudo_id=conteudo_id, concluido=1
        ))
        db.session.commit()
    return redirect("/aluno/conteudo")


# Rota legada referenciada no JS do template (/aluno/concluir/<id>)
@portal_aluno_bp.route("/concluir/<int:conteudo_id>", methods=["GET", "POST"])
@aluno_login_required
def concluir_aula_legado(conteudo_id):
    aluno = _get_aluno()
    prog  = ProgressoAula.query.filter_by(
        aluno_id=aluno.id, conteudo_id=conteudo_id
    ).first()
    if not prog:
        db.session.add(ProgressoAula(
            aluno_id=aluno.id, conteudo_id=conteudo_id, concluido=1
        ))
        db.session.commit()
    return redirect("/aluno/conteudo")


# ─── SERVIR ARQUIVO DE CONTEÚDO (PDF / download) ─────────────────────────────

@portal_aluno_bp.route("/arquivo/<int:conteudo_id>")
@aluno_login_required
def servir_arquivo(conteudo_id):
    """Serve o arquivo de um conteúdo apenas para alunos autenticados com acesso."""
    from flask import current_app
    aluno    = _get_aluno()
    conteudo = db.get_or_404(Conteudo, conteudo_id)

    if not conteudo.arquivo:
        abort(404)

    # Verifica se o aluno tem matrícula no curso da matéria
    materia = db.session.get(Materia, conteudo.materia_id)
    if materia:
        cursos_aluno = [
            m.curso_id for m in aluno.matriculas
            if m.status.upper() == "ATIVA"
        ]
        if materia.curso_id not in cursos_aluno:
            abort(403)

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    filename      = os.path.basename(conteudo.arquivo)
    return send_from_directory(upload_folder, filename)


# ─── TROCAR SENHA ────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/senha", methods=["GET", "POST"])
@aluno_login_required
def aluno_trocar_senha():
    aluno = _get_aluno()
    if request.method == "POST":
        atual  = request.form.get("atual",  "").strip()
        nova   = request.form.get("nova",   "").strip()
        repete = request.form.get("repete", "").strip()
        if not aluno.senha or not verificar_senha(atual, aluno.senha):
            flash("Senha atual incorreta.", "erro")
        elif nova != repete:
            flash("As senhas não coincidem.", "erro")
        elif len(nova) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "erro")
        else:
            aluno.senha = hash_senha(nova)
            db.session.commit()
            flash("Senha alterada com sucesso!", "sucesso")
            return redirect("/aluno/dashboard")
    return render_template("aluno/trocar_senha.html", aluno=aluno)
