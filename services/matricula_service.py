"""Serviço de matrículas."""
from db import db
from models import Matricula, Curso, Mensalidade, Aluno
from enums import StatusMatricula
from datetime import date


def get_matricula_ativa(aluno_id: int):
    """Retorna a Matricula ativa do aluno ou None."""
    return Matricula.query.filter(
        Matricula.aluno_id == aluno_id,
        db.func.upper(Matricula.status) == StatusMatricula.ATIVA.value
    ).first()


def get_cursos_matriculados_ativos(aluno_id: int):
    """Retorna cursos em que o aluno tem matrícula ATIVA."""
    return (
        Curso.query
        .join(Matricula, Matricula.curso_id == Curso.id)
        .filter(
            Matricula.aluno_id == aluno_id,
            db.func.upper(Matricula.status) == StatusMatricula.ATIVA.value
        )
        .order_by(Curso.nome)
        .all()
    )


def normalizar_status(matricula: Matricula):
    """Garante que o status da matrícula é sempre MAIÚSCULO e válido."""
    valor = (matricula.status or StatusMatricula.ATIVA.value).upper().strip()
    if valor not in StatusMatricula.valores():
        valor = StatusMatricula.ATIVA.value
    matricula.status = valor
    return matricula


def criar_matricula(form_data) -> int:
    """
    Cria matrícula + parcelas de mensalidade a partir dos dados do formulário.
    Retorna o id da Matricula criada.
    Lança ValueError se dados obrigatórios estiverem ausentes.
    """
    aluno_id  = form_data.get("aluno_id", type=int)
    curso_id  = form_data.get("curso_id", type=int)

    if not aluno_id:
        raise ValueError("Aluno não informado.")
    if not curso_id:
        raise ValueError("Curso não informado.")

    aluno = Aluno.query.get(aluno_id)
    if not aluno:
        raise ValueError("Aluno não encontrado.")

    curso = Curso.query.get(curso_id)
    if not curso:
        raise ValueError("Curso não encontrado.")

    valor_matricula   = float(form_data.get("valor_matricula")   or curso.valor_matricula or 0)
    valor_mensalidade = float(form_data.get("valor_mensalidade") or curso.valor_mensal    or 0)
    parcelas          = int(form_data.get("parcelas")            or curso.parcelas        or 1)
    tipo_curso        = form_data.get("tipo_curso")  or curso.tipo or ""
    data_matricula    = form_data.get("data_matricula") or date.today().isoformat()
    material_didatico = form_data.get("material_didatico") or ""
    valor_material    = float(form_data.get("valor_material") or 0)
    observacao        = form_data.get("observacao") or ""
    mes_inicio        = form_data.get("mes_inicio") or date.today().strftime("%Y-%m")

    # Cria o registro de matrícula
    matricula = Matricula(
        aluno_id            = aluno_id,
        curso_id            = curso_id,
        tipo_curso          = tipo_curso,
        data_matricula      = data_matricula,
        status              = StatusMatricula.ATIVA.value,
        valor_matricula     = valor_matricula,
        valor_mensalidade   = valor_mensalidade,
        quantidade_parcelas = parcelas,
        material_didatico   = material_didatico,
        valor_material      = valor_material,
        observacao          = observacao,
    )
    db.session.add(matricula)

    # Atualiza curso_id do aluno (compatibilidade legada)
    aluno.curso_id = curso_id

    # Gera parcela de matrícula (se houver valor)
    if valor_matricula > 0:
        db.session.add(Mensalidade(
            aluno_id    = aluno_id,
            valor       = valor_matricula,
            vencimento  = data_matricula,
            status      = "Pendente",
            tipo        = "matricula",
            parcela_ref = "Matrícula",
        ))

    # Gera parcelas de mensalidade
    try:
        ano, mes = int(mes_inicio[:4]), int(mes_inicio[5:7])
    except Exception:
        ano, mes = date.today().year, date.today().month

    for i in range(1, parcelas + 1):
        venc_mes = mes + i - 1
        venc_ano = ano + (venc_mes - 1) // 12
        venc_mes = ((venc_mes - 1) % 12) + 1
        vencimento = f"{venc_ano:04d}-{venc_mes:02d}-10"
        db.session.add(Mensalidade(
            aluno_id    = aluno_id,
            valor       = valor_mensalidade,
            vencimento  = vencimento,
            status      = "Pendente",
            tipo        = "mensalidade",
            parcela_ref = f"{i:02d}/{parcelas:02d}",
        ))

    # Gera parcela de material (se houver)
    if valor_material > 0:
        db.session.add(Mensalidade(
            aluno_id    = aluno_id,
            valor       = valor_material,
            vencimento  = data_matricula,
            status      = "Pendente",
            tipo        = "material",
            parcela_ref = "Material Didático",
        ))

    db.session.commit()
    return matricula.id
