import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect,
    flash, session, abort, Response, current_app, jsonify
)
from werkzeug.utils import secure_filename
from db import db
from models import (
    Materia, Exercicio, ExercicioQuestao, ExercicioAlternativa,
    RespostaExercicio, RespostaExercicioQuestao, ExercicioLiberado,
    Curso, CursoMateria, Aluno
)
from security import login_required

exercicios_bp = Blueprint("exercicios", __name__)

ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "docx", "doc"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def _upload_folder():
    return os.path.join(current_app.root_path, "static", "uploads", "exercicios")


def _materias_json():
    materias = Materia.query.order_by(Materia.nome).all()
    return materias, [{"id": m.id, "nome": m.nome, "curso_id": m.curso_id} for m in materias]


def _calcular_nota(total_pontos, pontos_max):
    if not pontos_max or pontos_max <= 0.0:
        return 0.0
    return round((total_pontos / pontos_max) * 10, 2)


# ── LISTAGEM GERAL ────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios")
@login_required
def exercicios_geral():
    cursos = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()
    curso_id_sel = request.args.get("curso_id", type=int)

    query = Exercicio.query
    if curso_id_sel:
        mids = [
            m.id for m in materias
            if any(cm.curso_id == curso_id_sel
                   for cm in CursoMateria.query.filter_by(materia_id=m.id).all())
        ]
        query = query.filter(Exercicio.materia_id.in_(mids)) if mids else query.filter(False)
    exercicios = query.order_by(Exercicio.id.desc()).all()

    return render_template(
        "exercicios_geral.html",
        cursos=cursos, materias=materias, materias_json=materias_json,
        exercicios=exercicios, curso_id_sel=curso_id_sel, view="lista",
    )


# ── CRIAR EXERCICIO ───────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/novo", methods=["GET", "POST"])
@login_required
def novo_exercicio():
    cursos = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()

    if request.method == "POST":
        f = request.form
        titulo      = f.get("titulo", "").strip()
        materia_id  = f.get("materia_id", type=int)
        descricao   = f.get("descricao", "").strip() or None
        ordem       = f.get("ordem", 1, type=int)
        tentativas  = max(1, f.get("tentativas", 1, type=int))
        tempo_limite = f.get("tempo_limite", type=int) or None
        nota_minima = f.get("nota_minima", 6.0, type=float)
        ativo       = 1 if f.get("ativo") else 0

        if not titulo or not materia_id:
            flash("Título e matéria são obrigatórios.", "erro")
            return redirect("/exercicios/novo")

        arquivo_nome = None
        arq = request.files.get("arquivo")
        if arq and arq.filename and _allowed(arq.filename):
            pasta = _upload_folder()
            os.makedirs(pasta, exist_ok=True)
            nome_seguro = secure_filename(
                f"{materia_id}_{int(datetime.now().timestamp())}_{arq.filename}"
            )
            arq.save(os.path.join(pasta, nome_seguro))
            arquivo_nome = f"exercicios/{nome_seguro}"

        ex = Exercicio(
            materia_id=materia_id, titulo=titulo, descricao=descricao,
            arquivo=arquivo_nome, ordem=ordem, tentativas=tentativas,
            tempo_limite=tempo_limite, nota_minima=nota_minima, ativo=ativo,
            criado_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            criado_por=session.get("usuario") or "",
        )
        db.session.add(ex)
        db.session.commit()
        flash(f"Exercício \u201c{titulo}\u201d criado! Adicione as questões.", "sucesso")
        return redirect(f"/exercicios/{ex.id}/questoes")

    return render_template(
        "exercicios_geral.html",
        cursos=cursos, materias=materias, materias_json=materias_json, view="novo",
    )


# ── EDITAR EXERCICIO ──────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/editar", methods=["GET", "POST"])
@login_required
def editar_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    cursos = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()

    if request.method == "POST":
        f = request.form
        ex.titulo       = f.get("titulo", ex.titulo).strip() or ex.titulo
        ex.descricao    = f.get("descricao", "").strip() or None
        ex.materia_id   = f.get("materia_id", type=int) or ex.materia_id
        ex.ordem        = f.get("ordem", ex.ordem, type=int)
        ex.tentativas   = max(1, f.get("tentativas", ex.tentativas or 1, type=int))
        ex.tempo_limite = f.get("tempo_limite", type=int) or None
        ex.nota_minima  = f.get("nota_minima", ex.nota_minima or 6.0, type=float)
        ex.ativo        = 1 if f.get("ativo") else 0

        arq = request.files.get("arquivo")
        if arq and arq.filename and _allowed(arq.filename):
            pasta = _upload_folder()
            os.makedirs(pasta, exist_ok=True)
            nome_seguro = secure_filename(
                f"{ex.materia_id}_{int(datetime.now().timestamp())}_{arq.filename}"
            )
            arq.save(os.path.join(pasta, nome_seguro))
            ex.arquivo = f"exercicios/{nome_seguro}"

        db.session.commit()
        flash("Exercício atualizado!", "sucesso")
        return redirect("/exercicios")

    return render_template(
        "exercicios_geral.html",
        exercicio=ex, cursos=cursos, materias=materias,
        materias_json=materias_json, view="editar",
    )


# ── TOGGLE ATIVO ──────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/toggle", methods=["POST"])
@login_required
def toggle_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    if ex.total_questoes == 0 and not ex.ativo:
        flash("Adicione ao menos uma questão antes de ativar o exercício.", "erro")
        return redirect("/exercicios")
    ex.ativo = 0 if ex.ativo else 1
    db.session.commit()
    estado = "ativado" if ex.ativo else "colocado em rascunho"
    flash(f"Exercício {estado}.", "sucesso")
    return redirect("/exercicios")


# ── EXCLUIR EXERCICIO ─────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/excluir", methods=["POST"])
@login_required
def excluir_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    db.session.delete(ex)
    db.session.commit()
    flash("Exercício excluído.", "sucesso")
    return redirect("/exercicios")


# ── GERENCIAR QUESTÕES ────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/questoes", methods=["GET", "POST"])
@login_required
def gerenciar_questoes_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)

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
                return redirect(f"/exercicios/{ex_id}/questoes")

            ordem = (db.session.query(db.func.max(ExercicioQuestao.ordem))
                     .filter_by(exercicio_id=ex_id).scalar() or 0) + 1
            q = ExercicioQuestao(
                exercicio_id=ex_id, enunciado=enunciado,
                tipo=tipo, ordem=ordem, pontos=pontos
            )
            db.session.add(q)
            db.session.flush()

            if tipo in ("multipla_escolha", "verdadeiro_falso"):
                textos   = request.form.getlist("alt_texto")
                corretas = request.form.getlist("alt_correta")
                for i, texto in enumerate(textos):
                    texto = texto.strip()
                    if not texto:
                        continue
                    db.session.add(ExercicioAlternativa(
                        questao_id=q.id, texto=texto,
                        correta=1 if str(i) in corretas else 0,
                        ordem=i + 1,
                    ))
            db.session.commit()
            flash("Questão adicionada.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

        elif acao == "del_questao":
            q_id = int(request.form.get("questao_id"))
            q    = db.get_or_404(ExercicioQuestao, q_id)
            if q.exercicio_id != ex_id:
                flash("Operação inválida.", "erro")
                return redirect(f"/exercicios/{ex_id}/questoes")
            db.session.delete(q)
            db.session.commit()
            flash("Questão removida.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

        elif acao == "edit_questao":
            q_id = int(request.form.get("questao_id"))
            q    = db.get_or_404(ExercicioQuestao, q_id)
            enun = request.form.get("enunciado", "").strip()
            if enun:
                q.enunciado = enun
            try:
                q.pontos = max(0.1, float(request.form.get("pontos", q.pontos)))
            except (ValueError, TypeError):
                pass

            textos   = request.form.getlist("alt_texto")
            corretas = request.form.getlist("alt_correta")
            alt_ids  = request.form.getlist("alt_id")

            nova_ordem = len(q.alternativas) + 1
            for idx, (alt_id, texto) in enumerate(zip(alt_ids, textos)):
                texto = texto.strip()
                if not texto:
                    continue
                if alt_id:
                    alt = db.session.get(ExercicioAlternativa, int(alt_id))
                    if alt and alt.questao_id == q.id:
                        alt.texto   = texto
                        alt.correta = 1 if str(idx) in corretas else 0
                else:
                    db.session.add(ExercicioAlternativa(
                        questao_id=q.id, texto=texto,
                        correta=1 if str(idx) in corretas else 0,
                        ordem=nova_ordem,
                    ))
                    nova_ordem += 1

            db.session.commit()
            flash("Questão atualizada.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

    return render_template("exercicios_geral.html", exercicio=ex, view="questoes")


# ── RESULTADOS ────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/resultados")
@login_required
def resultados_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    respostas = (
        RespostaExercicio.query
        .filter_by(exercicio_id=ex_id)
        .order_by(RespostaExercicio.finalizado_em.desc())
        .all()
    )
    pendentes = sum(1 for r in respostas if r.nota_obtida is None)
    return render_template(
        "exercicios_geral.html",
        exercicio=ex, respostas=respostas,
        pendentes=pendentes, view="resultados",
    )


# ── RECALCULAR NOTAS EM LOTE ──────────────────────────────────────────────────
# Corrige tentativas que ficaram com nota_obtida=NULL porque foram salvas por
# versões antigas do código (só objetivas; dissertativas são ignoradas).
# Acessível em: POST /exercicios/<ex_id>/recalcular-notas
#           ou: POST /exercicios/recalcular-notas  (todos os exercícios)

def _recalcular_tentativas_sem_nota(exercicio_id=None):
    """
    Recalcula nota_obtida e aprovado para todas as RespostaExercicio com
    nota_obtida IS NULL que NÃO possuem questão dissertativa pendente de correção.
    Retorna (corrigidas, ignoradas).
    """
    query = RespostaExercicio.query.filter(RespostaExercicio.nota_obtida.is_(None))
    if exercicio_id:
        query = query.filter_by(exercicio_id=exercicio_id)

    corrigidas = 0
    ignoradas  = 0  # têm dissertativa não corrigida — precisam de correção manual

    for resp in query.all():
        ex = db.session.get(Exercicio, resp.exercicio_id)
        if not ex:
            continue

        respostas_q = (
            db.session.query(RespostaExercicioQuestao, ExercicioQuestao)
            .join(ExercicioQuestao, ExercicioQuestao.id == RespostaExercicioQuestao.questao_id)
            .filter(RespostaExercicioQuestao.resposta_exercicio_id == resp.id)
            .all()
        )

        # Verifica se há dissertativa não corrigida
        tem_diss_pendente = any(
            q.tipo == "dissertativa" and not rq.corrigida
            for rq, q in respostas_q
        )
        if tem_diss_pendente:
            ignoradas += 1
            continue

        # Soma pontos de todas as questões
        total_pontos = 0.0
        pontos_max   = 0.0
        for rq, q in respostas_q:
            pts_questao  = max(0.0, float(q.pontos or 0.0))
            pontos_max  += pts_questao
            total_pontos += (rq.pontos_obtidos or 0.0)

        nota_final       = _calcular_nota(total_pontos, pontos_max)
        resp.nota_obtida = nota_final
        resp.aprovado    = 1 if nota_final >= float(ex.nota_minima or 6.0) else 0
        corrigidas      += 1

    db.session.commit()
    return corrigidas, ignoradas


@exercicios_bp.route("/exercicios/<int:ex_id>/recalcular-notas", methods=["POST"])
@login_required
def recalcular_notas_exercicio(ex_id):
    db.get_or_404(Exercicio, ex_id)
    corrigidas, ignoradas = _recalcular_tentativas_sem_nota(exercicio_id=ex_id)
    msg = f"{corrigidas} nota(s) recalculada(s)."
    if ignoradas:
        msg += f" {ignoradas} tentativa(s) ignorada(s) (têm dissertativa pendente — use 'Corrigir')."
    flash(msg, "sucesso" if corrigidas else "aviso")
    return redirect(f"/exercicios/{ex_id}/resultados")


@exercicios_bp.route("/exercicios/recalcular-notas", methods=["POST"])
@login_required
def recalcular_notas_todos():
    """Recalcula notas pendentes de TODOS os exercícios de uma vez."""
    corrigidas, ignoradas = _recalcular_tentativas_sem_nota()
    msg = f"{corrigidas} nota(s) recalculada(s) em todos os exercícios."
    if ignoradas:
        msg += f" {ignoradas} ignorada(s) (dissertativas pendentes)."
    flash(msg, "sucesso" if corrigidas else "aviso")
    return redirect("/exercicios")


# ── CORRIGIR TENTATIVA ────────────────────────────────────────────────────────
# Espelho exato de routes/provas.py → corrigir_tentativa

@exercicios_bp.route("/exercicios/<int:ex_id>/tentativa/<int:resp_id>/corrigir",
                     methods=["GET", "POST"])
@login_required
def corrigir_tentativa_exercicio(ex_id, resp_id):
    resp = db.get_or_404(RespostaExercicio, resp_id)
    ex   = db.get_or_404(Exercicio, ex_id)
    if resp.exercicio_id != ex_id:
        abort(403)
    aluno = db.get_or_404(Aluno, resp.aluno_id)

    respostas = (
        db.session.query(RespostaExercicioQuestao, ExercicioQuestao)
        .join(ExercicioQuestao, ExercicioQuestao.id == RespostaExercicioQuestao.questao_id)
        .filter(RespostaExercicioQuestao.resposta_exercicio_id == resp_id)
        .order_by(ExercicioQuestao.ordem)
        .all()
    )

    if request.method == "POST":
        total_pontos = 0.0
        pontos_max   = 0.0

        for rq, q in respostas:
            pts_questao  = max(0.0, float(q.pontos or 0.0))
            pontos_max  += pts_questao
            if q.tipo == "dissertativa":
                try:
                    pts = float(request.form.get(f"pontos_{rq.id}", 0))
                    pts = max(0.0, min(pts, pts_questao))
                except (ValueError, TypeError):
                    pts = 0.0
                rq.pontos_obtidos = pts
                rq.corrigida      = 1
                total_pontos     += pts
            else:
                total_pontos += (rq.pontos_obtidos or 0.0)

        nota_final       = _calcular_nota(total_pontos, pontos_max)
        resp.nota_obtida = nota_final
        resp.aprovado    = 1 if nota_final >= float(ex.nota_minima or 6.0) else 0
        db.session.commit()

        flash(
            f"Correção salva! {aluno.nome} \u2014 "
            f"Nota: {nota_final} ({'Aprovado' if resp.aprovado else 'Reprovado'}).",
            "sucesso"
        )
        return redirect(f"/exercicios/{ex_id}/resultados")

    gabarito = []
    for rq, q in respostas:
        correta   = ExercicioAlternativa.query.filter_by(questao_id=q.id, correta=1).first()
        escolhida = db.session.get(ExercicioAlternativa, rq.alternativa_id) if rq.alternativa_id else None
        gabarito.append({
            "questao":   q,
            "rq":        rq,
            "correta":   correta,
            "escolhida": escolhida,
        })

    return render_template(
        "exercicio_corrigir.html",
        exercicio=ex, resp=resp, aluno=aluno, gabarito=gabarito,
    )


# ── TENTATIVAS EXTRAS ─────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/extra-tentativas", methods=["POST"])
@login_required
def extra_tentativas_exercicio(ex_id):
    db.get_or_404(Exercicio, ex_id)
    aluno_id = request.form.get("aluno_id", type=int)
    qtd      = request.form.get("qtd", 1, type=int)
    if not aluno_id:
        flash("Aluno não informado.", "erro")
        return redirect(f"/exercicios/{ex_id}/resultados")
    lib = ExercicioLiberado.query.filter_by(aluno_id=aluno_id, exercicio_id=ex_id).first()
    if lib:
        lib.extra_tentativas = (lib.extra_tentativas or 0) + max(1, qtd)
    else:
        lib = ExercicioLiberado(
            aluno_id=aluno_id, exercicio_id=ex_id, liberado=1,
            liberado_por=session.get("usuario", ""),
            liberado_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            extra_tentativas=max(1, qtd),
        )
        db.session.add(lib)
    db.session.commit()
    flash(f"{qtd} tentativa(s) extra(s) concedida(s).", "sucesso")
    return redirect(f"/exercicios/{ex_id}/resultados")


# ── ROTAS LEGADAS ─────────────────────────────────────────────────────────────

@exercicios_bp.route("/materias/<int:materia_id>/exercicios")
@login_required
def lista_exercicios(materia_id):
    materia    = db.get_or_404(Materia, materia_id)
    exercicios = Exercicio.query.filter_by(materia_id=materia_id, ativo=1)\
                                .order_by(Exercicio.ordem).all()
    cursos = (
        db.session.query(Curso)
        .join(CursoMateria, CursoMateria.curso_id == Curso.id)
        .filter(CursoMateria.materia_id == materia_id)
        .all()
    )
    return render_template(
        "exercicios.html",
        materia=materia, exercicios=exercicios, cursos=cursos
    )


@exercicios_bp.route("/materias/<int:materia_id>/exercicios/criar", methods=["POST"])
@login_required
def criar_exercicio(materia_id):
    db.get_or_404(Materia, materia_id)
    titulo       = request.form.get("titulo", "").strip()
    descricao    = request.form.get("descricao", "").strip()
    ordem        = request.form.get("ordem", 1, type=int)
    tentativas   = request.form.get("tentativas", 1, type=int)
    tempo_limite = request.form.get("tempo_limite", type=int)
    if not titulo:
        flash("Título é obrigatório.", "erro")
        return redirect(f"/materias/{materia_id}/exercicios")

    arquivo_nome = None
    f = request.files.get("arquivo")
    if f and f.filename and _allowed(f.filename):
        pasta = _upload_folder()
        os.makedirs(pasta, exist_ok=True)
        nome_seguro = secure_filename(
            f"{materia_id}_{int(datetime.now().timestamp())}_{f.filename}"
        )
        f.save(os.path.join(pasta, nome_seguro))
        arquivo_nome = f"exercicios/{nome_seguro}"

    ex = Exercicio(
        materia_id=materia_id, titulo=titulo,
        descricao=descricao or None, arquivo=arquivo_nome,
        ordem=ordem, tentativas=max(1, tentativas or 1),
        tempo_limite=tempo_limite or None, ativo=1,
        criado_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        criado_por=session.get("usuario") or "",
    )
    db.session.add(ex)
    db.session.commit()
    flash(f"Exercício '{titulo}' criado!", "sucesso")
    return redirect(f"/exercicios/{ex.id}/questoes")


# ── SERVIR ARQUIVO ────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/arquivo")
@login_required
def ver_arquivo_exercicio(ex_id):
    import mimetypes
    ex = db.get_or_404(Exercicio, ex_id)
    if not ex.arquivo:
        abort(404)
    caminho = os.path.join(current_app.root_path, "static", "uploads", ex.arquivo)
    if not os.path.isfile(caminho):
        abort(404)
    mime, _ = mimetypes.guess_type(caminho)
    with open(caminho, "rb") as fp:
        dados = fp.read()
    r = Response(dados, mimetype=mime or "application/octet-stream")
    r.headers["Content-Disposition"] = "inline"
    return r
