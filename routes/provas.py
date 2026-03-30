from flask import Blueprint, render_template, request, redirect, flash, session
from db import db
from models import Prova, Questao, Alternativa, RespostaProva, Curso, Materia
from security import login_required, instrutor_required
from datetime import datetime

provas_bp = Blueprint("provas", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# LISTAGEM
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas")
@login_required
def listar_provas():
    curso_id = request.args.get("curso_id", type=int)
    q = Prova.query.order_by(Prova.id.desc())
    if curso_id:
        q = q.filter_by(curso_id=curso_id)
    provas  = q.all()
    cursos  = Curso.query.order_by(Curso.nome).all()
    return render_template("provas.html",
                           provas=provas,
                           cursos=cursos,
                           curso_id_sel=curso_id,
                           view="lista")


# ─────────────────────────────────────────────────────────────────────────────
# CRIAR PROVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/nova", methods=["GET", "POST"])
@login_required
def nova_prova():
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.filter_by(ativa=1).order_by(Materia.nome).all()

    if request.method == "POST":
        f = request.form
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
        flash(f"Prova \u201c{prova.titulo}\u201d criada. Agora adicione as quest\u00f5es.", "sucesso")
        return redirect(f"/provas/{prova.id}/questoes")

    return render_template("provas.html",
                           cursos=cursos,
                           materias=materias,
                           view="nova")


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR PROVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_prova(id):
    prova    = Prova.query.get_or_404(id)
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

    return render_template("provas.html",
                           prova=prova,
                           cursos=cursos,
                           materias=materias,
                           view="editar")


# ─────────────────────────────────────────────────────────────────────────────
# EXCLUIR PROVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_prova(id):
    prova = Prova.query.get_or_404(id)
    db.session.delete(prova)
    db.session.commit()
    flash("Prova excluída.", "sucesso")
    return redirect("/provas")


# ─────────────────────────────────────────────────────────────────────────────
# GERENCIAR QUESTÕES DE UMA PROVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/questoes", methods=["GET", "POST"])
@login_required
def gerenciar_questoes(id):
    prova = Prova.query.get_or_404(id)

    if request.method == "POST":
        acao = request.form.get("acao", "")

        # ── Adicionar nova questão ──
        if acao == "add_questao":
            enunciado = request.form.get("enunciado", "").strip()
            tipo      = request.form.get("tipo", "multipla_escolha")
            pontos    = float(request.form.get("pontos", 1.0))
            if not enunciado:
                flash("Enunciado não pode ser vazio.", "erro")
                return redirect(f"/provas/{id}/questoes")

            ordem = (db.session.query(db.func.max(Questao.ordem))
                     .filter_by(prova_id=id).scalar() or 0) + 1
            q = Questao(
                prova_id  = id,
                enunciado = enunciado,
                tipo      = tipo,
                ordem     = ordem,
                pontos    = pontos,
            )
            db.session.add(q)
            db.session.flush()  # gera q.id antes do commit

            # ── Alternativas (para objetivas) ──
            if tipo in ("multipla_escolha", "verdadeiro_falso"):
                textos  = request.form.getlist("alt_texto")
                corretas = request.form.getlist("alt_correta")  # valores = índice string
                for i, texto in enumerate(textos):
                    texto = texto.strip()
                    if not texto:
                        continue
                    alt = Alternativa(
                        questao_id = q.id,
                        texto      = texto,
                        correta    = 1 if str(i) in corretas else 0,
                        ordem      = i + 1,
                    )
                    db.session.add(alt)

            db.session.commit()
            flash("Questão adicionada.", "sucesso")
            return redirect(f"/provas/{id}/questoes")

        # ── Excluir questão ──
        elif acao == "del_questao":
            q_id = int(request.form.get("questao_id"))
            q = Questao.query.get_or_404(q_id)
            if q.prova_id != id:
                flash("Operação inválida.", "erro")
                return redirect(f"/provas/{id}/questoes")
            db.session.delete(q)
            db.session.commit()
            flash("Questão removida.", "sucesso")
            return redirect(f"/provas/{id}/questoes")

        # ── Editar questão ──
        elif acao == "edit_questao":
            q_id      = int(request.form.get("questao_id"))
            q         = Questao.query.get_or_404(q_id)
            enunciado = request.form.get("enunciado", "").strip()
            pontos    = float(request.form.get("pontos", q.pontos))
            if enunciado:
                q.enunciado = enunciado
            q.pontos = pontos

            # Atualiza alternativas existentes
            textos   = request.form.getlist("alt_texto")
            corretas = request.form.getlist("alt_correta")
            alt_ids  = request.form.getlist("alt_id")

            for idx, (alt_id, texto) in enumerate(zip(alt_ids, textos)):
                texto = texto.strip()
                if not texto:
                    continue
                alt = Alternativa.query.get(int(alt_id))
                if alt and alt.questao_id == q.id:
                    alt.texto   = texto
                    alt.correta = 1 if str(idx) in corretas else 0

            db.session.commit()
            flash("Questão atualizada.", "sucesso")
            return redirect(f"/provas/{id}/questoes")

    return render_template("provas.html",
                           prova=prova,
                           view="questoes")


# ─────────────────────────────────────────────────────────────────────────────
# RESULTADOS DE UMA PROVA
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/resultados")
@login_required
def resultados_prova(id):
    prova     = Prova.query.get_or_404(id)
    respostas = (RespostaProva.query
                 .filter_by(prova_id=id)
                 .order_by(RespostaProva.finalizado_em.desc())
                 .all())
    return render_template("provas.html",
                           prova=prova,
                           respostas=respostas,
                           view="resultados")


# ─────────────────────────────────────────────────────────────────────────────
# TOGGLE ATIVA/RASCUNHO
# ─────────────────────────────────────────────────────────────────────────────

@provas_bp.route("/provas/<int:id>/toggle", methods=["POST"])
@login_required
def toggle_prova(id):
    prova = Prova.query.get_or_404(id)
    if prova.total_questoes == 0 and prova.ativa == 0:
        flash("Adicione ao menos uma questão antes de ativar a prova.", "erro")
        return redirect("/provas")
    prova.ativa = 0 if prova.ativa else 1
    db.session.commit()
    estado = "ativada" if prova.ativa else "colocada em rascunho"
    flash(f"Prova {estado}.", "sucesso")
    return redirect("/provas")
