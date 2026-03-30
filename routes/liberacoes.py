from flask import Blueprint, render_template, session, redirect, flash, request
from db import db
from models import (
    Aluno, Matricula, Materia, Prova,
    MateriaLiberada, ProvaLiberada
)
from security import login_required
from datetime import datetime

liberacoes_bp = Blueprint("liberacoes", __name__)

PERFIS_PERMITIDOS = {"ADMIN", "SECRETARIA", "INSTRUTOR"}


def _check_perfil():
    perfil = (session.get("perfil") or "").upper()
    if perfil not in PERFIS_PERMITIDOS:
        flash("Acesso negado.", "erro")
        return False
    return True


# ─── PAINEL DE LIBERAÇÕES DE UM ALUNO ─────────────────────────────────────

@liberacoes_bp.route("/liberacoes/aluno/<int:aluno_id>")
@login_required
def painel_liberacoes(aluno_id):
    if not _check_perfil():
        return redirect("/dashboard")

    aluno = db.get_or_404(Aluno, aluno_id)

    # Todos os cursos com matrícula ativa do aluno
    matriculas_ativas = [
        m for m in aluno.matriculas if m.status.upper() == "ATIVA"
    ]

    # IDs já liberados
    ids_mat_lib = {
        ml.materia_id for ml in MateriaLiberada.query.filter_by(
            aluno_id=aluno_id, liberado=1
        ).all()
    }
    ids_prova_lib = {
        pl.prova_id for pl in ProvaLiberada.query.filter_by(
            aluno_id=aluno_id, liberado=1
        ).all()
    }

    # Monta estrutura por curso
    cursos_data = []
    for m in matriculas_ativas:
        curso = m.curso
        if not curso:
            continue
        materias = Materia.query.filter_by(curso_id=curso.id, ativa=1).all()
        provas   = Prova.query.filter_by(curso_id=curso.id, ativa=1).all()
        cursos_data.append({
            "curso":           curso,
            "materias":        materias,
            "provas":          provas,
            "ids_mat_lib":     ids_mat_lib,
            "ids_prova_lib":   ids_prova_lib,
        })

    return render_template(
        "liberacoes.html",
        aluno        = aluno,
        cursos_data  = cursos_data,
    )


# ─── TOGGLE MATÉRIA ─────────────────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/materia", methods=["POST"])
@login_required
def toggle_materia():
    if not _check_perfil():
        return redirect("/dashboard")

    aluno_id   = int(request.form.get("aluno_id",   0))
    materia_id = int(request.form.get("materia_id", 0))
    acao       = request.form.get("acao", "liberar")  # "liberar" | "bloquear"

    if not aluno_id or not materia_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    operador     = session.get("usuario") or session.get("nome") or "sistema"

    registro = MateriaLiberada.query.filter_by(
        aluno_id=aluno_id, materia_id=materia_id
    ).first()

    if registro:
        registro.liberado     = liberado_val
        registro.liberado_por = operador
        registro.liberado_em  = agora
    else:
        db.session.add(MateriaLiberada(
            aluno_id     = aluno_id,
            materia_id   = materia_id,
            liberado     = liberado_val,
            liberado_por = operador,
            liberado_em  = agora,
        ))

    db.session.commit()

    materia = db.session.get(Materia, materia_id)
    nome    = materia.nome if materia else f"ID {materia_id}"
    msg     = f"Matéria ‘{nome}’ {'liberada' if liberado_val else 'bloqueada'} com sucesso."
    flash(msg, "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}")


# ─── TOGGLE PROVA ───────────────────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/prova", methods=["POST"])
@login_required
def toggle_prova():
    if not _check_perfil():
        return redirect("/dashboard")

    aluno_id = int(request.form.get("aluno_id", 0))
    prova_id = int(request.form.get("prova_id", 0))
    acao     = request.form.get("acao", "liberar")  # "liberar" | "bloquear"

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

    prova = db.session.get(Prova, prova_id)
    nome  = prova.titulo if prova else f"ID {prova_id}"
    msg   = f"Prova ‘{nome}’ {'liberada' if liberado_val else 'bloqueada'} com sucesso."
    flash(msg, "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}")
