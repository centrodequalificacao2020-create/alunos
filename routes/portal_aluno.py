from flask import Blueprint, render_template, session, redirect, flash, request, send_from_directory, abort
from db import db
from models import (
    Aluno, Matricula, Mensalidade, Nota, Frequencia,
    Materia, Conteudo, ProgressoAula, AcessoConteudoCurso, Curso,
    MateriaLiberada, ProvaLiberada, Atividade, EntregaAtividade
)
from security import aluno_login_required, hash_senha, verificar_senha
from datetime import date, datetime
import os
import re

portal_aluno_bp = Blueprint("portal_aluno", __name__)


def _get_aluno():
    return db.get_or_404(Aluno, session["aluno_id"])


def _normalizar_cpf(cpf: str) -> str:
    """Remove tudo que nao for digito: '123.456.789-00' -> '12345678900'."""
    return re.sub(r"\D", "", cpf or "")


def _buscar_aluno_por_login(identificador: str):
    """
    Tenta localizar o aluno pelo identificador informado.
    Aceita:
      - E-mail  (contém '@')
      - CPF com mascara  ('123.456.789-00')
      - CPF sem mascara  ('12345678900')
    """
    ident = identificador.strip()

    if "@" in ident:
        # --- busca por e-mail (case-insensitive) ---
        return Aluno.query.filter(
            db.func.lower(Aluno.email) == ident.lower()
        ).first()

    # --- busca por CPF ---
    # Tenta primeiro com o valor exato digitado
    aluno = Aluno.query.filter_by(cpf=ident).first()
    if aluno:
        return aluno

    # Normaliza ambos os lados (remove mascara) e tenta de novo
    cpf_limpo = _normalizar_cpf(ident)
    if not cpf_limpo:
        return None

    # Busca todos os alunos cujo CPF normalizado bate
    # (resolve casos em que o banco tem '123.456.789-00' e o usuario digitou '12345678900')
    for a in Aluno.query.all():
        if _normalizar_cpf(a.cpf or "") == cpf_limpo:
            return a
    return None


# ─── LOGIN / LOGOUT ───────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/login", methods=["GET", "POST"])
def aluno_login():
    if request.method == "POST":
        identificador = request.form.get("cpf", "").strip()   # campo mantém name="cpf"
        senha         = request.form.get("senha", "").strip()

        aluno = _buscar_aluno_por_login(identificador)

        if not aluno:
            flash("Usuário não encontrado. Verifique o CPF ou e-mail digitado.", "erro")
            return redirect("/aluno/login")

        if not aluno.senha:
            flash(
                "Sua senha ainda não foi definida. "
                "Entre em contato com a secretaria para receber sua senha de acesso.",
                "erro"
            )
            return redirect("/aluno/login")

        if not verificar_senha(senha, aluno.senha):
            flash("Senha incorreta. Tente novamente.", "erro")
            return redirect("/aluno/login")

        # Login bem-sucedido — registra histórico
        from models import LoginHistoricoAluno
        db.session.add(LoginHistoricoAluno(
            aluno_id   = aluno.id,
            login_em   = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ip         = request.remote_addr,
            user_agent = request.user_agent.string[:300] if request.user_agent else None,
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


# ─── DASHBOARD ─────────────────────────────────────────────────────────────────────

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

    return render_template(
        "aluno/dashboard.html",
        aluno        = aluno,
        matricula    = matricula,
        atrasadas    = atrasadas,
        ultimo_login = aluno.ultimo_login,
    )


# ─── FINANCEIRO ──────────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/financeiro")
@aluno_login_required
def aluno_financeiro():
    aluno = _get_aluno()
    return render_template("aluno/financeiro.html",
                           aluno=aluno,
                           mensalidades=aluno.mensalidades)


# ─── NOTAS / BOLETIM ─────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/notas")
@aluno_login_required
def aluno_notas():
    aluno     = _get_aluno()
    matricula = aluno.matricula_ativa
    curso_id  = matricula.curso_id if matricula else None

    notas_dict = {}
    for n in aluno.notas:
        if n.publicada:
            notas_dict.setdefault(n.materia_id, []).append(n)

    materias = []
    if curso_id:
        materias = Materia.query.filter_by(curso_id=curso_id, ativa=1).all()

    from models import RespostaProva
    provas_realizadas = (
        RespostaProva.query
        .filter_by(aluno_id=aluno.id)
        .order_by(RespostaProva.prova_id, RespostaProva.tentativa_num.desc())
        .all()
    )

    melhor_por_prova = {}
    for rp in provas_realizadas:
        atual = melhor_por_prova.get(rp.prova_id)
        if atual is None or (rp.nota_obtida or 0.0) > (atual.nota_obtida or 0.0):
            melhor_por_prova[rp.prova_id] = rp

    return render_template(
        "aluno/notas.html",
        aluno             = aluno,
        matricula         = matricula,
        notas_dict        = notas_dict,
        materias          = materias,
        provas_realizadas = provas_realizadas,
        melhor_por_prova  = melhor_por_prova,
    )


# ─── FREQUÊNCIA ───────────────────────────────────────────────────────────────────

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


# ─── CURSOS ───────────────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/cursos")
@aluno_login_required
def aluno_cursos():
    aluno = _get_aluno()
    matriculas_ativas = [
        m for m in aluno.matriculas if m.status.upper() == "ATIVA"
    ]
    cursos_com_acesso = []
    for m in matriculas_ativas:
        acesso = AcessoConteudoCurso.query.filter_by(
            aluno_id=aluno.id, curso_id=m.curso_id, liberado=1
        ).first()
        cursos_com_acesso.append({
            "curso":    m.curso,
            "liberado": bool(acesso),
        })
    return render_template("aluno/cursos.html",
                           aluno=aluno,
                           cursos_com_acesso=cursos_com_acesso)


@portal_aluno_bp.route("/cursos/<int:curso_id>")
@aluno_login_required
def aluno_curso_detalhe(curso_id):
    aluno = _get_aluno()

    matricula = next(
        (m for m in aluno.matriculas
         if m.curso_id == curso_id and m.status.upper() == "ATIVA"), None
    )
    if not matricula:
        flash("Você não está matriculado neste curso.", "erro")
        return redirect("/aluno/cursos")

    acesso = AcessoConteudoCurso.query.filter_by(
        aluno_id=aluno.id, curso_id=curso_id, liberado=1
    ).first()
    if not acesso:
        flash("Seu acesso a este curso ainda não foi liberado. Fale com a secretaria.", "erro")
        return redirect("/aluno/cursos")

    curso = db.get_or_404(Curso, curso_id)

    ids_liberados = {
        ml.materia_id for ml in MateriaLiberada.query.filter_by(
            aluno_id=aluno.id, liberado=1
        ).all()
    }
    todas_materias   = Materia.query.filter_by(curso_id=curso_id, ativa=1).all()
    materias_visiveis = [m for m in todas_materias if m.id in ids_liberados]

    conteudos_raw = []
    if materias_visiveis:
        conteudos_raw = (
            Conteudo.query
            .filter(Conteudo.materia_id.in_([m.id for m in materias_visiveis]))
            .order_by(Conteudo.materia_id, Conteudo.id)
            .all()
        )
    progressos_map = {
        p.conteudo_id: p
        for p in ProgressoAula.query.filter_by(aluno_id=aluno.id).all()
    }
    conteudos = [(c, progressos_map.get(c.id)) for c in conteudos_raw]

    from models import Prova, RespostaProva
    ids_provas_liberadas = {
        pl.prova_id for pl in ProvaLiberada.query.filter_by(
            aluno_id=aluno.id, liberado=1
        ).all()
    }
    provas_do_curso  = Prova.query.filter_by(curso_id=curso_id, ativa=1).all()
    provas_visiveis  = []
    for p in provas_do_curso:
        if p.id not in ids_provas_liberadas:
            continue
        usadas = RespostaProva.query.filter_by(
            prova_id=p.id, aluno_id=aluno.id
        ).count()
        provas_visiveis.append({
            "prova":             p,
            "tentativas_usadas": usadas,
            "pode_fazer":        usadas < p.tentativas,
        })

    atividades  = Atividade.query.filter_by(curso_id=curso_id, ativa=1).all()
    entregas_map = {
        e.atividade_id: e
        for e in EntregaAtividade.query.filter_by(aluno_id=aluno.id).all()
    }

    return render_template(
        "aluno/curso_detalhe.html",
        aluno        = aluno,
        curso        = curso,
        materias     = materias_visiveis,
        conteudos    = conteudos,
        provas       = provas_visiveis,
        atividades   = atividades,
        entregas_map = entregas_map,
    )


# ─── ROTA LEGADA /conteudo ───────────────────────────────────────────────────────────

@portal_aluno_bp.route("/conteudo")
@aluno_login_required
def aluno_conteudo():
    return redirect("/aluno/cursos")


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
    return redirect(request.referrer or "/aluno/cursos")


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
    return redirect("/aluno/cursos")


# ─── ENTREGA DE ATIVIDADE ───────────────────────────────────────────────────────────

@portal_aluno_bp.route("/atividade/<int:atividade_id>/entregar", methods=["POST"])
@aluno_login_required
def entregar_atividade(atividade_id):
    from werkzeug.utils import secure_filename
    from flask import current_app
    aluno     = _get_aluno()
    atividade = db.get_or_404(Atividade, atividade_id)

    entrega = EntregaAtividade.query.filter_by(
        aluno_id=aluno.id, atividade_id=atividade_id
    ).first()
    if not entrega:
        entrega = EntregaAtividade(
            aluno_id     = aluno.id,
            atividade_id = atividade_id,
            entregue_em  = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        db.session.add(entrega)

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    for idx, campo in enumerate(["arquivo1", "arquivo2", "arquivo3"], 1):
        f = request.files.get(campo)
        if f and f.filename:
            fname = secure_filename(f"{aluno.id}_atv{atividade_id}_{idx}_{f.filename}")
            f.save(os.path.join(upload_folder, fname))
            setattr(entrega, campo, fname)

    entrega.status = "entregue"
    db.session.commit()
    flash("Atividade entregue com sucesso!", "sucesso")
    return redirect(f"/aluno/cursos/{atividade.curso_id}")


# ─── SERVIR ARQUIVO DE CONTEÚDO ────────────────────────────────────────────────────────

@portal_aluno_bp.route("/arquivo/<int:conteudo_id>")
@aluno_login_required
def servir_arquivo(conteudo_id):
    from flask import current_app
    aluno    = _get_aluno()
    conteudo = db.get_or_404(Conteudo, conteudo_id)

    if not conteudo.arquivo:
        abort(404)

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
