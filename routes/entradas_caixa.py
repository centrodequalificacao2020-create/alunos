"""Entradas de caixa manuais (sem vínculo com aluno/mensalidade).

Espelha `routes/despesas.py` no lado das entradas. A exclusão é lógica:
o registro nunca é apagado, apenas marcado como cancelado.

O lançamento e o cancelamento acontecem na página dedicada `/entradas-caixa`
(o card "Add. Caixa" do dashboard é um link para ela).
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, flash, session
from db import db
from models import EntradaCaixa
from security import financeiro_required

entradas_bp = Blueprint("entradas_caixa", __name__)

FORMAS = ["Dinheiro", "PIX", "Cartão débito", "Cartão crédito",
          "Transferência", "Outro"]

# Limite defensivo: evita valor absurdo por erro de digitação.
VALOR_MAXIMO = 1_000_000.0


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _usuario() -> str:
    return session.get("usuario_nome") or session.get("usuario") or "Sistema"


def _validar(dados) -> tuple:
    """Valida os campos de uma entrada. Retorna (valores, erro).

    `valores` é None quando há erro; `erro` é None quando está tudo certo.
    """
    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        return None, "Informe uma descrição."
    if len(descricao) > 200:
        return None, "A descrição deve ter no máximo 200 caracteres."

    try:
        valor = float(dados.get("valor") or 0)
    except (ValueError, TypeError):
        return None, "Valor inválido."
    if valor <= 0:
        return None, "O valor deve ser maior que R$ 0,00."
    if valor > VALOR_MAXIMO:
        return None, "Valor acima do limite permitido."

    data_str = (dados.get("data") or "").strip()
    if not data_str:
        return None, "Informe a data da entrada."
    try:
        datetime.strptime(data_str, "%Y-%m-%d")
    except ValueError:
        return None, "Data inválida. Use o formato AAAA-MM-DD."

    forma = (dados.get("forma") or "").strip()
    if forma not in FORMAS:
        forma = "Outro"

    return {
        "descricao": descricao,
        "valor": round(valor, 2),
        "data": data_str,
        "forma": forma,
        "categoria": (dados.get("categoria") or "").strip()[:60] or None,
        "observacao": (dados.get("observacao") or "").strip() or None,
    }, None


def _listar(mes: str = None):
    """Entradas não canceladas, opcionalmente filtradas por mês (YYYY-MM)."""
    q = EntradaCaixa.query.filter(EntradaCaixa.cancelado == 0)
    if mes:
        q = q.filter(EntradaCaixa.data.like(f"{mes}%"))
    return q.order_by(EntradaCaixa.data.desc(), EntradaCaixa.id.desc()).all()


@entradas_bp.route("/entradas-caixa", methods=["GET", "POST"])
@financeiro_required
def entradas_caixa():
    """Listagem (GET) e criação (POST) de entradas manuais."""
    if request.method == "POST":
        valores, erro = _validar(request.form)

        if erro:
            flash(erro, "erro")
            return redirect("/entradas-caixa")

        e = EntradaCaixa(
            descricao  = valores["descricao"],
            valor      = valores["valor"],
            data       = valores["data"],
            forma      = valores["forma"],
            categoria  = valores["categoria"],
            observacao = valores["observacao"],
            criado_em  = _agora(),
            criado_por = _usuario(),
            cancelado  = 0,
        )
        db.session.add(e)
        db.session.commit()

        flash("Entrada de caixa registrada.", "sucesso")
        return redirect("/entradas-caixa")

    # ── GET ────────────────────────────────────────────────────────────
    mes = (request.args.get("mes") or "").strip()
    entradas = _listar(mes)
    total = sum(float(e.valor or 0) for e in entradas)

    return render_template(
        "entradas_caixa.html",
        entradas=entradas,
        total=total,
        mes=mes,
        formas=FORMAS,
    )


@entradas_bp.route("/entradas-caixa/<int:id>/cancelar", methods=["POST"])
@financeiro_required
def cancelar_entrada(id):
    """Cancelamento LÓGICO — o registro permanece no banco para auditoria."""
    e = EntradaCaixa.query.get_or_404(id)

    if e.cancelado:
        flash("Esta entrada já está cancelada.", "erro")
        return redirect("/entradas-caixa")

    motivo = (request.form.get("motivo") or "").strip()[:200] or None

    e.cancelado           = 1
    e.cancelado_em        = _agora()
    e.cancelado_por       = _usuario()
    e.motivo_cancelamento = motivo
    db.session.commit()

    flash("Entrada cancelada.", "sucesso")
    return redirect("/entradas-caixa")
