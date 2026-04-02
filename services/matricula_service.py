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


def _get_float(form_data, *campos, fallback=0.0):
    """
    Lê o primeiro campo presente e não-vazio do form.
    Retorna float ou `fallback`.
    NUNCA usa valor do curso como padrão silencioso — o chamador
    decide se quer o fallback do curso.
    """
    for campo in campos:
        raw = form_data.get(campo, "").strip() if hasattr(form_data, 'get') else ""
        if raw != "":          # campo foi enviado (mesmo que seja "0")
            try:
                return float(raw)
            except (ValueError, TypeError):
                pass
    return fallback


def _get_int(form_data, *campos, fallback=0):
    """
    Igual a _get_float, mas retorna int.
    """
    for campo in campos:
        raw = form_data.get(campo, "").strip() if hasattr(form_data, 'get') else ""
        if raw != "":
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
    return fallback


def criar_matricula(form_data) -> int:
    """
    Cria matrícula + parcelas de mensalidade a partir dos dados do formulário.
    Retorna o id da Matricula criada.
    Lança ValueError se dados obrigatórios estiverem ausentes.

    REGRA: todas as Mensalidades geradas recebem curso_id, para que alunos
    com múltiplos cursos tenham parcelas corretamente separadas por curso.
    """
    aluno_id = _get_int(form_data, "aluno_id")
    curso_id = _get_int(form_data, "curso_id")

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

    # ── Valor da matrícula ────────────────────────────────────────────────────
    valor_matricula = 0.0 if apenas_mensalidade else _get_float(form_data, "valor_matricula")

    # ── Valor da mensalidade ──────────────────────────────────────────────────
    # Usa o valor digitado pelo usuário; só cai no padrão do curso se o campo
    # NÃO foi enviado (ausente ou None). Se o usuário digitou 0, respeita o 0.
    raw_mens = form_data.get("valor_mensalidade") or form_data.get("valor_mensal")
    if raw_mens is not None and str(raw_mens).strip() != "":
        try:
            valor_mensalidade = float(str(raw_mens).strip())
        except (ValueError, TypeError):
            valor_mensalidade = float(curso.valor_mensal or 0)
    else:
        # Campo realmente ausente: usa padrão do curso
        valor_mensalidade = float(curso.valor_mensal or 0)

    # ── Quantidade de parcelas de mensalidade ────────────────────────────────
    # Mesma lógica: 0 digitado pelo usuário = NÃO lançar mensalidades
    raw_parc = form_data.get("parcelas")
    if raw_parc is not None and str(raw_parc).strip() != "":
        try:
            parcelas = int(str(raw_parc).strip())
        except (ValueError, TypeError):
            parcelas = int(curso.parcelas or 0)
    else:
        # Campo ausente: usa padrão do curso
        parcelas = int(curso.parcelas or 0)

    # Garante que parcelas nunca seja negativo
    if parcelas < 0:
        parcelas = 0

    tipo_curso     = form_data.get("tipo_curso")     or curso.tipo or ""
    data_matricula = form_data.get("data_matricula") or date.today().isoformat()
    observacao     = form_data.get("observacao") or ""

    # ── Material didático ─────────────────────────────────────────────────────
    material_didatico = form_data.get("material_didatico") or ""
    valor_material    = _get_float(form_data, "valor_material")
    parcelas_material = _get_int(form_data, "parcelas_material", fallback=1)
    if parcelas_material < 1:
        parcelas_material = 1

    # ── Datas de vencimento ───────────────────────────────────────────────────
    mes_inicio_raw = (
        form_data.get("data_primeira_mensalidade") or
        form_data.get("mes_inicio") or
        date.today().strftime("%Y-%m")
    )
    try:
        ano = int(mes_inicio_raw[:4])
        mes = int(mes_inicio_raw[5:7])
    except Exception:
        ano, mes = date.today().year, date.today().month

    data_material_raw = form_data.get("data_material") or data_matricula
    try:
        ano_mat = int(data_material_raw[:4])
        mes_mat = int(data_material_raw[5:7])
    except Exception:
        ano_mat, mes_mat = ano, mes

    # ── Validações de negócio ─────────────────────────────────────────────────
    # Bloqueia envio se mensalidade > 0 mas parcelas == 0 (ou vice-versa)
    if valor_mensalidade > 0 and parcelas == 0:
        raise ValueError(
            "Informe a quantidade de parcelas de mensalidade (campo está em 0)."
        )
    if parcelas > 0 and valor_mensalidade == 0:
        raise ValueError(
            "O valor da mensalidade está em R$ 0,00. "
            "Preencha o valor ou zere a quantidade de parcelas."
        )

    # ── Cria o registro de matrícula ──────────────────────────────────────────
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
        aluno.curso_id = curso_id
    else:
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
            parcela_ref = "01/01",
        ))

    # ── Parcelas de mensalidade (só se valor > 0 E parcelas > 0) ─────────────
    if valor_mensalidade > 0 and parcelas > 0:
        for i in range(1, parcelas + 1):
            venc_mes = mes + i - 1
            venc_ano = ano + (venc_mes - 1) // 12
            venc_mes = ((venc_mes - 1) % 12) + 1
            vencimento = f"{venc_ano:04d}-{venc_mes:02d}-10"
            db.session.add(Mensalidade(
                aluno_id    = aluno_id,
                curso_id    = curso_id,
                valor       = valor_mensalidade,
                vencimento  = vencimento,
                status      = "Pendente",
                tipo        = "mensalidade",
                parcela_ref = f"{i:02d}/{parcelas:02d}",
            ))

    # ── Parcelas de material ──────────────────────────────────────────────────
    if valor_material > 0:
        for i in range(1, parcelas_material + 1):
            venc_mes = mes_mat + i - 1
            venc_ano = ano_mat + (venc_mes - 1) // 12
            venc_mes = ((venc_mes - 1) % 12) + 1
            vencimento = f"{venc_ano:04d}-{venc_mes:02d}-10"
            db.session.add(Mensalidade(
                aluno_id    = aluno_id,
                curso_id    = curso_id,
                valor       = round(valor_material / parcelas_material, 2),
                vencimento  = vencimento,
                status      = "Pendente",
                tipo        = "material",
                parcela_ref = f"{i:02d}/{parcelas_material:02d}",
            ))

    db.session.commit()
    return matricula.id
