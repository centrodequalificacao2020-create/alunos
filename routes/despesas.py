from flask import Blueprint, render_template, request, redirect, flash
from db import db
from models import Despesa
from security import login_required

despesas_bp = Blueprint("despesas", __name__)

@despesas_bp.route("/despesas", methods=["GET","POST"])
@login_required
def despesas():
    if request.method == "POST":
        f = request.form
        d = Despesa(
            descricao      = f.get("descricao"),
            valor          = float(f.get("valor") or 0),
            tipo           = f.get("tipo"),
            categoria      = f.get("categoria"),
            data           = f.get("data"),
            observacao     = f.get("observacao"),
            recorrente     = int(f.get("recorrente") or 0),
            dia_vencimento = int(f.get("dia_vencimento")) if f.get("dia_vencimento") else None,
        )
        db.session.add(d)
        db.session.commit()
        flash("Despesa cadastrada.", "sucesso")
        return redirect("/despesas")
    lista = Despesa.query.order_by(Despesa.data.desc()).all()
    return render_template("despesas.html", despesas=lista)

@despesas_bp.route("/editar_despesa/<int:id>", methods=["GET","POST"])
@login_required
def editar_despesa(id):
    d = Despesa.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        d.descricao  = f.get("descricao")
        d.valor      = float(f.get("valor") or 0)
        d.tipo       = f.get("tipo")
        d.categoria  = f.get("categoria")
        d.data       = f.get("data")
        d.observacao = f.get("observacao")
        db.session.commit()
        flash("Despesa atualizada.", "sucesso")
        return redirect("/despesas")
    return render_template("editar_despesa.html", despesa=d)

@despesas_bp.route("/excluir_despesa/<int:id>")
@login_required
def excluir_despesa(id):
    d = Despesa.query.get_or_404(id)
    db.session.delete(d)
    db.session.commit()
    flash("Despesa excluída.", "sucesso")
    return redirect("/despesas")