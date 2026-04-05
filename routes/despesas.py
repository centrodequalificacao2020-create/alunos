from flask import Blueprint, render_template, request, redirect, flash
from datetime import date
from db import db
from models import Despesa
from security import login_required

despesas_bp = Blueprint("despesas", __name__)


def _mes_str(d: date) -> str:
    """Retorna 'YYYY-MM' de um objeto date."""
    return d.strftime("%Y-%m")


@despesas_bp.route("/despesas", methods=["GET", "POST"])
@login_required
def despesas():
    if request.method == "POST":
        f    = request.form
        tipo = f.get("tipo", "variavel")
        hoje = date.today().isoformat()

        d = Despesa(
            descricao  = f.get("nome", "").strip(),
            valor      = float(f.get("valor") or 0),
            tipo       = tipo,
            data       = hoje,
            observacao = f.get("observacao", ""),
        )

        if tipo == "fixa":
            d.data_inicio  = f.get("data_inicio") or _mes_str(date.today())
            d.data_fim     = f.get("data_fim") or None  # None = vitalícia
            d.recorrente   = 1
        else:
            d.data = f.get("data") or hoje

        db.session.add(d)
        db.session.commit()
        flash("Despesa cadastrada.", "sucesso")
        return redirect("/despesas")

    # ── GET ────────────────────────────────────────────────────────────
    page   = request.args.get("page", 1, type=int)
    busca  = request.args.get("q", "").strip()
    mes    = request.args.get("mes", "").strip()

    fixas     = Despesa.query.filter_by(tipo="fixa").order_by(Despesa.data_inicio).all()
    total_fix = sum(d.valor for d in fixas)

    q_var = Despesa.query.filter(Despesa.tipo != "fixa")

    if busca:
        q_var = q_var.filter(Despesa.descricao.ilike(f"%{busca}%"))
    if mes:
        q_var = q_var.filter(Despesa.data.like(f"{mes}%"))

    q_var      = q_var.order_by(Despesa.data.desc())
    paginacao  = q_var.paginate(page=page, per_page=20, error_out=False)
    variaveis  = paginacao.items
    total_var  = sum(d.valor for d in q_var.all())

    return render_template(
        "despesas.html",
        fixas=fixas,
        variaveis=variaveis,
        paginacao=paginacao,
        total_fix=total_fix,
        total_var=total_var,
        busca=busca,
        mes=mes,
        despesas=fixas + variaveis,
        total=total_fix + total_var,
    )


@despesas_bp.route("/editar_despesa/<int:id>", methods=["GET", "POST"])
@login_required
def editar_despesa(id):
    d = Despesa.query.get_or_404(id)
    if request.method == "POST":
        f    = request.form
        tipo = f.get("tipo", "variavel")
        d.descricao  = f.get("nome", "").strip()
        d.valor      = float(f.get("valor") or 0)
        d.tipo       = tipo
        d.observacao = f.get("observacao", "")
        if tipo == "fixa":
            d.data_inicio = f.get("data_inicio") or d.data_inicio
            # String vazia explicitamente enviada = limpar data_fim (vitalícia)
            d.data_fim    = None if f.get("data_fim") == "" else (f.get("data_fim") or d.data_fim)
            d.recorrente  = 1
        else:
            d.data        = f.get("data") or d.data
            d.data_inicio = None
            d.data_fim    = None
            d.recorrente  = 0
        db.session.commit()
        flash("Despesa atualizada.", "sucesso")
        return redirect("/despesas")
    return render_template("editar_despesa.html", despesa=d)


@despesas_bp.route("/excluir_despesa/<int:id>", methods=["POST"])
@login_required
def excluir_despesa(id):
    d = Despesa.query.get_or_404(id)
    db.session.delete(d)
    db.session.commit()
    flash("Despesa excluída.", "sucesso")
    return redirect("/despesas")
