from flask import (Blueprint, render_template, request, redirect,
                   session, flash, send_file)
import sqlite3
import os
import io
from datetime import datetime, date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from db import conectar

academico_bp = Blueprint("academico", __name__)


def _logado():
    return "usuario_id" in session


def _cabecalho_pdf(pdf, largura, altura, titulo):
    from flask import current_app
    logo = os.path.join(current_app.root_path, "static", "logo_escola.png")
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, altura - 120, width=80, height=60,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, altura - 60, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, altura - 75,  "CNPJ: 39.368.679/0001-01")
    pdf.drawString(140, altura - 90,  "Rua: Prata Mancebo nº 148 - Centro")
    pdf.drawString(140, altura - 105, "Carapebus - RJ  CEP 27998-000")
    pdf.drawString(140, altura - 120, "Tel.: (22) 99868-4334")
    pdf.drawString(140, altura - 135, "E-mail: Centrodequalificacao@cqpcursos.com.br")
    pdf.line(50, altura - 150, largura - 50, altura - 150)
    y = altura - 180
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, titulo)
    return y


# ─────────────────────────── MATÉRIAS ───────────────────────────

@academico_bp.route("/materias", methods=["GET", "POST"])
def materias():
    if not _logado():
        return redirect("/login")

    conn   = conectar()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST" and "nova_materia" in request.form:
        nome     = request.form["nome"].strip()
        curso_id = request.form["curso_id"]
        if nome and curso_id:
            cursor.execute("INSERT INTO materias (nome, ativa) VALUES (?, 1)", (nome,))
            materia_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO cursos_materias (curso_id, materia_id) VALUES (?, ?)",
                (curso_id, materia_id))
            conn.commit()
            flash("Matéria cadastrada com sucesso!", "sucesso")

    if request.method == "POST" and "excluir_materia" in request.form:
        mid = request.form["materia_id"]
        cursor.execute("UPDATE materias SET ativa = 0 WHERE id = ?", (mid,))
        cursor.execute("DELETE FROM cursos_materias WHERE materia_id = ?", (mid,))
        conn.commit()
        flash("Matéria excluída!", "sucesso")

    if request.method == "POST" and "editar_materia" in request.form:
        mid       = request.form["materia_id"]
        novo_nome = request.form["novo_nome"].strip()
        if novo_nome:
            cursor.execute("UPDATE materias SET nome = ? WHERE id = ?", (novo_nome, mid))
            conn.commit()
            flash("Matéria atualizada!", "sucesso")

    cursor.execute("SELECT id, nome FROM cursos ORDER BY nome")
    cursos = cursor.fetchall()

    cursor.execute("""
        SELECT c.id, c.nome, m.id, m.nome
        FROM cursos c
        LEFT JOIN cursos_materias cm ON cm.curso_id = c.id
        LEFT JOIN materias m ON m.id = cm.materia_id AND m.ativa = 1
        ORDER BY c.nome, m.nome
    """)
    rows = cursor.fetchall()

    materias_por_curso = {}
    for curso_id, curso_nome, materia_id, materia_nome in rows:
        materias_por_curso.setdefault((curso_id, curso_nome), [])
        if materia_id:
            materias_por_curso[(curso_id, curso_nome)].append((materia_id, materia_nome))

    conn.close()
    return render_template("materias.html", cursos=cursos,
                           materias_por_curso=materias_por_curso)


# ─────────────────────────── NOTAS ───────────────────────────

@academico_bp.route("/notas", methods=["GET", "POST"])
def notas():
    if not _logado():
        return redirect("/login")

    termo    = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)

    conn = conectar()
    conn.row_factory = sqlite3.Row
    c    = conn.cursor()

    alunos = []
    cursos_matriculados = []
    materias_lista = []
    aluno_nome = ""

    if termo:
        c.execute("SELECT id, nome FROM alunos WHERE nome LIKE ? ORDER BY nome",
                  (f"%{termo}%",))
        alunos = c.fetchall()

    if aluno_id:
        c.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,))
        row = c.fetchone()
        if row:
            aluno_nome = row["nome"]
        c.execute("""
            SELECT c.id, c.nome
            FROM cursos c JOIN matriculas m ON m.curso_id = c.id
            WHERE m.aluno_id = ? ORDER BY c.nome
        """, (aluno_id,))
        cursos_matriculados = c.fetchall()

    c.execute("""
        SELECT m.id, m.nome, cm.curso_id
        FROM materias m
        JOIN cursos_materias cm ON cm.materia_id = m.id
        ORDER BY m.nome
    """)
    materias_lista = c.fetchall()

    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        curso_id = request.form.get("curso_id", type=int)
        for row in materias_lista:
            materia_id = row["id"]
            nota      = request.form.get(f"nota_{materia_id}") or None
            resultado = request.form.get(f"resultado_{materia_id}")
            c.execute("""
                INSERT INTO notas (aluno_id, curso_id, materia_id, nota, resultado)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(aluno_id, curso_id, materia_id)
                DO UPDATE SET nota=excluded.nota, resultado=excluded.resultado
            """, (aluno_id, curso_id, materia_id, nota, resultado))
        conn.commit()
        conn.close()
        return redirect(f"/notas?aluno_id={aluno_id}&curso_id={curso_id}")

    conn.close()
    return render_template("notas.html",
                           alunos=alunos, termo=termo,
                           aluno_id=aluno_id, aluno_nome=aluno_nome,
                           cursos_matriculados=cursos_matriculados,
                           curso_id=curso_id, materias=materias_lista)


@academico_bp.route("/notas_visualizar/<int:aluno_id>")
def notas_visualizar(aluno_id):
    if not _logado():
        return redirect("/login")

    conn = conectar()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    curso_id = request.args.get("curso_id", type=int)
    if not curso_id:
        c.execute("""
            SELECT curso_id FROM matriculas
            WHERE aluno_id = ? ORDER BY id DESC LIMIT 1
        """, (aluno_id,))
        mat = c.fetchone()
        if mat:
            curso_id = mat["curso_id"]

    c.execute("SELECT nome FROM alunos WHERE id=?", (aluno_id,))
    aluno = c.fetchone()
    aluno_nome = aluno["nome"] if aluno else "Aluno"

    curso_nome = ""
    if curso_id:
        c.execute("SELECT nome FROM cursos WHERE id=?", (curso_id,))
        curso = c.fetchone()
        if curso:
            curso_nome = curso["nome"]

    boletim = []
    if curso_id:
        c.execute("""
            SELECT m.nome, n.nota, n.resultado
            FROM cursos_materias cm
            JOIN materias m ON m.id = cm.materia_id
            LEFT JOIN notas n ON n.materia_id = m.id
                AND n.aluno_id = ? AND n.curso_id = ?
            WHERE cm.curso_id = ? ORDER BY m.nome
        """, (aluno_id, curso_id, curso_id))
        boletim = c.fetchall()

    conn.close()
    return render_template("notas_visualizar.html",
                           aluno_nome=aluno_nome, curso_nome=curso_nome, boletim=boletim)


@academico_bp.route("/notas_pdf/<int:aluno_id>/<int:curso_id>")
def notas_pdf(aluno_id, curso_id):
    from flask import current_app
    conn = conectar()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    aluno = cur.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,)).fetchone()
    curso = cur.execute("SELECT nome FROM cursos WHERE id = ?", (curso_id,)).fetchone()

    notas_rows = cur.execute("""
        SELECT m.nome AS materia, n.nota, n.resultado,
               CASE WHEN n.resultado IS NULL THEN 'CURSANDO'
                    WHEN n.resultado = 'NAO_CURSOU' THEN 'NÃO CURSADA'
                    ELSE 'CONCLUÍDA' END AS situacao
        FROM cursos_materias cm
        JOIN materias m ON m.id = cm.materia_id
        LEFT JOIN notas n ON n.materia_id = m.id
            AND n.aluno_id = ? AND n.curso_id = ?
        WHERE cm.curso_id = ? ORDER BY m.nome
    """, (aluno_id, curso_id, curso_id)).fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf    = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    logo_path = os.path.join(current_app.root_path, "static", "logo_escola.png")
    topo = altura - 80
    if os.path.exists(logo_path):
        pdf.drawImage(logo_path, 50, topo - 40, width=100, height=45,
                      preserveAspectRatio=True, mask="auto")
    texto_x = 170
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(texto_x, topo, "Centro de Qualificação Profissional")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(texto_x, topo - 18, "Endereço: Rua Prata Mancebo, 148 - Centro, Carapebus-RJ")
    pdf.drawString(texto_x, topo - 32, "Telefone: (22) 99868-4334")
    pdf.drawString(texto_x, topo - 46, "CNPJ: 39.368.679/0001-01")
    pdf.line(50, topo - 65, largura - 50, topo - 65)

    y = topo - 80
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Aluno: {aluno['nome']}")
    y -= 15
    pdf.drawString(50, y, f"Curso: {curso['nome']}")
    y -= 15
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data: {date.today().strftime('%d/%m/%Y')}")
    y -= 30

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Matéria")
    pdf.drawString(260, y, "Nota")
    pdf.drawString(330, y, "Resultado")
    pdf.drawString(440, y, "Situação")
    y -= 8
    pdf.line(50, y, largura - 50, y)
    y -= 20

    pdf.setFont("Helvetica", 10)
    for row in notas_rows:
        pdf.drawString(50,  y, str(row["materia"]))
        pdf.drawString(260, y, str(row["nota"] or ""))
        pdf.drawString(330, y, str(row["resultado"] or ""))
        pdf.drawString(440, y, str(row["situacao"]))
        y -= 18
        if y < 100:
            pdf.showPage()
            y = altura - 60

    y -= 30
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(largura / 2, y, "Assinatura da Escola")
    assinatura_path = os.path.join(current_app.root_path, "static", "assinatura.png")
    if os.path.exists(assinatura_path):
        pdf.drawImage(assinatura_path, largura / 2 - 80, y - 50, width=160, height=40,
                      preserveAspectRatio=True, mask="auto")
    else:
        pdf.line(largura / 2 - 100, y - 30, largura / 2 + 100, y - 30)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="boletim_notas.pdf", mimetype="application/pdf")


# ─────────────────────────── FREQUÊNCIA ───────────────────────────

@academico_bp.route("/frequencia", methods=["GET", "POST"])
def frequencia():
    if not _logado():
        return redirect("/login")

    conn = conectar()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    termo    = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)

    alunos = []
    aluno_nome = None
    cursos_matriculados = []
    curso_id = None

    if termo:
        c.execute("SELECT id, nome FROM alunos WHERE nome LIKE ? ORDER BY nome",
                  (f"%{termo}%",))
        alunos = c.fetchall()

    if aluno_id:
        c.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,))
        row = c.fetchone()
        if row:
            aluno_nome = row["nome"]

        c.execute("""
            SELECT c.id, c.nome
            FROM cursos c JOIN matriculas m ON m.curso_id = c.id
            WHERE m.aluno_id = ? AND m.status = 'ATIVA'
            ORDER BY c.nome
        """, (aluno_id,))
        cursos_matriculados = c.fetchall()

        c.execute("""
            SELECT curso_id FROM matriculas
            WHERE aluno_id = ? ORDER BY id DESC LIMIT 1
        """, (aluno_id,))
        mat = c.fetchone()
        if mat:
            curso_id = mat["curso_id"]

    if request.method == "POST":
        aluno_id  = request.form.get("aluno_id", type=int)
        curso_id  = request.form.get("curso_id",  type=int)
        data_aula = request.form.get("data")
        status    = request.form.get("status")
        if aluno_id and curso_id and data_aula and status:
            c.execute("""
                INSERT INTO frequencias (aluno_id, curso_id, data, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(aluno_id, curso_id, data)
                DO UPDATE SET status = excluded.status
            """, (aluno_id, curso_id, data_aula, status))
            conn.commit()
            flash("✅ Frequência salva com sucesso.", "sucesso")
            conn.close()
            return redirect(f"/frequencia?aluno_id={aluno_id}&curso_id={curso_id}&data={data_aula}")

    conn.close()
    return render_template("frequencia.html",
                           alunos=alunos, aluno_id=aluno_id,
                           aluno_nome=aluno_nome,
                           cursos_matriculados=cursos_matriculados,
                           curso_id=curso_id, termo=termo)


@academico_bp.route("/frequencia_historico")
def frequencia_historico():
    if not _logado():
        return redirect("/login")

    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)

    conn = conectar()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    aluno = curso = None
    historico = []

    if aluno_id and curso_id:
        c.execute("SELECT id, nome FROM alunos WHERE id = ?", (aluno_id,))
        aluno = c.fetchone()
        c.execute("SELECT id, nome FROM cursos WHERE id = ?", (curso_id,))
        curso = c.fetchone()
        c.execute("""
            SELECT data, status FROM frequencias
            WHERE aluno_id = ? AND curso_id = ? ORDER BY data
        """, (aluno_id, curso_id))
        historico = c.fetchall()

    conn.close()
    return render_template("frequencia_historico.html",
                           aluno=aluno, curso=curso, historico=historico)


@academico_bp.route("/frequencia_historico_pdf/<int:aluno_id>/<int:curso_id>")
def frequencia_historico_pdf(aluno_id, curso_id):
    from flask import current_app
    conn = conectar()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,))
    aluno = c.fetchone()
    c.execute("SELECT nome FROM cursos WHERE id = ?", (curso_id,))
    curso = c.fetchone()

    if not aluno or not curso:
        conn.close()
        return "Aluno ou curso não encontrado"

    c.execute("""
        SELECT data, status FROM frequencias
        WHERE aluno_id = ? AND curso_id = ? ORDER BY data
    """, (aluno_id, curso_id))
    historico = c.fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf    = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    logo_path = os.path.join(current_app.root_path, "static", "logo_escola.png")
    topo = altura - 80
    if os.path.exists(logo_path):
        pdf.drawImage(logo_path, 50, topo - 40, width=100, height=45,
                      preserveAspectRatio=True, mask="auto")
    texto_x = 170
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(texto_x, topo, "Centro de Qualificação Profissional")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(texto_x, topo - 18, "Endereço: Rua Prata Mancebo, 148 - Centro, Carapebus-RJ")
    pdf.drawString(texto_x, topo - 32, "Telefone: (22) 99868-4334")
    pdf.drawString(texto_x, topo - 46, "CNPJ: 39.368.679/0001-01")
    pdf.line(50, topo - 65, largura - 50, topo - 65)

    y = topo - 90
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "HISTÓRICO DE FREQUÊNCIA")
    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Aluno: {aluno['nome']}")
    y -= 15
    pdf.drawString(50, y, f"Curso: {curso['nome']}")
    y -= 15
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data: {date.today().strftime('%d/%m/%Y')}")
    y -= 25

    for h in historico:
        status_txt = "Presente" if h["status"] == "P" else "Falta"
        pdf.drawString(50, y, f"{h['data']} - {status_txt}")
        y -= 20
        if y < 150:
            pdf.showPage()
            y = altura - 60

    centro = largura / 2
    assinatura_path = os.path.join(current_app.root_path, "static", "assinatura.png")
    if os.path.exists(assinatura_path):
        pdf.drawImage(assinatura_path, centro - 80, 90, width=160, height=40,
                      preserveAspectRatio=True, mask="auto")
    else:
        pdf.line(centro - 100, 105, centro + 100, 105)

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(centro, 75, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL CQP")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(centro, 60, "CNPJ: 39.368.679/0001-01")

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True,
                     download_name="historico_frequencia.pdf",
                     mimetype="application/pdf")


# ─────────────────────────── RELATÓRIO ───────────────────────────

@academico_bp.route("/relatorio")
def relatorio():
    if not _logado():
        return redirect("/login")
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT SUM(valor) FROM mensalidades WHERE status='Pago'")
    pago = c.fetchone()[0] or 0
    c.execute("SELECT SUM(valor) FROM mensalidades WHERE status='Pendente'")
    pendente = c.fetchone()[0] or 0
    conn.close()
    return render_template("relatorio.html", total_pago=pago, total_pendente=pendente)


# ─────────────────────────── BACKUP ───────────────────────────

@academico_bp.route("/backup")
def backup():
    if not _logado():
        return redirect("/login")
    from flask import current_app
    db_path = "/home/site/wwwroot/cqp.db"
    if not os.path.exists(db_path):
        db_path = os.path.join(current_app.root_path, "cqp.db")
    if not os.path.exists(db_path):
        flash("Arquivo de banco de dados não encontrado.", "erro")
        return redirect("/")
    return send_file(db_path, as_attachment=True,
                     download_name=f"backup_cqp_{date.today().isoformat()}.db",
                     mimetype="application/octet-stream")
