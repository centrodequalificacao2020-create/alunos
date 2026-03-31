from flask import Blueprint, render_template, session, redirect, flash, request
from db import db
from models import (
    Aluno, Matricula, Materia, Prova, Exercicio,
    MateriaLiberada, ProvaLiberada, ExercicioLiberado, CursoMateria, Curso
)
from security import login_required
from datetime import datetime

liberacoes_bp = Blueprint("liberacoes", __name__)


def _agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _operador():
    return session.get("usuario_nome") or session.get("usuario") or session.get("nome") or "sistema"


# ─── PAINEL ───────────────────────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/aluno/<int:aluno_id>")
@login_required
def painel_liberacoes(aluno_id):
    aluno = db.get_or_404(Aluno, aluno_id)

    curso_id_filtro = request.args.get("curso_id", type=int)
    curso_filtrado  = db.session.get(Curso, curso_id_filtro) if curso_id_filtro else None

    matriculas_ativas = [m for m in aluno.matriculas if m.status.upper() == "ATIVA"]
    if curso_id_filtro:
        matriculas_ativas = [m for m in matriculas_ativas if m.curso_id == curso_id_filtro]

    ids_mat_lib = {
        (ml.materia_id, ml.curso_id)
        for ml in MateriaLiberada.query.filter_by(aluno_id=aluno_id, liberado=1).all()
    }
    ids_prova_lib = {
        pl.prova_id for pl in ProvaLiberada.query.filter_by(aluno_id=aluno_id, liberado=1).all()
    }
    ids_ex_lib = {
        el.exercicio_id for el in ExercicioLiberado.query.filter_by(aluno_id=aluno_id, liberado=1).all()
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
            exs = Exercicio.query.filter_by(materia_id=mat.id, ativo=1).order_by(Exercicio.ordem).all()
            if exs:
                exercicios_por_mat[mat.id] = exs

        # Atividades
        atividades = []
        try:
            from models import Atividade, AtividadeLiberada
            atividades = Atividade.query.filter_by(curso_id=curso.id, ativa=1).all()
        except Exception:
            pass

        ids_atv_lib = set()
        try:
            from models import AtividadeLiberada
            ids_atv_lib = {
                al.atividade_id
                for al in AtividadeLiberada.query.filter_by(aluno_id=aluno_id, liberado=1).all()
            }
        except Exception:
            pass

        # Curso tem acesso se pelo menos 1 matéria está liberada
        tem_mat_lib = any((mat.id, curso.id) in ids_mat_lib for mat in materias)

        cursos_data.append({
            "curso":              curso,
            "materias":           materias,
            "provas":             provas,
            "exercicios_por_mat": exercicios_por_mat,
            "atividades":         atividades,
            "ids_mat_lib":        ids_mat_lib,
            "ids_prova_lib":      ids_prova_lib,
            "ids_ex_lib":         ids_ex_lib,
            "ids_atv_lib":        ids_atv_lib,
            "curso_liberado":     tem_mat_lib,
        })

    return render_template(
        "liberacoes.html",
        aluno          = aluno,
        cursos_data    = cursos_data,
        curso_filtrado = curso_filtrado,
    )


# ─── BLOQUEAR CURSO INTEIRO ───────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/curso/bloquear", methods=["POST"])
@login_required
def bloquear_curso():
    aluno_id = int(request.form.get("aluno_id", 0))
    curso_id = int(request.form.get("curso_id", 0))
    if not aluno_id or not curso_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    agora = _agora()
    op    = _operador()

    # Bloqueia todas as matérias do curso
    for ml in MateriaLiberada.query.filter_by(aluno_id=aluno_id, curso_id=curso_id).all():
        ml.liberado = 0; ml.liberado_por = op; ml.liberado_em = agora
    # Bloqueia todas as provas do curso
    provas_ids = [p.id for p in Prova.query.filter_by(curso_id=curso_id).all()]
    for pl in ProvaLiberada.query.filter(ProvaLiberada.aluno_id == aluno_id, ProvaLiberada.prova_id.in_(provas_ids)).all():
        pl.liberado = 0; pl.liberado_por = op; pl.liberado_em = agora
    # Bloqueia todos os exercícios do curso
    materias_ids = [cm.materia_id for cm in CursoMateria.query.filter_by(curso_id=curso_id).all()]
    ex_ids = [e.id for e in Exercicio.query.filter(Exercicio.materia_id.in_(materias_ids)).all()]
    for el in ExercicioLiberado.query.filter(ExercicioLiberado.aluno_id == aluno_id, ExercicioLiberado.exercicio_id.in_(ex_ids)).all():
        el.liberado = 0; el.liberado_por = op; el.liberado_em = agora
    # Bloqueia atividades do curso
    try:
        from models import Atividade, AtividadeLiberada
        atv_ids = [a.id for a in Atividade.query.filter_by(curso_id=curso_id).all()]
        for al in AtividadeLiberada.query.filter(AtividadeLiberada.aluno_id == aluno_id, AtividadeLiberada.atividade_id.in_(atv_ids)).all():
            al.liberado = 0; al.liberado_por = op; al.liberado_em = agora
    except Exception:
        pass

    db.session.commit()
    flash("Acesso ao curso bloqueado com sucesso.", "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")


# ─── TOGGLE MATÉRIA ───────────────────────────────────────────────────────────

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
    agora = _agora()
    op    = _operador()

    registro = MateriaLiberada.query.filter_by(aluno_id=aluno_id, materia_id=materia_id, curso_id=curso_id).first()
    if registro:
        registro.liberado = liberado_val; registro.liberado_por = op; registro.liberado_em = agora
    else:
        db.session.add(MateriaLiberada(aluno_id=aluno_id, materia_id=materia_id, curso_id=curso_id,
                                       liberado=liberado_val, liberado_por=op, liberado_em=agora))
    db.session.commit()
    materia = db.session.get(Materia, materia_id)
    nome = materia.nome if materia else f"ID {materia_id}"
    flash(f"Matéria '{nome}' {'liberada' if liberado_val else 'bloqueada'}.", "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")


# ─── TOGGLE TODAS AS MATÉRIAS DO CURSO ────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/materia/todas", methods=["POST"])
@login_required
def toggle_todas_materias():
    aluno_id = int(request.form.get("aluno_id", 0))
    curso_id = int(request.form.get("curso_id", 0))
    acao     = request.form.get("acao", "liberar")

    if not aluno_id or not curso_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora = _agora()
    op    = _operador()

    materias = (
        db.session.query(Materia)
        .join(CursoMateria, CursoMateria.materia_id == Materia.id)
        .filter(CursoMateria.curso_id == curso_id, Materia.ativa == 1).all()
    )
    for mat in materias:
        reg = MateriaLiberada.query.filter_by(aluno_id=aluno_id, materia_id=mat.id, curso_id=curso_id).first()
        if reg:
            reg.liberado = liberado_val; reg.liberado_por = op; reg.liberado_em = agora
        else:
            db.session.add(MateriaLiberada(aluno_id=aluno_id, materia_id=mat.id, curso_id=curso_id,
                                           liberado=liberado_val, liberado_por=op, liberado_em=agora))
    db.session.commit()
    flash(f"Todas as matérias {'liberadas' if liberado_val else 'bloqueadas'}.", "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")


# ─── TOGGLE PROVA ─────────────────────────────────────────────────────────────

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
    agora = _agora()
    op    = _operador()

    registro = ProvaLiberada.query.filter_by(aluno_id=aluno_id, prova_id=prova_id).first()
    if registro:
        registro.liberado = liberado_val; registro.liberado_por = op; registro.liberado_em = agora
    else:
        db.session.add(ProvaLiberada(aluno_id=aluno_id, prova_id=prova_id,
                                     liberado=liberado_val, liberado_por=op, liberado_em=agora))
    db.session.commit()
    prova = db.session.get(Prova, prova_id)
    nome     = prova.titulo if prova else f"ID {prova_id}"
    curso_id = prova.curso_id if prova else 0
    flash(f"Prova '{nome}' {'liberada' if liberado_val else 'bloqueada'}.", "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}" if curso_id else f"/liberacoes/aluno/{aluno_id}")


# ─── TOGGLE TODAS AS PROVAS DO CURSO ──────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/prova/todas", methods=["POST"])
@login_required
def toggle_todas_provas():
    aluno_id = int(request.form.get("aluno_id", 0))
    curso_id = int(request.form.get("curso_id", 0))
    acao     = request.form.get("acao", "liberar")

    if not aluno_id or not curso_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora = _agora()
    op    = _operador()

    provas = Prova.query.filter_by(curso_id=curso_id, ativa=1).all()
    for pv in provas:
        reg = ProvaLiberada.query.filter_by(aluno_id=aluno_id, prova_id=pv.id).first()
        if reg:
            reg.liberado = liberado_val; reg.liberado_por = op; reg.liberado_em = agora
        else:
            db.session.add(ProvaLiberada(aluno_id=aluno_id, prova_id=pv.id,
                                         liberado=liberado_val, liberado_por=op, liberado_em=agora))
    db.session.commit()
    flash(f"Todas as provas {'liberadas' if liberado_val else 'bloqueadas'}.", "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")


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
    agora = _agora()
    op    = _operador()

    registro = ExercicioLiberado.query.filter_by(aluno_id=aluno_id, exercicio_id=exercicio_id).first()
    if registro:
        registro.liberado = liberado_val; registro.liberado_por = op; registro.liberado_em = agora
    else:
        db.session.add(ExercicioLiberado(aluno_id=aluno_id, exercicio_id=exercicio_id,
                                         liberado=liberado_val, liberado_por=op, liberado_em=agora))
    db.session.commit()
    ex = db.session.get(Exercicio, exercicio_id)
    nome = ex.titulo if ex else f"ID {exercicio_id}"
    curso_id = 0
    if ex and ex.materia and ex.materia.curso_materias:
        curso_id = ex.materia.curso_materias[0].curso_id
    flash(f"Exercício '{nome}' {'liberado' if liberado_val else 'bloqueado'}.", "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}" if curso_id else f"/liberacoes/aluno/{aluno_id}")


# ─── TOGGLE TODOS OS EXERCÍCIOS DO CURSO ──────────────────────────────────────

@liberacoes_bp.route("/liberacoes/exercicio/todos", methods=["POST"])
@login_required
def toggle_todos_exercicios():
    aluno_id = int(request.form.get("aluno_id", 0))
    curso_id = int(request.form.get("curso_id", 0))
    acao     = request.form.get("acao", "liberar")

    if not aluno_id or not curso_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora = _agora()
    op    = _operador()

    materias_ids = [cm.materia_id for cm in CursoMateria.query.filter_by(curso_id=curso_id).all()]
    exercicios = Exercicio.query.filter(Exercicio.materia_id.in_(materias_ids), Exercicio.ativo == 1).all()
    for ex in exercicios:
        reg = ExercicioLiberado.query.filter_by(aluno_id=aluno_id, exercicio_id=ex.id).first()
        if reg:
            reg.liberado = liberado_val; reg.liberado_por = op; reg.liberado_em = agora
        else:
            db.session.add(ExercicioLiberado(aluno_id=aluno_id, exercicio_id=ex.id,
                                             liberado=liberado_val, liberado_por=op, liberado_em=agora))
    db.session.commit()
    flash(f"Todos os exercícios {'liberados' if liberado_val else 'bloqueados'}.", "sucesso" if liberado_val else "aviso")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")


# ─── TOGGLE ATIVIDADE ─────────────────────────────────────────────────────────

@liberacoes_bp.route("/liberacoes/atividade", methods=["POST"])
@login_required
def toggle_atividade():
    aluno_id     = int(request.form.get("aluno_id",     0))
    atividade_id = int(request.form.get("atividade_id", 0))
    acao         = request.form.get("acao", "liberar")

    if not aluno_id or not atividade_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora = _agora()
    op    = _operador()
    curso_id = 0

    try:
        from models import Atividade, AtividadeLiberada
        atv = db.session.get(Atividade, atividade_id)
        curso_id = atv.curso_id if atv else 0
        reg = AtividadeLiberada.query.filter_by(aluno_id=aluno_id, atividade_id=atividade_id).first()
        if reg:
            reg.liberado = liberado_val; reg.liberado_por = op; reg.liberado_em = agora
        else:
            db.session.add(AtividadeLiberada(aluno_id=aluno_id, atividade_id=atividade_id,
                                             liberado=liberado_val, liberado_por=op, liberado_em=agora))
        db.session.commit()
        nome = atv.titulo if atv else f"ID {atividade_id}"
        flash(f"Atividade '{nome}' {'liberada' if liberado_val else 'bloqueada'}.", "sucesso" if liberado_val else "aviso")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao alterar atividade: {e}", "erro")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}" if curso_id else f"/liberacoes/aluno/{aluno_id}")


# ─── TOGGLE TODAS AS ATIVIDADES DO CURSO ──────────────────────────────────────

@liberacoes_bp.route("/liberacoes/atividade/todas", methods=["POST"])
@login_required
def toggle_todas_atividades():
    aluno_id = int(request.form.get("aluno_id", 0))
    curso_id = int(request.form.get("curso_id", 0))
    acao     = request.form.get("acao", "liberar")

    if not aluno_id or not curso_id:
        flash("Dados inválidos.", "erro")
        return redirect(request.referrer or "/dashboard")

    liberado_val = 1 if acao == "liberar" else 0
    agora = _agora()
    op    = _operador()

    try:
        from models import Atividade, AtividadeLiberada
        atividades = Atividade.query.filter_by(curso_id=curso_id, ativa=1).all()
        for atv in atividades:
            reg = AtividadeLiberada.query.filter_by(aluno_id=aluno_id, atividade_id=atv.id).first()
            if reg:
                reg.liberado = liberado_val; reg.liberado_por = op; reg.liberado_em = agora
            else:
                db.session.add(AtividadeLiberada(aluno_id=aluno_id, atividade_id=atv.id,
                                                 liberado=liberado_val, liberado_por=op, liberado_em=agora))
        db.session.commit()
        flash(f"Todas as atividades {'liberadas' if liberado_val else 'bloqueadas'}.", "sucesso" if liberado_val else "aviso")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro: {e}", "erro")
    return redirect(f"/liberacoes/aluno/{aluno_id}?curso_id={curso_id}")
