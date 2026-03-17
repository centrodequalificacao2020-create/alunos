from flask import Blueprint, render_template, request, redirect, flash, session
from db import conectar
from security import login_required, admin_required, hash_senha

funcionario_bp = Blueprint("funcionario", __name__)


# ─────────────────────────── LISTAR ───────────────────────────

@funcionario_bp.route("/funcionarios")
@login_required
def listar_funcionarios():
    conn = conectar()
    conn.row_factory = __import__('sqlite3').Row
    c = conn.cursor()
    c.execute("SELECT id, nome, usuario, perfil, cpf, telefone, email FROM usuarios ORDER BY nome")
    funcionarios = c.fetchall()
    conn.close()
    return render_template("funcionario.html", funcionarios=funcionarios)


# ─────────────────────────── NOVO ───────────────────────────

@funcionario_bp.route("/novo_funcionario", methods=["GET"])
@login_required
def novo_funcionario():
    return render_template("funcionario.html", funcionarios=[], novo=True)


@funcionario_bp.route("/salvar_funcionario", methods=["POST"])
@admin_required
def salvar_funcionario():
    f = request.form
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        INSERT INTO usuarios (nome, usuario, senha, perfil, cpf, telefone, email)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        f.get("nome"), f.get("usuario"),
        hash_senha(f.get("senha", "")),
        f.get("perfil", "secretaria"),
        f.get("cpf"), f.get("telefone"), f.get("email"),
    ))
    conn.commit()
    conn.close()
    flash("Funcionário cadastrado.", "sucesso")
    return redirect("/funcionarios")


# ─────────────────────────── EDITAR ───────────────────────────

@funcionario_bp.route("/editar_funcionario/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_funcionario(id):
    conn = conectar()
    conn.row_factory = __import__('sqlite3').Row
    c = conn.cursor()
    if request.method == "POST":
        f = request.form
        if f.get("senha"):
            c.execute("""
                UPDATE usuarios SET nome=?, perfil=?, email=?, senha=?
                WHERE id=?
            """, (f.get("nome"), f.get("perfil"), f.get("email"),
                   hash_senha(f.get("senha")), id))
        else:
            c.execute("""
                UPDATE usuarios SET nome=?, perfil=?, email=?
                WHERE id=?
            """, (f.get("nome"), f.get("perfil"), f.get("email"), id))
        conn.commit()
        conn.close()
        flash("Funcionário atualizado.", "sucesso")
        return redirect("/funcionarios")
    c.execute("SELECT * FROM usuarios WHERE id=?", (id,))
    funcionario = c.fetchone()
    conn.close()
    if not funcionario:
        flash("Funcionário não encontrado.", "erro")
        return redirect("/funcionarios")
    return render_template("editar_funcionario.html", funcionario=funcionario)


# ─────────────────────────── VER ───────────────────────────

@funcionario_bp.route("/ver_funcionario/<int:id>")
@login_required
def ver_funcionario(id):
    conn = conectar()
    conn.row_factory = __import__('sqlite3').Row
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE id=?", (id,))
    funcionario = c.fetchone()
    conn.close()
    if not funcionario:
        flash("Funcionário não encontrado.", "erro")
        return redirect("/funcionarios")
    return render_template("ver_funcionario.html", funcionario=funcionario)
