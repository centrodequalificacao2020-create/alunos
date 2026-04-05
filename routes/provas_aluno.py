import hmac
import hashlib
import json
import random
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, flash, session, abort, current_app
from db import db
from security import aluno_login_required

provas_aluno_bp = Blueprint("provas_aluno", __name__)

# ── Tolerância de tempo (segundos) ───────────────────────────────────────────
# Permite até 30s além do limite para compensar latência de rede/submit
_TOLERANCIA_SEGUNDOS = 30


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


# ── BUG-07: helpers para timestamp assinado ──────────────────────────────────

def _assinar(payload: str) -> str:
    """Retorna HMAC-SHA256 hex do payload usando SECRET_KEY."""
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def _criar_token_inicio(aluno_id: int, prova_id: int, agora_str: str) -> str:
    """Cria campo oculto assinado: 'aluno_id:prova_id:agora_str:hmac'."""
    payload = f"{aluno_id}:{prova_id}:{agora_str}"
    sig = _assinar(payload)
    return f"{payload}:{sig}"


def _verificar_token_inicio(token: str, aluno_id: int, prova_id: int):
    """Verifica assinatura e retorna datetime de início ou None se inválido."""
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return None
        payload, sig = parts
        if not hmac.compare_digest(sig, _assinar(payload)):
            return None
        # payload = aluno_id:prova_id:agora_str
        p_parts = payload.split(":")
        if len(p_parts) != 3:
            return None
        p_aluno, p_prova, p_ts = p_parts
        if int(p_aluno) != aluno_id or int(p_prova) != prova_id:
            return None
        return datetime.strptime(p_ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


# ── BUG-08: helpers para ordem de alternativas assinada ──────────────────────

def _criar_token_ordem(aluno_id: int, prova_id: int, ordem: dict) -> str:
    """Serializa e assina o mapa {questao_id: [alt_id, ...]}."""
    payload = json.dumps(ordem, separators=(",", ":"), sort_keys=True)
    sig = _assinar(f"{aluno_id}:{prova_id}:{payload}")
    return f"{payload}|{sig}"


def _verificar_token_ordem(token: str, aluno_id: int, prova_id: int):
    """Verifica e retorna o mapa de ordem ou None se inválido."""
    try:
        payload, sig = token.rsplit("|", 1)
        esperado = _assinar(f"{aluno_id}:{prova_id}:{payload}")
        if not hmac.compare_digest(sig, esperado):
            return None
        return json.loads(payload)
    except Exception:
        return None


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
        # ── BUG-07: validar tempo no servidor ────────────────────────────────
        if prova.tempo_limite:
            token_inicio = request.form.get("token_inicio", "")
            dt_inicio = _verificar_token_inicio(token_inicio, aluno.id, prova_id)
            agora = datetime.now()
            if dt_inicio is None:
                # Token inválido ou adulterado — rejeita
                flash("Sessão de prova inválida. Recarregue a página e tente novamente.", "erro")
                return redirect(f"/aluno/provas/{prova_id}/realizar")
            tempo_decorrido = agora - dt_inicio
            limite_com_tolerancia = timedelta(
                minutes=prova.tempo_limite, seconds=_TOLERANCIA_SEGUNDOS
            )
            if tempo_decorrido > limite_com_tolerancia:
                flash(
                    f"Tempo esgotado! Você levou "
                    f"{int(tempo_decorrido.total_seconds() // 60)} min para uma prova de "
                    f"{prova.tempo_limite} min. A tentativa foi registrada sem pontuação.",
                    "aviso"
                )
                # Registra tentativa consumida sem nota (para não burlar limite de tentativas)
                resp_vazia = RespostaProva(
                    prova_id=prova_id,
                    aluno_id=aluno.id,
                    tentativa_num=tentativas_feitas + 1,
                    iniciado_em=dt_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                    finalizado_em=agora.strftime("%Y-%m-%d %H:%M:%S"),
                    nota_obtida=0.0,
                    aprovado=0,
                )
                db.session.add(resp_vazia)
                db.session.commit()
                return redirect("/aluno/provas")

        # ── BUG-08: recuperar e validar ordem de alternativas assinada ───────
        token_ordem = request.form.get("token_ordem", "")
        ordem_alts = _verificar_token_ordem(token_ordem, aluno.id, prova_id) if token_ordem else None
        # ordem_alts: {str(questao_id): [alt_id_int, ...]} ou None (fallback: sem reordenação)

        agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Se passou pela validação de tempo, usa o dt_inicio já calculado
        if prova.tempo_limite and 'dt_inicio' in dir():
            iniciado_str = dt_inicio.strftime("%Y-%m-%d %H:%M:%S")
        else:
            iniciado_str = request.form.get("iniciado_em_raw", agora_str)

        resp_prova = RespostaProva(
            prova_id      = prova_id,
            aluno_id      = aluno.id,
            tentativa_num = tentativas_feitas + 1,
            iniciado_em   = iniciado_str,
            finalizado_em = agora_str,
        )
        db.session.add(resp_prova)
        db.session.flush()

        nota_total       = 0.0
        pontos_max       = 0.0
        tem_dissertativa = False

        for questao in questoes:
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
                # BUG-08: correção por ID real da alternativa (independente da ordem visual)
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

    # ── GET: embaralhar alternativas no servidor (BUG-08) ────────────────────
    # Monta lista de alternativas embaralhadas por questão e serializa assinado
    questoes_display = []  # lista de dicts com alternativas na ordem embaralhada
    ordem_map = {}  # {str(questao_id): [alt_id, ...]}
    for q in questoes:
        if q.tipo != "dissertativa":
            alts = list(q.alternativas)  # já ordenadas por Alternativa.ordem
            random.shuffle(alts)
            ordem_map[str(q.id)] = [a.id for a in alts]
            questoes_display.append({"questao": q, "alts": alts})
        else:
            questoes_display.append({"questao": q, "alts": []})

    token_ordem = _criar_token_ordem(aluno.id, prova_id, ordem_map)

    # ── BUG-07: gerar timestamp de início assinado ───────────────────────────
    agora_str  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    token_inicio = _criar_token_inicio(aluno.id, prova_id, agora_str) if prova.tempo_limite else ""

    return render_template(
        "aluno/provas_realizar.html",
        aluno=aluno,
        prova=prova,
        questoes=questoes,
        questoes_display=questoes_display,
        token_inicio=token_inicio,
        token_ordem=token_ordem,
    )


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
