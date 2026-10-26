"""Serviço de frequência.

Os registros de frequência são gravados com os códigos curtos ``P`` / ``F``
(enviados pelo formulário ``templates/frequencia.html``), mas o model
``Frequencia`` declara default ``"Presente"`` e ``enums.StatusFrequencia``
define os rótulos por extenso. As funções deste módulo aceitam **as duas
grafias**, para que dados antigos e novos sejam lidos corretamente.

Importe ``is_presente`` / ``normalizar_status`` em vez de comparar strings
de status diretamente.
"""
from datetime import date

from db import db
from models import Frequencia

# Grafias aceitas para cada situação.
STATUS_PRESENTE    = frozenset({"p", "presente", "presença", "presenca"})
STATUS_FALTA       = frozenset({"f", "falta", "ausente"})
STATUS_JUSTIFICADA = frozenset({"j", "justificada", "justificado"})

# Justificativa NÃO entra no percentual de presença — preserva a regra original
# (calcular_percentual contava apenas presença efetiva). Se a instituição passar
# a abonar faltas justificadas, basta adicionar STATUS_JUSTIFICADA aqui.
STATUS_CONTAM_COMO_PRESENCA = STATUS_PRESENTE


def normalizar_status(status) -> str:
    """Devolve ``P``, ``F``, ``J`` ou string vazia se não reconhecido."""
    valor = str(status or "").strip().lower()
    if valor in STATUS_PRESENTE:
        return "P"
    if valor in STATUS_FALTA:
        return "F"
    if valor in STATUS_JUSTIFICADA:
        return "J"
    return ""


def is_presente(status) -> bool:
    """True para ``P`` e ``Presente`` — nunca lance comparação direta."""
    return normalizar_status(status) == "P"


def percentual_presenca(statuses) -> float:
    """Percentual de presença a partir de uma sequência de status.

    Função pura: não consulta o banco. Retorna 0.0 quando não há registros.
    """
    statuses = list(statuses)
    if not statuses:
        return 0.0
    presentes = sum(1 for s in statuses if is_presente(s))
    return round(presentes / len(statuses) * 100, 1)


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
    """Calcula % de presença. Retorna 0.0 se sem registros.

    Aceita tanto ``P`` (grafia gravada pelo formulário) quanto ``Presente``
    (default do model). Ver DT-02 no SYSTEM_CONTEXT.
    """
    registros = Frequencia.query.filter_by(
        aluno_id=aluno_id, curso_id=curso_id
    ).all()
    return percentual_presenca(f.status for f in registros)
