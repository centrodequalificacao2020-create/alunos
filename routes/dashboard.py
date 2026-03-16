from flask import Blueprint, render_template, request, jsonify
from db import db
from models import Mensalidade, Aluno, Despesa, Matricula, Relatorio
from security import login_required
from datetime import date
import sqlalchemy as sa

dashboard_bp = Blueprint("dashboard", __name__)

def _mes_atual():
    return date.today().strftime("%Y-%m")

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    mes = request.args.get("mes", _mes_atual())
    inicio = f"{mes}-01"
    fim    = f"{mes}-31"

    recebido  = db.session.scalar(sa.select(sa.func.sum(Mensalidade.valor)).where(
        Mensalidade.status=="Pago", Mensalidade.data_pagamento.between(inicio, fim))) or 0
    a_receber = db.session.scalar(sa.select(sa.func.sum(Mensalidade.valor)).where(
        Mensalidade.status=="Pendente", Mensalidade.vencimento.between(inicio, fim))) or 0
    despesas  = db.session.scalar(sa.select(sa.func.sum(Despesa.valor)).where(
        Despesa.recorrente==0, Despesa.data.between(inicio, fim))) or 0
    ativos    = Aluno.query.filter_by(status="Ativo").count()
    matriculas_mes = Matricula.query.filter(Matricula.data_matricula.between(inicio, fim)).count()
    lucro     = recebido - despesas

    rel = Relatorio.query.filter_by(mes=mes).first()
    meta      = rel.meta if rel else 0

    return render_template("dashboard.html",
        mes=mes, recebido_mes=recebido, arecebermes=a_receber,
        despesas_mes=despesas, alunos_ativos=ativos,
        matriculas_mes=matriculas_mes, lucro_liquido=lucro,
        margem_lucro=(lucro/recebido*100 if recebido else 0),
        meta_mensal=meta)

@dashboard_bp.route("/api/dashboard_mes")
@login_required
def api_dashboard_mes():
    """Endpoint JSON para gráficos AJAX."""
    mes = request.args.get("mes", _mes_atual())
    inicio, fim = f"{mes}-01", f"{mes}-31"
    recebido = db.session.scalar(sa.select(sa.func.sum(Mensalidade.valor)).where(
        Mensalidade.status=="Pago", Mensalidade.data_pagamento.between(inicio, fim))) or 0
    despesas = db.session.scalar(sa.select(sa.func.sum(Despesa.valor)).where(
        Despesa.recorrente==0, Despesa.data.between(inicio, fim))) or 0
    return jsonify(recebido=recebido, despesas=despesas, lucro=recebido-despesas)

@dashboard_bp.route("/salvar_relatorio", methods=["POST"])
@login_required
def salvar_relatorio():
    dados = request.get_json()
    rel = Relatorio.query.filter_by(mes=dados["mes"]).first()
    if not rel:
        rel = Relatorio(mes=dados["mes"])
        db.session.add(rel)
    rel.meta             = dados.get("meta", 0)
    rel.realizado        = dados.get("realizado", 0)
    rel.matriculas       = dados.get("matriculas", 0)
    rel.matriculas_venda = dados.get("matriculas_venda", 0)
    db.session.commit()
    return jsonify(status="ok")