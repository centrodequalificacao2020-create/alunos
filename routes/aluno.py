from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, flash, jsonify, session, url_for
from db import db
from models import Aluno, Curso, Mensalidade, Matricula
from security import login_required, verificar_senha, hash_senha
from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError


aluno_bp = Blueprint("aluno", __name__)


def _cpf_limpo(cpf: str) -> str:
    return (cpf or "").replace(".", "").replace("-", "").replace(" ", "").strip()


def _get_acesso(aluno_id, curso_id):
    """Busca registro de acesso ao conteudo. Retorna None se tabela nao existir."""
    try:
        from models import AcessoConteudoCurso
        return AcessoConteudoCurso.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id
        ).first()
    except OperationalError:
        return None


def _toggle_acesso(aluno_id, curso_id, acao, admin_nome):
    """Cria/atualiza registro de acesso. Retorna False se tabela nao existir."""
    try:
        from models import AcessoConteudoCurso
        acesso = AcessoConteudoCurso.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id
        ).first()
        if acesso is None:
            acesso = AcessoConteudoCurso(aluno_id=aluno_id, curso_id=curso_id)
            db.session.add(acesso)
        acesso.liberado     = 1 if acao == "liberar" else 0
        acesso.liberado_por = admin_nome
        acesso.liberado_em  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()
        return True
    except OperationalError:
        db.session.rollback()
        return False


def _contagens_globais():
    """Retorna dict com totais reais do banco, independente de paginacao ou filtro."""
    hoje = date.today().isoformat()

    rows = (
        db.session.query(Aluno.status, func.count(Aluno.id))
        .group_by(Aluno.status)
        .all()
    )
    por_status = {r[0]: r[1] for r in rows}

    inadimplentes_ids = {
        r[0] for r in db.session.query(Mensalidade.aluno_id.distinct())
        .filter(Mensalidade.status == "Pendente", Mensalidade.vencimento < hoje).all()
    }

    return {
        "cnt_ativos":      por_status.get("Ativo", 0),
        "cnt_trancados":   por_status.get("Trancado", 0),
        "cnt_cancelados":  por_status.get("Cancelado", 0),
        "cnt_finalizados": por_status.get("Finalizado", 0),
        "inadimplentes":   len(inadimplentes_ids),
        "inadimplentes_ids": inadimplentes_ids,
    }


@aluno_bp.route("/cadastro", methods=["GET", "POST"])
@login_required
def cadastro():
    if request.method == "POST":
        f   = request.form
        cpf = _cpf_limpo(f.get("cpf", ""))

        if cpf:
            existente = Aluno.query.filter(
                func.replace(func.replace(func.replace(Aluno.cpf, ".", ""), "-", ""), " ", "") == cpf
            ).first()
            if existente:
                flash(f"CPF já cadastrado para o aluno \u201c{existente.nome}\u201d.", "erro")
                c = _contagens_globais()
                paginacao = Aluno.query.order_by(Aluno.nome).paginate(page=1, per_page=20, error_out=False)
                for a in paginacao.items:
                    a.inadimplente = "true" if a.id in c["inadimplentes_ids"] else "false"
                return render_template("cadastro.html",
                                       alunos=paginacao.items,
                                       cursos=Curso.query.order_by(Curso.nome).all(),
                                       paginacao=paginacao, busca="", status="",
                                       **{k: v for k, v in c.items() if k != "inadimplentes_ids"})

        senha_inicial = cpf or _cpf_limpo(f.get("email", ""))
        if not senha_inicial:
            flash("Informe ao menos o CPF ou e-mail para gerar o acesso ao portal.", "erro")
            return redirect("/cadastro")

        a = Aluno(
            nome                   = f.get("nome"),
            cpf                    = f.get("cpf"),
            rg                     = f.get("rg"),
            data_nascimento        = f.get("data_nascimento") or None,
            telefone               = f.get("telefone"),
            whatsapp               = f.get("whatsapp"),
            telefone_contato       = f.get("telefone_contato"),
            email                  = f.get("email"),
            endereco               = f.get("endereco"),
            status                 = f.get("status", "Ativo"),
            curso_id               = f.get("curso_id") or None,
            responsavel_nome       = f.get("responsavel_nome"),
            responsavel_cpf        = f.get("responsavel_cpf"),
            responsavel_telefone   = f.get("responsavel_telefone"),
            responsavel_parentesco = f.get("responsavel_parentesco"),
            senha                  = hash_senha(senha_inicial),
        )
        db.session.add(a)
        db.session.commit()
        flash(
            f"Aluno cadastrado! Acesso ao portal liberado \u2014 "
            f"senha inicial: {senha_inicial} (CPF sem pontos).",
            "sucesso"
        )
        return redirect("/cadastro")

    page   = request.args.get("page", 1, type=int)
    busca  = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    c = _contagens_globais()
    inadimplentes_ids = c["inadimplentes_ids"]

    query = Aluno.query.order_by(Aluno.nome)
    if busca:
        query = query.filter(
            db.or_(
                Aluno.nome.ilike(f"%{busca}%"),
                Aluno.cpf.like(f"%{busca}%"),
            )
        )
    if status == "Inadimplente":
        query = query.filter(Aluno.id.in_(inadimplentes_ids))
    elif status:
        query = query.filter(Aluno.status == status)

    paginacao = query.paginate(page=page, per_page=20, error_out=False)
    for a in paginacao.items:
        a.inadimplente = "true" if a.id in inadimplentes_ids else "false"

    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("cadastro.html",
                           alunos=paginacao.items, cursos=cursos,
                           paginacao=paginacao, busca=busca, status=status,
                           **{k: v for k, v in c.items() if k != "inadimplentes_ids"})


@aluno_bp.route("/aluno/<int:id>/pendencias")
@login_required
def pendencias_aluno(id):
    pendentes = Mensalidade.query.filter_by(aluno_id=id, status="Pendente").all()
    total     = sum(m.valor or 0 for m in pendentes)
    return jsonify({"total_parcelas": len(pendentes), "total_valor": float(total)})


@aluno_bp.route("/excluir_aluno/<int:id>", methods=["POST"])
@login_required
def excluir_aluno(id):
    from models import Usuario, TurmaAluno, Nota, Frequencia, ProgressoAula
    senha = request.form.get("senha", "")
    user  = db.session.get(Usuario, session.get("usuario_id"))
    if not user or not verificar_senha(senha, user.senha):
        flash("Senha incorreta. Exclusão cancelada.", "erro")
        return redirect("/cadastro")
    a    = db.get_or_404(Aluno, id)
    nome = a.nome
    TurmaAluno.query.filter_by(aluno_id=id).delete()
    Nota.query.filter_by(aluno_id=id).delete()
    Frequencia.query.filter_by(aluno_id=id).delete()
    ProgressoAula.query.filter_by(aluno_id=id).delete()
    Mensalidade.query.filter_by(aluno_id=id).delete()
    Matricula.query.filter_by(aluno_id=id).delete()
    try:
        db.session.execute(
            text("DELETE FROM acesso_conteudo_curso WHERE aluno_id = :aid"),
            {"aid": id}
        )
    except OperationalError:
        db.session.rollback()
    db.session.delete(a)
    db.session.commit()
    flash(f"Aluno \u201c{nome}\u201d excluído com sucesso.", "sucesso")
    return redirect("/cadastro")


@aluno_bp.route("/editar_aluno/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    a = db.get_or_404(Aluno, id)
    if request.method == "POST":
        f   = request.form
        cpf = _cpf_limpo(f.get("cpf", ""))
        if cpf:
            existente = Aluno.query.filter(
                func.replace(func.replace(func.replace(Aluno.cpf, ".", ""), "-", ""), " ", "") == cpf,
                Aluno.id != id
            ).first()
            if existente:
                flash(f"CPF já cadastrado para o aluno \u201c{existente.nome}\u201d.", "erro")
                cursos = Curso.query.order_by(Curso.nome).all()
                return render_template("editar_aluno.html", aluno=a, cursos=cursos)

        a.nome                   = f.get("nome")
        a.cpf                    = f.get("cpf")
        a.rg                     = f.get("rg")
        a.data_nascimento        = f.get("data_nascimento") or None
        a.telefone               = f.get("telefone")
        a.whatsapp               = f.get("whatsapp")
        a.email                  = f.get("email")
        a.endereco               = f.get("endereco")
        a.status                 = f.get("status")
        a.curso_id               = f.get("curso_id") or None
        a.responsavel_nome       = f.get("responsavel_nome")
        a.responsavel_cpf        = f.get("responsavel_cpf")
        a.responsavel_telefone   = f.get("responsavel_telefone")
        a.responsavel_parentesco = f.get("responsavel_parentesco")

        nova_senha = f.get("senha_portal", "").strip()
        confirm    = f.get("senha_portal_confirm", "").strip()
        if nova_senha:
            if nova_senha != confirm:
                flash("As senhas do portal não conferem.", "erro")
                cursos = Curso.query.order_by(Curso.nome).all()
                return render_template("editar_aluno.html", aluno=a, cursos=cursos)
            a.senha = hash_senha(nova_senha)
        if not a.senha:
            fallback = cpf or _cpf_limpo(a.email or "")
            if fallback:
                a.senha = hash_senha(fallback)

        db.session.commit()
        flash("Aluno atualizado.", "sucesso")
        return redirect("/cadastro")

    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("editar_aluno.html", aluno=a, cursos=cursos)


@aluno_bp.route("/aluno/<int:aluno_id>")
@login_required
def ficha_aluno(aluno_id):
    from models import RespostaProva, RespostaExercicio, Prova, Exercicio
    aluno      = db.get_or_404(Aluno, aluno_id)
    matriculas = (
        Matricula.query
        .filter_by(aluno_id=aluno_id)
        .order_by(Matricula.data_matricula.desc())
        .all()
    )
    for m in matriculas:
        curso        = db.session.get(Curso, m.curso_id)
        m.curso_nome = curso.nome if curso else "\u2014"
        m.acesso_conteudo = _get_acesso(aluno_id, m.curso_id)

    ids_ativos = {
        m.curso_id for m in matriculas
        if m.status and m.status.upper() == "ATIVA"
    }
    cursos_disponiveis = [
        c for c in Curso.query.order_by(Curso.nome).all()
        if c.id not in ids_ativos
    ]

    try:
        tentativas_provas = (
            RespostaProva.query
            .filter_by(aluno_id=aluno_id)
            .order_by(RespostaProva.finalizado_em.desc())
            .all()
        )
        for tp in tentativas_provas:
            p = db.session.get(Prova, tp.prova_id)
            tp.prova_titulo = p.titulo if p else f"Prova #{tp.prova_id}"
    except Exception:
        tentativas_provas = []

    try:
        tentativas_exercicios = (
            RespostaExercicio.query
            .filter_by(aluno_id=aluno_id)
            .order_by(RespostaExercicio.finalizado_em.desc())
            .all()
        )
        for te in tentativas_exercicios:
            ex = db.session.get(Exercicio, te.exercicio_id)
            te.exercicio_titulo = ex.titulo if ex else f"Exercício #{te.exercicio_id}"
    except Exception:
        tentativas_exercicios = []

    entregas_atividades = []
    try:
        from models import EntregaAtividade, Atividade
        entregas_atividades = (
            EntregaAtividade.query
            .filter_by(aluno_id=aluno_id)
            .order_by(EntregaAtividade.entregue_em.desc())
            .all()
        )
        for ea in entregas_atividades:
            atv = db.session.get(Atividade, ea.atividade_id)
            ea.atividade_titulo = atv.titulo if atv else f"Atividade #{ea.atividade_id}"
    except Exception:
        entregas_atividades = []

    return render_template(
        "ficha_aluno.html",
        aluno=aluno,
        matriculas=matriculas,
        cursos_disponiveis=cursos_disponiveis,
        tentativas_provas=tentativas_provas,
        tentativas_exercicios=tentativas_exercicios,
        entregas_atividades=entregas_atividades,
    )


@aluno_bp.route("/aluno/<int:aluno_id>/tentativa_prova/<int:resp_id>/excluir", methods=["POST"])
@login_required
def excluir_tentativa_prova(aluno_id, resp_id):
    from models import RespostaProva, RespostaQuestao
    rp = db.get_or_404(RespostaProva, resp_id)
    if rp.aluno_id != aluno_id:
        flash("Operação inválida.", "erro")
        return redirect(f"/aluno/{aluno_id}")
    RespostaQuestao.query.filter_by(resposta_prova_id=resp_id).delete()
    db.session.delete(rp)
    db.session.commit()
    flash("Tentativa de prova excluída.", "sucesso")
    return redirect(f"/aluno/{aluno_id}")


@aluno_bp.route("/aluno/<int:aluno_id>/tentativa_exercicio/<int:resp_id>/excluir", methods=["POST"])
@login_required
def excluir_tentativa_exercicio(aluno_id, resp_id):
    from models import RespostaExercicio, RespostaExercicioQuestao
    re_ = db.get_or_404(RespostaExercicio, resp_id)
    if re_.aluno_id != aluno_id:
        flash("Operação inválida.", "erro")
        return redirect(f"/aluno/{aluno_id}")
    RespostaExercicioQuestao.query.filter_by(resposta_exercicio_id=resp_id).delete()
    db.session.delete(re_)
    db.session.commit()
    flash("Tentativa de exercício excluída.", "sucesso")
    return redirect(f"/aluno/{aluno_id}")


@aluno_bp.route("/aluno/<int:aluno_id>/entrega_atividade/<int:entrega_id>/excluir", methods=["POST"])
@login_required
def excluir_entrega_atividade(aluno_id, entrega_id):
    from models import EntregaAtividade
    ea = db.get_or_404(EntregaAtividade, entrega_id)
    if ea.aluno_id != aluno_id:
        flash("Operação inválida.", "erro")
        return redirect(f"/aluno/{aluno_id}")
    db.session.delete(ea)
    db.session.commit()
    flash("Entrega de atividade excluída.", "sucesso")
    return redirect(f"/aluno/{aluno_id}")


@aluno_bp.route("/aluno/<int:aluno_id>/liberar_acesso", methods=["POST"])
@login_required
def liberar_acesso_conteudo(aluno_id):
    from flask import session as flask_session
    from models import Usuario
    curso_id   = request.form.get("curso_id", type=int)
    acao       = request.form.get("acao", "liberar")
    user       = db.session.get(Usuario, flask_session.get("usuario_id"))
    admin_nome = user.nome if user else "admin"
    ok = _toggle_acesso(aluno_id, curso_id, acao, admin_nome)
    if ok:
        verbo = "liberado" if acao == "liberar" else "bloqueado"
        flash(f"Acesso ao conteúdo {verbo}.", "sucesso")
    else:
        flash("Tabela de acesso não encontrada. Execute a migração pendente.", "erro")
    return redirect(url_for("aluno.ficha_aluno", aluno_id=aluno_id))


@aluno_bp.route("/excluir_matricula/<int:matricula_id>", methods=["POST"])
@login_required
def excluir_matricula(matricula_id):
    m        = db.get_or_404(Matricula, matricula_id)
    aluno_id = m.aluno_id
    curso_id = m.curso_id

    Mensalidade.query.filter_by(aluno_id=aluno_id, curso_id=curso_id).delete()
    try:
        from models import MateriaLiberada
        MateriaLiberada.query.filter_by(aluno_id=aluno_id, curso_id=curso_id).delete()
    except Exception:
        pass
    try:
        db.session.execute(
            text("DELETE FROM acesso_conteudo_curso WHERE aluno_id = :aid AND curso_id = :cid"),
            {"aid": aluno_id, "cid": curso_id}
        )
    except OperationalError:
        db.session.rollback()

    db.session.delete(m)
    db.session.commit()
    flash("Matrícula excluída.", "sucesso")
    return redirect(f"/aluno/{aluno_id}")
