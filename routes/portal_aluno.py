import os
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, session, flash, abort, Response
from models import (
    Aluno, Mensalidade, Frequencia, Conteudo, Materia, Matricula,
    ProgressoAula, CursoMateria, Nota, Curso, LoginHistoricoAluno
)
from security import verificar_senha, aluno_login_required, hash_senha
from db import db
from app import limiter
from sqlalchemy.exc import OperationalError

portal_aluno_bp = Blueprint("portal_aluno", __name__)


def _matriculas_ativas(aluno_id):
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
    return (
        Matricula.query
        .filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == "ATIVA"
        )
        .order_by(Matricula.id.desc())
        .first()
    )


def _curso_liberado(aluno_id, curso_id):
    try:
        from models import AcessoConteudoCurso
        acesso = AcessoConteudoCurso.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id
        ).first()
        return acesso is not None and acesso.liberado == 1
    except OperationalError:
        return True


def _aluno_pode_acessar_conteudo(aluno_id, conteudo):
    matriculas = _matriculas_ativas(aluno_id)
    for mat in matriculas:
        if not _curso_liberado(aluno_id, mat.curso_id):
            continue
        vinculo = (
            db.session.query(CursoMateria)
            .filter(
                CursoMateria.materia_id == conteudo.materia_id,
                CursoMateria.curso_id   == mat.curso_id,
            ).first()
        )
        if vinculo:
            return True
    return False


def _contar_atrasadas(mensalidades):
    hoje = date.today().strftime("%Y-%m-%d")
    return sum(
        1 for m in mensalidades
        if m.status != "Pago" and m.vencimento and str(m.vencimento) < hoje
    )


def _registrar_login(aluno_id):
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()
        ua = (request.headers.get("User-Agent") or "")[:300]
        db.session.add(LoginHistoricoAluno(
            aluno_id=aluno_id,
            login_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ip=ip, user_agent=ua
        ))
        db.session.commit()
    except OperationalError:
        db.session.rollback()
    except Exception:
        db.session.rollback()


def _buscar_aluno_por_login(identificador: str):
    """Aceita CPF (com ou sem mascara) ou e-mail."""
    import re
    ident = identificador.strip()
    if not ident:
        return None
    # e-mail
    if "@" in ident:
        return Aluno.query.filter(
            db.func.lower(Aluno.email) == ident.lower()
        ).first()
    # CPF exato
    aluno = Aluno.query.filter_by(cpf=ident).first()
    if aluno:
        return aluno
    # CPF sem mascara
    cpf_limpo = re.sub(r"\D", "", ident)
    if cpf_limpo:
        for a in Aluno.query.all():
            if re.sub(r"\D", "", a.cpf or "") == cpf_limpo:
                return a
    return None


# ─── LOGIN / LOGOUT ───────────────────────────────────────────────────────────

@portal_aluno_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login_aluno():
    if request.method == "POST":
        # campo "cpf" no template aceita CPF ou e-mail
        identificador = request.form.get("cpf", "").strip()
        senha         = request.form.get("senha", "")

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

        session.clear()
        session.permanent = True
        session["aluno_id"] = aluno.id
        session["perfil"]   = "aluno"
        _registrar_login(aluno.id)
        return redirect("/aluno/dashboard")

    return render_template("aluno/login.html")


@portal_aluno_bp.route("/logout")
def logout_aluno():
    session.clear()
    return redirect("/aluno/login")


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/dashboard")
@aluno_login_required
def dashboard_aluno():
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    matricula    = _matricula_ativa(aluno.id)
    mensalidades = Mensalidade.query.filter_by(aluno_id=aluno.id).order_by(Mensalidade.vencimento).all()
    atrasadas    = _contar_atrasadas(mensalidades)
    val_pend     = sum(m.valor for m in mensalidades if m.status != "Pago")

    ultimo_login = None
    try:
        logins = (
            LoginHistoricoAluno.query
            .filter_by(aluno_id=aluno.id)
            .order_by(LoginHistoricoAluno.login_em.desc())
            .limit(2).all()
        )
        ultimo_login = logins[1] if len(logins) >= 2 else (logins[0] if logins else None)
    except OperationalError:
        pass
    except Exception:
        pass

    return render_template("aluno/dashboard.html", aluno=aluno,
        matricula=matricula, atrasadas=atrasadas, valor_pendente=val_pend,
        ultimo_login=ultimo_login)


# ─── FINANCEIRO ───────────────────────────────────────────────────────────────

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


# ─── FREQUÊNCIA ───────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/frequencia")
@aluno_login_required
def frequencia_aluno():
    aluno       = db.get_or_404(Aluno, session["aluno_id"])
    frequencias = Frequencia.query.filter_by(aluno_id=aluno.id).order_by(Frequencia.data.desc()).all()
    return render_template("aluno/frequencia.html", aluno=aluno, frequencias=frequencias)


# ─── NOTAS ────────────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/notas")
@aluno_login_required
def notas_aluno():
    aluno     = db.get_or_404(Aluno, session["aluno_id"])
    matricula = _matricula_ativa(aluno.id)
    notas = []
    media = None
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
            .filter(CursoMateria.curso_id == matricula.curso_id, Materia.ativa == 1)
            .order_by(Materia.nome).all()
        )
        notas = [(nota, materia) for materia, nota in rows]
        valores = [n.nota for n, m in notas if n is not None and n.nota is not None]
        if valores:
            media = round(sum(valores) / len(valores), 1)
    return render_template("aluno/notas.html", aluno=aluno,
                           matricula=matricula, notas=notas, media=media)


# ─── CURSOS (lista) ───────────────────────────────────────────────────────────

@portal_aluno_bp.route("/cursos")
@aluno_login_required
def cursos_aluno():
    aluno      = db.get_or_404(Aluno, session["aluno_id"])
    matriculas = _matriculas_ativas(aluno.id)

    cursos_com_acesso = []
    for mat in matriculas:
        curso = db.session.get(Curso, mat.curso_id)
        if not curso:
            continue
        liberado = _curso_liberado(aluno.id, curso.id)
        cursos_com_acesso.append({
            "curso":     curso,
            "matricula": mat,
            "liberado":  liberado,
        })

    return render_template("aluno/cursos.html", aluno=aluno,
                           cursos_com_acesso=cursos_com_acesso)


# ─── CURSO DETALHE ────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/cursos/<int:curso_id>")
@aluno_login_required
def curso_detalhe(curso_id):
    aluno = db.get_or_404(Aluno, session["aluno_id"])
    matricula = Matricula.query.filter(
        Matricula.aluno_id == aluno.id,
        Matricula.curso_id == curso_id,
        db.func.upper(Matricula.status) == "ATIVA"
    ).first()
    if not matricula:
        abort(403)
    if not _curso_liberado(aluno.id, curso_id):
        flash("O acesso ao conteúdo deste curso ainda não foi liberado. "
              "Entre em contato com a secretaria.", "aviso")
        return redirect("/aluno/cursos")

    curso = db.get_or_404(Curso, curso_id)
    conteudos = (
        db.session.query(Conteudo, ProgressoAula)
        .outerjoin(
            ProgressoAula,
            (ProgressoAula.conteudo_id == Conteudo.id) &
            (ProgressoAula.aluno_id    == aluno.id)
        )
        .join(Materia,      Materia.id == Conteudo.materia_id)
        .join(CursoMateria, CursoMateria.materia_id == Materia.id)
        .filter(CursoMateria.curso_id == curso_id)
        .order_by(Materia.nome, Conteudo.data)
        .all()
    )

    # Provas liberadas para este aluno neste curso
    provas = []
    try:
        from models import Prova, ProvaLiberada, RespostaProva
        ids_liberadas = {
            pl.prova_id
            for pl in ProvaLiberada.query.filter_by(aluno_id=aluno.id, liberado=1).all()
        }
        for p in Prova.query.filter_by(curso_id=curso_id, ativa=1).all():
            if p.id not in ids_liberadas:
                continue
            usadas = RespostaProva.query.filter_by(prova_id=p.id, aluno_id=aluno.id).count()
            provas.append({
                "prova":             p,
                "tentativas_usadas": usadas,
                "pode_fazer":        usadas < (p.tentativas or 1),
            })
    except OperationalError:
        pass
    except Exception:
        pass

    # Atividades deste curso
    atividades   = []
    entregas_map = {}
    try:
        from models import Atividade, EntregaAtividade
        atividades = Atividade.query.filter_by(curso_id=curso_id, ativa=1).all()
        entregas_map = {
            e.atividade_id: e
            for e in EntregaAtividade.query.filter_by(aluno_id=aluno.id).all()
        }
    except OperationalError:
        pass
    except Exception:
        pass

    return render_template("aluno/curso_detalhe.html",
                           aluno=aluno, curso=curso, conteudos=conteudos,
                           provas=provas,
                           atividades=atividades, entregas_map=entregas_map)


# ─── CONTEÚDO (rotas antigas mantidas por compatibilidade) ────────────────────

@portal_aluno_bp.route("/conteudo")
@aluno_login_required
def conteudo_cursos():
    return redirect("/aluno/cursos")


@portal_aluno_bp.route("/conteudo/<int:curso_id>")
@aluno_login_required
def conteudo_aluno(curso_id):
    return redirect(f"/aluno/cursos/{curso_id}")


# ─── ARQUIVO ──────────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/arquivo/<int:conteudo_id>")
@aluno_login_required
def abrir_arquivo_conteudo(conteudo_id):
    import mimetypes
    conteudo = db.get_or_404(Conteudo, conteudo_id)
    if not _aluno_pode_acessar_conteudo(session["aluno_id"], conteudo):
        abort(403)
    if not conteudo.arquivo:
        abort(404)
    arquivo = conteudo.arquivo.strip()
    if arquivo.startswith("http://") or arquivo.startswith("https://"):
        return redirect(arquivo)
    base_dir   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    caminho    = arquivo.lstrip("/")
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
            resp = Response(dados, mimetype=mime)
            resp.headers["Content-Disposition"]   = "inline"
            resp.headers["X-Frame-Options"]        = "SAMEORIGIN"
            resp.headers["X-Content-Type-Options"] = "nosniff"
            resp.headers["Cache-Control"]          = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"]                 = "no-cache"
            return resp
    abort(404)


# ─── CONCLUIR AULA ────────────────────────────────────────────────────────────

@portal_aluno_bp.route("/conteudo/concluir/<int:conteudo_id>")
@aluno_login_required
def concluir_aula(conteudo_id):
    conteudo = db.get_or_404(Conteudo, conteudo_id)
    materia  = db.session.get(Materia, conteudo.materia_id)
    curso_id = None
    if materia:
        cm = CursoMateria.query.filter_by(materia_id=materia.id).first()
        if cm:
            curso_id = cm.curso_id
    p = ProgressoAula.query.filter_by(
        aluno_id=session["aluno_id"], conteudo_id=conteudo_id).first()
    if not p:
        db.session.add(ProgressoAula(
            aluno_id=session["aluno_id"], conteudo_id=conteudo_id, concluido=1
        ))
    else:
        p.concluido = 1
    db.session.commit()
    return redirect(f"/aluno/cursos/{curso_id}" if curso_id else "/aluno/cursos")


# ─── ENTREGAR ATIVIDADE ───────────────────────────────────────────────────────

@portal_aluno_bp.route("/atividade/<int:atividade_id>/entregar", methods=["POST"])
@aluno_login_required
def entregar_atividade(atividade_id):
    from werkzeug.utils import secure_filename
    from flask import current_app
    aluno = db.get_or_404(Aluno, session["aluno_id"])
    try:
        from models import Atividade, EntregaAtividade
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
                fname = secure_filename(
                    f"{aluno.id}_atv{atividade_id}_{idx}_{f.filename}"
                )
                f.save(os.path.join(upload_folder, fname))
                setattr(entrega, campo, fname)
        entrega.status = "entregue"
        db.session.commit()
        flash("Atividade entregue com sucesso!", "sucesso")
        return redirect(f"/aluno/cursos/{atividade.curso_id}")
    except OperationalError:
        db.session.rollback()
        flash("Erro ao entregar atividade. Tente novamente.", "erro")
        return redirect("/aluno/cursos")


# ─── TROCAR SENHA ─────────────────────────────────────────────────────────────

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
