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


def _ids_materias_liberadas(aluno_id, curso_id):
    """Retorna set de materia_id liberados para o aluno neste curso."""
    from models import MateriaLiberada
    return {
        ml.materia_id
        for ml in MateriaLiberada.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id, liberado=1
        ).all()
    }


def _curso_tem_acesso(aluno_id, curso_id):
    return len(_ids_materias_liberadas(aluno_id, curso_id)) > 0


def _aluno_pode_acessar_conteudo(aluno_id, conteudo):
    matriculas = _matriculas_ativas(aluno_id)
    for mat in matriculas:
        ids_lib = _ids_materias_liberadas(aluno_id, mat.curso_id)
        if not ids_lib:
            continue
        vinculo = (
            db.session.query(CursoMateria)
            .filter(
                CursoMateria.materia_id == conteudo.materia_id,
                CursoMateria.curso_id   == mat.curso_id,
            ).first()
        )
        if vinculo and conteudo.materia_id in ids_lib:
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
    import re
    ident = identificador.strip()
    if not ident:
        return None
    if "@" in ident:
        return Aluno.query.filter(db.func.lower(Aluno.email) == ident.lower()).first()
    aluno = Aluno.query.filter_by(cpf=ident).first()
    if aluno:
        return aluno
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
        identificador = request.form.get("cpf", "").strip()
        senha         = request.form.get("senha", "")
        aluno = _buscar_aluno_por_login(identificador)
        if not aluno:
            flash("Usuário não encontrado. Verifique o CPF ou e-mail digitado.", "erro")
            return redirect("/aluno/login")
        if not aluno.senha:
            flash("Sua senha ainda não foi definida. Entre em contato com a secretaria.", "erro")
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
        liberado = _curso_tem_acesso(aluno.id, curso.id)
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

    if not _curso_tem_acesso(aluno.id, curso_id):
        flash("O acesso ao conteúdo deste curso ainda não foi liberado. "
              "Entre em contato com a secretaria.", "aviso")
        return redirect("/aluno/cursos")

    curso = db.get_or_404(Curso, curso_id)

    ids_mat_lib = _ids_materias_liberadas(aluno.id, curso_id)
    materias_do_curso = (
        db.session.query(Materia)
        .join(CursoMateria, CursoMateria.materia_id == Materia.id)
        .filter(CursoMateria.curso_id == curso_id, Materia.ativa == 1)
        .order_by(Materia.nome).all()
    )
    materias_liberadas = [m for m in materias_do_curso if m.id in ids_mat_lib]

    ids_materias_visiveis = {m.id for m in materias_liberadas}
    conteudos_raw = (
        db.session.query(Conteudo, ProgressoAula)
        .outerjoin(
            ProgressoAula,
            (ProgressoAula.conteudo_id == Conteudo.id) &
            (ProgressoAula.aluno_id    == aluno.id)
        )
        .filter(Conteudo.materia_id.in_(ids_materias_visiveis))
        .order_by(Conteudo.data)
        .all()
    ) if ids_materias_visiveis else []

    conteudos_por_mat = {}
    for c, prog in conteudos_raw:
        conteudos_por_mat.setdefault(c.materia_id, []).append((c, prog))

    conteudos = []
    for mat in materias_liberadas:
        for item in conteudos_por_mat.get(mat.id, []):
            conteudos.append(item)

    # BUG5-FIX: nao silencia OperationalError (tabela ausente deve aparecer como erro
    # explicito, nao como lista vazia)
    exercicios_por_mat = {}
    try:
        from models import Exercicio, ExercicioLiberado, RespostaExercicio
        ids_ex_lib = {
            el.exercicio_id: el
            for el in ExercicioLiberado.query.filter_by(aluno_id=aluno.id, liberado=1).all()
        }
        for mat in materias_liberadas:
            exs_mat = []
            for ex in Exercicio.query.filter_by(materia_id=mat.id, ativo=1).order_by(Exercicio.ordem).all():
                lib = ids_ex_lib.get(ex.id)
                if not lib:
                    continue
                usadas = RespostaExercicio.query.filter_by(
                    exercicio_id=ex.id, aluno_id=aluno.id
                ).count()
                max_tent = (ex.tentativas or 1) + (lib.extra_tentativas or 0)
                exs_mat.append({
                    "exercicio":         ex,
                    "tentativas_usadas": usadas,
                    "max_tentativas":    max_tent,
                    "pode_fazer":        usadas < max_tent,
                })
            if exs_mat:
                exercicios_por_mat[mat.id] = exs_mat
    except OperationalError as e:
        flash(f"Erro ao carregar exercícios: {e}. Execute a migração pendente.", "erro")

    provas = []
    try:
        from models import Prova, ProvaLiberada, RespostaProva
        ids_provas_lib = {
            pl.prova_id
            for pl in ProvaLiberada.query.filter_by(aluno_id=aluno.id, liberado=1).all()
        }
        for p in Prova.query.filter_by(curso_id=curso_id, ativa=1).all():
            if p.id not in ids_provas_lib:
                continue
            usadas = RespostaProva.query.filter_by(prova_id=p.id, aluno_id=aluno.id).count()
            provas.append({
                "prova":             p,
                "tentativas_usadas": usadas,
                "pode_fazer":        usadas < (p.tentativas or 1),
            })
    except Exception:
        pass

    atividades   = []
    entregas_map = {}
    try:
        from models import Atividade, EntregaAtividade, AtividadeLiberada
        ids_atv_lib = {
            al.atividade_id
            for al in AtividadeLiberada.query.filter_by(aluno_id=aluno.id, liberado=1).all()
        }
        atividades = [
            a for a in Atividade.query.filter_by(curso_id=curso_id, ativa=1).all()
            if a.id in ids_atv_lib
        ]
        entregas_map = {
            e.atividade_id: e
            for e in EntregaAtividade.query.filter_by(aluno_id=aluno.id).all()
        }
    except Exception:
        try:
            from models import Atividade, EntregaAtividade
            atividades = Atividade.query.filter_by(curso_id=curso_id, ativa=1).all()
            entregas_map = {
                e.atividade_id: e
                for e in EntregaAtividade.query.filter_by(aluno_id=aluno.id).all()
            }
        except Exception:
            pass

    return render_template(
        "aluno/curso_detalhe.html",
        aluno                = aluno,
        curso                = curso,
        materias_liberadas   = materias_liberadas,
        conteudos            = conteudos,
        conteudos_por_mat    = conteudos_por_mat,
        exercicios_por_mat   = exercicios_por_mat,
        provas               = provas,
        atividades           = atividades,
        entregas_map         = entregas_map,
    )


# ─── REALIZAR EXERCÍCIO ──────────────────────────────────────────────────────

@portal_aluno_bp.route("/exercicio/<int:ex_id>")
@aluno_login_required
def realizar_exercicio(ex_id):
    from models import Exercicio, ExercicioLiberado, RespostaExercicio
    aluno_id = session["aluno_id"]
    aluno    = db.get_or_404(Aluno, aluno_id)

    ex = db.get_or_404(Exercicio, ex_id)
    lib = ExercicioLiberado.query.filter_by(
        aluno_id=aluno_id, exercicio_id=ex_id, liberado=1
    ).first()
    if not lib:
        flash("Este exercício não está liberado para você.", "erro")
        return redirect("/aluno/cursos")

    usadas   = RespostaExercicio.query.filter_by(exercicio_id=ex_id, aluno_id=aluno_id).count()
    max_tent = (ex.tentativas or 1) + (lib.extra_tentativas or 0)
    if usadas >= max_tent:
        flash("Você já esgotou todas as tentativas neste exercício.", "erro")
        return redirect("/aluno/cursos")

    if not ex.questoes:
        flash("Este exercício ainda não possui questões. Aguarde.", "aviso")
        return redirect("/aluno/cursos")

    return render_template(
        "aluno/realizar_exercicio.html",
        aluno          = aluno,
        exercicio      = ex,
        usadas         = usadas,
        max_tentativas = max_tent,
    )


# ─── RESPONDER EXERCÍCIO ────────────────────────────────────────────────────

@portal_aluno_bp.route("/exercicio/<int:ex_id>/responder", methods=["POST"])
@aluno_login_required
def responder_exercicio(ex_id):
    from models import (
        Exercicio, ExercicioLiberado, RespostaExercicio,
        ExercicioAlternativa, RespostaExercicioQuestao,
    )
    aluno_id = session["aluno_id"]

    ex = db.get_or_404(Exercicio, ex_id)
    lib = ExercicioLiberado.query.filter_by(
        aluno_id=aluno_id, exercicio_id=ex_id, liberado=1
    ).first()
    if not lib:
        abort(403)

    usadas   = RespostaExercicio.query.filter_by(exercicio_id=ex_id, aluno_id=aluno_id).count()
    max_tent = (ex.tentativas or 1) + (lib.extra_tentativas or 0)
    if usadas >= max_tent:
        flash("Tentativas esgotadas.", "erro")
        return redirect("/aluno/cursos")

    tentativa_num  = usadas + 1
    agora          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_questoes = len(ex.questoes)

    # BUG4-FIX: flush/commit dentro de try-except com rollback explicito
    try:
        resp = RespostaExercicio(
            aluno_id       = aluno_id,
            exercicio_id   = ex_id,
            tentativa_num  = tentativa_num,
            iniciado_em    = agora,
            finalizado_em  = agora,
            total_questoes = total_questoes,
            acertos        = 0,
            percentual     = 0.0,
        )
        db.session.add(resp)
        db.session.flush()  # gera resp.id sem commitar

        acertos = 0
        for q in ex.questoes:
            alt_id_str    = request.form.get(f"questao_{q.id}")
            alt_escolhida = None
            acertou       = False

            if q.tipo in ("multipla_escolha", "verdadeiro_falso"):
                correta_alt = next((a for a in q.alternativas if a.correta), None)
                if alt_id_str:
                    try:
                        alt_escolhida = db.session.get(ExercicioAlternativa, int(alt_id_str))
                    except (ValueError, TypeError):
                        alt_escolhida = None
                if alt_escolhida and correta_alt and alt_escolhida.id == correta_alt.id:
                    acertou  = True
                    acertos += 1

            db.session.add(RespostaExercicioQuestao(
                resposta_exercicio_id = resp.id,
                questao_id            = q.id,
                alternativa_id        = alt_escolhida.id if alt_escolhida else None,
                acertou               = 1 if acertou else 0,
            ))

        percentual      = round((acertos / total_questoes * 100), 1) if total_questoes else 0.0
        resp.acertos    = acertos
        resp.percentual = percentual
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash("Erro ao processar suas respostas. Tente novamente.", "erro")
        return redirect(f"/aluno/exercicio/{ex_id}")

    return redirect(f"/aluno/exercicio/{ex_id}/resultado/{resp.id}")


# ─── RESULTADO DO EXERCÍCIO ───────────────────────────────────────────────────

@portal_aluno_bp.route("/exercicio/<int:ex_id>/resultado/<int:resp_id>")
@aluno_login_required
def resultado_exercicio(ex_id, resp_id):
    from models import Exercicio, RespostaExercicio
    aluno_id = session["aluno_id"]
    aluno    = db.get_or_404(Aluno, aluno_id)
    ex       = db.get_or_404(Exercicio, ex_id)
    resp     = db.get_or_404(RespostaExercicio, resp_id)

    # Garante que o resultado pertence ao aluno e esta finalizado (BUG6-FIX)
    if resp.aluno_id != aluno_id or resp.exercicio_id != ex_id:
        abort(403)
    if not resp.finalizado_em:
        abort(404)

    gabarito = []
    for rq in sorted(resp.respostas_questao, key=lambda r: r.questao.ordem):
        q           = rq.questao
        correta_alt = next((a for a in q.alternativas if a.correta), None)
        gabarito.append({
            "questao":   q,
            "escolhida": rq.alternativa,
            "correta":   correta_alt,
            "acertou":   bool(rq.acertou),
        })

    return render_template(
        "aluno/resultado_exercicio.html",
        aluno     = aluno,
        exercicio = ex,
        resp      = resp,
        gabarito  = gabarito,
    )


# ─── ARQUIVO DE EXERCÍCIO ─────────────────────────────────────────────────────

@portal_aluno_bp.route("/exercicio/<int:ex_id>/arquivo")
@aluno_login_required
def arquivo_exercicio_aluno(ex_id):
    import mimetypes
    aluno_id = session["aluno_id"]
    try:
        from models import Exercicio, ExercicioLiberado
        ex = db.get_or_404(Exercicio, ex_id)
        lib = ExercicioLiberado.query.filter_by(aluno_id=aluno_id, exercicio_id=ex_id, liberado=1).first()
        if not lib:
            abort(403)
        if not ex.arquivo:
            abort(404)
        caminho = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
            "static", "uploads", ex.arquivo
        )
        if not os.path.isfile(caminho):
            abort(404)
        mime, _ = mimetypes.guess_type(caminho)
        with open(caminho, "rb") as f:
            dados = f.read()
        resp = Response(dados, mimetype=mime or "application/octet-stream")
        resp.headers["Content-Disposition"] = "inline"
        return resp
    except OperationalError:
        abort(404)


# ─── CONTEÚDO (retrocompat) ───────────────────────────────────────────────────

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
    p = ProgressoAula.query.filter_by(aluno_id=session["aluno_id"], conteudo_id=conteudo_id).first()
    if not p:
        db.session.add(ProgressoAula(aluno_id=session["aluno_id"], conteudo_id=conteudo_id, concluido=1))
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
        entrega = EntregaAtividade.query.filter_by(aluno_id=aluno.id, atividade_id=atividade_id).first()
        if not entrega:
            entrega = EntregaAtividade(
                aluno_id=aluno.id, atividade_id=atividade_id,
                entregue_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
