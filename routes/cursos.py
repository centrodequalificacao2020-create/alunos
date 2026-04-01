from flask import Blueprint, render_template, request, redirect, flash, jsonify
from db import db
from models import Curso, Matricula, Aluno
from security import login_required, admin_required
from sqlalchemy import distinct

cursos_bp = Blueprint("cursos", __name__)


def _calcular_total(valor_mensal, parcelas, valor_matricula):
    return round(
        float(valor_matricula or 0) + float(valor_mensal or 0) * int(parcelas or 1), 2
    )


@cursos_bp.route("/cursos")
@login_required
def listar_cursos():
    cursos = Curso.query.order_by(Curso.nome).all()
    # lista de tipos que realmente têm cursos cadastrados
    tipos = [
        r[0] for r in
        db.session.query(distinct(Curso.tipo))
        .filter(Curso.tipo != None, Curso.tipo != "")
        .order_by(Curso.tipo).all()
    ]
    return render_template("cursos.html", cursos=cursos, tipos=tipos)


@cursos_bp.route("/salvar_curso", methods=["POST"])
@login_required
def salvar_curso():
    f = request.form
    valor_mensal    = float(f.get("valor_mensal")    or 0)
    valor_matricula = float(f.get("valor_matricula") or 0)
    parcelas        = int(f.get("parcelas")          or 1)
    curso = Curso(
        nome            = f["nome"],
        valor_mensal    = valor_mensal,
        valor_matricula = valor_matricula,
        parcelas        = parcelas,
        valor_total     = _calcular_total(valor_mensal, parcelas, valor_matricula),
        tipo            = f.get("tipo", ""),
    )
    db.session.add(curso)
    db.session.commit()
    flash("Curso salvo com sucesso.", "sucesso")
    return redirect("/cursos")


@cursos_bp.route("/editar_curso/<int:id>", methods=["GET", "POST"])
@login_required
def editar_curso(id):
    curso = Curso.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        curso.nome            = f["nome"]
        curso.valor_mensal    = float(f.get("valor_mensal")    or 0)
        curso.valor_matricula = float(f.get("valor_matricula") or 0)
        curso.parcelas        = int(f.get("parcelas")          or 1)
        curso.tipo            = f.get("tipo", curso.tipo or "")
        curso.valor_total     = _calcular_total(
            curso.valor_mensal, curso.parcelas, curso.valor_matricula
        )
        db.session.commit()
        flash("Curso atualizado.", "sucesso")
        return redirect("/cursos")
    return render_template("editar_curso.html", curso=curso)


@cursos_bp.route("/excluir_curso/<int:id>", methods=["POST"])
@admin_required
def excluir_curso(id):
    curso = Curso.query.get_or_404(id)
    db.session.delete(curso)
    db.session.commit()
    flash("Curso excluído.", "sucesso")
    return redirect("/cursos")


# ── API JSON ─────────────────────────────────────────────────────

@cursos_bp.route("/cursos/<int:curso_id>/alunos")
@login_required
def alunos_por_curso(curso_id):
    """Retorna JSON com alunos matriculados em um curso específico."""
    rows = (
        db.session.query(Aluno, Matricula.status)
        .join(Matricula, Matricula.aluno_id == Aluno.id)
        .filter(Matricula.curso_id == curso_id)
        .order_by(Aluno.nome)
        .all()
    )
    return jsonify([
        {
            "id": a.id,
            "nome": a.nome,
            "status_aluno": a.status or "—",
            "status_matricula": m_status or "—",
        }
        for a, m_status in rows
    ])


@cursos_bp.route("/cursos/tipo/<path:tipo>/alunos")
@login_required
def alunos_por_tipo(tipo):
    """Retorna JSON agrupado por curso para um tipo de curso."""
    cursos_do_tipo = Curso.query.filter_by(tipo=tipo).order_by(Curso.nome).all()
    resultado = []
    for curso in cursos_do_tipo:
        rows = (
            db.session.query(Aluno, Matricula.status)
            .join(Matricula, Matricula.aluno_id == Aluno.id)
            .filter(Matricula.curso_id == curso.id)
            .order_by(Aluno.nome)
            .all()
        )
        resultado.append({
            "curso_id":   curso.id,
            "curso_nome": curso.nome,
            "total":      len(rows),
            "alunos": [
                {
                    "id": a.id,
                    "nome": a.nome,
                    "status_aluno": a.status or "—",
                    "status_matricula": m_status or "—",
                }
                for a, m_status in rows
            ],
        })
    return jsonify(resultado)
