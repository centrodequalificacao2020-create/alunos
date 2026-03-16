from flask import Blueprint, render_template, request, redirect, flash, session
from db import db
from models import Aluno, Mensalidade, Matricula, Curso
from security import login_required, verificar_senha
from services.pdf_service import gerar_recibo, gerar_carne
from services.matricula_service import criar_matricula
from datetime import date
from flask import send_file, make_response

financeiro_bp = Blueprint("financeiro", __name__)

@financeiro_bp.route("/financeiro")
@login_required
def financeiro():
    alunos   = Aluno.query.filter(Aluno.status.in_(["Ativo","Pré-Matrícula"])).order_by(Aluno.nome).all()
    aluno_id = request.args.get("aluno_id", type=int)
    pendentes, pagas, totais = [], [], {}
    if aluno_id:
        pendentes = Mensalidade.query.filter_by(aluno_id=aluno_id, status="Pendente").order_by(Mensalidade.vencimento).all()
        pagas     = Mensalidade.query.filter_by(aluno_id=aluno_id, status="Pago").order_by(Mensalidade.vencimento).all()
        total_pago   = sum(m.valor for m in pagas)
        total_pagar  = sum(m.valor for m in pendentes)
        totais = dict(total_pago=total_pago, total_pagar=total_pagar, saldo=total_pago-total_pagar)
    return render_template("financeiro.html", alunos=alunos, aluno_id=aluno_id,
                           pendentes=pendentes, pagas=pagas, **totais)

@financeiro_bp.route("/pagar/<int:id>", methods=["GET","POST"])
@login_required
def pagar(id):
    mensalidade = Mensalidade.query.get_or_404(id)
    if request.method == "POST":
        mensalidade.forma_pagamento  = request.form.get("forma")
        mensalidade.data_pagamento   = date.today().isoformat()
        mensalidade.status           = "Pago"
        mensalidade.usuario_pagamento= session.get("usuario_nome", "Sistema")
        db.session.commit()
        flash("Pagamento registrado com sucesso.", "sucesso")
        return redirect(f"/financeiro?aluno_id={mensalidade.aluno_id}")
    return render_template("pagar.html", id=id, aluno_id=mensalidade.aluno_id)

@financeiro_bp.route("/editar_parcela/<int:id>", methods=["GET","POST"])
@login_required
def editar_parcela(id):
    parcela = Mensalidade.query.get_or_404(id)
    if request.method == "POST":
        parcela.valor     = float(request.form.get("valor") or 0)
        parcela.vencimento= request.form.get("vencimento")
        parcela.tipo      = request.form.get("tipo")
        db.session.commit()
        flash("Parcela atualizada.", "sucesso")
        return redirect(f"/financeiro?aluno_id={parcela.aluno_id}")
    return render_template("editar_parcela.html", parcela=parcela)

@financeiro_bp.route("/excluir_parcela/<int:id>/<int:aluno_id>", methods=["POST"])
@login_required
def excluir_parcela(id, aluno_id):
    from models import Usuario
    senha = request.form.get("senha", "")
    user  = Usuario.query.get(session["usuario_id"])
    if not user or not verificar_senha(senha, user.senha):
        flash("Senha incorreta. Exclusão cancelada.", "erro")
        return redirect(f"/financeiro?aluno_id={aluno_id}")
    parcela = Mensalidade.query.get_or_404(id)
    db.session.delete(parcela)
    db.session.commit()
    flash("Parcela excluída.", "sucesso")
    return redirect(f"/financeiro?aluno_id={aluno_id}")

@financeiro_bp.route("/recibo/<int:mensalidade_id>")
@login_required
def recibo(mensalidade_id):
    m = Mensalidade.query.get_or_404(mensalidade_id)
    buf = gerar_recibo(m)
    resp = make_response(buf.read())
    resp.headers["Content-Type"]        = "application/pdf"
    resp.headers["Content-Disposition"] = "inline; filename=recibo.pdf"
    return resp

@financeiro_bp.route("/carne/<int:aluno_id>")
@login_required
def carne(aluno_id):
    aluno    = Aluno.query.get_or_404(aluno_id)
    parcelas = Mensalidade.query.filter_by(aluno_id=aluno_id).order_by(Mensalidade.vencimento).all()
    return send_file(gerar_carne(aluno, parcelas), mimetype="application/pdf")

@financeiro_bp.route("/movimentacao")
@login_required
def movimentacao():
    alunos = Aluno.query.filter(Aluno.status.in_(["Ativo","Pré-Matrícula"])).order_by(Aluno.nome).all()
    cursos = Curso.query.order_by(Curso.nome).all()
    aluno_id   = request.args.get("aluno_id")
    matricula_id = request.args.get("matricula_id")
    return render_template("movimentacao.html", alunos=alunos, cursos=cursos,
                           aluno_id=aluno_id, matricula_id=matricula_id)

@financeiro_bp.route("/salvar_matricula", methods=["POST"])
@login_required
def salvar_matricula():
    matricula_id = criar_matricula(request.form)   # lógica no service
    flash("Matrícula realizada com sucesso.", "sucesso")
    return redirect(f"/movimentacao?matricula_id={matricula_id}")
