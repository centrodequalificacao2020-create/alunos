from flask import Blueprint, render_template, request, redirect, flash, session
from db import conectar
from security import login_required, admin_required

aluno_bp = Blueprint("aluno", __name__)


# ─────────────────────────── CADASTRO ───────────────────────────

@aluno_bp.route("/cadastro")
@login_required
def cadastro():
    conn = conectar()
    conn.row_factory = __import__('sqlite3').Row
    c = conn.cursor()
    c.execute("SELECT id, nome, status FROM alunos ORDER BY nome")
    alunos = c.fetchall()
    c.execute("SELECT id, nome FROM cursos ORDER BY nome")
    cursos = c.fetchall()
    conn.close()
    return render_template("cadastro.html", alunos=alunos, cursos=cursos)


@aluno_bp.route("/salvar_aluno", methods=["POST"])
@login_required
def salvar_aluno():
    f = request.form
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        INSERT INTO alunos
            (nome, cpf, rg, data_nascimento, telefone, whatsapp,
             telefone_contato, email, endereco, status, curso_id,
             responsavel_nome, responsavel_cpf,
             responsavel_telefone, responsavel_parentesco)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        f.get("nome"), f.get("cpf"), f.get("rg"),
        f.get("data_nascimento"), f.get("telefone"),
        f.get("whatsapp"), f.get("telefone_contato"),
        f.get("email"), f.get("endereco"),
        f.get("status", "Ativo"),
        f.get("curso_id") or None,
        f.get("responsavel_nome"), f.get("responsavel_cpf"),
        f.get("responsavel_telefone"), f.get("responsavel_parentesco"),
    ))
    conn.commit()
    conn.close()
    flash("Aluno cadastrado com sucesso.", "sucesso")
    return redirect("/cadastro")


@aluno_bp.route("/editar_aluno/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    conn = conectar()
    conn.row_factory = __import__('sqlite3').Row
    c = conn.cursor()
    if request.method == "POST":
        f = request.form
        c.execute("""
            UPDATE alunos SET
                nome=?, cpf=?, rg=?, data_nascimento=?,
                telefone=?, whatsapp=?, email=?, endereco=?,
                status=?, curso_id=?,
                responsavel_nome=?, responsavel_cpf=?,
                responsavel_telefone=?, responsavel_parentesco=?
            WHERE id=?
        """, (
            f.get("nome"), f.get("cpf"), f.get("rg"),
            f.get("data_nascimento"), f.get("telefone"),
            f.get("whatsapp"), f.get("email"), f.get("endereco"),
            f.get("status"), f.get("curso_id") or None,
            f.get("responsavel_nome"), f.get("responsavel_cpf"),
            f.get("responsavel_telefone"), f.get("responsavel_parentesco"),
            id,
        ))
        conn.commit()
        conn.close()
        flash("Aluno atualizado.", "sucesso")
        return redirect("/cadastro")
    c.execute("SELECT * FROM alunos WHERE id=?", (id,))
    aluno = c.fetchone()
    c.execute("SELECT id, nome FROM cursos ORDER BY nome")
    cursos = c.fetchall()
    conn.close()
    if not aluno:
        flash("Aluno não encontrado.", "erro")
        return redirect("/cadastro")
    return render_template("editar_aluno.html", aluno=aluno, cursos=cursos)


@aluno_bp.route("/excluir_aluno/<int:id>", methods=["POST"])
@login_required
def excluir_aluno(id):
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mensalidades WHERE aluno_id=?", (id,))
    total = c.fetchone()[0]
    if total > 0:
        conn.close()
        flash("Não é possível excluir: aluno possui registros financeiros.", "erro")
        return redirect("/cadastro")
    c.execute("DELETE FROM alunos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Aluno excluído.", "sucesso")
    return redirect("/cadastro")


@aluno_bp.route("/aluno/<int:aluno_id>")
@login_required
def ficha_aluno(aluno_id):
    conn = conectar()
    conn.row_factory = __import__('sqlite3').Row
    c = conn.cursor()
    c.execute("SELECT * FROM alunos WHERE id=?", (aluno_id,))
    aluno = c.fetchone()
    conn.close()
    if not aluno:
        flash("Aluno não encontrado.", "erro")
        return redirect("/cadastro")
    return render_template("ficha_aluno.html", aluno=aluno)
