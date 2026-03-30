from flask import Blueprint, render_template, request, redirect, flash, session
from db import db
from models import Aluno, Mensalidade, Matricula, Curso
from security import login_required, verificar_senha
from services.pdf_service import gerar_recibo, gerar_carne
from services.matricula_service import criar_matricula
from datetime import date, datetime
from flask import send_file, make_response
from sqlalchemy import distinct

financeiro_bp = Blueprint("financeiro", __name__)


def _tipos_curso():
    rows = db.session.query(distinct(Curso.tipo)).filter(
        Curso.tipo != None, Curso.tipo != ""
    ).order_by(Curso.tipo).all()
    return [r[0] for r in rows]


@financeiro_bp.route("/financeiro")
@login_required
def financeiro():
    alunos   = Aluno.query.order_by(Aluno.nome).all()
    aluno_id = request.args.get("aluno_id", type=int)
    pendentes, pagas = [], []
    total_pago = total_pagar = vencidas_total = 0
    hoje = date.today()

    if aluno_id:
        pendentes = (Mensalidade.query
                     .filter_by(aluno_id=aluno_id, status="Pendente")
                     .order_by(Mensalidade.vencimento)
                     .all())
        pagas     = (Mensalidade.query
                     .filter_by(aluno_id=aluno_id, status="Pago")
                     .order_by(Mensalidade.vencimento)
                     .all())
        total_pago  = sum(m.valor for m in pagas)
        total_pagar = sum(m.valor for m in pendentes)

        def _vencida(m):
            try:
                return datetime.strptime(str(m.vencimento)[:10], "%Y-%m-%d").date() < hoje
            except (ValueError, TypeError):
                return False

        vencidas_total = sum(m.valor for m in pendentes if _vencida(m))

        # Enriquece cada parcela com o nome do curso usando curso_id da própria parcela
        curso_map = {c.id: c.nome for c in Curso.query.all()}
        for m in pendentes + pagas:
            if m.curso_id:
                m.curso_nome = curso_map.get(m.curso_id, "-")
            else:
                # Fallback: matrícula mais recente (parcelas antigas sem curso_id)
                mat = (Matricula.query
                       .filter_by(aluno_id=aluno_id)
                       .order_by(Matricula.id.desc())
                       .first())
                m.curso_nome = curso_map.get(mat.curso_id, "-") if mat else "-"

    return render_template("financeiro.html",
                           alunos=alunos,
                           aluno_id=aluno_id,
                           pendentes=pendentes,
                           pagas=pagas,
                           total_pago=total_pago,
                           total_pagar=total_pagar,
                           vencidas_total=vencidas_total,
                           hoje=hoje)


@financeiro_bp.route("/pagar/<int:id>", methods=["GET", "POST"])
@login_required
def pagar(id):
    parcela = Mensalidade.query.get_or_404(id)
    if request.method == "POST":
        parcela.forma_pagamento   = request.form.get("forma")
        parcela.data_pagamento    = request.form.get("data_pagamento") or date.today().isoformat()
        parcela.status            = "Pago"
        parcela.usuario_pagamento = session.get("usuario_nome", "Sistema")
        db.session.commit()
        flash("Pagamento registrado com sucesso.", "sucesso")
        return redirect(f"/financeiro?aluno_id={parcela.aluno_id}")
    return render_template("pagar.html", parcela=parcela, aluno_id=parcela.aluno_id)


@financeiro_bp.route("/editar_parcela/<int:id>", methods=["GET", "POST"])
@login_required
def editar_parcela(id):
    parcela = Mensalidade.query.get_or_404(id)
    if request.method == "POST":
        parcela.valor      = float(request.form.get("valor") or 0)
        parcela.vencimento = request.form.get("vencimento")
        parcela.tipo       = request.form.get("tipo")
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
    m    = Mensalidade.query.get_or_404(mensalidade_id)
    buf  = gerar_recibo(m)
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
    alunos = Aluno.query.filter(Aluno.status.in_(["Ativo", "Pré-Matrícula"])).order_by(Aluno.nome).all()
    cursos = Curso.query.order_by(Curso.nome).all()
    tipos  = _tipos_curso()
    aluno_id     = request.args.get("aluno_id")
    matricula_id = request.args.get("matricula_id")
    curso_tipo   = {c.id: (c.tipo or "") for c in cursos}
    return render_template("movimentacao.html",
                           alunos=alunos, cursos=cursos, tipos=tipos,
                           curso_tipo=curso_tipo,
                           aluno_id=aluno_id, matricula_id=matricula_id)


@financeiro_bp.route("/salvar_matricula", methods=["POST"])
@login_required
def salvar_matricula():
    try:
        matricula_id = criar_matricula(request.form)
        flash("Matrícula realizada com sucesso.", "sucesso")
        return redirect(f"/movimentacao?matricula_id={matricula_id}")
    except ValueError as e:
        flash(str(e), "erro")
        return redirect("/movimentacao")


@financeiro_bp.route("/lancar_mensalidade", methods=["GET", "POST"])
@login_required
def lancar_mensalidade():
    """Lança parcelas avulsas sem criar nova matrícula."""
    alunos = Aluno.query.filter(Aluno.status.in_(["Ativo", "Pré-Matrícula"])).order_by(Aluno.nome).all()
    cursos = Curso.query.order_by(Curso.nome).all()
    tipos  = _tipos_curso()
    curso_tipo = {c.id: (c.tipo or "") for c in cursos}

    if request.method == "POST":
        # Injeta flag para o service não criar matrícula
        data = request.form.copy()
        # ImmutableMultiDict → dict mutável
        from werkzeug.datastructures import ImmutableMultiDict
        mutable = data.to_dict(flat=False)
        mutable["apenas_mensalidade"] = ["1"]
        mutable["valor_matricula"]    = ["0"]  # não gera parcela de matrícula
        try:
            criar_matricula(ImmutableMultiDict(mutable))
            flash("Parcelas lançadas com sucesso.", "sucesso")
        except ValueError as e:
            flash(str(e), "erro")
        aluno_id = request.form.get("aluno_id", "")
        return redirect(f"/financeiro?aluno_id={aluno_id}")

    return render_template("lancar_mensalidade.html",
                           alunos=alunos, cursos=cursos, tipos=tipos,
                           curso_tipo=curso_tipo)
