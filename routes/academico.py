from flask import (Blueprint, render_template, request,
                   redirect, flash, send_file)
from db import db
from models import (Aluno, Curso, Materia, CursoMateria,
                    Conteudo, Nota, Frequencia, Turma, TurmaAluno)
from security import login_required
import io
import os
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

academico_bp = Blueprint("academico", __name__)


# ───────────────────────── TURMAS ─────────────────────────

@academico_bp.route("/turmas")
@login_required
def turmas():
    lista = Turma.query.order_by(Turma.nome).all()
    cursos = Curso.query.order_by(Curso.nome).all()
    return render_template("turmas.html", turmas=lista, cursos=cursos)


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
    if request.method == "POST":
        turma.nome       = request.form["nome"].strip()
        turma.modalidade = request.form["modalidade"]
        turma.tipo       = request.form["tipo"]
        turma.curso_id   = request.form.get("curso_id") or None
        db.session.commit()
        flash("Turma atualizada!", "sucesso")
        return redirect("/turmas")
    return render_template("editar_turma.html", turma=turma, cursos=cursos)


@academico_bp.route("/turmas/<int:turma_id>/excluir", methods=["POST"])
@login_required
def excluir_turma(turma_id):
    turma = Turma.query.get_or_404(turma_id)
    db.session.delete(turma)
    db.session.commit()
    flash("Turma excluída.", "sucesso")
    return redirect("/turmas")


@academico_bp.route("/turmas/<int:turma_id>/alunos/adicionar", methods=["POST"])
@login_required
def adicionar_aluno_turma(turma_id):
    Turma.query.get_or_404(turma_id)
    aluno_id = request.form.get("aluno_id", type=int)
    if not aluno_id:
        flash("Selecione um aluno.", "erro")
        return redirect(f"/turmas/{turma_id}/editar")
    existe = TurmaAluno.query.filter_by(
        turma_id=turma_id, aluno_id=aluno_id).first()
    if existe:
        flash("Aluno já está nesta turma.", "erro")
        return redirect(f"/turmas/{turma_id}/editar")
    db.session.add(TurmaAluno(turma_id=turma_id, aluno_id=aluno_id))
    db.session.commit()
    flash("Aluno adicionado à turma!", "sucesso")
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


# ───────────────────────── MATÉRIAS ─────────────────────────

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
                db.session.add(CursoMateria(curso_id=curso_id, materia_id=m.id))
                db.session.commit()
                flash("Matéria cadastrada!", "sucesso")
            else:
                flash("Preencha nome e curso.", "erro")

        elif acao == "editar":
            mid  = request.form.get("materia_id", type=int)
            nome = request.form["novo_nome"].strip()
            m    = Materia.query.get_or_404(mid)
            if nome:
                m.nome = nome
                db.session.commit()
                flash("Matéria atualizada!", "sucesso")

        elif acao == "excluir":
            mid = request.form.get("materia_id", type=int)
            m   = Materia.query.get_or_404(mid)
            m.ativa = 0
            CursoMateria.query.filter_by(materia_id=mid).delete()
            db.session.commit()
            flash("Matéria excluída!", "sucesso")

        return redirect("/materias")

    # Monta dicionário {(curso_id, curso_nome): [matérias]}
    materias_por_curso = {}
    for curso in cursos:
        lista = (Materia.query
                 .filter_by(curso_id=curso.id, ativa=1)
                 .order_by(Materia.nome).all())
        materias_por_curso[(curso.id, curso.nome)] = lista

    return render_template("materias.html",
                           cursos=cursos,
                           materias_por_curso=materias_por_curso)


# ───────────────────────── NOTAS ─────────────────────────

@academico_bp.route("/notas", methods=["GET", "POST"])
@login_required
def notas():
    termo    = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)

    alunos              = []
    cursos_matriculados = []
    materias_lista      = []
    notas_existentes    = {}
    aluno_nome          = ""

    if termo:
        alunos = (Aluno.query
                  .filter(Aluno.nome.ilike(f"%{termo}%"))
                  .order_by(Aluno.nome).all())

    if aluno_id:
        aluno = Aluno.query.get(aluno_id)
        if aluno:
            aluno_nome = aluno.nome
        cursos_matriculados = (
            Curso.query
            .join(Curso.matriculas)
            .filter_by(aluno_id=aluno_id)
            .order_by(Curso.nome).all()
        )

    if aluno_id and curso_id:
        materias_lista = (
            Materia.query
            .join(CursoMateria, CursoMateria.materia_id == Materia.id)
            .filter(CursoMateria.curso_id == curso_id, Materia.ativa == 1)
            .order_by(Materia.nome).all()
        )
        notas_rows = Nota.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id).all()
        notas_existentes = {n.materia_id: n for n in notas_rows}

    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        curso_id = request.form.get("curso_id", type=int)
        mats = (Materia.query
                .join(CursoMateria, CursoMateria.materia_id == Materia.id)
                .filter(CursoMateria.curso_id == curso_id,
                        Materia.ativa == 1).all())
        for m in mats:
            nota_val  = request.form.get(f"nota_{m.id}") or None
            resultado = request.form.get(f"resultado_{m.id}") or None
            nota_obj  = Nota.query.filter_by(
                aluno_id=aluno_id, materia_id=m.id,
                curso_id=curso_id).first()
            if nota_obj:
                nota_obj.nota      = nota_val
                nota_obj.resultado = resultado
            else:
                db.session.add(Nota(
                    aluno_id=aluno_id, materia_id=m.id,
                    curso_id=curso_id, nota=nota_val,
                    resultado=resultado))
        db.session.commit()
        flash("Notas salvas!", "sucesso")
        return redirect(f"/notas?aluno_id={aluno_id}&curso_id={curso_id}")

    return render_template("notas.html",
                           alunos=alunos, termo=termo,
                           aluno_id=aluno_id, aluno_nome=aluno_nome,
                           cursos_matriculados=cursos_matriculados,
                           curso_id=curso_id,
                           materias=materias_lista,
                           notas_existentes=notas_existentes)


@academico_bp.route("/notas_visualizar/<int:aluno_id>")
@login_required
def notas_visualizar(aluno_id):
    curso_id = request.args.get("curso_id", type=int)
    aluno    = Aluno.query.get_or_404(aluno_id)

    if not curso_id:
        mat = aluno.matriculas[-1] if aluno.matriculas else None
        if mat:
            curso_id = mat.curso_id

    curso      = Curso.query.get(curso_id) if curso_id else None
    curso_nome = curso.nome if curso else ""

    boletim = []
    if curso_id:
        mats = (Materia.query
                .join(CursoMateria, CursoMateria.materia_id == Materia.id)
                .filter(CursoMateria.curso_id == curso_id,
                        Materia.ativa == 1)
                .order_by(Materia.nome).all())
        for m in mats:
            n = Nota.query.filter_by(
                aluno_id=aluno_id, materia_id=m.id,
                curso_id=curso_id).first()
            boletim.append({
                "materia":   m.nome,
                "nota":      n.nota      if n else None,
                "resultado": n.resultado if n else None,
            })

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

    alunos              = []
    aluno_nome          = None
    cursos_matriculados = []
    curso_id            = None

    if termo:
        alunos = (Aluno.query
                  .filter(Aluno.nome.ilike(f"%{termo}%"))
                  .order_by(Aluno.nome).all())

    if aluno_id:
        aluno = Aluno.query.get(aluno_id)
        if aluno:
            aluno_nome = aluno.nome
        cursos_matriculados = (
            Curso.query
            .join(Curso.matriculas)
            .filter_by(aluno_id=aluno_id, status="ATIVA")
            .order_by(Curso.nome).all()
        )
        last = (Frequencia.query
                .filter_by(aluno_id=aluno_id)
                .order_by(Frequencia.id.desc()).first())
        if last:
            curso_id = last.curso_id

    if request.method == "POST":
        aluno_id  = request.form.get("aluno_id", type=int)
        curso_id  = request.form.get("curso_id",  type=int)
        data_aula = request.form.get("data")
        status    = request.form.get("status")
        if aluno_id and curso_id and data_aula and status:
            freq = Frequencia.query.filter_by(
                aluno_id=aluno_id, curso_id=curso_id,
                data=data_aula).first()
            if freq:
                freq.status = status
            else:
                db.session.add(Frequencia(
                    aluno_id=aluno_id, curso_id=curso_id,
                    data=data_aula, status=status))
            db.session.commit()
            flash("Frequência salva!", "sucesso")
            return redirect(
                f"/frequencia?aluno_id={aluno_id}&curso_id={curso_id}"
                f"&data={data_aula}")

    return render_template("frequencia.html",
                           alunos=alunos, aluno_id=aluno_id,
                           aluno_nome=aluno_nome,
                           cursos_matriculados=cursos_matriculados,
                           curso_id=curso_id, termo=termo)


@academico_bp.route("/frequencia_historico")
@login_required
def frequencia_historico():
    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)
    aluno = curso = None
    historico = []
    if aluno_id and curso_id:
        aluno    = Aluno.query.get(aluno_id)
        curso    = Curso.query.get(curso_id)
        historico = (Frequencia.query
                     .filter_by(aluno_id=aluno_id, curso_id=curso_id)
                     .order_by(Frequencia.data).all())
    return render_template("frequencia_historico.html",
                           aluno=aluno, curso=curso,
                           historico=historico)


# ───────────────────────── PDFs ─────────────────────────

@academico_bp.route("/notas_pdf/<int:aluno_id>/<int:curso_id>")
@login_required
def notas_pdf(aluno_id, curso_id):
    from flask import current_app
    aluno = Aluno.query.get_or_404(aluno_id)
    curso = Curso.query.get_or_404(curso_id)
    mats  = (Materia.query
             .join(CursoMateria, CursoMateria.materia_id == Materia.id)
             .filter(CursoMateria.curso_id == curso_id,
                     Materia.ativa == 1)
             .order_by(Materia.nome).all())
    notas_map = {
        n.materia_id: n
        for n in Nota.query.filter_by(
            aluno_id=aluno_id, curso_id=curso_id).all()
    }

    buffer   = io.BytesIO()
    pdf      = canvas.Canvas(buffer, pagesize=A4)
    larg, alt = A4
    logo = os.path.join(current_app.root_path, "static", "logo_escola.png")
    topo = alt - 80
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, topo - 40, width=100, height=45,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(170, topo, "Centro de Qualificação Profissional")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(170, topo - 18, "Rua Prata Mancebo, 148 - Centro, Carapebus-RJ")
    pdf.drawString(170, topo - 32, "Tel.: (22) 99868-4334  |  CNPJ: 39.368.679/0001-01")
    pdf.line(50, topo - 50, larg - 50, topo - 50)
    y = topo - 75
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Aluno: {aluno.nome}")
    y -= 16
    pdf.drawString(50, y, f"Curso: {curso.nome}")
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data: {date.today().strftime('%d/%m/%Y')}")
    y -= 28
    pdf.setFont("Helvetica-Bold", 10)
    for col, txt in [(50, "Matéria"), (270, "Nota"), (340, "Resultado")]:
        pdf.drawString(col, y, txt)
    y -= 8
    pdf.line(50, y, larg - 50, y)
    y -= 18
    pdf.setFont("Helvetica", 10)
    for m in mats:
        n = notas_map.get(m.id)
        pdf.drawString(50,  y, m.nome)
        pdf.drawString(270, y, str(n.nota      if n and n.nota      else ""))
        pdf.drawString(340, y, str(n.resultado if n and n.resultado else ""))
        y -= 18
        if y < 100:
            pdf.showPage()
            y = alt - 60
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="boletim_notas.pdf",
                     mimetype="application/pdf")


@academico_bp.route("/frequencia_historico_pdf/<int:aluno_id>/<int:curso_id>")
@login_required
def frequencia_historico_pdf(aluno_id, curso_id):
    from flask import current_app
    aluno    = Aluno.query.get_or_404(aluno_id)
    curso    = Curso.query.get_or_404(curso_id)
    historico = (Frequencia.query
                 .filter_by(aluno_id=aluno_id, curso_id=curso_id)
                 .order_by(Frequencia.data).all())

    buffer   = io.BytesIO()
    pdf      = canvas.Canvas(buffer, pagesize=A4)
    larg, alt = A4
    logo = os.path.join(current_app.root_path, "static", "logo_escola.png")
    topo = alt - 80
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, topo - 40, width=100, height=45,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(170, topo, "Centro de Qualificação Profissional")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(170, topo - 18, "Rua Prata Mancebo, 148 - Centro, Carapebus-RJ")
    pdf.drawString(170, topo - 32, "Tel.: (22) 99868-4334  |  CNPJ: 39.368.679/0001-01")
    pdf.line(50, topo - 50, larg - 50, topo - 50)
    y = topo - 75
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "HISTÓRICO DE FREQUÊNCIA")
    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Aluno: {aluno.nome}")
    y -= 16
    pdf.drawString(50, y, f"Curso: {curso.nome}")
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data: {date.today().strftime('%d/%m/%Y')}")
    y -= 28
    for h in historico:
        txt = "Presente" if h.status == "P" else "Falta"
        pdf.drawString(50, y, f"{h.data}  —  {txt}")
        y -= 18
        if y < 120:
            pdf.showPage()
            y = alt - 60
    centro = larg / 2
    assin  = os.path.join(current_app.root_path, "static", "assinatura.png")
    if os.path.exists(assin):
        pdf.drawImage(assin, centro - 80, 90, width=160, height=40,
                      preserveAspectRatio=True, mask="auto")
    else:
        pdf.line(centro - 100, 105, centro + 100, 105)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(centro, 75, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL CQP")
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(centro, 60, "CNPJ: 39.368.679/0001-01")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="historico_frequencia.pdf",
                     mimetype="application/pdf")


# ───────────────────────── BACKUP ─────────────────────────

@academico_bp.route("/backup")
@login_required
def backup():
    from flask import current_app
    db_path = "/home/site/wwwroot/cqp.db"
    if not os.path.exists(db_path):
        db_path = os.path.join(current_app.root_path, "cqp.db")
    if not os.path.exists(db_path):
        flash("Banco de dados não encontrado.", "erro")
        return redirect("/")
    return send_file(db_path, as_attachment=True,
                     download_name=f"backup_cqp_{date.today().isoformat()}.db",
                     mimetype="application/octet-stream")
