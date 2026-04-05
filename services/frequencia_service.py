"""Serviço de frequência."""
from datetime import date
from db import db
from models import Frequencia


def registrar_frequencia(aluno_id: int, curso_id: int,
                         data_aula: str, status: str):
    """Cria ou atualiza registro de frequência. Retorna o objeto.

    BUG-13: rejeita datas futuras com ValueError.
    """
    try:
        data_obj = date.fromisoformat(str(data_aula)[:10])
    except (ValueError, TypeError):
        raise ValueError(
            f"Data inválida: '{data_aula}'. Use o formato AAAA-MM-DD."
        )

    if data_obj > date.today():
        raise ValueError(
            f"Não é possível registrar frequência para uma data futura "
            f"({data_obj.strftime('%d/%m/%Y')}). "
            f"Verifique a data informada."
        )

    freq = Frequencia.query.filter_by(
        aluno_id=aluno_id, curso_id=curso_id, data=data_aula
    ).first()
    if freq:
        freq.status = status
    else:
        freq = Frequencia(
            aluno_id=aluno_id, curso_id=curso_id,
            data=data_aula, status=status
        )
        db.session.add(freq)
    db.session.commit()
    return freq


def get_historico(aluno_id: int, curso_id: int = None):
    """Retorna frequências do aluno, opcionalmente filtradas por curso."""
    q = Frequencia.query.filter_by(aluno_id=aluno_id)
    if curso_id:
        q = q.filter_by(curso_id=curso_id)
    return q.order_by(Frequencia.data.desc()).all()


def calcular_percentual(aluno_id: int, curso_id: int) -> float:
    """Calcula % de presença. Retorna 0.0 se sem registros."""
    registros = Frequencia.query.filter_by(
        aluno_id=aluno_id, curso_id=curso_id
    ).all()
    if not registros:
        return 0.0
    presentes = sum(1 for f in registros if f.status == "Presente")
    return round((presentes / len(registros)) * 100, 1)
