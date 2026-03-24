"""Serviço de notas — lógica isolada das rotas."""
from db import db
from models import Materia, CursoMateria, Nota, Matricula
from enums import StatusMatricula


def get_materias_do_curso(curso_id: int):
    """Retorna matérias ativas de um curso via CursoMateria (fonte correta)."""
    return (
        Materia.query
        .join(CursoMateria, CursoMateria.materia_id == Materia.id)
        .filter(CursoMateria.curso_id == curso_id, Materia.ativa == 1)
        .order_by(Materia.nome)
        .all()
    )


def get_notas_map(aluno_id: int, curso_id: int) -> dict:
    """Retorna {materia_id: Nota} para o aluno/curso."""
    return {
        n.materia_id: n
        for n in Nota.query.filter_by(aluno_id=aluno_id, curso_id=curso_id).all()
    }


def get_boletim(aluno_id: int, curso_id: int) -> list:
    """Retorna lista de dicts {materia, nota, resultado} para exibição."""
    mats = get_materias_do_curso(curso_id)
    notas = get_notas_map(aluno_id, curso_id)
    return [
        {
            "materia":   m.nome,
            "nota":      notas[m.id].nota      if m.id in notas else None,
            "resultado": notas[m.id].resultado if m.id in notas else None,
        }
        for m in mats
    ]


def salvar_notas(aluno_id: int, curso_id: int, form_data: dict):
    """Persiste notas vindas do form. form_data = request.form."""
    mats = get_materias_do_curso(curso_id)
    for m in mats:
        nota_val  = form_data.get(f"nota_{m.id}") or None
        resultado = form_data.get(f"resultado_{m.id}") or None
        nota_obj  = Nota.query.filter_by(
            aluno_id=aluno_id, materia_id=m.id, curso_id=curso_id
        ).first()
        if nota_obj:
            nota_obj.nota      = nota_val
            nota_obj.resultado = resultado
        else:
            db.session.add(
                Nota(aluno_id=aluno_id, materia_id=m.id,
                     curso_id=curso_id, nota=nota_val, resultado=resultado)
            )
    db.session.commit()


def get_curso_ativo_do_aluno(aluno_id: int):
    """Retorna curso_id ativo via Matricula (fonte da verdade)."""
    mat = Matricula.query.filter(
        Matricula.aluno_id == aluno_id,
        db.func.upper(Matricula.status) == StatusMatricula.ATIVA.value
    ).first()
    return mat.curso_id if mat else None
