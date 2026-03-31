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
    RespostaExercicio, ExercicioLiberado,
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


# ─────────────────────────────────────────────────────────────────────────
# LISTAGEM GERAL
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios")
@login_required
def exercicios_geral():
    cursos        = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()
    curso_id_sel  = request.args.get("curso_id", type=int)

    # FIX: mostra todos (ativo=0 e ativo=1), igual às provas
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


# ─────────────────────────────────────────────────────────────────────────
# CRIAR EXERCICIO  (GET renderiza form, POST salva)
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/novo", methods=["GET", "POST"])
@login_required
def novo_exercicio():
    cursos        = Curso.query.order_by(Curso.nome).all()
    materias, materias_json = _materias_json()

    if request.method == "POST":
        f            = request.form
        titulo       = f.get("titulo", "").strip()
        materia_id   = f.get("materia_id", type=int)
        curso_id     = f.get("curso_id", type=int)
        descricao    = f.get("descricao", "").strip() or None
        ordem        = f.get("ordem", 1, type=int)
        tentativas   = max(1, f.get("tentativas", 1, type=int))
        tempo_limite = f.get("tempo_limite", type=int) or None
        ativo        = 1 if f.get("ativo") else 0

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
            materia_id   = materia_id,
            titulo       = titulo,
            descricao    = descricao,
            arquivo      = arquivo_nome,
            ordem        = ordem,
            tentativas   = tentativas,
            tempo_limite = tempo_limite,
            ativo        = ativo,
            criado_em    = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            criado_por   = session.get("usuario") or "",
        )
        db.session.add(ex)
        db.session.commit()
        flash(f"Exercício \u201c{titulo}\u201d criado! Adicione as questões.", "sucesso")
        return redirect(f"/exercicios/{ex.id}/questoes")

    return render_template(
        "exercicios_geral.html",
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        view          = "novo",
    )


# ─────────────────────────────────────────────────────────────────────────
# EDITAR EXERCICIO  (GET renderiza form, POST salva)
# ─────────────────────────────────────────────────────────────────────────

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
        exercicio     = ex,
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        view          = "editar",
    )


# ─────────────────────────────────────────────────────────────────────────
# TOGGLE ATIVO / RASCUNHO
# ─────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────
# EXCLUIR EXERCICIO  (delete real, igual às provas)
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/excluir", methods=["POST"])
@login_required
def excluir_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    db.session.delete(ex)
    db.session.commit()
    flash("Exercício excluído.", "sucesso")
    return redirect("/exercicios")


# ─────────────────────────────────────────────────────────────────────────
# GERENCIAR QUESTOES DE UM EXERCICIO
# ─────────────────────────────────────────────────────────────────────────

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
                if alt_id:  # alternativa existente
                    alt = db.session.get(ExercicioAlternativa, int(alt_id))
                    if alt and alt.questao_id == q.id:
                        alt.texto   = texto
                        alt.correta = 1 if str(idx) in corretas else 0
                else:       # FIX: nova alternativa adicionada pelo modal
                    db.session.add(ExercicioAlternativa(
                        questao_id=q.id, texto=texto,
                        correta=1 if str(idx) in corretas else 0,
                        ordem=nova_ordem,
                    ))
                    nova_ordem += 1

            db.session.commit()
            flash("Questão atualizada.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

    return render_template("exercicio_questoes.html", exercicio=ex, view="questoes")


# ─────────────────────────────────────────────────────────────────────────
# RESULTADOS DO EXERCICIO
# ─────────────────────────────────────────────────────────────────────────

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
    return render_template("exercicio_questoes.html",
                           exercicio=ex, respostas=respostas, view="resultados")


# ─────────────────────────────────────────────────────────────────────────
# CONCEDER TENTATIVAS EXTRAS
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/extra-tentativas", methods=["POST"])
@login_required
def extra_tentativas_exercicio(ex_id):
    ex       = db.get_or_404(Exercicio, ex_id)
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


# ─────────────────────────────────────────────────────────────────────────
# ROTAS LEGADAS (mantidas para compatibilidade)
# ─────────────────────────────────────────────────────────────────────────

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
    flash(f"Exercício '{titulo}' criado!", "sucesso")
    return redirect(f"/exercicios/{ex.id}/questoes")


# ─────────────────────────────────────────────────────────────────────────
# SERVIR ARQUIVO
# ─────────────────────────────────────────────────────────────────────────

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
