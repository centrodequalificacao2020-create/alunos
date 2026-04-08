from flask import Blueprint, render_template, request, redirect, flash, session, jsonify
from db import db
from models import Aluno, Mensalidade, Matricula, Curso
from security import login_required, verificar_senha
from services.pdf_service import gerar_recibo, gerar_carne, gerar_pre_matricula
from services.matricula_service import criar_matricula
from datetime import date, datetime
from flask import send_file, make_response
from sqlalchemy import distinct
from enums import StatusMatricula, StatusAluno

financeiro_bp = Blueprint("financeiro", __name__)

# Mapeamento: StatusMatricula -> StatusAluno correspondente
_MATRICULA_PARA_ALUNO = {
    StatusMatricula.ATIVA.value:     StatusAluno.ATIVO.value,
    StatusMatricula.INATIVA.value:   StatusAluno.CANCELADO.value,
    StatusMatricula.TRANCADA.value:  StatusAluno.TRANCADO.value,
    StatusMatricula.CONCLUIDA.value: StatusAluno.FINALIZADO.value,
}


def _tipos_curso():
    rows = db.session.query(distinct(Curso.tipo)).filter(
        Curso.tipo != None, Curso.tipo != ""
    ).order_by(Curso.tipo).all()
    return [r[0] for r in rows]


def _sincronizar_status_aluno(aluno: Aluno):
    """
    Recomputa Aluno.status com base nas matriculas:
    - Se houver qualquer matricula ATIVA  -> Ativo
    - Caso contrario, usa o status da matricula mais recente
    - Se nao houver nenhuma matricula, nao altera
    """
    matriculas = (
        Matricula.query
        .filter_by(aluno_id=aluno.id)
        .order_by(Matricula.id.desc())
        .all()
    )
    if not matriculas:
        return
    tem_ativa = any(
        m.status and m.status.upper() == StatusMatricula.ATIVA.value
        for m in matriculas
    )
    if tem_ativa:
        aluno.status = StatusAluno.ATIVO.value
    else:
        status_mais_recente = matriculas[0].status or StatusMatricula.ATIVA.value
        aluno.status = _MATRICULA_PARA_ALUNO.get(
            status_mais_recente.upper(), StatusAluno.ATIVO.value
        )


@financeiro_bp.route("/matricula/<int:matricula_id>/status", methods=["POST"])
@login_required
def alterar_status_matricula(matricula_id):
    matricula  = db.get_or_404(Matricula, matricula_id)
    novo_status = (request.form.get("status") or "").upper().strip()

    if novo_status not in StatusMatricula.valores():
        flash("Status de matrícula inválido.", "erro")
        return redirect(f"/aluno/{matricula.aluno_id}")

    status_anterior = matricula.status
    matricula.status = novo_status

    aluno = db.session.get(Aluno, matricula.aluno_id)
    if aluno:
        _sincronizar_status_aluno(aluno)

    db.session.commit()

    label = {
        StatusMatricula.ATIVA.value:     "Ativa",
        StatusMatricula.INATIVA.value:   "Inativa",
        StatusMatricula.TRANCADA.value:  "Trancada",
        StatusMatricula.CONCLUIDA.value: "Concluída",
    }.get(novo_status, novo_status)

    flash(
        f"Status da matrícula alterado para '{label}'."
        + (f" Status do aluno atualizado para '{aluno.status}'." if aluno else ""),
        "sucesso"
    )
    return redirect(f"/aluno/{matricula.aluno_id}")


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

        curso_map = {c.id: c.nome for c in Curso.query.all()}
        for m in pendentes + pagas:
            if m.curso_id:
                m.curso_nome = curso_map.get(m.curso_id, "-")
            else:
                m.curso_nome = "-"

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

    if parcela.status == "Pago":
        flash(
            f"Esta parcela já foi registrada como paga "
            f"em {parcela.data_pagamento or 'data desconhecida'}. "
            f"Para corrigir, use Editar Parcela.",
            "erro"
        )
        return redirect(f"/financeiro?aluno_id={parcela.aluno_id}")

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
        try:
            novo_valor = float(request.form.get("valor") or 0)
        except (ValueError, TypeError):
            novo_valor = 0.0

        if novo_valor <= 0:
            flash("O valor da parcela deve ser maior que R$ 0,00.", "erro")
            return render_template("editar_parcela.html", parcela=parcela)

        parcela.valor      = novo_valor
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
        aluno_id = request.form.get("aluno_id", "")
        form_data = request.form.copy()
        form_data = form_data.to_dict()
        form_data["apenas_mensalidade"] = "1"
        try:
            criar_matricula(form_data)
            flash("Parcelas lançadas com sucesso.", "sucesso")
        except ValueError as e:
            flash(str(e), "erro")
        return redirect(f"/financeiro?aluno_id={aluno_id}")

    aluno_id_qs = request.args.get("aluno_id", type=int)

    cursos_do_aluno = []
    if aluno_id_qs:
        mats = (Matricula.query
                .filter_by(aluno_id=aluno_id_qs)
                .filter(db.func.upper(Matricula.status) == "ATIVA")
                .order_by(Matricula.id.desc())
                .all())
        ids_vistos = set()
        for mat in mats:
            if mat.curso_id not in ids_vistos:
                ids_vistos.add(mat.curso_id)
                curso = Curso.query.get(mat.curso_id)
                if curso:
                    cursos_do_aluno.append(curso)

    return render_template("lancar_mensalidade.html",
                           alunos=alunos,
                           cursos=cursos,
                           tipos=tipos,
                           curso_tipo=curso_tipo,
                           aluno_id_qs=aluno_id_qs,
                           cursos_do_aluno=cursos_do_aluno)


@financeiro_bp.route("/api/cursos_ativos_aluno")
@login_required
def api_cursos_ativos_aluno():
    aluno_id = request.args.get("aluno_id", type=int)
    if not aluno_id:
        return jsonify([])

    mats = (Matricula.query
            .filter_by(aluno_id=aluno_id)
            .filter(db.func.upper(Matricula.status) == "ATIVA")
            .order_by(Matricula.id.desc())
            .all())

    ids_vistos = set()
    resultado  = []
    for mat in mats:
        if mat.curso_id not in ids_vistos:
            ids_vistos.add(mat.curso_id)
            curso = Curso.query.get(mat.curso_id)
            if curso:
                resultado.append({"id": curso.id, "nome": curso.nome})

    return jsonify(resultado)


@financeiro_bp.route("/pre_matricula_pdf/<int:aluno_id>", methods=["POST"])
@login_required
def pre_matricula_pdf(aluno_id):
    from flask import current_app
    aluno = db.get_or_404(Aluno, aluno_id)
    f = request.form

    idade = ""
    if aluno.data_nascimento:
        try:
            dn   = date.fromisoformat(str(aluno.data_nascimento))
            hoje = date.today()
            idade = hoje.year - dn.year - ((hoje.month, hoje.day) < (dn.month, dn.day))
        except Exception:
            pass

    def _fmt(s):
        try:
            return date.fromisoformat(s).strftime("%d/%m/%Y")
        except Exception:
            return s or ""

    try:
        taxa        = float(f.get("taxa_matricula") or 0)
        mensalidade = float(f.get("valor_mensalidade") or 0)
        parcelas    = int(f.get("parcelas") or 1)
        val_mat     = float(f.get("valor_material") or 0)
        parc_mat    = int(f.get("parcelas_material") or 1)
    except (ValueError, TypeError):
        flash("Valores financeiros inválidos.", "erro")
        return redirect(f"/aluno/{aluno_id}")

    numero = str(Matricula.query.count() + 1).zfill(4)

    dados = {
        "aluno_nome":                aluno.nome or "",
        "aluno_idade":               idade,
        "aluno_endereco":            aluno.endereco or "",
        "aluno_responsavel":         aluno.responsavel_nome or "",
        "aluno_cpf":                 aluno.cpf or "",
        "aluno_whatsapp":            aluno.telefone or "",   # fix: campo correto é telefone
        "taxa_matricula":            taxa,
        "valor_mensalidade":         mensalidade,
        "parcelas":                  parcelas,
        "material_didatico":         f.get("material_didatico") or "",
        "valor_material":            val_mat,
        "parcelas_material":         parc_mat,
        "data_pagamento_matricula":  _fmt(f.get("data_pagamento_matricula", "")),
        "data_primeira_mensalidade": _fmt(f.get("data_primeira_mensalidade", "")),
        "numero_pre_matricula":      numero,
    }

    buf  = gerar_pre_matricula(dados, root_path=current_app.root_path)
    resp = make_response(buf.read())
    resp.headers["Content-Type"]        = "application/pdf"
    resp.headers["Content-Disposition"] = f"inline; filename=pre_matricula_{aluno_id}.pdf"
    return resp
