from datetime import datetime
from flask import Blueprint, render_template, request, redirect, flash, session, abort
from db import db
from models import (
    Aluno, Prova, Questao, Alternativa,
    RespostaProva, RespostaQuestao, Matricula
)
from security import aluno_login_required

provas_aluno_bp = Blueprint("provas_aluno", __name__)


def _cursos_ativos(aluno_id):
    """Retorna lista (não set) de curso_id com matrícula ATIVA."""
    return [
        m.curso_id for m in
        Matricula.query.filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == "ATIVA"
        ).all()
        if m.curso_id
    ]


def _tentativas_usadas(prova_id, aluno_id):
    return RespostaProva.query.filter_by(
        prova_id=prova_id, aluno_id=aluno_id
    ).count()


def _ultima_tentativa(prova_id, aluno_id):
    return (
        RespostaProva.query
        .filter_by(prova_id=prova_id, aluno_id=aluno_id)
        .order_by(RespostaProva.id.desc())
        .first()
    )


# ── LISTAGEM DE PROVAS ───────────────────────────────────────────────────────

@provas_aluno_bp.route("/provas")
@aluno_login_required
def listar_provas_aluno():
    aluno        = db.get_or_404(Aluno, session["aluno_id"])
    cursos_aluno = _cursos_ativos(aluno.id)

    # Protege contra IN() com lista vazia (gera SQL inválido em algumas versões)
    if not cursos_aluno:
        return render_template("aluno/provas_lista.html",
                               aluno=aluno, provas=[])

    provas_raw = (
        Prova.query
        .filter(Prova.ativa == 1, Prova.curso_id.in_(cursos_aluno))
        .order_by(Prova.id.desc())
        .all()
    )

    provas = []
    for prova in provas_raw:
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
    aluno = db.get_or_404(Aluno, session["aluno_id"])
    prova = db.get_or_404(Prova, prova_id)

    cursos_aluno = _cursos_ativos(aluno.id)
    if not prova.ativa or prova.curso_id not in cursos_aluno:
        flash("Esta prova não está disponível para você.", "erro")
        return redirect("/aluno/provas")

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
            pontos_max += questao.pontos
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
                pts_obtidos = questao.pontos if acertou else 0.0
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
            nota_final             = round((nota_total / pontos_max) * 10, 2) if pontos_max else 0.0
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
    aluno      = db.get_or_404(Aluno, session["aluno_id"])
    prova      = db.get_or_404(Prova, prova_id)
    resp_prova = db.get_or_404(RespostaProva, resp_id)

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
