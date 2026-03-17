from flask import Blueprint, render_template, request, redirect, session, jsonify
import sqlite3
import os
from datetime import datetime, date

dashboard_bp = Blueprint("dashboard", __name__)


def _conectar():
    db_path = "/home/site/wwwroot/cqp.db"
    if not os.path.exists(db_path):
        from flask import current_app
        db_path = os.path.join(current_app.root_path, "cqp.db")
    return sqlite3.connect(db_path, timeout=30, check_same_thread=False)


def _buscar_relatorio_mes(mes):
    conn = _conectar()
    c = conn.cursor()
    c.execute("""
        SELECT meta, realizado, matriculas, matriculas_venda
        FROM relatorios WHERE mes = ?
    """, (mes,))
    r = c.fetchone()
    conn.close()
    if r:
        return {"meta": r[0] or 0, "realizado": r[1] or 0,
                "matriculas": r[2] or 0, "vendas": r[3] or 0}
    return {"meta": 0, "realizado": 0, "matriculas": 0, "vendas": 0}


def _logado():
    return "usuario_id" in session


# ─────────────────────────── DASHBOARD ───────────────────────────

@dashboard_bp.route("/dashboard")
def dashboard():
    if not _logado():
        return redirect("/login")

    conn = _conectar()
    c = conn.cursor()

    hoje = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes = request.args.get("mes") or mes_atual

    inicio = f"{mes}-01"
    fim    = f"{mes}-31"

    # ── RECEBIDO NO MÊS ──
    c.execute("""
        SELECT SUM(valor) FROM mensalidades
        WHERE status='Pago' AND data_pagamento BETWEEN ? AND ?
    """, (inicio, fim))
    recebido_mes = c.fetchone()[0] or 0

    # ── A RECEBER ──
    c.execute("""
        SELECT SUM(valor) FROM mensalidades
        WHERE status='Pendente' AND vencimento BETWEEN ? AND ?
    """, (inicio, fim))
    a_receber_mes = c.fetchone()[0] or 0

    # ── ATRASO ──
    c.execute("""
        SELECT SUM(valor) FROM mensalidades
        WHERE status='Pendente' AND vencimento < ?
    """, (inicio,))
    total_atraso = c.fetchone()[0] or 0

    # ── INADIMPLENTES ──
    c.execute("""
        SELECT COUNT(DISTINCT aluno_id) FROM mensalidades
        WHERE status='Pendente' AND vencimento < ?
    """, (inicio,))
    inadimplentes = c.fetchone()[0] or 0

    # ── ALUNOS ATIVOS ──
    c.execute("SELECT COUNT(*) FROM alunos WHERE status='Ativo'")
    alunos_ativos = c.fetchone()[0] or 0

    # ── MATRÍCULAS NO MÊS ──
    inicio_base = "2026-01-01"
    c.execute("""
        SELECT COUNT(*) FROM matriculas
        WHERE data_matricula BETWEEN ? AND ? AND data_matricula >= ?
    """, (inicio, fim, inicio_base))
    matriculas_mes = c.fetchone()[0] or 0

    # ── VENCENDO NO MÊS ──
    c.execute("""
        SELECT COUNT(*) FROM mensalidades
        WHERE status='Pendente' AND vencimento BETWEEN ? AND ?
    """, (inicio, fim))
    vencendo = c.fetchone()[0] or 0

    # ── MATRÍCULAS FUTURAS ──
    c.execute("""
        SELECT SUM(valor) FROM mensalidades
        WHERE status='Pendente' AND tipo='Matrícula'
    """)
    matriculas_futuras = c.fetchone()[0] or 0

    # ── RECEBIMENTO DE MATRÍCULAS NO MÊS ──
    c.execute("""
        SELECT SUM(valor) FROM mensalidades
        WHERE status='Pago' AND tipo='Matrícula'
        AND data_pagamento BETWEEN ? AND ?
    """, (inicio, fim))
    recebimento_matricula = c.fetchone()[0] or 0

    # ── DESPESAS DO MÊS ──
    c.execute("""
        SELECT SUM(valor) FROM despesas
        WHERE recorrente = 0 AND data BETWEEN ? AND ?
    """, (inicio, fim))
    variaveis = c.fetchone()[0] or 0

    c.execute("SELECT valor, dia_vencimento, data FROM despesas WHERE recorrente = 1")
    fixas = 0
    for valor, dia, data_inicio in c.fetchall():
        if not dia:
            continue
        if str(data_inicio)[:7] <= mes:
            try:
                fixas += float(valor or 0)
            except:
                continue
    despesas_mes = variaveis + fixas

    # ── LUCRO ──
    lucro_liquido = recebido_mes - despesas_mes
    margem_lucro  = (lucro_liquido / recebido_mes * 100) if recebido_mes > 0 else 0

    # ── INDICADORES ──
    receita_projetada  = recebido_mes + a_receber_mes
    ticket_medio       = recebido_mes / alunos_ativos if alunos_ativos > 0 else 0
    total_carteira     = a_receber_mes + total_atraso
    taxa_inadimplencia = (total_atraso / total_carteira * 100) if total_carteira > 0 else 0

    c.execute("SELECT COUNT(*) FROM alunos WHERE LOWER(status) = 'cancelado'")
    cancelamentos = c.fetchone()[0] or 0

    receita_media = recebido_mes / matriculas_mes if matriculas_mes > 0 else 0
    meta_mensal   = alunos_ativos * 200
    total_alunos  = alunos_ativos + cancelamentos
    taxa_evasao   = (cancelamentos / total_alunos * 100) if total_alunos > 0 else 0

    # ── GRÁFICO RECEITA x DESPESA ──
    grafico_financeiro = [
        ("Receita",  recebido_mes),
        ("Despesas", despesas_mes),
        ("Lucro",    lucro_liquido if lucro_liquido > 0 else 0),
    ]

    # ── GRÁFICO RECEITA MENSAL (JAN–MÊS ATUAL) ──
    meses   = []
    valores = []
    meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]

    for m in range(1, hoje.month + 1):
        ini_m = f"{hoje.year}-{m:02d}-01"
        fim_m = f"{hoje.year}-{m:02d}-31"
        c.execute("""
            SELECT SUM(valor) FROM mensalidades
            WHERE status='Pago' AND data_pagamento BETWEEN ? AND ?
        """, (ini_m, fim_m))
        total = c.fetchone()[0] or 0
        meses.append(f"{meses_pt[m-1]}/{str(hoje.year)[2:]}")
        valores.append(total)

    # ── RANKING DE CURSOS ──
    c.execute("""
        SELECT c.nome, SUM(m.valor) as total
        FROM mensalidades m
        JOIN matriculas mat ON mat.aluno_id = m.aluno_id
        JOIN cursos c ON c.id = mat.curso_id
        WHERE m.status = 'Pago' AND m.data_pagamento BETWEEN ? AND ?
        GROUP BY c.nome
        ORDER BY total DESC
        LIMIT 5
    """, (inicio, fim))
    ranking_cursos = c.fetchall()

    # ── VENDAS POR TIPO ──
    c.execute("""
        SELECT COALESCE(tipo_curso, 'Não definido'), COUNT(*)
        FROM matriculas WHERE status = 'ATIVA'
        GROUP BY tipo_curso
    """)
    vendas_tipo = c.fetchall()

    # ── ANÁLISE COMERCIAL (RELATÓRIO) ──
    rel            = _buscar_relatorio_mes(mes)
    rel_meta       = rel["meta"]
    rel_realizado  = rel["realizado"]
    rel_matriculas = rel["matriculas"]
    rel_vendas     = rel["vendas"]

    conn.close()

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
        meses=meses,
        valores=valores,
        ranking_cursos=ranking_cursos,
        vendas_tipo=vendas_tipo,
        recebimento_matricula=recebimento_matricula,
        rel_meta=rel_meta,
        rel_realizado=rel_realizado,
        rel_matriculas=rel_matriculas,
        rel_vendas=rel_vendas,
    )


# ── SALVAR RELATÓRIO (API JSON) ──
@dashboard_bp.route("/salvar_relatorio", methods=["POST"])
def salvar_relatorio():
    dados = request.get_json()
    conn  = _conectar()
    c     = conn.cursor()
    c.execute("""
        INSERT INTO relatorios (mes, meta, realizado, matriculas, matriculas_venda)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(mes) DO UPDATE SET
            meta=excluded.meta,
            realizado=excluded.realizado,
            matriculas=excluded.matriculas,
            matriculas_venda=excluded.matriculas_venda
    """, (
        dados.get("mes"), dados.get("meta"), dados.get("realizado"),
        dados.get("matriculas"), dados.get("matriculas_venda")
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ── CARREGAR RELATÓRIO ──
@dashboard_bp.route("/carregar_relatorio/<mes>")
def carregar_relatorio(mes):
    conn = _conectar()
    c    = conn.cursor()
    c.execute("""
        SELECT meta, realizado, matriculas, matriculas_venda
        FROM relatorios WHERE mes=?
    """, (mes,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({"meta": row[0], "realizado": row[1],
                        "matriculas": row[2], "matriculas_venda": row[3]})
    return jsonify({})


# ── RELATÓRIO TRIMESTRAL ──
@dashboard_bp.route("/relatorio_trimestre/<ano>/<tri>")
def relatorio_trimestre(ano, tri):
    meses_tri = {"1":["01","02","03"],"2":["04","05","06"],
                 "3":["07","08","09"],"4":["10","11","12"]}
    lista = [f"{ano}-{m}" for m in meses_tri[tri]]
    conn  = _conectar()
    c     = conn.cursor()
    totais = {"meta":0,"realizado":0,"matriculas":0,"matriculas_venda":0}
    for mes in lista:
        c.execute("""
            SELECT meta, realizado, matriculas, matriculas_venda
            FROM relatorios WHERE mes=?
        """, (mes,))
        row = c.fetchone()
        if row:
            totais["meta"]            += row[0] or 0
            totais["realizado"]       += row[1] or 0
            totais["matriculas"]      += row[2] or 0
            totais["matriculas_venda"]+= row[3] or 0
    conn.close()
    return jsonify(totais)
