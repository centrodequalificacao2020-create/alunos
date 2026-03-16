from flask import Blueprint, render_template, request, session, redirect
import sqlite3

aluno_bp = Blueprint("aluno", __name__, url_prefix="/aluno")


# =========================
# CONEXÃO COM BANCO
# =========================

def conectar_banco():
    conn = sqlite3.connect("cqp.db")
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# LOGIN DO ALUNO
# =========================

@aluno_bp.route("/login", methods=["GET", "POST"])
def login_aluno():

    if request.method == "POST":

        email = request.form.get("email")
        senha = request.form.get("senha")

        conn = conectar_banco()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM alunos WHERE email=? AND senha=?",
            (email, senha)
        )

        aluno = cursor.fetchone()
        conn.close()

        if aluno:
            session["aluno_id"] = aluno["id"]
            return redirect("/aluno/dashboard")

    return render_template("aluno/login.html")


# =========================
# DASHBOARD DO ALUNO
# =========================

@aluno_bp.route("/dashboard")
def dashboard_aluno():

    if "aluno_id" not in session:
        return redirect("/aluno/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    aluno_id = session["aluno_id"]

    # dados do aluno
    cursor.execute("SELECT * FROM alunos WHERE id=?", (aluno_id,))
    aluno = cursor.fetchone()
    # buscar curso do aluno
    cursor.execute("""
    SELECT cursos.nome
    FROM matriculas
    JOIN cursos ON cursos.id = matriculas.curso_id
    WHERE matriculas.aluno_id=?
    LIMIT 1
    """, (aluno_id,))

    curso_row = cursor.fetchone()

    curso = None
    if curso_row:
        curso = curso_row[0]

    # parcelas em aberto
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM mensalidades
        WHERE aluno_id=? AND status!='Pago'
    """, (aluno_id,))

    pendentes = cursor.fetchone()["total"]

    # valor total em aberto
    cursor.execute("""
        SELECT SUM(valor) as total
        FROM mensalidades
        WHERE aluno_id=? AND status!='Pago'
    """, (aluno_id,))

    valor_pendente = cursor.fetchone()["total"]

    if valor_pendente is None:
        valor_pendente = 0

    # lista de mensalidades
    cursor.execute("""
        SELECT 
            valor,
            vencimento,
            status,
            tipo,
            parcela_ref,
            CASE
                WHEN status = 'Pago' THEN 'Pago'
                WHEN date(vencimento) < date('now') THEN 'Vencida'
                ELSE 'A vencer'
            END as situacao
        FROM mensalidades
        WHERE aluno_id=?
        ORDER BY vencimento
    """, (aluno_id,))

    mensalidades = cursor.fetchall()

    conn.close()

    return render_template(
        "aluno/dashboard.html",
        aluno=aluno,
        curso=curso,
        mensalidades=mensalidades,
        pendentes=pendentes,
        valor_pendente=valor_pendente
    )

# =========================
# LOGOUT DO ALUNO
# =========================

@aluno_bp.route("/logout")
def logout_aluno():
    session.pop("aluno_id", None)
    return redirect("/aluno/login")


# =========================
# FREQUÊNCIA DO ALUNO
# =========================

@aluno_bp.route("/frequencia")
def frequencia_aluno():

    if "aluno_id" not in session:
        return redirect("/aluno/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    aluno_id = session["aluno_id"]

    cursor.execute("""
        SELECT data, status
        FROM frequencias
        WHERE aluno_id=?
        ORDER BY data DESC
    """, (aluno_id,))

    frequencias = cursor.fetchall()

    cursor.execute("SELECT * FROM alunos WHERE id=?", (aluno_id,))
    aluno = cursor.fetchone()

    conn.close()

    return render_template(
        "aluno/frequencia.html",
        aluno=aluno,
        frequencias=frequencias
    )
@aluno_bp.route("/conteudo")
def conteudo_aluno():

    if "aluno_id" not in session:
        return redirect("/aluno/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    aluno_id = session["aluno_id"]

    # descobrir curso do aluno
    c.execute("""
        SELECT curso_id
        FROM matriculas
        WHERE aluno_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (aluno_id,))

    matricula = c.fetchone()

    if not matricula:
        conn.close()
        return render_template("aluno/conteudo.html", conteudos=[])

    curso_id = matricula["curso_id"]

    # buscar conteúdos do curso
    c.execute("""
    SELECT
        conteudos.id,
        conteudos.titulo,
        conteudos.arquivo,
        conteudos.data,
        materias.nome AS materia,
        COALESCE(progresso_aulas.concluido,0) as concluido
    FROM conteudos
    JOIN materias
        ON materias.id = conteudos.materia_id
    JOIN cursos_materias
        ON cursos_materias.materia_id = materias.id
    LEFT JOIN progresso_aulas
        ON progresso_aulas.conteudo_id = conteudos.id
        AND progresso_aulas.aluno_id = ?
    WHERE cursos_materias.curso_id = ?
    ORDER BY materias.nome, conteudos.data
    """, (aluno_id, curso_id))

    conteudos = c.fetchall()

    conn.close()

    return render_template(
        "aluno/conteudo.html",
        conteudos=conteudos
    )

@aluno_bp.route("/buscar_materias/<int:curso_id>")
def buscar_materias(curso_id):

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome
        FROM materias
        WHERE curso_id = ?
        ORDER BY nome
    """, (curso_id,))

    materias = cursor.fetchall()

    conn.close()

    lista = []

    for m in materias:
        lista.append({
            "id": m["id"],
            "nome": m["nome"]
        })

    return lista
@aluno_bp.route("/concluir/<int:conteudo_id>")
def concluir_aula(conteudo_id):

    if "aluno_id" not in session:
        return redirect("/aluno/login")

    aluno_id = session["aluno_id"]

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
    INSERT OR REPLACE INTO progresso_aulas
    (aluno_id, conteudo_id, concluido)
    VALUES (?, ?, 1)
    """, (aluno_id, conteudo_id))

    conn.commit()
    conn.close()

    return redirect("/aluno/conteudo")

