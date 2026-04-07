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
    """Nota na escala 0-10. Retorna 0.0 se pontos_max <= 0."""
    if not pontos_max or pontos_max <= 0.0:
        return 0.0
    return round((total_pontos / pontos_max) * 10, 2)


# ───────────────────────────────────────────────────────────────────────────
# LISTAGEM GERAL
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios")
@login_required
def exercicios_geral():
    cursos        = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()
    curso_id_sel  = request.args.get("curso_id", type=int)

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
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        exercicios    = exercicios,
        curso_id_sel  = curso_id_sel,
        view          = "lista",
    )


# ───────────────────────────────────────────────────────────────────────────
# CRIAR EXERCICIO
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/novo", methods=["GET", "POST"])
@login_required
def novo_exercicio():
    cursos        = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()

    if request.method == "POST":
        f            = request.form
        titulo       = f.get("titulo", "").strip()
        materia_id   = f.get("materia_id", type=int)
        descricao    = f.get("descricao", "").strip() or None
        ordem        = f.get("ordem", 1, type=int)
        tentativas   = max(1, f.get("tentativas", 1, type=int))
        tempo_limite = f.get("tempo_limite", type=int) or None
        nota_minima  = f.get("nota_minima", 6.0, type=float)
        ativo        = 1 if f.get("ativo") else 0

        if not titulo or not materia_id:
            flash("T\u00edtulo e mat\u00e9ria s\u00e3o obrigat\u00f3rios.", "erro")
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
            materia_id   = materia_id,
            titulo       = titulo,
            descricao    = descricao,
            arquivo      = arquivo_nome,
            ordem        = ordem,
            tentativas   = tentativas,
            tempo_limite = tempo_limite,
            nota_minima  = nota_minima,
            ativo        = ativo,
            criado_em    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            criado_por   = session.get("usuario") or "",
        )
        db.session.add(ex)
        db.session.commit()
        flash(f"Exerc\u00edcio \u201c{titulo}\u201d criado! Adicione as quest\u00f5es.", "sucesso")
        return redirect(f"/exercicios/{ex.id}/questoes")

    return render_template(
        "exercicios_geral.html",
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        view          = "novo",
    )


# ───────────────────────────────────────────────────────────────────────────
# EDITAR EXERCICIO
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/editar", methods=["GET", "POST"])
@login_required
def editar_exercicio(ex_id):
    ex            = db.get_or_404(Exercicio, ex_id)
    cursos        = Curso.query.order_by(Curso.nome).all()
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
        flash("Exerc\u00edcio atualizado!", "sucesso")
        return redirect("/exercicios")

    return render_template(
        "exercicios_geral.html",
        exercicio     = ex,
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        view          = "editar",
    )


# ───────────────────────────────────────────────────────────────────────────
# TOGGLE ATIVO / RASCUNHO
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/toggle", methods=["POST"])
@login_required
def toggle_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    if ex.total_questoes == 0 and not ex.ativo:
        flash("Adicione ao menos uma quest\u00e3o antes de ativar o exerc\u00edcio.", "erro")
        return redirect("/exercicios")
    ex.ativo = 0 if ex.ativo else 1
    db.session.commit()
    estado = "ativado" if ex.ativo else "colocado em rascunho"
    flash(f"Exerc\u00edcio {estado}.", "sucesso")
    return redirect("/exercicios")


# ───────────────────────────────────────────────────────────────────────────
# EXCLUIR EXERCICIO
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/excluir", methods=["POST"])
@login_required
def excluir_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    db.session.delete(ex)
    db.session.commit()
    flash("Exerc\u00edcio exclu\u00eddo.", "sucesso")
    return redirect("/exercicios")


# ───────────────────────────────────────────────────────────────────────────
# GERENCIAR QUESTOES
# ───────────────────────────────────────────────────────────────────────────

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
                flash("Enunciado n\u00e3o pode ser vazio.", "erro")
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
            flash("Quest\u00e3o adicionada.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

        elif acao == "del_questao":
            q_id = int(request.form.get("questao_id"))
            q    = db.get_or_404(ExercicioQuestao, q_id)
            if q.exercicio_id != ex_id:
                flash("Opera\u00e7\u00e3o inv\u00e1lida.", "erro")
                return redirect(f"/exercicios/{ex_id}/questoes")
            db.session.delete(q)
            db.session.commit()
            flash("Quest\u00e3o removida.", "sucesso")
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
            flash("Quest\u00e3o atualizada.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

    return render_template("exercicios_geral.html", exercicio=ex, view="questoes")


# ───────────────────────────────────────────────────────────────────────────
# RESULTADOS DO EXERCICIO
# ───────────────────────────────────────────────────────────────────────────

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
    # pendentes: tentativas com questão dissertativa ainda sem nota
    tem_dissertativa = any(q.tipo == "dissertativa" for q in ex.questoes)
    pendentes = sum(
        1 for r in respostas
        if tem_dissertativa and r.nota_obtida is None
    ) if tem_dissertativa else 0

    return render_template(
        "exercicios_geral.html",
        exercicio = ex,
        respostas = respostas,
        pendentes = pendentes,
        view      = "resultados",
    )


# ───────────────────────────────────────────────────────────────────────────
# CORRIGIR TENTATIVA (dissertativas) — espelho de provas
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/tentativa/<int:resp_id>/corrigir",
                     methods=["GET", "POST"])
@login_required
def corrigir_tentativa_exercicio(ex_id, resp_id):
    ex   = db.get_or_404(Exercicio, ex_id)
    resp = db.get_or_404(RespostaExercicio, resp_id)
    if resp.exercicio_id != ex_id:
        abort(403)

    respostas = (
        db.session.query(RespostaExercicioQuestao, ExercicioQuestao)
        .join(ExercicioQuestao, ExercicioQuestao.id == RespostaExercicioQuestao.questao_id)
        .filter(RespostaExercicioQuestao.resposta_exercicio_id == resp_id)
        .order_by(ExercicioQuestao.ordem)
        .all()
    )

    if request.method == "POST":
        total_pontos = 0.0
        pontos_max   = sum(q.pontos for _, q in respostas)

        for rq, q in respostas:
            if q.tipo == "dissertativa":
                campo_pts = f"pontos_{rq.id}"
                try:
                    pts = float(request.form.get(campo_pts, rq.pontos_obtidos or 0))
                    pts = max(0.0, min(float(q.pontos), pts))
                except (ValueError, TypeError):
                    pts = rq.pontos_obtidos or 0.0
                rq.pontos_obtidos = pts
                rq.corrigida      = 1
            else:
                # multipla_escolha / verdadeiro_falso: pontuação já calculada
                # automaticamente ao responder; usa o valor gravado
                pts = rq.pontos_obtidos or 0.0
            total_pontos += pts

        nota_final  = _calcular_nota(total_pontos, pontos_max)
        nota_minima = float(ex.nota_minima or 6.0)
        resp.nota_obtida = nota_final
        resp.aprovado    = 1 if nota_final >= nota_minima else 0
        db.session.commit()
        flash(f"Corre\u00e7\u00e3o salva. Nota: {nota_final}.", "sucesso")
        return redirect(f"/exercicios/{ex_id}/resultados")

    aluno = db.session.get(Aluno, resp.aluno_id)
    return render_template(
        "exercicio_corrigir.html",
        exercicio = ex,
        resp      = resp,
        respostas = respostas,
        aluno     = aluno,
    )


# ───────────────────────────────────────────────────────────────────────────
# CONCEDER TENTATIVAS EXTRAS
# ───────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/extra-tentativas", methods=["POST"])
@login_required
def extra_tentativas_exercicio(ex_id):
    db.get_or_404(Exercicio, ex_id)
    aluno_id = request.form.get("aluno_id", type=int)
    qtd      = request.form.get("qtd", 1, type=int)
    if not aluno_id:
        flash("Aluno n\u00e3o informado.", "erro")
        return redirect(f"/exercicios/{ex_id}/resultados")
    lib = ExercicioLiberado.query.filter_by(aluno_id=aluno_id, exercicio_id=ex_id).first()
    if lib:
        lib.extra_tentativas = (lib.extra_tentativas or 0) + max(1, qtd)
    else:
        lib = ExercicioLiberado(
            aluno_id         = aluno_id,
            exercicio_id     = ex_id,
            liberado         = 1,
            liberado_por     = session.get("usuario", ""),
            liberado_em      = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            extra_tentativas = max(1, qtd),
        )
        db.session.add(lib)
    db.session.commit()
    flash(f"{qtd} tentativa(s) extra(s) concedida(s).", "sucesso")
    return redirect(f"/exercicios/{ex_id}/resultados")


# ───────────────────────────────────────────────────────────────────────────
# ROTAS LEGADAS
# ───────────────────────────────────────────────────────────────────────────

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
        flash("T\u00edtulo \u00e9 obrigat\u00f3rio.", "erro")
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
        materia_id   = materia_id,
        titulo       = titulo,
        descricao    = descricao or None,
        arquivo      = arquivo_nome,
        ordem        = ordem,
        tentativas   = max(1, tentativas or 1),
        tempo_limite = tempo_limite or None,
        ativo        = 1,
        criado_em    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        criado_por   = session.get("usuario") or "",
    )
    db.session.add(ex)
    db.session.commit()
    flash(f"Exerc\u00edcio '{titulo}' criado!", "sucesso")
    return redirect(f"/exercicios/{ex.id}/questoes")


# ───────────────────────────────────────────────────────────────────────────
# SERVIR ARQUIVO
# ───────────────────────────────────────────────────────────────────────────

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
    resp = Response(dados, mimetype=mime or "application/octet-stream")
    resp.headers["Content-Disposition"] = "inline"
    return resp
