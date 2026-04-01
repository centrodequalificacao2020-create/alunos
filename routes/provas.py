from flask import Blueprint, render_template, request, redirect, flash, session, jsonify
from db import db
from security import login_required
from datetime import datetime

provas_bp = Blueprint("provas", __name__)


def _calcular_nota(total_pontos, pontos_max):
    """Nota na escala 0-10. Retorna 0.0 se pontos_max <= 0 (evita div/zero)."""
    if not pontos_max or pontos_max <= 0.0:
        return 0.0
    return round((total_pontos / pontos_max) * 10, 2)


# ─────────────────────────────────────────────────────────────────────────────────
# LISTAGEM
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas")
@login_required
def listar_provas():
    from models import Prova, Curso
    curso_id = request.args.get("curso_id", type=int)
    try:
        q = Prova.query.order_by(Prova.id.desc())
        if curso_id:
            q = q.filter_by(curso_id=curso_id)
        provas = q.all()
    except Exception:
        provas = []
    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("provas.html",
                           provas=provas, cursos=cursos,
                           curso_id_sel=curso_id, view="lista")


# ─────────────────────────────────────────────────────────────────────────────────
# CRIAR PROVA
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/nova", methods=["GET", "POST"])
@login_required
def nova_prova():
    from models import Prova, Curso, Materia
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.filter_by(ativa=1).order_by(Materia.nome).all()

    if request.method == "POST":
        f      = request.form
        titulo = f.get("titulo", "").strip()
        if not titulo:
            flash("Título é obrigatório.", "erro")
            return redirect("/provas/nova")

        prova = Prova(
            titulo       = titulo,
            descricao    = f.get("descricao", "").strip() or None,
            curso_id     = int(f.get("curso_id")),
            materia_id   = int(f.get("materia_id")) if f.get("materia_id") else None,
            tempo_limite = int(f.get("tempo_limite")) if f.get("tempo_limite") else None,
            tentativas   = int(f.get("tentativas", 1)),
            nota_minima  = float(f.get("nota_minima", 6.0)),
            ativa        = 1 if f.get("ativa") else 0,
            criado_em    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            criado_por   = session.get("usuario", ""),
        )
        db.session.add(prova)
        db.session.commit()
        flash(f"Prova \u201c{prova.titulo}\u201d criada. Adicione as quest\u00f5es.", "sucesso")
        return redirect(f"/provas/{prova.id}/questoes")

    return render_template("provas.html", cursos=cursos, materias=materias, view="nova")


# ─────────────────────────────────────────────────────────────────────────────────
# EDITAR PROVA
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_prova(id):
    from models import Prova, Curso, Materia
    prova    = db.get_or_404(Prova, id)
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.filter_by(ativa=1).order_by(Materia.nome).all()

    if request.method == "POST":
        f = request.form
        prova.titulo       = f.get("titulo", "").strip() or prova.titulo
        prova.descricao    = f.get("descricao", "").strip() or None
        prova.curso_id     = int(f.get("curso_id"))
        prova.materia_id   = int(f.get("materia_id")) if f.get("materia_id") else None
        prova.tempo_limite = int(f.get("tempo_limite")) if f.get("tempo_limite") else None
        prova.tentativas   = int(f.get("tentativas", 1))
        prova.nota_minima  = float(f.get("nota_minima", 6.0))
        prova.ativa        = 1 if f.get("ativa") else 0
        db.session.commit()
        flash("Prova atualizada.", "sucesso")
        return redirect("/provas")

    return render_template("provas.html", prova=prova,
                           cursos=cursos, materias=materias, view="editar")


# ─────────────────────────────────────────────────────────────────────────────────
# EXCLUIR PROVA
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_prova(id):
    from models import Prova
    prova = db.get_or_404(Prova, id)
    # O cascade "all, delete-orphan" nos relacionamentos de Prova cuida
    # de questoes, alternativas, respostas e liberacoes automaticamente.
    db.session.delete(prova)
    db.session.commit()
    flash("Prova excluída.", "sucesso")
    return redirect("/provas")


# ─────────────────────────────────────────────────────────────────────────────────
# GERENCIAR QUESTÕES
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/questoes", methods=["GET", "POST"])
@login_required
def gerenciar_questoes(id):
    from models import Prova, Questao, Alternativa
    prova = db.get_or_404(Prova, id)

    if request.method == "POST":
        acao = request.form.get("acao", "")

        if acao == "add_questao":
            enunciado = request.form.get("enunciado", "").strip()
            tipo      = request.form.get("tipo", "multipla_escolha")
            try:
                pontos = float(request.form.get("pontos", 1.0))
            except (ValueError, TypeError):
                pontos = 1.0
            pontos = max(0.1, pontos)

            if not enunciado:
                flash("Enunciado não pode ser vazio.", "erro")
                return redirect(f"/provas/{id}/questoes")

            ordem = (db.session.query(db.func.max(Questao.ordem))
                     .filter_by(prova_id=id).scalar() or 0) + 1
            q = Questao(prova_id=id, enunciado=enunciado,
                        tipo=tipo, ordem=ordem, pontos=pontos)
            db.session.add(q)
            db.session.flush()

            if tipo in ("multipla_escolha", "verdadeiro_falso"):
                textos   = request.form.getlist("alt_texto")
                corretas = request.form.getlist("alt_correta")
                for i, texto in enumerate(textos):
                    texto = texto.strip()
                    if not texto:
                        continue
                    db.session.add(Alternativa(
                        questao_id=q.id, texto=texto,
                        correta=1 if str(i) in corretas else 0,
                        ordem=i + 1,
                    ))

            db.session.commit()
            flash("Questão adicionada.", "sucesso")
            return redirect(f"/provas/{id}/questoes")

        elif acao == "del_questao":
            q_id = int(request.form.get("questao_id"))
            q    = db.get_or_404(Questao, q_id)
            if q.prova_id != id:
                flash("Operação inválida.", "erro")
                return redirect(f"/provas/{id}/questoes")
            db.session.delete(q)
            db.session.commit()
            flash("Questão removida.", "sucesso")
            return redirect(f"/provas/{id}/questoes")

        elif acao == "edit_questao":
            q_id = int(request.form.get("questao_id"))
            q    = db.get_or_404(Questao, q_id)
            enun = request.form.get("enunciado", "").strip()
            if enun:
                q.enunciado = enun
            try:
                novos_pontos = float(request.form.get("pontos", q.pontos))
            except (ValueError, TypeError):
                novos_pontos = q.pontos
            q.pontos = max(0.1, novos_pontos)

            textos   = request.form.getlist("alt_texto")
            corretas = request.form.getlist("alt_correta")
            alt_ids  = request.form.getlist("alt_id")
            for idx, (alt_id, texto) in enumerate(zip(alt_ids, textos)):
                texto = texto.strip()
                if not texto:
                    continue
                alt = db.session.get(Alternativa, int(alt_id))
                if alt and alt.questao_id == q.id:
                    alt.texto   = texto
                    alt.correta = 1 if str(idx) in corretas else 0
            db.session.commit()
            flash("Questão atualizada.", "sucesso")
            return redirect(f"/provas/{id}/questoes")

    return render_template("provas.html", prova=prova, view="questoes")


# ─────────────────────────────────────────────────────────────────────────────────
# RESULTADOS DE UMA PROVA (admin)
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/resultados")
@login_required
def resultados_prova(id):
    from models import Prova, RespostaProva
    prova = db.get_or_404(Prova, id)
    try:
        respostas = (
            RespostaProva.query
            .filter_by(prova_id=id)
            .order_by(RespostaProva.finalizado_em.desc())
            .all()
        )
    except Exception:
        respostas = []
    pendentes = sum(1 for r in respostas if r.nota_obtida is None)
    return render_template("provas.html",
                           prova=prova, respostas=respostas,
                           pendentes=pendentes, view="resultados")


# ─────────────────────────────────────────────────────────────────────────────────
# CORRIGIR TENTATIVA DISSERTATIVA
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/corrigir/<int:resp_id>", methods=["GET", "POST"])
@login_required
def corrigir_tentativa(resp_id):
    from models import Prova, Questao, Alternativa, RespostaProva, RespostaQuestao, Aluno
    resp_prova = db.get_or_404(RespostaProva, resp_id)
    prova      = db.get_or_404(Prova, resp_prova.prova_id)
    aluno      = db.get_or_404(Aluno, resp_prova.aluno_id)

    respostas = (
        db.session.query(RespostaQuestao, Questao)
        .join(Questao, Questao.id == RespostaQuestao.questao_id)
        .filter(RespostaQuestao.resposta_prova_id == resp_id)
        .order_by(Questao.ordem)
        .all()
    )

    if request.method == "POST":
        total_pontos = 0.0
        pontos_max   = 0.0

        for rq, q in respostas:
            pts_questao = max(0.0, float(q.pontos or 0.0))
            pontos_max += pts_questao
            if q.tipo == "dissertativa":
                campo = f"pontos_{rq.id}"
                try:
                    pts = float(request.form.get(campo, 0))
                    pts = max(0.0, min(pts, pts_questao))
                except (ValueError, TypeError):
                    pts = 0.0
                rq.pontos_obtidos = pts
                rq.corrigida      = 1
                total_pontos += pts
            else:
                total_pontos += (rq.pontos_obtidos or 0.0)

        nota_final = _calcular_nota(total_pontos, pontos_max)
        resp_prova.nota_obtida = nota_final
        resp_prova.aprovado    = 1 if nota_final >= prova.nota_minima else 0
        db.session.commit()

        flash(
            f"Correção salva! Aluno {aluno.nome} — "
            f"Nota: {nota_final} ({'Aprovado' if resp_prova.aprovado else 'Reprovado'}).",
            "sucesso"
        )
        return redirect(f"/provas/{prova.id}/resultados")

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

    return render_template("provas_corrigir.html",
                           resp_prova=resp_prova, prova=prova,
                           aluno=aluno, gabarito=gabarito)


# ─────────────────────────────────────────────────────────────────────────────────
# TOGGLE ATIVA/RASCUNHO
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/toggle", methods=["POST"])
@login_required
def toggle_prova(id):
    from models import Prova
    prova = db.get_or_404(Prova, id)
    if prova.total_questoes == 0 and prova.ativa == 0:
        flash("Adicione ao menos uma questão antes de ativar a prova.", "erro")
        return redirect("/provas")
    prova.ativa = 0 if prova.ativa else 1
    db.session.commit()
    estado = "ativada" if prova.ativa else "colocada em rascunho"
    flash(f"Prova {estado}.", "sucesso")
    return redirect("/provas")


# ─────────────────────────────────────────────────────────────────────────────────
# API JSON — estatísticas
# ─────────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/stats.json")
@login_required
def stats_prova(id):
    from models import Prova, RespostaProva
    prova = db.get_or_404(Prova, id)
    try:
        respostas = RespostaProva.query.filter_by(prova_id=id).all()
    except Exception:
        respostas = []
    notas     = [r.nota_obtida for r in respostas if r.nota_obtida is not None]
    aprovados = sum(1 for r in respostas if r.aprovado == 1)
    pendentes = sum(1 for r in respostas if r.nota_obtida is None)
    return jsonify({
        "total_tentativas": len(respostas),
        "pendentes":        pendentes,
        "aprovados":        aprovados,
        "reprovados":       len(notas) - aprovados,
        "media":            round(sum(notas) / len(notas), 2) if notas else None,
        "maior_nota":       max(notas) if notas else None,
        "menor_nota":       min(notas) if notas else None,
    })
