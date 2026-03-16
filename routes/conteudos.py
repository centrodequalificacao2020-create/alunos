from flask import Blueprint, render_template, redirect, request
import sqlite3
import os

conteudos_bp = Blueprint("conteudos", __name__)

# =========================
# CONTEÚDOS (AULAS)
# =========================
@conteudos_bp.route("/conteudos", methods=["GET", "POST"])
def conteudos():

    from app import conectar_banco, logado, limpar_nome_arquivo

    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ================= CURSOS =================
    c.execute("SELECT id, nome FROM cursos ORDER BY nome")
    cursos = c.fetchall()

    # ================= MATÉRIAS =================
    c.execute("""
        SELECT 
            m.id,
            m.nome,
            cm.curso_id
        FROM materias m
        JOIN cursos_materias cm
            ON cm.materia_id = m.id
        ORDER BY m.nome
    """)
    materias = [dict(m) for m in c.fetchall()]

    # ================= SALVAR CONTEÚDO =================
    if request.method == "POST":

        titulo = request.form.get("titulo")
        materia_id = request.form.get("materia_id")
        modulo = request.form.get("modulo")
        video = request.form.get("video")
        arquivo = request.files.get("arquivo")

        caminho_arquivo = None

        # upload PDF
        if arquivo and arquivo.filename != "":
            nome_seguro = limpar_nome_arquivo(arquivo.filename)
            caminho = os.path.join("static/uploads", nome_seguro)
            arquivo.save(caminho)
            caminho_arquivo = caminho

        # caso seja vídeo
        if not caminho_arquivo and video:
            caminho_arquivo = video

        c.execute("""
            INSERT INTO conteudos
            (titulo, materia_id, modulo, arquivo, data)
            VALUES (?, ?, ?, ?, date('now'))
        """, (titulo, materia_id, modulo, caminho_arquivo))

        conn.commit()

        return redirect("/conteudos")

    # ================= LISTAR CONTEÚDOS =================
    c.execute("""
        SELECT
            conteudos.id,
            conteudos.titulo,
            conteudos.modulo,
            conteudos.arquivo,
            conteudos.data,
            materias.nome AS materia,
            cursos.nome AS curso,
            cursos.id AS curso_id
        FROM conteudos
        INNER JOIN materias
            ON materias.id = conteudos.materia_id
        INNER JOIN cursos_materias
            ON cursos_materias.materia_id = materias.id
        INNER JOIN cursos
            ON cursos.id = cursos_materias.curso_id
        ORDER BY cursos.nome, materias.nome, conteudos.id
    """)

    conteudos = c.fetchall()

    conn.close()

    return render_template(
        "conteudos.html",
        cursos=cursos,
        materias=materias,
        conteudos=conteudos
    )


# =========================
# EXCLUIR CONTEÚDO
# =========================
@conteudos_bp.route("/conteudos/excluir/<int:id>")
def excluir_conteudo(id):

    from app import logado

    if not logado():
        return redirect("/login")

    conn = sqlite3.connect("cqp.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT arquivo FROM conteudos WHERE id=?", (id,))
    conteudo = c.fetchone()

    if conteudo and conteudo["arquivo"]:
        caminho = conteudo["arquivo"]

        if os.path.exists(caminho):
            os.remove(caminho)

    c.execute("DELETE FROM conteudos WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/conteudos")

@conteudos_bp.route("/curso/excluir/<int:id>")
def excluir_curso(id):

    from app import conectar_banco, logado
    from flask import redirect

    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    # excluir conteúdos do curso
    cursor.execute("DELETE FROM conteudos WHERE curso_id=?", (id,))

    # excluir curso
    cursor.execute("DELETE FROM cursos WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/conteudos")