from datetime import datetime
from flask import Blueprint, render_template, request, redirect, flash, session, abort
from db import db
from models import (
    Aluno, Prova, Questao, Alternativa,
    RespostaProva, RespostaQuestao, Matricula
)
from security import aluno_login_required

provas_aluno_bp = Blueprint("provas_aluno", __name__)


def _matriculas_ativas(aluno_id):
    return {
        m.curso_id for m in
        Matricula.query.filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == "ATIVA"
        ).all()
    }


def _prova_disponivel(prova, aluno_id):
    """Verifica se o aluno pode acessar esta prova."""
    if not prova.ativa:
        return False
    cursos_aluno = _matriculas_ativas(aluno_id)
    return prova.curso_id in cursos_aluno


def _tentativas_usadas(prova_id, aluno_id):
    return RespostaProva.query.filter_by(
        prova_id=prova_id,
        aluno_id=aluno_id
    ).count()


def _ultima_tentativa(prova_id, aluno_id):
    return (
        RespostaProva.query
        .filter_by(prova_id=prova_id, aluno_id=aluno_id)
        .order_by(RespostaProva.finalizado_em.desc())
        .first()
    )


# ─────────────────────────────────────────────────────────────────────────────
# LISTAGEM DE PROVAS DO ALUNO
# ─────────────────────────────────────────────────────────────────────────────

@provas_aluno_bp.route("/provas")
@aluno_login_required
def listar_provas_aluno():
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    cursos_aluno = _matriculas_ativas(aluno.id)

    provas_raw = (
        Prova.query
        .filter(Prova.ativa == 1, Prova.curso_id.in_(cursos_aluno))
        .order_by(Prova.id.desc())
        .all()
    ) if cursos_aluno else []

    provas = []
    for prova in provas_raw:
        tentativas_feitas = _tentativas_usadas(prova.id, aluno.id)
        pode_fazer        = tentativas_feitas < prova.tentativas
        ultima            = _ultima_tentativa(prova.id, aluno.id)
        provas.append({
            "prova":            prova,
            "tentativas_feitas": tentativas_feitas,
            "pode_fazer":       pode_fazer,
            "ultima":           ultima,
        })

    return render_template("aluno/provas_lista.html",
                           aluno=aluno, provas=provas)


# ─────────────────────────────────────────────────────────────────────────────
# REALIZAR PROVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_aluno_bp.route("/provas/<int:prova_id>/realizar", methods=["GET", "POST"])
@aluno_login_required
def realizar_prova(prova_id):
    aluno = db.get_or_404(Aluno, session["aluno_id"])
    prova = db.get_or_404(Prova, prova_id)

    if not _prova_disponivel(prova, aluno.id):
        flash("Esta prova n\u00e3o est\u00e1 dispon\u00edvel para voc\u00ea.", "erro")
        return redirect("/aluno/provas")

    tentativas_feitas = _tentativas_usadas(prova_id, aluno.id)
    if tentativas_feitas >= prova.tentativas:
        flash("Voc\u00ea j\u00e1 utilizou todas as tentativas desta prova.", "erro")
        return redirect("/aluno/provas")

    questoes = (
        Questao.query
        .filter_by(prova_id=prova_id)
        .order_by(Questao.ordem)
        .all()
    )
    if not questoes:
        flash("Esta prova n\u00e3o possui quest\u00f5es.", "erro")
        return redirect("/aluno/provas")

    if request.method == "POST":
        iniciado_em = request.form.get("iniciado_em", "")
        agora       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Cria registro de tentativa
        resp_prova = RespostaProva(
            prova_id      = prova_id,
            aluno_id      = aluno.id,
            iniciado_em   = iniciado_em or agora,
            finalizado_em = agora,
        )
        db.session.add(resp_prova)
        db.session.flush()  # gera resp_prova.id

        nota_total  = 0.0
        pontos_max  = 0.0

        for questao in questoes:
            pontos_max += questao.pontos
            campo = f"questao_{questao.id}"

            if questao.tipo == "dissertativa":
                texto_resp = (request.form.get(campo) or "").strip()
                rq = RespostaQuestao(
                    resposta_prova_id  = resp_prova.id,
                    questao_id         = questao.id,
                    resposta_texto     = texto_resp,
                    pontos_obtidos     = 0.0,  # correcão manual
                )
                db.session.add(rq)

            else:  # múltipla escolha ou verdadeiro/falso
                alt_id_str = request.form.get(campo)
                alt_id     = int(alt_id_str) if alt_id_str and alt_id_str.isdigit() else None
                alternativa_correta = Alternativa.query.filter_by(
                    questao_id=questao.id, correta=1
                ).first()
                correta_id  = alternativa_correta.id if alternativa_correta else None
                acertou     = (alt_id == correta_id) if alt_id else False
                pts_obtidos = questao.pontos if acertou else 0.0
                nota_total += pts_obtidos

                rq = RespostaQuestao(
                    resposta_prova_id  = resp_prova.id,
                    questao_id         = questao.id,
                    alternativa_id     = alt_id,
                    pontos_obtidos     = pts_obtidos,
                )
                db.session.add(rq)

        # Calcula nota final sobre 10
        if pontos_max > 0:
            nota_final = round((nota_total / pontos_max) * 10, 2)
        else:
            nota_final = 0.0

        tem_dissertativa = any(q.tipo == "dissertativa" for q in questoes)
        resp_prova.nota_obtida = nota_final
        resp_prova.aprovado    = 0 if tem_dissertativa else (
            1 if nota_final >= prova.nota_minima else 0
        )
        db.session.commit()

        if tem_dissertativa:
            flash("Prova enviada! Quest\u00f5es dissertativas ser\u00e3o corrigidas pelo instrutor.", "sucesso")
        elif resp_prova.aprovado:
            flash(f"Parab\u00e9ns! Voc\u00ea foi aprovado com nota {nota_final}.", "sucesso")
        else:
            flash(f"Voc\u00ea foi reprovado. Nota: {nota_final} (m\u00ednimo: {prova.nota_minima}).", "erro")

        return redirect(f"/aluno/provas/{prova_id}/resultado/{resp_prova.id}")

    # GET — exibe formulário da prova
    return render_template("aluno/provas_realizar.html",
                           aluno=aluno, prova=prova, questoes=questoes)


# ─────────────────────────────────────────────────────────────────────────────
# RESULTADO DE UMA TENTATIVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_aluno_bp.route("/provas/<int:prova_id>/resultado/<int:resp_id>")
@aluno_login_required
def resultado_prova_aluno(prova_id, resp_id):
    aluno      = db.get_or_404(Aluno, session["aluno_id"])
    prova      = db.get_or_404(Prova, prova_id)
    resp_prova = db.get_or_404(RespostaProva, resp_id)

    # garante que o resultado é do aluno logado
    if resp_prova.aluno_id != aluno.id:
        abort(403)

    respostas = (
        db.session.query(RespostaQuestao, Questao)
        .join(Questao, Questao.id == RespostaQuestao.questao_id)
        .filter(RespostaQuestao.resposta_prova_id == resp_id)
        .order_by(Questao.ordem)
        .all()
    )

    # anexa alternativas corretas e a escolhida para exibir gabarito
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
