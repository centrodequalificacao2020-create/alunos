import os
from flask import (Blueprint, render_template, request,
                   redirect, flash, send_file, current_app, jsonify)
from db import db
from models import (Aluno, Curso, Materia, CursoMateria,
                    Nota, Frequencia, Turma, TurmaAluno)
from security import login_required
from services.pdf_service import (
    gerar_boletim_notas, gerar_historico_frequencia,
    gerar_declaracao_conclusao
)
from services.notas_service import (
    get_materias_do_curso, get_notas_map, get_boletim,
    salvar_notas, get_curso_ativo_do_aluno
)
from services.matricula_service import (
    get_matricula_ativa, get_cursos_matriculados_ativos
)
from services.frequencia_service import (
    registrar_frequencia, get_historico, calcular_percentual
)
from datetime import date
from sqlalchemy import distinct

academico_bp = Blueprint("academico", __name__)


def _tipos_curso():
    rows = db.session.query(distinct(Curso.tipo)).filter(
        Curso.tipo != None, Curso.tipo != ""
    ).order_by(Curso.tipo).all()
    return [r[0] for r in rows]


# ──────────────────────────── TURMAS ────────────────────────────

@academico_bp.route("/turmas")
@login_required
def turmas():
    lista  = Turma.query.order_by(Turma.nome).all()
    cursos = Curso.query.order_by(Curso.nome).all()
    tipos  = _tipos_curso()
    return render_template("turmas.html", turmas=lista, cursos=cursos, tipos=tipos)


@academico_bp.route("/turmas/criar", methods=["POST"])
@login_required
def criar_turma():
    nome       = request.form["nome"].strip()
    modalidade = request.form["modalidade"]
    tipo       = request.form["tipo"]
    curso_id   = request.form.get("curso_id") or None
    if not nome or not modalidade or not tipo:
        flash("Preencha nome, modalidade e tipo.", "erro")
        return redirect("/turmas")
    t = Turma(nome=nome, modalidade=modalidade, tipo=tipo, curso_id=curso_id)
    db.session.add(t)
    db.session.commit()
    flash(f"Turma '{nome}' criada com sucesso!", "sucesso")
    return redirect("/turmas")


@academico_bp.route("/turmas/<int:turma_id>/editar", methods=["GET", "POST"])
@login_required
def editar_turma(turma_id):
    turma  = Turma.query.get_or_404(turma_id)
    cursos = Curso.query.order_by(Curso.nome).all()
    tipos  = _tipos_curso()
    if request.method == "POST":
        turma.nome       = request.form["nome"].strip()
        turma.modalidade = request.form["modalidade"]
        turma.tipo       = request.form["tipo"]
        turma.curso_id   = request.form.get("curso_id") or None
        db.session.commit()
        flash("Turma atualizada!", "sucesso")
        return redirect("/turmas")
    ids_na_turma = {ta.aluno_id for ta in turma.alunos}
    alunos_disponiveis = (
        Aluno.query
        .filter(Aluno.status == "Ativo")
        .filter(~Aluno.id.in_(ids_na_turma))
        .order_by(Aluno.nome).all()
    )
    return render_template("editar_turma.html",
                           turma=turma,
                           cursos=cursos,
                           tipos=tipos,
                           alunos_disponiveis=alunos_disponiveis)


@academico_bp.route("/turmas/<int:turma_id>/excluir", methods=["POST"])
@login_required
def excluir_turma(turma_id):
    turma = Turma.query.get_or_404(turma_id)
    db.session.delete(turma)
    db.session.commit()
    flash("Turma exclu\u00edda.", "sucesso")
    return redirect("/turmas")


@academico_bp.route("/turmas/<int:turma_id>/alunos/adicionar", methods=["POST"])
@login_required
def adicionar_aluno_turma(turma_id):
    Turma.query.get_or_404(turma_id)
    aluno_id = request.form.get("aluno_id", type=int)
    if not aluno_id:
        flash("Selecione um aluno.", "erro")
        return redirect(f"/turmas/{turma_id}/editar")
    if TurmaAluno.query.filter_by(turma_id=turma_id, aluno_id=aluno_id).first():
        flash("Aluno j\u00e1 est\u00e1 nesta turma.", "erro")
        return redirect(f"/turmas/{turma_id}/editar")
    db.session.add(TurmaAluno(turma_id=turma_id, aluno_id=aluno_id))
    db.session.commit()
    flash("Aluno adicionado \u00e0 turma!", "sucesso")
    return redirect(f"/turmas/{turma_id}/editar")


@academico_bp.route("/turmas/<int:turma_id>/alunos/<int:aluno_id>/remover",
                    methods=["POST"])
@login_required
def remover_aluno_turma(turma_id, aluno_id):
    ta = TurmaAluno.query.filter_by(
        turma_id=turma_id, aluno_id=aluno_id).first_or_404()
    db.session.delete(ta)
    db.session.commit()
    flash("Aluno removido da turma.", "sucesso")
    return redirect(f"/turmas/{turma_id}/editar")


# ────────────────────────── MATÉRIAS ──────────────────────────

@academico_bp.route("/materias", methods=["GET", "POST"])
@login_required
def materias():
    cursos = Curso.query.order_by(Curso.nome).all()
    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "criar":
            nome     = request.form["nome"].strip()
            curso_id = request.form.get("curso_id")
            if nome and curso_id:
                m = Materia(nome=nome, curso_id=curso_id, ativa=1)
                db.session.add(m)
                db.session.flush()
                existe = CursoMateria.query.filter_by(
                    curso_id=curso_id, materia_id=m.id).first()
                if not existe:
                    db.session.add(CursoMateria(curso_id=curso_id, materia_id=m.id))
                db.session.commit()
                flash("Mat\u00e9ria cadastrada!", "sucesso")
            else:
                flash("Preencha nome e curso.", "erro")
        elif acao == "editar":
            mid  = request.form.get("materia_id", type=int)
            nome = request.form["novo_nome"].strip()
            m    = Materia.query.get_or_404(mid)
            if nome:
                m.nome = nome
                db.session.commit()
                flash("Mat\u00e9ria atualizada!", "sucesso")
        elif acao == "excluir":
            mid = request.form.get("materia_id", type=int)
            m   = Materia.query.get_or_404(mid)
            m.ativa = 0
            CursoMateria.query.filter_by(materia_id=mid).delete()
            db.session.commit()
            flash("Mat\u00e9ria exclu\u00edda!", "sucesso")
        return redirect("/materias")
    materias_por_curso = {
        (c.id, c.nome): Materia.query.filter_by(curso_id=c.id, ativa=1)
                                      .order_by(Materia.nome).all()
        for c in cursos
    }
    return render_template("materias.html", cursos=cursos,
                           materias_por_curso=materias_por_curso)


# ─────────────────────────── NOTAS ───────────────────────────

@academico_bp.route("/notas", methods=["GET", "POST"])
@login_required
def notas():
    termo    = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)
    alunos = cursos_matriculados = materias_lista = []
    notas_existentes = {}
    aluno_nome = ""

    if termo:
        alunos = Aluno.query.filter(
            Aluno.nome.ilike(f"%{termo}%")
        ).order_by(Aluno.nome).all()

    if aluno_id:
        aluno = Aluno.query.get(aluno_id)
        if aluno:
            aluno_nome = aluno.nome
        cursos_matriculados = (
            Curso.query.join(Curso.matriculas)
            .filter_by(aluno_id=aluno_id).order_by(Curso.nome).all()
        )

    if aluno_id and curso_id:
        materias_lista   = get_materias_do_curso(curso_id)
        notas_existentes = get_notas_map(aluno_id, curso_id)

    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        curso_id = request.form.get("curso_id", type=int)
        salvar_notas(aluno_id, curso_id, request.form)
        flash("Notas salvas!", "sucesso")
        return redirect(f"/notas?aluno_id={aluno_id}&curso_id={curso_id}")

    return render_template("notas.html",
                           alunos=alunos, termo=termo,
                           aluno_id=aluno_id, aluno_nome=aluno_nome,
                           cursos_matriculados=cursos_matriculados,
                           curso_id=curso_id, materias=materias_lista,
                           notas_existentes=notas_existentes)


@academico_bp.route("/notas_visualizar/<int:aluno_id>")
@login_required
def notas_visualizar(aluno_id):
    curso_id = request.args.get("curso_id", type=int)
    aluno    = Aluno.query.get_or_404(aluno_id)
    if not curso_id:
        curso_id = get_curso_ativo_do_aluno(aluno_id)
    curso      = Curso.query.get(curso_id) if curso_id else None
    curso_nome = curso.nome if curso else ""
    boletim    = get_boletim(aluno_id, curso_id) if curso_id else []
    return render_template("notas_visualizar.html",
                           aluno_nome=aluno.nome,
                           curso_nome=curso_nome,
                           boletim=boletim)


# ───────────────────────── FREQUÊNCIA ─────────────────────────

@academico_bp.route("/frequencia", methods=["GET", "POST"])
@login_required
def frequencia():
    termo    = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)
    alunos = cursos_matriculados = []
    aluno_nome        = None
    curso_id          = None
    aluno_frequencias = []
    percentual        = 0.0

    if termo:
        alunos = Aluno.query.filter(
            Aluno.nome.ilike(f"%{termo}%")
        ).order_by(Aluno.nome).all()

    if aluno_id:
        aluno = Aluno.query.get(aluno_id)
        if aluno:
            aluno_nome = aluno.nome
        cursos_matriculados = get_cursos_matriculados_ativos(aluno_id)
        aluno_frequencias   = get_historico(aluno_id)
        if aluno_frequencias:
            curso_id = aluno_frequencias[0].curso_id
            percentual = calcular_percentual(aluno_id, curso_id)

    if request.method == "POST":
        aluno_id  = request.form.get("aluno_id", type=int)
        curso_id  = request.form.get("curso_id",  type=int)
        data_aula = request.form.get("data")
        status    = request.form.get("status")
        if aluno_id and curso_id and data_aula and status:
            try:
                registrar_frequencia(aluno_id, curso_id, data_aula, status)
                flash("Frequ\u00eancia salva!", "sucesso")
            except ValueError as e:
                flash(str(e), "erro")
                return redirect(
                    f"/frequencia?aluno_id={aluno_id}&curso_id={curso_id}")
            return redirect(
                f"/frequencia?aluno_id={aluno_id}&curso_id={curso_id}&data={data_aula}")

    return render_template("frequencia.html",
                           alunos=alunos, aluno_id=aluno_id,
                           aluno_nome=aluno_nome,
                           cursos_matriculados=cursos_matriculados,
                           curso_id=curso_id, termo=termo,
                           aluno_frequencias=aluno_frequencias,
                           percentual=percentual)


@academico_bp.route("/frequencia/<int:freq_id>/excluir", methods=["POST"])
@login_required
def excluir_frequencia(freq_id):
    f        = Frequencia.query.get_or_404(freq_id)
    aluno_id = f.aluno_id
    curso_id = f.curso_id
    db.session.delete(f)
    db.session.commit()
    flash("Registro de frequ\u00eancia removido.", "sucesso")
    return redirect(f"/frequencia?aluno_id={aluno_id}&curso_id={curso_id}")


@academico_bp.route("/frequencia/excluir_tudo", methods=["POST"])
@login_required
def excluir_frequencia_tudo():
    aluno_id = request.form.get("aluno_id", type=int)
    curso_id = request.form.get("curso_id", type=int)
    if not aluno_id or not curso_id:
        flash("Dados inv\u00e1lidos.", "erro")
        return redirect("/frequencia")
    total = Frequencia.query.filter_by(aluno_id=aluno_id, curso_id=curso_id).delete()
    db.session.commit()
    flash(f"{total} registro(s) de frequ\u00eancia removido(s).", "sucesso")
    return redirect(f"/frequencia?aluno_id={aluno_id}")


@academico_bp.route("/frequencia_historico")
@login_required
def frequencia_historico():
    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)
    aluno = curso = None
    historico  = []
    percentual = 0.0
    if aluno_id and curso_id:
        aluno      = Aluno.query.get(aluno_id)
        curso      = Curso.query.get(curso_id)
        historico  = get_historico(aluno_id, curso_id)
        percentual = calcular_percentual(aluno_id, curso_id)
    return render_template("frequencia_historico.html",
                           aluno=aluno, curso=curso,
                           historico=historico,
                           percentual=percentual)


# ─────────────────────────── PDFs ───────────────────────────

@academico_bp.route("/notas_pdf/<int:aluno_id>/<int:curso_id>")
@login_required
def notas_pdf(aluno_id, curso_id):
    aluno     = Aluno.query.get_or_404(aluno_id)
    curso     = Curso.query.get_or_404(curso_id)
    mats      = get_materias_do_curso(curso_id)
    notas_map = get_notas_map(aluno_id, curso_id)
    buf = gerar_boletim_notas(aluno, curso, mats, notas_map,
                               root_path=current_app.root_path)
    return send_file(buf, as_attachment=True,
                     download_name="boletim_notas.pdf",
                     mimetype="application/pdf")


@academico_bp.route("/frequencia_historico_pdf/<int:aluno_id>/<int:curso_id>")
@login_required
def frequencia_historico_pdf(aluno_id, curso_id):
    aluno     = Aluno.query.get_or_404(aluno_id)
    curso     = Curso.query.get_or_404(curso_id)
    historico = get_historico(aluno_id, curso_id)
    buf = gerar_historico_frequencia(aluno, curso, historico,
                                     root_path=current_app.root_path)
    return send_file(buf, as_attachment=True,
                     download_name="historico_frequencia.pdf",
                     mimetype="application/pdf")


@academico_bp.route("/declaracao_conclusao_pdf/<int:aluno_id>/<int:curso_id>")
@login_required
def declaracao_conclusao_pdf(aluno_id, curso_id):
    """Gera declara\u00e7\u00e3o de conclus\u00e3o.
    Query params opcionais:
      - modalidade: EAD (padr\u00e3o) ou Presencial
      - parceiro_nome: nome da institui\u00e7\u00e3o parceira
      - parceiro_cnpj: CNPJ da institui\u00e7\u00e3o parceira
    """
    aluno          = Aluno.query.get_or_404(aluno_id)
    curso          = Curso.query.get_or_404(curso_id)
    modalidade     = request.args.get("modalidade", "EAD")
    parceiro_nome  = request.args.get("parceiro_nome", "")
    parceiro_cnpj  = request.args.get("parceiro_cnpj", "")
    buf = gerar_declaracao_conclusao(
        aluno, curso,
        modalidade=modalidade,
        parceiro_nome=parceiro_nome,
        parceiro_cnpj=parceiro_cnpj,
        root_path=current_app.root_path
    )
    nome_arquivo = f"declaracao_{aluno.nome.split()[0].lower()}_{aluno_id}.pdf"
    return send_file(buf, as_attachment=True,
                     download_name=nome_arquivo,
                     mimetype="application/pdf")


# NOTA: a rota /backup foi removida deste blueprint.
# O backup do banco de dados \u00e9 feito exclusivamente via routes/backup.py
# com @admin_required, evitando acesso n\u00e3o autorizado.
