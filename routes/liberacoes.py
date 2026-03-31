from flask import Blueprint, render_template, session, redirect, flash, request
from db import db
from models import (
    Aluno, Matricula, Materia, Prova, Exercicio,
    MateriaLiberada, ProvaLiberada, ExercicioLiberado, CursoMateria, Curso
)
from security import login_required
from datetime import datetime

liberacoes_bp = Blueprint("liberacoes", __name__)


# ─── PAINEL DE LIBERAÇÕES DE UM ALUNO ────────────────────────────────────

@liberacoes_bp.route("/liberacoes/aluno/<int:aluno_id>")
@login_required
def painel_liberacoes(aluno_id):
    aluno = db.get_or_404(Aluno, aluno_id)

    # Filtro opcional por curso_id via query string
    curso_id_filtro = request.args.get("curso_id", type=int)
    curso_filtrado  = db.session.get(Curso, curso_id_filtro) if curso_id_filtro else None

    matriculas_ativas = [
        m for m in aluno.matriculas if m.status.upper() == "ATIVA"
    ]
    if curso_id_filtro:
        matriculas_ativas = [m for m in matriculas_ativas if m.curso_id == curso_id_filtro]

    # IDs já liberados
    ids_mat_lib = {
        (ml.materia_id, ml.curso_id)
        for ml in MateriaLiberada.query.filter_by(aluno_id=aluno_id, liberado=1).all()
    }
    ids_prova_lib = {
        pl.prova_id for pl in ProvaLiberada.query.filter_by(
            aluno_id=aluno_id, liberado=1
        ).all()
    }
    ids_ex_lib = {
        el.exercicio_id for el in ExercicioLiberado.query.filter_by(
            aluno_id=aluno_id, liberado=1
        ).all()
    }

    cursos_data = []
    for m in matriculas_ativas:
        curso = m.curso
        if not curso:
            continue
        materias = (
            db.session.query(Materia)
            .join(CursoMateria, CursoMateria.materia_id == Materia.id)
            .filter(CursoMateria.curso_id == curso.id, Materia.ativa == 1)
            .order_by(Materia.nome).all()
        )
        provas = Prova.query.filter_by(curso_id=curso.id, ativa=1).all()

        exercicios_por_mat = {}
        for mat in materias:
            exs = Exercicio.query.filter_by(materia_id=mat.id, ativo=1)\
                                 .order_by(Exercicio.ordem).all()
            if exs:
                exercicios_por_mat[mat.id] = exs

        cursos_data.append({
            "curso":              curso,
            "materias":           materias,
            "provas":             provas,
            "exercicios_por_mat": exercicios_por_mat,
            "ids_mat_lib":        ids_mat_lib,
            "ids_prova_lib":      ids_prova_lib,
            "ids_ex_lib":         ids_ex_lib,
        })

    return render_template(
        "liberacoes.html",
        aluno          = aluno,
        cursos_data    = cursos_data,
        curso_filtrado = curso_filtrado,
    )


# ─── TOGGLE MATÉRIA (por curso) ─────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/materia", methods=["POST"])
@login_required
def toggle_materia():
    aluno_id   = int(request.form.get("aluno_id",   0))
    materia_id = int(request.form.get("materia_id", 0))
    curso_id   = int(request.form.get("curso_id",   0))
    acao       = request.form.get("acao", "liberar")

    if not aluno_id or not materia_id or not curso_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    operador     = session.get("usuario") or session.get("nome") or "sistema"

    registro = MateriaLiberada.query.filter_by(
        aluno_id=aluno_id, materia_id=materia_id, curso_id=curso_id
    ).first()

    if registro:
        registro.liberado     = liberado_val
        registro.liberado_por = operador
        registro.liberado_em  = agora
    else:
        db.session.add(MateriaLiberada(
            aluno_id     = aluno_id,
            materia_id   = materia_id,
            curso_id     = curso_id,
            liberado     = liberado_val,
            liberado_por = operador,
            liberado_em  = agora,
        ))

    db.session.commit()
    materia = db.session.get(Materia, materia_id)
    nome    = materia.nome if materia else f"ID {materia_id}"
    flash(f"Matéria '{nome}' {'liberada' if liberado_val else 'bloqueada'}.",
          "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")


# ─── TOGGLE PROVA ───────────────────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/prova", methods=["POST"])
@login_required
def toggle_prova():
    aluno_id = int(request.form.get("aluno_id", 0))
    prova_id = int(request.form.get("prova_id", 0))
    acao     = request.form.get("acao", "liberar")

    if not aluno_id or not prova_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    operador     = session.get("usuario") or session.get("nome") or "sistema"

    registro = ProvaLiberada.query.filter_by(
        aluno_id=aluno_id, prova_id=prova_id
    ).first()

    if registro:
        registro.liberado     = liberado_val
        registro.liberado_por = operador
        registro.liberado_em  = agora
    else:
        db.session.add(ProvaLiberada(
            aluno_id     = aluno_id,
            prova_id     = prova_id,
            liberado     = liberado_val,
            liberado_por = operador,
            liberado_em  = agora,
        ))

    db.session.commit()
    prova    = db.session.get(Prova, prova_id)
    nome     = prova.titulo if prova else f"ID {prova_id}"
    curso_id = prova.curso_id if prova else 0
    flash(f"Prova '{nome}' {'liberada' if liberado_val else 'bloqueada'}.",
          "sucesso" if liberado_val else "aviso")
    redirect_url = f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}" if curso_id else f"/liberacoes/aluno/{aluno_id}"
    return redirect(redirect_url)


# ─── TOGGLE EXERCÍCIO ─────────────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/exercicio", methods=["POST"])
@login_required
def toggle_exercicio():
    aluno_id     = int(request.form.get("aluno_id",     0))
    exercicio_id = int(request.form.get("exercicio_id", 0))
    acao         = request.form.get("acao", "liberar")

    if not aluno_id or not exercicio_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    operador     = session.get("usuario") or session.get("nome") or "sistema"

    registro = ExercicioLiberado.query.filter_by(
        aluno_id=aluno_id, exercicio_id=exercicio_id
    ).first()

    if registro:
        registro.liberado     = liberado_val
        registro.liberado_por = operador
        registro.liberado_em  = agora
    else:
        db.session.add(ExercicioLiberado(
            aluno_id     = aluno_id,
            exercicio_id = exercicio_id,
            liberado     = liberado_val,
            liberado_por = operador,
            liberado_em  = agora,
        ))

    db.session.commit()
    ex   = db.session.get(Exercicio, exercicio_id)
    nome = ex.titulo if ex else f"ID {exercicio_id}"
    curso_id = ex.materia.curso_materias[0].curso_id if (ex and ex.materia and ex.materia.curso_materias) else 0
    flash(f"Exercício '{nome}' {'liberado' if liberado_val else 'bloqueado'}.",
          "sucesso" if liberado_val else "aviso")
    redirect_url = f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}" if curso_id else f"/liberacoes/aluno/{aluno_id}"
    return redirect(redirect_url)
