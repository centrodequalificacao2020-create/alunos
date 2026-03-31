from datetime import datetime
from flask import Blueprint, render_template, request, redirect, flash, session, abort
from db import db
from security import aluno_login_required

provas_aluno_bp = Blueprint("provas_aluno", __name__)


def _cursos_ativos(aluno_id):
    """Retorna lista de curso_id com matrícula ATIVA (comparação em Python — portável)."""
    from models import Matricula
    try:
        matriculas = Matricula.query.filter_by(aluno_id=aluno_id).all()
        return [
            m.curso_id for m in matriculas
            if (m.status or "").strip().upper() == "ATIVA" and m.curso_id
        ]
    except Exception:
        return []


def _tentativas_usadas(prova_id, aluno_id):
    from models import RespostaProva
    try:
        return RespostaProva.query.filter_by(
            prova_id=prova_id, aluno_id=aluno_id
        ).count()
    except Exception:
        return 0


def _ultima_tentativa(prova_id, aluno_id):
    from models import RespostaProva
    try:
        return (
            RespostaProva.query
            .filter_by(prova_id=prova_id, aluno_id=aluno_id)
            .order_by(RespostaProva.id.desc())
            .first()
        )
    except Exception:
        return None


def _prova_liberada_para(prova_id, aluno_id):
    """Verifica se a prova foi explicitamente liberada para o aluno."""
    from models import ProvaLiberada
    try:
        pl = ProvaLiberada.query.filter_by(
            prova_id=prova_id, aluno_id=aluno_id, liberado=1
        ).first()
        return pl is not None
    except Exception:
        # Se a tabela ainda não existir, permite acesso (modo degradado)
        return True


def _calcular_nota(nota_total, pontos_max):
    """Calcula nota na escala 0-10. Retorna 0.0 se pontos_max <= 0."""
    if not pontos_max or pontos_max <= 0.0:
        return 0.0
    return round((nota_total / pontos_max) * 10, 2)


# ── LISTAGEM DE PROVAS ───────────────────────────────────────────────────────

@provas_aluno_bp.route("/provas")
@aluno_login_required
def listar_provas_aluno():
    from models import Aluno, Prova
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    cursos_aluno = _cursos_ativos(aluno.id)

    if not cursos_aluno:
        return render_template("aluno/provas_lista.html",
                               aluno=aluno, provas=[])

    try:
        provas_raw = (
            Prova.query
            .filter(Prova.ativa == 1, Prova.curso_id.in_(cursos_aluno))
            .order_by(Prova.id.desc())
            .all()
        )
    except Exception:
        return render_template("aluno/provas_lista.html",
                               aluno=aluno, provas=[])

    provas = []
    for prova in provas_raw:
        # Só exibe provas liberadas para este aluno
        if not _prova_liberada_para(prova.id, aluno.id):
            continue
        tentativas_feitas = _tentativas_usadas(prova.id, aluno.id)
        pode_fazer        = tentativas_feitas < prova.tentativas
        ultima            = _ultima_tentativa(prova.id, aluno.id)
        provas.append({
            "prova":             prova,
            "tentativas_feitas": tentativas_feitas,
            "pode_fazer":        pode_fazer,
            "ultima":            ultima,
        })

    return render_template("aluno/provas_lista.html",
                           aluno=aluno, provas=provas)


# ── REALIZAR PROVA ───────────────────────────────────────────────────────────

@provas_aluno_bp.route("/provas/<int:prova_id>/realizar", methods=["GET", "POST"])
@aluno_login_required
def realizar_prova(prova_id):
    from models import Aluno, Prova, Questao, Alternativa, RespostaProva, RespostaQuestao
    aluno = db.get_or_404(Aluno, session["aluno_id"])
    prova = db.get_or_404(Prova, prova_id)

    # ── Verificação 1: prova ativa e aluno matriculado no curso ──────────────
    cursos_aluno = _cursos_ativos(aluno.id)
    if not prova.ativa or prova.curso_id not in cursos_aluno:
        flash("Esta prova não está disponível para você.", "erro")
        return redirect("/aluno/provas")

    # ── Verificação 2: prova liberada individualmente para este aluno ─────────
    if not _prova_liberada_para(prova_id, aluno.id):
        flash("Esta prova ainda não foi liberada para você. Aguarde a secretaria.", "erro")
        return redirect("/aluno/provas")

    # ── Verificação 3: tentativas disponíveis ────────────────────────────────
    tentativas_feitas = _tentativas_usadas(prova_id, aluno.id)
    if tentativas_feitas >= prova.tentativas:
        flash("Você já utilizou todas as tentativas desta prova.", "erro")
        return redirect("/aluno/provas")

    questoes = (
        Questao.query
        .filter_by(prova_id=prova_id)
        .order_by(Questao.ordem)
        .all()
    )
    if not questoes:
        flash("Esta prova não possui questões cadastradas.", "erro")
        return redirect("/aluno/provas")

    if request.method == "POST":
        iniciado_em = request.form.get("iniciado_em", "")
        agora       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        resp_prova = RespostaProva(
            prova_id      = prova_id,
            aluno_id      = aluno.id,
            tentativa_num = tentativas_feitas + 1,
            iniciado_em   = iniciado_em or agora,
            finalizado_em = agora,
        )
        db.session.add(resp_prova)
        db.session.flush()

        nota_total       = 0.0
        pontos_max       = 0.0
        tem_dissertativa = False

        for questao in questoes:
            # Bug 1 fix: garante que pontos seja float positivo (mínimo 0)
            pts_questao = max(0.0, float(questao.pontos or 0.0))
            pontos_max += pts_questao
            campo       = f"questao_{questao.id}"

            if questao.tipo == "dissertativa":
                tem_dissertativa = True
                texto_resp = (request.form.get(campo) or "").strip()
                db.session.add(RespostaQuestao(
                    resposta_prova_id = resp_prova.id,
                    questao_id        = questao.id,
                    texto_resposta    = texto_resp,
                    pontos_obtidos    = None,
                    corrigida         = 0,
                ))
            else:
                alt_id_str = request.form.get(campo)
                alt_id     = int(alt_id_str) if alt_id_str and alt_id_str.isdigit() else None
                correta    = Alternativa.query.filter_by(
                    questao_id=questao.id, correta=1
                ).first()
                acertou     = alt_id is not None and correta is not None and alt_id == correta.id
                pts_obtidos = pts_questao if acertou else 0.0
                nota_total += pts_obtidos

                db.session.add(RespostaQuestao(
                    resposta_prova_id = resp_prova.id,
                    questao_id        = questao.id,
                    alternativa_id    = alt_id,
                    pontos_obtidos    = pts_obtidos,
                    corrigida         = 1,
                ))

        if tem_dissertativa:
            resp_prova.nota_obtida = None
            resp_prova.aprovado    = None
        else:
            # Bug 1 fix: usa _calcular_nota que trata pontos_max <= 0
            nota_final             = _calcular_nota(nota_total, pontos_max)
            resp_prova.nota_obtida = nota_final
            resp_prova.aprovado    = 1 if nota_final >= prova.nota_minima else 0

        db.session.commit()

        if tem_dissertativa:
            flash("Prova enviada! Questões dissertativas aguardam correção do instrutor.", "sucesso")
        elif resp_prova.aprovado:
            flash(f"Parabéns! Aprovado com nota {resp_prova.nota_obtida}.", "sucesso")
        else:
            flash(f"Reprovado. Sua nota: {resp_prova.nota_obtida} (mínimo: {prova.nota_minima}).", "erro")

        return redirect(f"/aluno/provas/{prova_id}/resultado/{resp_prova.id}")

    return render_template("aluno/provas_realizar.html",
                           aluno=aluno, prova=prova, questoes=questoes)


# ── RESULTADO DA TENTATIVA ───────────────────────────────────────────────────

@provas_aluno_bp.route("/provas/<int:prova_id>/resultado/<int:resp_id>")
@aluno_login_required
def resultado_prova_aluno(prova_id, resp_id):
    from models import Aluno, Prova, RespostaProva, RespostaQuestao, Questao, Alternativa
    aluno      = db.get_or_404(Aluno, session["aluno_id"])
    prova      = db.get_or_404(Prova, prova_id)
    resp_prova = db.get_or_404(RespostaProva, resp_id)

    # Garante que o aluno só veja seu próprio resultado
    if resp_prova.aluno_id != aluno.id:
        abort(403)

    respostas = (
        db.session.query(RespostaQuestao, Questao)
        .join(Questao, Questao.id == RespostaQuestao.questao_id)
        .filter(RespostaQuestao.resposta_prova_id == resp_id)
        .order_by(Questao.ordem)
        .all()
    )

    gabarito = []
    for rq, q in respostas:
        correta   = Alternativa.query.filter_by(questao_id=q.id, correta=1).first()
        escolhida = db.session.get(Alternativa, rq.alternativa_id) if rq.alternativa_id else None
        gabarito.append({
            "questao":   q,
            "rq":        rq,
            "correta":   correta,
            "escolhida": escolhida,
        })

    return render_template("aluno/provas_resultado.html",
                           aluno=aluno, prova=prova,
                           resp_prova=resp_prova, gabarito=gabarito)
