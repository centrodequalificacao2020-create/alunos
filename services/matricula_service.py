"""Serviço de matrículas."""
from db import db
from models import Matricula, Curso, Mensalidade, Aluno
from enums import StatusMatricula
from datetime import date, datetime


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
    NUNCA usa valor do curso como padrão silencioso — o chamador decide.
    """
    for campo in campos:
        raw = (form_data.get(campo) or "") if hasattr(form_data, 'get') else ""
        raw = str(raw).strip()
        if raw != "":
            try:
                return float(raw)
            except (ValueError, TypeError):
                pass
    return fallback


def _get_int(form_data, *campos, fallback=0):
    """Igual a _get_float, mas retorna int."""
    for campo in campos:
        raw = (form_data.get(campo) or "") if hasattr(form_data, 'get') else ""
        raw = str(raw).strip()
        if raw != "":
            try:
                return int(raw)
            except (ValueError, TypeError):
                pass
    return fallback


def _campo_enviado(form_data, campo):
    """Retorna True se o campo foi enviado com algum conteúdo (mesmo '0')."""
    raw = form_data.get(campo) if hasattr(form_data, 'get') else None
    return raw is not None and str(raw).strip() != ""


def _validar_data(data_str: str, nome_campo: str = "Data") -> str:
    """
    Valida que data_str está no formato YYYY-MM-DD e é uma data real.
    Retorna a string original se válida.
    Lança ValueError com mensagem amigável se inválida.
    """
    if not data_str:
        return date.today().isoformat()
    try:
        dt = datetime.strptime(str(data_str).strip()[:10], "%Y-%m-%d").date()
        # Sanidade: rejeita anos impossíveis (antes de 2000 ou mais de 10 anos no futuro)
        if dt.year < 2000 or dt.year > date.today().year + 10:
            raise ValueError(f"{nome_campo} com ano inválido: {dt.year}.")
        return dt.isoformat()
    except ValueError as e:
        if "ano inválido" in str(e):
            raise
        raise ValueError(
            f"{nome_campo} inválida: '{data_str}'. Use o formato DD/MM/AAAA."
        )


def criar_matricula(form_data) -> int:
    """
    Cria matrícula + parcelas a partir dos dados do formulário.
    Retorna o id da Matricula criada.
    Lança ValueError se dados obrigatórios estiverem ausentes ou
    se a combinação de valor/parcelas for inconsistente.

    BUG-14: envolto em try/except com rollback explícito para garantir
    que nenhuma operação parcial fique gravada em caso de erro inesperado.

    REGRAS:
    - Matrícula pode ser criada SEM mensalidades e SEM material (ambos opcionais).
    - Mensalidade só é lançada se AMBOS valor_mensalidade > 0 E parcelas >= 1.
    - Campos em branco = sem mensalidades. Nunca usa valores do curso como fallback.
    - Se valor_material > 0, parcelas_material deve ser >= 1.
    """
    try:
        return _criar_matricula_interno(form_data)
    except ValueError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        raise ValueError(
            f"Erro inesperado ao processar a matrícula. "
            f"Nenhum dado foi gravado. Detalhe: {e}"
        ) from e


def _criar_matricula_interno(form_data) -> int:
    """Lógica interna de criação de matrícula. Chamada por criar_matricula()."""
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

    # ── Flag: lançamento avulso ──────────────────────────────────────────────
    apenas_mensalidade = form_data.get("apenas_mensalidade") == "1"

    # ── BUG 4 FIX: bloqueia matrícula duplicada ──────────────────────────────
    if not apenas_mensalidade:
        duplicada = Matricula.query.filter(
            Matricula.aluno_id == aluno_id,
            Matricula.curso_id == curso_id,
            db.func.upper(Matricula.status) == StatusMatricula.ATIVA.value
        ).first()
        if duplicada:
            raise ValueError(
                f"Este aluno já possui uma matrícula ATIVA neste curso "
                f"(matrícula #{duplicada.id}, em {duplicada.data_matricula}). "
                f"Cancele a matrícula anterior antes de criar uma nova."
            )

    # ── Valor da matrícula ───────────────────────────────────────────────────
    valor_matricula = 0.0 if apenas_mensalidade else _get_float(form_data, "valor_matricula")

    # ── Valor e parcelas de mensalidade ──────────────────────────────────────
    # Campo em branco = sem mensalidades. NUNCA usa fallback do curso.
    valor_mensalidade = _get_float(form_data, "valor_mensalidade", "valor_mensal")
    parcelas = _get_int(form_data, "parcelas")

    if parcelas < 0:
        parcelas = 0

    # ── Validação: bloqueia combinações inconsistentes ───────────────────────
    if valor_mensalidade > 0 and parcelas == 0:
        raise ValueError(
            "Informe a quantidade de parcelas de mensalidade (campo está em 0)."
        )
    if parcelas > 0 and valor_mensalidade == 0:
        raise ValueError(
            "O valor da mensalidade está em R$ 0,00. "
            "Preencha o valor ou deixe a quantidade de parcelas em branco "
            "para matricular sem mensalidades."
        )

    tipo_curso     = form_data.get("tipo_curso") or curso.tipo or ""
    observacao     = form_data.get("observacao") or ""

    # ── BUG 5 FIX: validação de data ─────────────────────────────────────────
    data_matricula_raw = form_data.get("data_matricula") or date.today().isoformat()
    data_matricula = _validar_data(data_matricula_raw, "Data da matrícula")

    # ── Material didático ────────────────────────────────────────────────────
    material_didatico = form_data.get("material_didatico") or ""
    valor_material    = _get_float(form_data, "valor_material")
    parcelas_material = _get_int(form_data, "parcelas_material", fallback=0)

    # ── BUG 3 FIX: parcelas_material=0 com valor>0 agora gera erro explícito ─
    if valor_material > 0 and parcelas_material < 1:
        raise ValueError(
            "Informe a quantidade de parcelas do material didático (campo está em 0 ou vazio)."
        )
    if parcelas_material < 1:
        parcelas_material = 1

    # ── Datas de vencimento ──────────────────────────────────────────────────
    mes_inicio_raw = (
        form_data.get("data_primeira_mensalidade") or
        form_data.get("mes_inicio") or
        date.today().strftime("%Y-%m")
    )
    try:
        ano = int(mes_inicio_raw[:4])
        mes = int(mes_inicio_raw[5:7])
        if ano < 2000 or mes < 1 or mes > 12:
            raise ValueError
    except Exception:
        ano, mes = date.today().year, date.today().month

    data_material_raw = form_data.get("data_material") or data_matricula
    try:
        ano_mat = int(data_material_raw[:4])
        mes_mat = int(data_material_raw[5:7])
        if ano_mat < 2000 or mes_mat < 1 or mes_mat > 12:
            raise ValueError
    except Exception:
        ano_mat, mes_mat = ano, mes

    # ── Cria o registro de matrícula ─────────────────────────────────────────
    if not apenas_mensalidade:
        matricula = Matricula(
            aluno_id            = aluno_id,
            curso_id            = curso_id,
            tipo_curso          = tipo_curso,
            data_matricula      = data_matricula,
            data_cadastro       = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

    # ── Parcelas de material (só se valor > 0) ────────────────────────────────
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
