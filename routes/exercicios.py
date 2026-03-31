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


# ─────────────────────────────────────────────────────────────────────────
# LISTAGEM GERAL
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios", methods=["GET", "POST"])
@login_required
def exercicios_geral():
    cursos   = Curso.query.order_by(Curso.nome).all()
    materias = Materia.query.order_by(Materia.nome).all()
    curso_id_sel = request.args.get("curso_id", type=int)

    query = Exercicio.query.filter_by(ativo=1)
    if curso_id_sel:
        mids = [m.id for m in materias if any(
            cm.curso_id == curso_id_sel
            for cm in CursoMateria.query.filter_by(materia_id=m.id).all()
        )]
        query = query.filter(Exercicio.materia_id.in_(mids)) if mids else query.filter(False)
    exercicios = query.order_by(Exercicio.materia_id, Exercicio.ordem).all()

    if request.method == "POST":
        titulo       = request.form.get("titulo", "").strip()
        descricao    = request.form.get("descricao", "").strip()
        materia_id   = request.form.get("materia_id", type=int)
        ordem        = request.form.get("ordem", 1, type=int)
        tentativas   = request.form.get("tentativas", 1, type=int)
        tempo_limite = request.form.get("tempo_limite", type=int)

        if not titulo or not materia_id:
            flash("Título e matéria são obrigatórios.", "erro")
            return redirect("/exercicios")

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
        flash(f"Exercício '{titulo}' criado! Adicione as questões.", "sucesso")
        return redirect(f"/exercicios/{ex.id}/questoes")

    materias_json = [{"id": m.id, "nome": m.nome, "curso_id": m.curso_id} for m in materias]
    return render_template(
        "exercicios_geral.html",
        cursos        = cursos,
        materias      = materias,
        materias_json = materias_json,
        exercicios    = exercicios,
        curso_id_sel  = curso_id_sel,
    )


# ─────────────────────────────────────────────────────────────────────────
# GERENCIAR QUESTOES DE UM EXERCICIO (admin/instrutor)
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
            for idx, (alt_id, texto) in enumerate(zip(alt_ids, textos)):
                texto = texto.strip()
                if not texto:
                    continue
                alt = db.session.get(ExercicioAlternativa, int(alt_id))
                if alt and alt.questao_id == q.id:
                    alt.texto   = texto
                    alt.correta = 1 if str(idx) in corretas else 0
            db.session.commit()
            flash("Questão atualizada.", "sucesso")
            return redirect(f"/exercicios/{ex_id}/questoes")

    return render_template("exercicio_questoes.html", exercicio=ex, view="questoes")


# ─────────────────────────────────────────────────────────────────────────
# RESULTADOS DO EXERCICIO (admin/instrutor)
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/resultados")
@login_required
def resultados_exercicio(ex_id):
    ex        = db.get_or_404(Exercicio, ex_id)
    respostas = (
        RespostaExercicio.query
        .filter_by(exercicio_id=ex_id)
        .order_by(RespostaExercicio.finalizado_em.desc())
        .all()
    )
    return render_template("exercicio_questoes.html",
                           exercicio=ex, respostas=respostas, view="resultados")


# ─────────────────────────────────────────────────────────────────────────
# CONCEDER TENTATIVAS EXTRAS (admin/instrutor)
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
            aluno_id=aluno_id, exercicio_id=ex_id,
            liberado=1,
            liberado_por=session.get("usuario", ""),
            liberado_em=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            extra_tentativas=max(1, qtd),
        )
        db.session.add(lib)
    db.session.commit()
    flash(f"{qtd} tentativa(s) extra(s) concedida(s) para o aluno.", "sucesso")
    return redirect(f"/exercicios/{ex_id}/resultados")


# ─────────────────────────────────────────────────────────────────────────
# EDITAR / EXCLUIR exercicio
# ─────────────────────────────────────────────────────────────────────────

@exercicios_bp.route("/exercicios/<int:ex_id>/editar", methods=["POST"])
@login_required
def editar_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    ex.titulo       = request.form.get("titulo", ex.titulo).strip()
    ex.descricao    = request.form.get("descricao", ex.descricao or "").strip() or None
    ex.ordem        = request.form.get("ordem", ex.ordem, type=int)
    ex.tentativas   = max(1, request.form.get("tentativas", ex.tentativas or 1, type=int))
    ex.tempo_limite = request.form.get("tempo_limite", type=int) or None

    f = request.files.get("arquivo")
    if f and f.filename and _allowed(f.filename):
        pasta = _upload_folder()
        os.makedirs(pasta, exist_ok=True)
        nome_seguro = secure_filename(f"{ex.materia_id}_{int(datetime.now().timestamp())}_{f.filename}")
        f.save(os.path.join(pasta, nome_seguro))
        ex.arquivo = f"exercicios/{nome_seguro}"

    db.session.commit()
    flash("Exercício atualizado!", "sucesso")
    redirect_to = request.form.get("redirect_to", f"/exercicios/{ex_id}/questoes")
    return redirect(redirect_to)


@exercicios_bp.route("/exercicios/<int:ex_id>/excluir", methods=["POST"])
@login_required
def excluir_exercicio(ex_id):
    ex = db.get_or_404(Exercicio, ex_id)
    ex.ativo = 0
    db.session.commit()
    flash("Exercício removido.", "sucesso")
    redirect_to = request.form.get("redirect_to", "/exercicios")
    return redirect(redirect_to)


# ─────────────────────────────────────────────────────────────────────────
# ROTAS ANTIGAS de lista por materia (mantidas para compatibilidade)
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
        nome_seguro = secure_filename(f"{materia_id}_{int(datetime.now().timestamp())}_{f.filename}")
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
# SERVIR ARQUIVO (somente admin/instrutor)
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
