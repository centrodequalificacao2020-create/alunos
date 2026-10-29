import calendar
from flask import Blueprint, render_template, request, jsonify
from datetime import datetime
from db import db
from models import Mensalidade, Aluno, Matricula, Despesa, Relatorio, Curso, EntradaCaixa
from security import financeiro_required, relatorio_required
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


def _despesas_do_mes(mes: str) -> float:
    inicio = f"{mes}-01"
    fim    = _fim_mes(mes)

    variaveis = db.session.query(func.sum(Despesa.valor)).filter(
        Despesa.tipo != "fixa",
        Despesa.data.between(inicio, fim)
    ).scalar() or 0

    fixas_ativas = Despesa.query.filter(
        Despesa.tipo == "fixa",
        Despesa.data_inicio <= mes,
        db.or_(Despesa.data_fim >= mes, Despesa.data_fim.is_(None), Despesa.data_fim == "")
    ).all()
    fixas = sum(float(d.valor or 0) for d in fixas_ativas)

    legadas = Despesa.query.filter(
        Despesa.tipo == "fixa",
        Despesa.recorrente == 1,
        Despesa.data_inicio.is_(None)
    ).all()
    fixas += sum(float(d.valor or 0) for d in legadas)

    return float(variaveis) + fixas


def _status_matricula_por_aluno():
    """Mapa aluno_id -> status da matrícula mais recente (normalizado em maiúsculas).

    Alunos sem nenhum registro em `Matricula` não aparecem no mapa.
    """
    sub = (
        db.session.query(
            Matricula.aluno_id.label("aluno_id"),
            Matricula.status.label("status"),
        )
        .order_by(Matricula.aluno_id, Matricula.id.desc())
        .distinct(Matricula.aluno_id)
        .subquery()
    )
    return {
        row.aluno_id: (row.status or "").upper().strip()
        for row in db.session.query(sub.c.aluno_id, sub.c.status).all()
    }


def _em_atraso_por_status_matricula(inicio: str):
    """Separa o valor em atraso entre matrículas ATIVAS e não-ativas.

    Critério de "em atraso": status da mensalidade em (Pendente, Atrasado)
    e vencimento anterior ao início do mês de referência.

    Retorna (em_aberto, perda_financeira, qtd_em_aberto, qtd_perda).
    Alunos sem registro de matrícula contam como perda financeira.
    """
    rows = (
        db.session.query(
            Mensalidade.aluno_id,
            func.sum(Mensalidade.valor).label("total"),
        )
        .filter(
            Mensalidade.status.in_(["Pendente", "Atrasado"]),
            Mensalidade.vencimento < inicio,
        )
        .group_by(Mensalidade.aluno_id)
        .all()
    )

    status_por_aluno = _status_matricula_por_aluno()

    em_aberto = perda = 0.0
    qtd_em_aberto = qtd_perda = 0
    for aluno_id, total in rows:
        valor = float(total or 0)
        if status_por_aluno.get(aluno_id) == "ATIVA":
            em_aberto += valor
            qtd_em_aberto += 1
        else:
            perda += valor
            qtd_perda += 1

    return em_aberto, perda, qtd_em_aberto, qtd_perda


def _matriculas_novas_periodo(inicio: str, fim: str):
    """Matrículas novas: taxa de matrícula PAGA no período.

    Regra de negócio (definida pelo cliente em 2026-10-29):
    a matrícula nova conta no mês em que a **taxa de matrícula foi paga**, não
    na data em que o aluno se matriculou. Ex.: aluno matriculado em julho que
    paga a taxa em agosto aparece em agosto.

    "Nova" = o aluno ainda não tinha matrícula ATIVA em outro curso até a
    data do pagamento. Quem já era aluno é rematrícula (ver
    `_rematriculas_periodo`), e rematrícula **não tem taxa**.

    Deduplicação por (aluno, curso): duas taxas pagas no mesmo mês para o
    mesmo curso contam uma única vez, garantindo que o número do card seja
    sempre igual ao número de linhas da lista.

    Retorna lista de dicts: aluno_id, aluno_nome, curso, data.
    """
    rows = (
        db.session.query(Mensalidade, Aluno)
        .join(Aluno, Aluno.id == Mensalidade.aluno_id)
        .filter(
            func.lower(Mensalidade.tipo) == "matricula",
            Mensalidade.status == "Pago",
            Mensalidade.data_pagamento.between(inicio, fim),
        )
        .order_by(Mensalidade.data_pagamento.asc(), Mensalidade.id.asc())
        .all()
    )
    if not rows:
        return []

    aluno_ids = {mens.aluno_id for mens, _ in rows}

    matriculas_por_aluno = {}
    for mat in (
        Matricula.query
        .filter(Matricula.aluno_id.in_(aluno_ids))
        .order_by(Matricula.aluno_id, Matricula.data_matricula, Matricula.id)
        .all()
    ):
        matriculas_por_aluno.setdefault(mat.aluno_id, []).append(mat)

    cursos = {c.id: c.nome for c in Curso.query.all()}

    vistos = set()
    resultado = []
    for mens, aluno in rows:
        pagamento = mens.data_pagamento or ""
        curso_id  = mens.curso_id
        mats      = matriculas_por_aluno.get(aluno.id, [])

        # Legado: taxas antigas podem estar sem `curso_id`. Usa a matrícula
        # mais recente até a data do pagamento para descobrir o curso.
        if curso_id is None:
            candidatas = [
                m for m in mats if (m.data_matricula or "") <= pagamento
            ]
            escolhida = candidatas[-1] if candidatas else (mats[-1] if mats else None)
            curso_id = escolhida.curso_id if escolhida else None

        chave = (aluno.id, curso_id)
        if chave in vistos:
            continue
        vistos.add(chave)

        # O aluno já tinha qualquer matrícula em OUTRO curso antes do pagamento
        # -> é rematrícula, que não tem taxa e por isso não entra aqui.
        # Não exigimos que a matrícula anterior esteja ATIVA: aluno que
        # transferiu (INATIVA/CONCLUIDA) e entrou em outro curso continua
        # sendo rematrícula.
        ja_era_aluno = any(
            m.curso_id != curso_id
            and (m.data_matricula or "") <= pagamento
            for m in mats
        )
        if ja_era_aluno:
            continue

        resultado.append({
            "aluno_id":   aluno.id,
            "aluno_nome": aluno.nome,
            "curso":      cursos.get(curso_id) or "\u2014",
            "data":       mens.data_pagamento,
        })

    return resultado


def _rematriculas_periodo(inicio: str, fim: str):
    """Rematrículas: aluno ATIVO que se matriculou em OUTRO curso no período.

    Definição do cliente: rematrícula é o aluno que **já estudava aqui** e se
    cadastrou em **outro curso**. Rematrícula **não tem taxa de matrícula**,
    então o critério é a data da matrícula (`Matricula.data_matricula`),
    nunca pagamento.

    Critérios:
    - a nova matrícula tem `data_matricula` no período;
    - o aluno está com `Aluno.status = Ativo`;
    - o aluno já tinha alguma matrícula em curso diferente, anterior a esta.
      Não exigimos que a anterior esteja ATIVA (transferência fica INATIVA).

    Retorna lista de dicts: aluno_id, aluno_nome, curso, curso_anterior, data.
    """
    candidatas = (
        Matricula.query
        .join(Aluno, Aluno.id == Matricula.aluno_id)
        .filter(
            Matricula.data_matricula.between(inicio, fim),
            func.upper(Matricula.status) == "ATIVA",
            func.upper(Aluno.status) == "ATIVO",
        )
        .order_by(Matricula.data_matricula, Matricula.id)
        .all()
    )
    if not candidatas:
        return []

    aluno_ids = {m.aluno_id for m in candidatas}
    todas_por_aluno = {}
    for mat in (
        Matricula.query
        .filter(Matricula.aluno_id.in_(aluno_ids))
        .order_by(Matricula.aluno_id, Matricula.data_matricula, Matricula.id)
        .all()
    ):
        todas_por_aluno.setdefault(mat.aluno_id, []).append(mat)

    cursos = {c.id: c.nome for c in Curso.query.all()}

    vistos = set()
    resultado = []
    for mat in candidatas:
        mats = todas_por_aluno.get(mat.aluno_id, [])

        anteriores = [
            m for m in mats
            if m.curso_id != mat.curso_id
            and (m.data_matricula or "") < (mat.data_matricula or "")
        ]
        if not anteriores:
            continue

        chave = (mat.aluno_id, mat.curso_id)
        if chave in vistos:
            continue
        vistos.add(chave)

        aluno = db.session.get(Aluno, mat.aluno_id)
        resultado.append({
            "aluno_id":       mat.aluno_id,
            "aluno_nome":     aluno.nome if aluno else "\u2014",
            "curso":          cursos.get(mat.curso_id) or "\u2014",
            "curso_anterior": cursos.get(anteriores[-1].curso_id) or "\u2014",
            "data":           mat.data_matricula,
        })

    return resultado


@dashboard_bp.route("/dashboard")
@financeiro_required
def dashboard():
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"
    fim       = _fim_mes(mes)

    recebido_mes = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pago",
        Mensalidade.data_pagamento.between(inicio, fim)
    ).scalar() or 0

    # Entradas manuais de caixa (tabela entradas_caixa, exclusão lógica).
    # Somam no card "Entradas" junto com o recebido de mensalidades.
    entradas_manuais = db.session.query(func.sum(EntradaCaixa.valor)).filter(
        EntradaCaixa.cancelado == 0,
        EntradaCaixa.data.between(inicio, fim),
    ).scalar() or 0

    entradas_total = float(recebido_mes or 0) + float(entradas_manuais or 0)

    a_receber_mes = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pendente",
        Mensalidade.vencimento.between(inicio, fim)
    ).scalar() or 0

    total_atraso = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status.in_(["Pendente", "Atrasado"]),
        Mensalidade.vencimento < inicio
    ).scalar() or 0

    # Em Aberto (matrícula ATIVA) x Perda Financeira (demais status / sem matrícula)
    em_aberto, perda_financeira, qtd_em_aberto, qtd_perda = \
        _em_atraso_por_status_matricula(inicio)

    inadimplentes = db.session.query(
        func.count(Mensalidade.aluno_id.distinct())
    ).filter(
        Mensalidade.status.in_(["Pendente", "Atrasado"]),
        Mensalidade.vencimento < inicio
    ).scalar() or 0

    alunos_ativos = Aluno.query.filter_by(status="Ativo").count()

    # "Novas" e "Rematrículas" usam regras distintas de propósito:
    # - nova: conta pela TAXA PAGA (matrícula nova tem taxa);
    # - rematrícula: conta pela DATA DA MATRÍCULA (não tem taxa).
    # Cada card usa exatamente a mesma fonte da respectiva lista, então o
    # número do card é sempre igual ao número de linhas ao clicar.
    matriculas_novas = len(_matriculas_novas_periodo(inicio, fim))
    rematriculas     = len(_rematriculas_periodo(inicio, fim))
    matriculas_mes   = matriculas_novas + rematriculas

    vencendo = Mensalidade.query.filter(
        Mensalidade.status == "Pendente",
        Mensalidade.vencimento.between(inicio, fim)
    ).count()

    matriculas_futuras = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status.in_(["Pendente", "Atrasado"]),
        func.lower(Mensalidade.tipo) == "matricula",
        Mensalidade.vencimento >= inicio
    ).scalar() or 0

    recebimento_apostilas = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status.in_(["Pendente", "Atrasado"]),
        func.lower(Mensalidade.tipo) == "material",
        Mensalidade.vencimento >= inicio
    ).scalar() or 0

    recebimento_matricula = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pago",
        func.lower(Mensalidade.tipo) == "matricula",
        Mensalidade.data_pagamento.between(inicio, fim)
    ).scalar() or 0

    # Apostilas (material) pagas no mês — lado direito do card teal
    recebimento_apostila_pago = db.session.query(func.sum(Mensalidade.valor)).filter(
        Mensalidade.status == "Pago",
        func.lower(Mensalidade.tipo) == "material",
        Mensalidade.data_pagamento.between(inicio, fim)
    ).scalar() or 0

    despesas_mes = _despesas_do_mes(mes)

    # EBITDA e margem consideram as entradas manuais (dinheiro real que entrou).
    lucro_liquido      = entradas_total - despesas_mes
    margem_lucro       = (lucro_liquido / entradas_total * 100) if entradas_total > 0 else 0
    receita_projetada  = entradas_total + a_receber_mes
    ticket_medio       = entradas_total / alunos_ativos if alunos_ativos > 0 else 0

    # ─── Taxa de inadimplência ─────────────────────────────────────────────────────────
    # Fórmula correta: Em atraso / (Recebido + A receber + Em atraso)
    receita_total      = float(entradas_total) + float(a_receber_mes) + float(total_atraso)
    taxa_inadimplencia = (float(total_atraso) / receita_total * 100) if receita_total > 0 else 0
    # ───────────────────────────────────────────────────────────────────────────

    cancelamentos = Aluno.query.filter(
        func.lower(Aluno.status) == "cancelado"
    ).count()

    receita_media = entradas_total / matriculas_mes if matriculas_mes > 0 else 0
    meta_mensal   = alunos_ativos * 200
    total_alunos  = alunos_ativos + cancelamentos
    taxa_evasao   = (cancelamentos / total_alunos * 100) if total_alunos > 0 else 0

    grafico_financeiro = [
        ("Receita",  entradas_total),
        ("Despesas", despesas_mes),
        ("Lucro",    lucro_liquido if lucro_liquido > 0 else 0),
    ]

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
        valores.append(float(total))

    ranking_cursos = [[nome, float(valor or 0)] for nome, valor in (
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
    )]

    vendas_tipo = [[tipo or "N\u00e3o definido", int(qtd)] for tipo, qtd in (
        db.session.query(
            func.coalesce(Matricula.tipo_curso, "N\u00e3o definido"),
            func.count()
        )
        .filter(Matricula.status == "ATIVA")
        .group_by(Matricula.tipo_curso)
        .all()
    )]

    matricula_ativa_sub = (
        db.session.query(
            Matricula.aluno_id,
            func.coalesce(Matricula.tipo_curso, "N\u00e3o definido").label("tipo")
        )
        .filter(Matricula.status == "ATIVA")
        .order_by(Matricula.aluno_id, Matricula.id.desc())
        .distinct(Matricula.aluno_id)
        .subquery()
    )

    faturamento_tipo = [[tipo or "N\u00e3o definido", float(total or 0)] for tipo, total in (
        db.session.query(
            matricula_ativa_sub.c.tipo,
            func.sum(Mensalidade.valor)
        )
        .join(Mensalidade, Mensalidade.aluno_id == matricula_ativa_sub.c.aluno_id)
        .filter(
            Mensalidade.status == "Pago",
            Mensalidade.data_pagamento.between(inicio, fim)
        )
        .group_by(matricula_ativa_sub.c.tipo)
        .order_by(func.sum(Mensalidade.valor).desc())
        .all()
    )]

    rel = _buscar_relatorio_mes(mes)

    return render_template(
        "dashboard.html",
        mes=mes,
        recebido_mes=recebido_mes,
        entradas_manuais=entradas_manuais,
        entradas_total=entradas_total,
        a_receber_mes=a_receber_mes,
        total_atraso=total_atraso,
        em_aberto=em_aberto,
        perda_financeira=perda_financeira,
        qtd_em_aberto=qtd_em_aberto,
        qtd_perda=qtd_perda,
        inadimplentes=inadimplentes,
        alunos_ativos=alunos_ativos,
        despesas_mes=despesas_mes,
        lucro_liquido=lucro_liquido,
        margem_lucro=margem_lucro,
        matriculas_mes=matriculas_mes,
        matriculas_novas=matriculas_novas,
        rematriculas=rematriculas,
        vencendo=vencendo,
        matriculas_futuras=matriculas_futuras,
        recebimento_apostilas=recebimento_apostilas,
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
        faturamento_tipo=faturamento_tipo,
        recebimento_matricula=recebimento_matricula,
        recebimento_apostila_pago=recebimento_apostila_pago,
        rel_meta=rel["meta"],
        rel_realizado=rel["realizado"],
        rel_matriculas=rel["matriculas"],
        rel_vendas=rel["vendas"],
    )


@dashboard_bp.route("/salvar_relatorio", methods=["POST"])
@relatorio_required
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


@dashboard_bp.route("/relatorio")
@relatorio_required
def relatorio():
    return render_template("relatorio.html")


@dashboard_bp.route("/carregar_relatorio/<mes>")
@relatorio_required
def carregar_relatorio(mes):
    r = Relatorio.query.filter_by(mes=mes).first()
    if r:
        return jsonify({"meta": r.meta, "realizado": r.realizado,
                        "matriculas": r.matriculas,
                        "matriculas_venda": r.matriculas_venda})
    return jsonify({})


@dashboard_bp.route("/relatorio_trimestre/<ano>/<tri>")
@relatorio_required
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


@dashboard_bp.route("/matriculas")
@financeiro_required
def matriculas_novas_detalhe():
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"
    fim       = _fim_mes(mes)

    # Mesma fonte do card: matrículas novas = taxa de matrícula paga no período.
    resultado = _matriculas_novas_periodo(inicio, fim)
    resultado.sort(key=lambda p: p["data"] or "", reverse=True)

    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]
    ano_n, mes_n = int(mes[:4]), int(mes[5:7])
    mes_label = f"{meses_pt[mes_n - 1]}/{str(ano_n)[2:]}"

    return render_template(
        "matriculas.html",
        mes=mes,
        mes_label=mes_label,
        resultado=resultado,
    )


@dashboard_bp.route("/rematriculas")
@financeiro_required
def rematriculas_detalhe():
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"
    fim       = _fim_mes(mes)

    # Mesma fonte do card: rematrículas pela data da matrícula (não têm taxa).
    resultado = [
        {
            "aluno_id":       p["aluno_id"],
            "aluno_nome":     p["aluno_nome"],
            "curso_novo":     p["curso"],
            "curso_anterior": p["curso_anterior"] or "\u2014",
            "data":           p["data"],
        }
        for p in _rematriculas_periodo(inicio, fim)
    ]
    resultado.sort(key=lambda p: p["data"] or "", reverse=True)

    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]
    ano_n, mes_n = int(mes[:4]), int(mes[5:7])
    mes_label = f"{meses_pt[mes_n - 1]}/{str(ano_n)[2:]}"

    return render_template(
        "rematriculas.html",
        mes=mes,
        mes_label=mes_label,
        resultado=resultado,
    )


@dashboard_bp.route("/matriculas-futuras")
@financeiro_required
def matriculas_futuras_detalhe():
    """Matrículas a receber (Pendentes) com vencimento no mês em diante."""
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"
    fim       = _fim_mes(mes)

    rows = (
        db.session.query(Mensalidade, Aluno, Curso)
        .join(Aluno, Aluno.id == Mensalidade.aluno_id)
        .outerjoin(Curso, Curso.id == Mensalidade.curso_id)
        .filter(
            func.lower(Mensalidade.tipo) == "matricula",
            Mensalidade.status.in_(["Pendente", "Atrasado"]),
            Mensalidade.vencimento >= inicio,
        )
        .order_by(Mensalidade.vencimento.asc())
        .all()
    )

    resultado = [
        {
            "aluno_id":   aluno.id,
            "aluno_nome": aluno.nome,
            "curso":      curso.nome if curso else "\u2014",
            "vencimento": mens.vencimento,
            "valor":      mens.valor,
            "status":     mens.status,
        }
        for mens, aluno, curso in rows
    ]

    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]
    ano_n, mes_n = int(mes[:4]), int(mes[5:7])
    mes_label = f"{meses_pt[mes_n - 1]}/{str(ano_n)[2:]}"

    return render_template(
        "matriculas_futuras.html",
        mes=mes,
        mes_label=mes_label,
        resultado=resultado,
    )


@dashboard_bp.route("/apostilas")
@financeiro_required
def apostilas_detalhe():
    """Recebimento de apostilas (material): pagas no mês ou pendentes a receber."""
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    situacao  = request.args.get("situacao", "futuras")  # 'pagas' | 'futuras'
    inicio    = f"{mes}-01"
    fim       = _fim_mes(mes)

    if situacao == "pagas":
        rows = (
            db.session.query(Mensalidade, Aluno, Curso)
            .join(Aluno, Aluno.id == Mensalidade.aluno_id)
            .outerjoin(Curso, Curso.id == Mensalidade.curso_id)
            .filter(
                func.lower(Mensalidade.tipo) == "material",
                Mensalidade.status == "Pago",
                Mensalidade.data_pagamento.between(inicio, fim)
            )
            .order_by(Mensalidade.data_pagamento.desc())
            .all()
        )
        resultado = [
            {
                "aluno_id":   aluno.id,
                "aluno_nome": aluno.nome,
                "curso":      curso.nome if curso else "\u2014",
                "data":       mens.data_pagamento,
                "valor":      mens.valor,
            }
            for mens, aluno, curso in rows
        ]
        titulo = "Recebimento de apostilas (pagas)"
    else:
        rows = (
            db.session.query(Mensalidade, Aluno, Curso)
            .join(Aluno, Aluno.id == Mensalidade.aluno_id)
            .outerjoin(Curso, Curso.id == Mensalidade.curso_id)
            .filter(
                func.lower(Mensalidade.tipo) == "material",
                Mensalidade.status.in_(["Pendente", "Atrasado"]),
                Mensalidade.vencimento >= inicio
            )
            .order_by(Mensalidade.vencimento.asc())
            .all()
        )
        resultado = [
            {
                "aluno_id":   aluno.id,
                "aluno_nome": aluno.nome,
                "curso":      curso.nome if curso else "\u2014",
                "vencimento": mens.vencimento,
                "valor":      mens.valor,
                "status":     mens.status,
            }
            for mens, aluno, curso in rows
        ]
        titulo = "Recebimento futuro de apostilas"

    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]
    ano_n, mes_n = int(mes[:4]), int(mes[5:7])
    mes_label = f"{meses_pt[mes_n - 1]}/{str(ano_n)[2:]}"

    return render_template(
        "apostilas.html",
        mes=mes,
        mes_label=mes_label,
        situacao=situacao,
        titulo=titulo,
        resultado=resultado,
    )


def _mes_label(mes: str) -> str:
    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]
    ano_n, mes_n = int(mes[:4]), int(mes[5:7])
    return f"{meses_pt[mes_n - 1]}/{str(ano_n)[2:]}"


def _listar_atraso(inicio: str, apenas_ativos: bool):
    """Lista mensalidades em atraso (Pendente/Atrasado, vencimento < inicio).

    `apenas_ativos=True`  → somente alunos com matrícula ATIVA (Em Aberto).
    `apenas_ativos=False` → demais status e alunos sem matrícula (Perda Financeira).
    """
    rows = (
        db.session.query(Mensalidade, Aluno, Curso)
        .join(Aluno, Aluno.id == Mensalidade.aluno_id)
        .outerjoin(Curso, Curso.id == Mensalidade.curso_id)
        .filter(
            Mensalidade.status.in_(["Pendente", "Atrasado"]),
            Mensalidade.vencimento < inicio,
        )
        .order_by(Mensalidade.vencimento.asc())
        .all()
    )

    status_por_aluno = _status_matricula_por_aluno()

    resultado = []
    for mens, aluno, curso in rows:
        status_mat = status_por_aluno.get(aluno.id)
        is_ativo   = status_mat == "ATIVA"
        if is_ativo != apenas_ativos:
            continue
        resultado.append({
            "aluno_id":        aluno.id,
            "aluno_nome":      aluno.nome,
            "curso":           curso.nome if curso else "\u2014",
            "tipo":            mens.tipo or "\u2014",
            "parcela_ref":     mens.parcela_ref or "\u2014",
            "vencimento":      mens.vencimento,
            "valor":           mens.valor,
            "status":          mens.status,
            "status_matricula": status_mat or "Sem matr\u00edcula",
        })

    return resultado


@dashboard_bp.route("/em-aberto")
@financeiro_required
def em_aberto_detalhe():
    """Parcelas/material em atraso de alunos com matrícula ATIVA."""
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"

    resultado = _listar_atraso(inicio, apenas_ativos=True)
    total     = sum(float(r["valor"] or 0) for r in resultado)

    return render_template(
        "em_aberto.html",
        mes=mes,
        mes_label=_mes_label(mes),
        resultado=resultado,
        total=total,
    )


@dashboard_bp.route("/perda-financeira")
@financeiro_required
def perda_financeira_detalhe():
    """Parcelas/material em atraso de alunos com matrícula não-ativa ou sem matrícula."""
    hoje      = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes       = request.args.get("mes") or mes_atual
    inicio    = f"{mes}-01"

    resultado = _listar_atraso(inicio, apenas_ativos=False)
    total     = sum(float(r["valor"] or 0) for r in resultado)

    return render_template(
        "perda_financeira.html",
        mes=mes,
        mes_label=_mes_label(mes),
        resultado=resultado,
        total=total,
    )
