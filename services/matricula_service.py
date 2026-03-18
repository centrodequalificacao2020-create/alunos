from db import db
from models import Matricula, Mensalidade
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

def criar_matricula(form):
    """
    Cria matrícula + mensalidades numa única transação.
    Retorna o id da matrícula criada.
    Lança ValueError se já existe matrícula ATIVA para o mesmo aluno/curso.
    """
    aluno_id         = int(form.get("aluno_id"))
    curso_id         = int(form.get("curso_id"))
    tipo_curso       = form.get("tipo_curso", "")
    valor_matricula  = float(form.get("valor_matricula") or 0)
    valor_mensal     = float(form.get("valor_mensal") or 0)
    parcelas         = int(form.get("parcelas") or 1)
    material         = form.get("material_didatico", "Digital")
    valor_material   = float(form.get("valor_material") or 0)
    parc_material    = int(form.get("parcelas_material") or 1)
    observacao       = form.get("observacao")

    hoje = date.today()
    d_matricula   = _parse_date(form.get("data_matricula"))             or hoje
    d_mensalidade = _parse_date(form.get("data_primeira_mensalidade"))  or hoje
    d_material    = _parse_date(form.get("data_material"))              or hoje

    # ── GUARD: dupla matrícula ──────────────────────────────────────────
    duplicada = Matricula.query.filter_by(
        aluno_id=aluno_id, curso_id=curso_id, status="ATIVA"
    ).first()
    if duplicada:
        raise ValueError(
            f"Aluno já possui matrícula ATIVA neste curso (id={duplicada.id})."
        )
    # ───────────────────────────────────────────────────────────────────

    try:
        matricula = Matricula(
            aluno_id=aluno_id, curso_id=curso_id, tipo_curso=tipo_curso,
            data_matricula=d_matricula.strftime("%Y-%m-%d"), status="ATIVA",
            valor_matricula=valor_matricula, valor_mensalidade=valor_mensal,
            quantidade_parcelas=parcelas, material_didatico=material,
            valor_material=valor_material, observacao=observacao,
        )
        db.session.add(matricula)
        db.session.flush()

        if valor_matricula > 0:
            db.session.add(Mensalidade(
                aluno_id=aluno_id, valor=valor_matricula,
                vencimento=d_matricula.strftime("%Y-%m-%d"),
                status="Pendente", tipo="Matrícula", parcela_ref="1/1"))

        for i in range(parcelas):
            venc = d_mensalidade + relativedelta(months=i)
            db.session.add(Mensalidade(
                aluno_id=aluno_id, valor=valor_mensal,
                vencimento=venc.strftime("%Y-%m-%d"),
                status="Pendente", tipo="Mensalidade",
                parcela_ref=f"{i+1}/{parcelas}"))

        if valor_material > 0:
            val_parc = round(valor_material / parc_material, 2)
            for i in range(parc_material):
                venc = d_material + relativedelta(months=i)
                db.session.add(Mensalidade(
                    aluno_id=aluno_id, valor=val_parc,
                    vencimento=venc.strftime("%Y-%m-%d"),
                    status="Pendente", tipo="Material",
                    parcela_ref=f"{i+1}/{parc_material}"))

        db.session.commit()
        return matricula.id

    except Exception as e:
        db.session.rollback()
        raise e


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None
