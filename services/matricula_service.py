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

    REGRA: todas as Mensalidades geradas recebem curso_id, para que alunos
    com múltiplos cursos tenham parcelas corretamente separadas por curso.
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

    # ── Flag: lançamento avulso (não cria matrícula, não cria parcela de matrícula) ──
    apenas_mensalidade = form_data.get("apenas_mensalidade") == "1"

    # O formulário pode enviar valor_mensal OU valor_mensalidade
    # Em lançamento avulso, valor_matricula deve ser ZERO — nunca cria parcela de matrícula
    valor_matricula   = 0.0 if apenas_mensalidade else float(form_data.get("valor_matricula") or 0)
    valor_mensalidade = float(
        form_data.get("valor_mensalidade") or
        form_data.get("valor_mensal")      or
        curso.valor_mensal or 0
    )
    parcelas          = int(form_data.get("parcelas") or curso.parcelas or 1)
    tipo_curso        = form_data.get("tipo_curso")     or curso.tipo or ""
    data_matricula    = form_data.get("data_matricula") or date.today().isoformat()

    # Material didático — parcelável em qualquer modo (matrícula OU avulso)
    material_didatico = form_data.get("material_didatico") or ""
    valor_material    = float(form_data.get("valor_material") or 0)
    # parcelas_material: usa o campo do form; padrão 1 (integral)
    parcelas_material = int(form_data.get("parcelas_material") or 1)
    if parcelas_material < 1:
        parcelas_material = 1

    observacao        = form_data.get("observacao") or ""

    # mes_inicio a partir do campo data_primeira_mensalidade (formulário) ou mes_inicio
    mes_inicio_raw = (
        form_data.get("data_primeira_mensalidade") or
        form_data.get("mes_inicio") or
        date.today().strftime("%Y-%m")
    )
    # aceita tanto "YYYY-MM-DD" quanto "YYYY-MM"
    try:
        ano = int(mes_inicio_raw[:4])
        mes = int(mes_inicio_raw[5:7])
    except Exception:
        ano, mes = date.today().year, date.today().month

    # data de vencimento do material (primeira parcela)
    data_material_raw = form_data.get("data_material") or data_matricula
    try:
        ano_mat = int(data_material_raw[:4])
        mes_mat = int(data_material_raw[5:7])
    except Exception:
        ano_mat, mes_mat = ano, mes

    # ── Cria o registro de matrícula ─────────────────────────────────────────
    if not apenas_mensalidade:
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
        # Atualiza curso_id legado do aluno apenas na criação de matrícula
        aluno.curso_id = curso_id
    else:
        # Apenas lança parcelas — busca matrícula existente para o curso especificado
        # IMPORTANTE: filtra pelo curso_id do form para não pegar matrícula de outro curso
        matricula = Matricula.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id
        ).order_by(Matricula.id.desc()).first()
        if not matricula:
            raise ValueError(
                "Aluno não possui matrícula neste curso. "
                "Crie a matrícula primeiro na aba Matrículas."
            )

    # ── Parcela de matrícula (nunca em modo avulso) ───────────────────────────
    if not apenas_mensalidade and valor_matricula > 0:
        db.session.add(Mensalidade(
            aluno_id    = aluno_id,
            curso_id    = curso_id,
            valor       = valor_matricula,
            vencimento  = data_matricula,
            status      = "Pendente",
            tipo        = "matricula",
            parcela_ref = "Matrícula",
        ))

    # ── Parcelas de mensalidade ───────────────────────────────────────────────
    for i in range(1, parcelas + 1):
        venc_mes = mes + i - 1
        venc_ano = ano + (venc_mes - 1) // 12
        venc_mes = ((venc_mes - 1) % 12) + 1
        vencimento = f"{venc_ano:04d}-{venc_mes:02d}-10"
        db.session.add(Mensalidade(
            aluno_id    = aluno_id,
            curso_id    = curso_id,   # ← sempre vincula ao curso do formulário
            valor       = valor_mensalidade,
            vencimento  = vencimento,
            status      = "Pendente",
            tipo        = "mensalidade",
            parcela_ref = f"{i:02d}/{parcelas:02d}",
        ))

    # ── Parcelas de material (parcelável, funciona em ambos os modos) ────────
    if valor_material > 0:
        for i in range(1, parcelas_material + 1):
            venc_mes = mes_mat + i - 1
            venc_ano = ano_mat + (venc_mes - 1) // 12
            venc_mes = ((venc_mes - 1) % 12) + 1
            vencimento = f"{venc_ano:04d}-{venc_mes:02d}-10"
            ref = f"{i:02d}/{parcelas_material:02d}" if parcelas_material > 1 else "Material Didático"
            db.session.add(Mensalidade(
                aluno_id    = aluno_id,
                curso_id    = curso_id,
                valor       = round(valor_material / parcelas_material, 2),
                vencimento  = vencimento,
                status      = "Pendente",
                tipo        = "material",
                parcela_ref = ref,
            ))

    db.session.commit()
    return matricula.id
