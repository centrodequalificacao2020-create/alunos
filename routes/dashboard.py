import calendar
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from db import db
from models import Mensalidade, Aluno, Matricula, Despesa, Relatorio, Curso
from security import login_required
from sqlalchemy import func

dashboard_bp = Blueprint("dashboard", __name__)


def _fim_mes(mes_str: str) -> str:
    ano, mes = int(mes_str[:4]), int(mes_str[5:7])
    ultimo = calendar.monthrange(ano, mes)[1]
    return f"{mes_str}-{ultimo:02d}"


def _buscar_relatorio_mes(mes: str) -> dict:
    r = Relatorio.query.filter_by(mes=mes).first()
    if r:
        return {"meta": r.meta or 0, "realizado": r.realizado or 0,
                "matriculas": r.matriculas or 0, "vendas": r.matriculas_venda or 0}
    return {"meta": 0, "realizado": 0, "matriculas": 0, "vendas": 0}


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"
    fim       = _fim_mes(mes)

    # ── RECEITAS ──
    recebido_mes = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pago",
        Mensalidade.data_pagamento.between(inicio, fim)
    ).scalar() or 0

    a_receber_mes = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pendente",
        Mensalidade.vencimento.between(inicio, fim)
    ).scalar() or 0

    total_atraso = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pendente",
        Mensalidade.vencimento < inicio
    ).scalar() or 0

    inadimplentes = db.session.query(
        func.count(Mensalidade.aluno_id.distinct())
    ).filter(
        Mensalidade.status == "Pendente",
        Mensalidade.vencimento < inicio
    ).scalar() or 0

    alunos_ativos = Aluno.query.filter_by(status="Ativo").count()

    matriculas_mes = Matricula.query.filter(
        Matricula.data_matricula.between(inicio, fim),
        Matricula.data_matricula >= "2026-01-01"
    ).count()

    vencendo = Mensalidade.query.filter(
        Mensalidade.status == "Pendente",
        Mensalidade.vencimento.between(inicio, fim)
    ).count()

    matriculas_futuras = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pendente",
        Mensalidade.tipo == "Matrícula"
    ).scalar() or 0

    recebimento_matricula = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pago",
        Mensalidade.tipo == "Matrícula",
        Mensalidade.data_pagamento.between(inicio, fim)
    ).scalar() or 0

    # ── DESPESAS ──
    variaveis = db.session.query(func.sum(Despesa.valor)).filter(
        Despesa.recorrente == 0,
        Despesa.data.between(inicio, fim)
    ).scalar() or 0

    fixas_list = Despesa.query.filter_by(recorrente=1).all()
    fixas = sum(
        float(d.valor or 0)
        for d in fixas_list
        if d.dia_vencimento and str(d.data or "")[:7] <= mes
    )
    despesas_mes = variaveis + fixas

    # ── INDICADORES ──
    lucro_liquido      = recebido_mes - despesas_mes
    margem_lucro       = (lucro_liquido / recebido_mes * 100) if recebido_mes > 0 else 0
    receita_projetada  = recebido_mes + a_receber_mes
    ticket_medio       = recebido_mes / alunos_ativos if alunos_ativos > 0 else 0
    total_carteira     = a_receber_mes + total_atraso
    taxa_inadimplencia = (total_atraso / total_carteira * 100) if total_carteira > 0 else 0

    cancelamentos = Aluno.query.filter(
        func.lower(Aluno.status) == "cancelado"
    ).count()

    receita_media = recebido_mes / matriculas_mes if matriculas_mes > 0 else 0
    meta_mensal   = alunos_ativos * 200
    total_alunos  = alunos_ativos + cancelamentos
    taxa_evasao   = (cancelamentos / total_alunos * 100) if total_alunos > 0 else 0

    grafico_financeiro = [
        ("Receita",  recebido_mes),
        ("Despesas", despesas_mes),
        ("Lucro",    lucro_liquido if lucro_liquido > 0 else 0),
    ]

    # ── GRÁFICO RECEITA MENSAL ──
    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]
    meses_label, valores = [], []
    for m in range(1, hoje.month + 1):
        mes_str = f"{hoje.year}-{m:02d}"
        total = db.session.query(func.sum(Mensalidade.valor)).filter(
            Mensalidade.status == "Pago",
            Mensalidade.data_pagamento.between(f"{mes_str}-01", _fim_mes(mes_str))
        ).scalar() or 0
        meses_label.append(f"{meses_pt[m-1]}/{str(hoje.year)[2:]}")
        valores.append(total)

    # ── RANKING DE CURSOS — join limpo via ORM ──
    ranking_cursos = (
        db.session.query(Curso.nome, func.sum(Mensalidade.valor))
        .join(Matricula, Matricula.curso_id == Curso.id)
        .join(Mensalidade, Mensalidade.aluno_id == Matricula.aluno_id)
        .filter(
            Mensalidade.status == "Pago",
            Mensalidade.data_pagamento.between(inicio, fim)
        )
        .group_by(Curso.nome)
        .order_by(func.sum(Mensalidade.valor).desc())
        .limit(5)
        .all()
    )

    vendas_tipo = (
        db.session.query(
            func.coalesce(Matricula.tipo_curso, "Não definido"),
            func.count()
        )
        .filter(Matricula.status == "ATIVA")
        .group_by(Matricula.tipo_curso)
        .all()
    )

    rel = _buscar_relatorio_mes(mes)

    return render_template(
        "dashboard.html",
        mes=mes,
        recebido_mes=recebido_mes,
        a_receber_mes=a_receber_mes,
        total_atraso=total_atraso,
        inadimplentes=inadimplentes,
        alunos_ativos=alunos_ativos,
        despesas_mes=despesas_mes,
        lucro_liquido=lucro_liquido,
        margem_lucro=margem_lucro,
        matriculas_mes=matriculas_mes,
        vencendo=vencendo,
        matriculas_futuras=matriculas_futuras,
        receita_projetada=receita_projetada,
        ticket_medio=ticket_medio,
        taxa_inadimplencia=taxa_inadimplencia,
        cancelamentos=cancelamentos,
        receita_media=receita_media,
        meta_mensal=meta_mensal,
        taxa_evasao=taxa_evasao,
        grafico_financeiro=grafico_financeiro,
        meses=meses_label,
        valores=valores,
        ranking_cursos=ranking_cursos,
        vendas_tipo=vendas_tipo,
        recebimento_matricula=recebimento_matricula,
        rel_meta=rel["meta"],
        rel_realizado=rel["realizado"],
        rel_matriculas=rel["matriculas"],
        rel_vendas=rel["vendas"],
    )


@dashboard_bp.route("/salvar_relatorio", methods=["POST"])
@login_required
def salvar_relatorio():
    dados = request.get_json()
    r = Relatorio.query.filter_by(mes=dados.get("mes")).first()
    if not r:
        r = Relatorio(mes=dados.get("mes"))
        db.session.add(r)
    r.meta             = dados.get("meta")
    r.realizado        = dados.get("realizado")
    r.matriculas       = dados.get("matriculas")
    r.matriculas_venda = dados.get("matriculas_venda")
    db.session.commit()
    return jsonify({"status": "ok"})


@dashboard_bp.route("/carregar_relatorio/<mes>")
@login_required
def carregar_relatorio(mes):
    r = Relatorio.query.filter_by(mes=mes).first()
    if r:
        return jsonify({"meta": r.meta, "realizado": r.realizado,
                        "matriculas": r.matriculas,
                        "matriculas_venda": r.matriculas_venda})
    return jsonify({})


@dashboard_bp.route("/relatorio_trimestre/<ano>/<tri>")
@login_required
def relatorio_trimestre(ano, tri):
    meses_tri = {"1":["01","02","03"],"2":["04","05","06"],
                 "3":["07","08","09"],"4":["10","11","12"]}
    lista  = [f"{ano}-{m}" for m in meses_tri.get(tri, [])]
    totais = {"meta":0, "realizado":0, "matriculas":0, "matriculas_venda":0}
    for mes in lista:
        r = Relatorio.query.filter_by(mes=mes).first()
        if r:
            totais["meta"]            += r.meta             or 0
            totais["realizado"]       += r.realizado        or 0
            totais["matriculas"]      += r.matriculas       or 0
            totais["matriculas_venda"]+= r.matriculas_venda or 0
    return jsonify(totais)
