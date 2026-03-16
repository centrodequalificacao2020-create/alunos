from flask import Flask, render_template, request, redirect, session, flash, url_for, send_file, make_response, jsonify
import sqlite3
import os
import io
import shutil
import re
from datetime import datetime, timedelta, date
from reportlab.lib.pagesizes import A4

from routes.conteudos import conteudos_bp
from routes.aluno import aluno_bp


# FUNÇÃO PARA LIMPAR NOME DE ARQUIVO
def limpar_nome_arquivo(nome):
    nome = nome.lower()
    nome = nome.replace(" ", "_")
    nome = re.sub(r"[^a-z0-9_.-]", "", nome)
    return nome


app = Flask(__name__)
app.secret_key = "cqp_secret_key"

# REGISTRAR BLUEPRINTS
app.register_blueprint(aluno_bp)
app.register_blueprint(conteudos_bp)
# =========================
# FUNÇÃO CABEÇALHO PDF
# =========================
def cabecalho_pdf(pdf, largura, altura, titulo):

    logo = os.path.join(app.root_path, "static", "logo_escola.png")

    # logo
    if os.path.exists(logo):
        pdf.drawImage(
            logo,
            50,
            altura - 120,
            width=80,
            height=60,
            preserveAspectRatio=True,
            mask='auto'
        )

    # dados da escola
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, altura - 60, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL")

    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, altura - 75, "CNPJ: 39.368.679/0001-01")
    pdf.drawString(140, altura - 90, "Rua: Prata Mancebo nº 148 - Centro")
    pdf.drawString(140, altura - 105, "Carapebus - RJ  CEP 27998-000")
    pdf.drawString(140, altura - 120, "Tel.: (22) 99868-4334")
    pdf.drawString(140, altura - 135, "E-mail: Centrodequalificacao@cqpcursos.com.br")

    # linha separadora
    pdf.line(50, altura - 150, largura - 50, altura - 150)

    # título
    y = altura - 180
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, titulo)

    return y
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from dateutil.relativedelta import relativedelta


def atualizar_status_mensalidades():
    hoje = date.today().isoformat()

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        UPDATE mensalidades
        SET status = 'Pendente'
        WHERE status = 'Pendente'
        AND vencimento < ?
    """, (hoje,))

    conn.commit()
    conn.close()

# ================== BANCO ==================

def conectar_banco():
    # Caminho persistente no Azure
    db_path = "/home/site/wwwroot/cqp.db"

    # Se estiver rodando local (fora do Azure)
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.dirname(__file__), "cqp.db")

    return sqlite3.connect(
        db_path,
        timeout=30,
        check_same_thread=False
    )


def verificar_banco():
    conn = conectar_banco()
    c = conn.cursor()

    # Garantir colunas na tabela despesas
    try:
        c.execute("ALTER TABLE despesas ADD COLUMN recorrente INTEGER DEFAULT 0;")
    except:
        pass

    try:
        c.execute("ALTER TABLE despesas ADD COLUMN dia_vencimento INTEGER;")
    except:
        pass

    # Garantir tabela relatorios
    c.execute("""
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT UNIQUE,
            meta INTEGER,
            realizado INTEGER,
            matriculas INTEGER,
            matriculas_venda INTEGER
        )
    """)

    conn.commit()
    conn.close()


# Executa verificação automática ao iniciar
verificar_banco()

# ================== LOGIN ==================

def logado():
    return "usuario_id" in session

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["usuario"]
        s = request.form["senha"]
        c = conectar_banco().cursor()
        c.execute(
            "SELECT id,nome,perfil FROM usuarios WHERE usuario=? AND senha=?",
            (u, s)
        )
        r = c.fetchone()
        if r:
            session["usuario_id"], session["usuario_nome"], session["perfil"] = r
            return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================== HOME ==================

@app.route("/")
def home():
    if not logado():
        return redirect("/login")
    return render_template("home.html")

# ================== CURSOS ==================

@app.route("/salvar_curso", methods=["POST"])
def salvar_curso():
    f = request.form
    conn = conectar_banco()
    c = conn.cursor()

    nome = f["nome"]
    valor_mensal = f["valor_mensal"]
    valor_matricula = f["valor_matricula"] or 0
    parcelas = f["parcelas"]
    tipo = f.get("tipo", "")

    c.execute("""
        INSERT INTO cursos (nome, valor_mensal, valor_matricula, parcelas, tipo)
        VALUES (?, ?, ?, ?, ?)
    """, (nome, valor_mensal, valor_matricula, parcelas, tipo))

    conn.commit()
    conn.close()

    return redirect("/cursos")

@app.route("/editar_curso/<int:id>", methods=["GET", "POST"])
def editar_curso(id):
    c = conectar_banco().cursor()
    if request.method == "POST":
        f = request.form
        c.execute("""
            UPDATE cursos SET nome=?,valor_mensal=?,valor_matricula=?,parcelas=?
            WHERE id=?
        """, (f["nome"], f["valor_mensal"], f["valor_matricula"], f["parcelas"], id))
        c.connection.commit()
        return redirect("/cursos")

    c.execute("SELECT * FROM cursos WHERE id=?", (id,))
    return render_template("editar_curso.html", curso=c.fetchone())

@app.route("/excluir_curso/<int:id>")
def excluir_curso(id):
    c = conectar_banco().cursor()
    c.execute("DELETE FROM cursos WHERE id=?", (id,))
    c.connection.commit()
    return redirect("/cursos")

@app.route("/movimentacao", methods=["GET"])
def movimentacao():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # alunos ativos
    c.execute("SELECT id, nome, status FROM alunos WHERE status IN ('Ativo', 'Pré-Matrícula')")
    alunos = [(a[0], f"{a[1]} ({a[2]})") for a in c.fetchall()]

    # 🔹 cursos disponíveis
    c.execute("SELECT id, nome FROM cursos ORDER BY nome")
    cursos = c.fetchall()

    conn.close()

    aluno_id = request.args.get("aluno_id")
    matricula_id = request.args.get("matricula_id")

    return render_template(
        "movimentacao.html",
        alunos=alunos,
        cursos=cursos,
        matricula_id=matricula_id,
        aluno_id=aluno_id
    )

@app.route("/excluir_aluno/<int:id>", methods=["GET","POST"])
def excluir_aluno(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # verifica se tem financeiro
    c.execute("SELECT COUNT(*) FROM mensalidades WHERE aluno_id = ?", (id,))
    total = c.fetchone()[0]

    if total > 0:
        conn.close()
        flash("⚠️ Não é possível excluir o aluno porque ele possui registros financeiros.", "erro")
        return redirect("/cadastro")

    # exclui aluno
    c.execute("DELETE FROM alunos WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("✅ Aluno excluído com sucesso.", "sucesso")
    return redirect("/cadastro")

@app.route("/editar_aluno/<int:id>", methods=["GET", "POST"])
def editar_aluno(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # cursos
    c.execute("SELECT id, nome FROM cursos")
    cursos = c.fetchall()

    # aluno
    c.execute("SELECT * FROM alunos WHERE id = ?", (id,))
    aluno = c.fetchone()

    if request.method == "POST":
        nome = request.form.get("nome")
        cpf = request.form.get("cpf")
        rg = request.form.get("rg")
        data_nascimento = request.form.get("data_nascimento")
        telefone = request.form.get("telefone")
        whatsapp = request.form.get("whatsapp")
        email = request.form.get("email")
        endereco = request.form.get("endereco")
        status = request.form.get("status")
        curso_id = request.form.get("curso_id")

        responsavel_nome = request.form.get("responsavel_nome")
        responsavel_cpf = request.form.get("responsavel_cpf")
        responsavel_telefone = request.form.get("responsavel_telefone")
        responsavel_parentesco = request.form.get("responsavel_parentesco")

        # 🔒 calcula se é menor de idade
        from datetime import date
        menor = 0
        if data_nascimento:
            nascimento = date.fromisoformat(data_nascimento)
            hoje = date.today()
            idade = hoje.year - nascimento.year - (
                (hoje.month, hoje.day) < (nascimento.month, nascimento.day)
            )
            if idade < 18:
                menor = 1

        c.execute("""
            UPDATE alunos SET
                nome = ?, cpf = ?, rg = ?, data_nascimento = ?,
                telefone = ?, whatsapp = ?, email = ?,
                endereco = ?, status = ?, curso_id = ?,
                menor = ?,
                responsavel_nome = ?, responsavel_cpf = ?,
                responsavel_telefone = ?, responsavel_parentesco = ?
            WHERE id = ?
        """, (
            nome, cpf, rg, data_nascimento,
            telefone, whatsapp, email,
            endereco, status, curso_id,
            menor,
            responsavel_nome, responsavel_cpf,
            responsavel_telefone, responsavel_parentesco,
            id
        ))

        conn.commit()
        conn.close()
        return redirect("/cadastro")

    conn.close()
    return render_template(
        "editar_aluno.html",
        aluno=aluno,
        cursos=cursos
    )

# ================== ALUNOS ==================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # BUSCA CURSOS PARA O SELECT
    c.execute("SELECT id, nome FROM cursos")
    cursos = c.fetchall()

    # CADASTRO DO ALUNO
    if request.method == "POST":
        nome = request.form.get("nome")
        cpf = request.form.get("cpf")
        rg = request.form.get("rg")
        data_nascimento = request.form.get("data_nascimento")
        telefone = request.form.get("telefone")
        telefone_contato = request.form.get("telefone_contato")
        email = request.form.get("email")
        endereco = request.form.get("endereco")
        status = request.form.get("status")
        curso_id = request.form.get("curso_id")

        # dados do responsável
        responsavel_nome = request.form.get("responsavel_nome")
        responsavel_cpf = request.form.get("responsavel_cpf")
        responsavel_telefone = request.form.get("responsavel_telefone")
        responsavel_parentesco = request.form.get("responsavel_parentesco")
        responsavel_email = request.form.get("responsavel_email")
        responsavel_endereco = request.form.get("responsavel_endereco")

        c.execute("""
            INSERT INTO alunos (
                nome, cpf, rg, data_nascimento,
                telefone, telefone_contato, email,
                endereco, status, curso_id,
                responsavel_nome, responsavel_cpf,
                responsavel_telefone, responsavel_parentesco,
                responsavel_email, responsavel_endereco
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nome, cpf, rg, data_nascimento,
            telefone, telefone_contato, email,
            endereco, status, curso_id,
            responsavel_nome, responsavel_cpf,
            responsavel_telefone, responsavel_parentesco,
            responsavel_email, responsavel_endereco
        ))

        conn.commit()
        conn.close()
        return redirect("/cadastro")

        # LISTA DE ALUNOS
    c.execute("""
    SELECT 
        a.id,
        a.nome,
        a.telefone,
        a.email,
        a.status,
        a.telefone_contato,

        CASE 
            WHEN EXISTS (
                SELECT 1
                FROM mensalidades m
                WHERE m.aluno_id = a.id
                AND m.status = 'Pendente'
                AND m.vencimento < date('now')
            )
            THEN 1
            ELSE 0
        END as inadimplente

    FROM alunos a
    ORDER BY a.nome
    """)

    alunos = c.fetchall()
    # ================= INADIMPLENTES =================
    c.execute("""
        SELECT COUNT(DISTINCT aluno_id)
        FROM mensalidades
        WHERE status='Pendente'
        AND vencimento < date('now')
    """)

    inadimplentes = c.fetchone()[0] or 0

    conn.close()

    return render_template(
        "cadastro.html",
        cursos=cursos,
        alunos=alunos,
        inadimplentes=inadimplentes
    )

@app.route("/salvar_aluno", methods=["POST"])
def salvar_aluno():
    if not logado():
        return redirect("/login")

    nome = request.form.get("nome")
    cpf = request.form.get("cpf")
    rg = request.form.get("rg")
    data_nascimento = request.form.get("data_nascimento")
    telefone = request.form.get("telefone")
    whatsapp = request.form.get("whatsapp")
    email = request.form.get("email")
    endereco = request.form.get("endereco")
    status = request.form.get("status")
    curso_id = request.form.get("curso_id")

    # calcula se é menor
    from datetime import date
    menor = 0
    if data_nascimento:
        nascimento = date.fromisoformat(data_nascimento)
        hoje = date.today()
        idade = hoje.year - nascimento.year - (
            (hoje.month, hoje.day) < (nascimento.month, nascimento.day)
        )
        if idade < 18:
            menor = 1

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        INSERT INTO alunos (
            nome, cpf, rg, data_nascimento,
            telefone, whatsapp, email,
            endereco, status, curso_id, menor
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nome, cpf, rg, data_nascimento,
        telefone, whatsapp, email,
        endereco, status, curso_id, menor
    ))

    conn.commit()
    conn.close()
    return redirect("/cadastro")


@app.route("/financeiro")
def financeiro():
    if not logado():
        return redirect("/login")

    atualizar_status_mensalidades()

    aluno_id = request.args.get("aluno_id", type=int)

    conn = conectar_banco()
    c = conn.cursor()

    # alunos para o select
    c.execute("SELECT id, nome FROM alunos WHERE status='Ativo'")
    alunos = c.fetchall()

    pendentes = []
    pagas = []

    total_a_pagar = 0
    total_pago = 0

    # ================= SE UM ALUNO FOI SELECIONADO =================
    if aluno_id:

        # A PAGAR
        c.execute("""
            SELECT id, valor, vencimento, tipo, parcela_ref
            FROM mensalidades
            WHERE aluno_id = ? AND status = 'Pendente'
            ORDER BY vencimento
        """, (aluno_id,))
        pendentes = c.fetchall()

        for p in pendentes:
            total_a_pagar += float(p[1] or 0)

        # PAGAS
        c.execute("""
            SELECT id, valor, vencimento, tipo, parcela_ref,
                   data_pagamento, usuario_pagamento
            FROM mensalidades
            WHERE aluno_id = ? AND status = 'Pago'
            ORDER BY data_pagamento
        """, (aluno_id,))
        pagas = c.fetchall()

        for p in pagas:
            total_pago += float(p[1] or 0)

    conn.close()

    saldo_restante = total_a_pagar

    return render_template(
        "financeiro.html",
        alunos=alunos,
        aluno_id=aluno_id,
        pendentes=pendentes,
        pagas=pagas,
        total_a_pagar=total_a_pagar,
        total_pago=total_pago,
        saldo_restante=saldo_restante
    )

@app.route("/excluir_parcela/<int:parcela_id>/<int:aluno_id>")
def excluir_parcela(parcela_id, aluno_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # exclui somente a parcela selecionada
    c.execute("DELETE FROM mensalidades WHERE id=?", (parcela_id,))

    conn.commit()
    conn.close()

    return redirect(f"/financeiro?aluno_id={aluno_id}")

SENHA_EXCLUSAO = "1234"

@app.route("/excluir_parcela_segura/<int:parcela_id>/<int:aluno_id>", methods=["POST"])
def excluir_parcela_segura(parcela_id, aluno_id):
    if not logado():
        return redirect("/login")

    senha = request.form.get("senha")

    if senha != SENHA_EXCLUSAO:
        flash("❌ Senha incorreta. Parcela NÃO excluída.", "erro")
        return redirect(f"/financeiro?aluno_id={aluno_id}")

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("DELETE FROM mensalidades WHERE id = ?", (parcela_id,))

    conn.commit()
    conn.close()

    flash("✅ Parcela excluída com sucesso.", "sucesso")
    return redirect(f"/financeiro?aluno_id={aluno_id}")


# ================== FINANCEIRO ==================

@app.route("/gerar_financeiro/<int:aluno_id>")
def gerar_financeiro(aluno_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # 🔓 VERIFICAÇÃO SIMPLES (SÓ BLOQUEIA SE JÁ EXISTIR QUALQUER FINANCEIRO)
    c.execute("SELECT COUNT(*) FROM mensalidades WHERE aluno_id=?", (aluno_id,))
    if c.fetchone()[0] > 0:
        conn.close()
        return redirect(f"/financeiro?aluno_id={aluno_id}&ja_existe=1")

    # dados do curso
    c.execute("""
        SELECT c.valor_mensal, c.valor_matricula, c.parcelas
        FROM alunos a
        JOIN cursos c ON c.id = a.curso_id
        WHERE a.id=?
    """, (aluno_id,))
    curso = c.fetchone()

    if not curso:
        conn.close()
        return redirect(f"/financeiro?aluno_id={aluno_id}&erro=sem_curso")

    # 🔒 PROTEÇÃO CONTRA None
    valor_mensal = curso[0] or 0
    valor_matricula = curso[1] or 0
    parcelas = curso[2] or 1

    parcelas = int(parcelas)
    if parcelas <= 0:
        parcelas = 1

    hoje = datetime.today()

    # matrícula
    if valor_matricula > 0:
        c.execute("""
            INSERT INTO mensalidades
            (aluno_id, valor, vencimento, status, tipo, parcela_ref)
            VALUES (?, ?, ?, 'Pendente', 'Matrícula', '1/1')
        """, (aluno_id, valor_matricula, hoje.strftime("%Y-%m-%d")))

    # mensalidades
    for i in range(parcelas):
        venc = hoje + relativedelta(months=i + 1)
        ref = f"{i+1}/{parcelas}"
        c.execute("""
            INSERT INTO mensalidades
            (aluno_id, valor, vencimento, status, tipo, parcela_ref)
            VALUES (?, ?, ?, 'Pendente', 'Mensalidade', ?)
        """, (aluno_id, valor_mensal, venc.strftime("%Y-%m-%d"), ref))

    conn.commit()
    conn.close()

    return redirect(f"/financeiro?aluno_id={aluno_id}&gerado=1")
@app.route("/adicionar_mensalidades/<int:aluno_id>", methods=["POST"])
def adicionar_mensalidades(aluno_id):
    if not logado():
        return redirect("/login")

    quantidade = int(request.form.get("quantidade", 1))

    conn = conectar_banco()
    c = conn.cursor()

    # busca valor da mensalidade do curso
    c.execute("""
        SELECT c.valor_mensal
        FROM alunos a
        JOIN cursos c ON c.id = a.curso_id
        WHERE a.id = ?
    """, (aluno_id,))
    curso = c.fetchone()

    if not curso:
        conn.close()
        return redirect(f"/financeiro?aluno_id={aluno_id}")

    valor_mensal = curso[0] or 0

    # última mensalidade (ignora material e matrícula)
    c.execute("""
        SELECT MAX(vencimento)
        FROM mensalidades
        WHERE aluno_id = ?
        AND tipo LIKE 'Mensalidade%'
    """, (aluno_id,))
    ultima = c.fetchone()[0]

    if ultima:
        data_base = datetime.strptime(ultima, "%Y-%m-%d")
    else:
        data_base = datetime.today()

    for i in range(quantidade):
        venc = data_base + relativedelta(months=i + 1)

        c.execute("""
            INSERT INTO mensalidades
            (aluno_id, valor, vencimento, status, tipo, parcela_ref)
            VALUES (?, ?, ?, 'Pendente', 'Mensalidade Extra', ?)
        """, (
            aluno_id,
            valor_mensal,
            venc.strftime("%Y-%m-%d"),
            f"Extra {i+1}/{quantidade}"
        ))

    conn.commit()
    conn.close()

    flash("✅ Novas mensalidades adicionadas com sucesso.", "sucesso")

    return redirect(f"/financeiro?aluno_id={aluno_id}")

@app.route("/editar_parcela/<int:id>", methods=["GET", "POST"])
def editar_parcela(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # BUSCA A PARCELA
    c.execute(
        "SELECT * FROM mensalidades WHERE id = ?",
        (id,)
    )
    parcela = c.fetchone()

    if parcela is None:
        conn.close()
        return redirect("/financeiro")

    aluno_id = parcela["aluno_id"]

    if request.method == "POST":
        valor = float(request.form.get("valor") or 0)
        vencimento = request.form.get("vencimento")
        tipo = request.form.get("tipo")

        c.execute(
            "UPDATE mensalidades SET valor=?, vencimento=?, tipo=? WHERE id=?",
            (valor, vencimento, tipo, id)
        )

        conn.commit()
        conn.close()
        return redirect(f"/financeiro?aluno_id={aluno_id}")

    conn.close()
    return render_template(
        "editar_parcela.html",
        parcela=parcela,          # 👈 AGORA EXISTE
        parcela_id=id,
        aluno_id=aluno_id,
        valor=parcela["valor"],
        vencimento=parcela["vencimento"],
        tipo=parcela["tipo"]
    )


@app.route("/pagar/<int:id>", methods=["GET", "POST"])
def pagar(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # pega o aluno da parcela
    c.execute("SELECT aluno_id FROM mensalidades WHERE id=?", (id,))
    aluno_id = c.fetchone()[0]

    if request.method == "POST":
        forma = request.form.get("forma")
        hoje = datetime.today().strftime("%Y-%m-%d")
        usuario = session.get("usuario_nome", "Sistema")

        c.execute("""
            UPDATE mensalidades
            SET status='Pago',
                data_pagamento=?,
                forma_pagamento=?,
                usuario_pagamento=?
            WHERE id=?
        """, (hoje, forma, usuario, id))

        conn.commit()
        conn.close()

        flash("💰 Pagamento registrado com sucesso.", "sucesso")

        return redirect(f"/financeiro?aluno_id={aluno_id}")

    conn.close()
    return render_template("pagar.html", id=id, aluno_id=aluno_id)

# ================== RELATÓRIO ==================

@app.route("/relatorio")
def relatorio():
    c = conectar_banco().cursor()
    c.execute("SELECT SUM(valor) FROM mensalidades WHERE status='Pago'")
    pago = c.fetchone()[0] or 0
    c.execute("SELECT SUM(valor) FROM mensalidades WHERE status='Pendente'")
    pendente = c.fetchone()[0] or 0
    return render_template("relatorio.html", total_pago=pago, total_pendente=pendente)
@app.route('/api/aluno/<int:aluno_id>')
def api_aluno(aluno_id):
    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        SELECT 
            id, nome, cpf, data_nascimento, email, telefone,
            responsavel_nome, responsavel_cpf, responsavel_telefone
        FROM alunos
        WHERE id = ?
    """, (aluno_id,))

    aluno = c.fetchone()
    conn.close()

    if not aluno:
        return jsonify({'erro': 'Aluno não encontrado'}), 404

    return jsonify({
        "id": aluno[0],
        "nome": aluno[1],
        "cpf": aluno[2],
        "data_nascimento": aluno[3],
        "email": aluno[4],
        "telefone": aluno[5],
        "responsavel_nome": aluno[6],
        "responsavel_cpf": aluno[7],
        "responsavel_telefone": aluno[8],
    })


@app.route("/salvar_matricula", methods=["POST"])
def salvar_matricula():
    if not logado():
        return redirect("/login")

    aluno_id = int(request.form.get("aluno_id"))
    curso_id = int(request.form.get("curso_id"))
    tipo_curso = request.form.get("tipo_curso")

    valor_matricula = float(request.form.get("valor_matricula") or 0)
    valor_mensal = float(request.form.get("valor_mensal") or 0)
    parcelas = int(request.form.get("parcelas") or 1)

    material_didatico = request.form.get("material_didatico") or "Digital"
    valor_material = float(request.form.get("valor_material") or 0)
    parcelas_material = int(request.form.get("parcelas_material") or 1)

    observacao = request.form.get("observacao")

    # DATAS
    hoje = datetime.today()
    data_matricula = request.form.get("data_matricula")
    data_primeira_mensalidade = request.form.get("data_primeira_mensalidade")
    data_material = request.form.get("data_material")

    data_matricula = datetime.strptime(data_matricula, "%Y-%m-%d") if data_matricula else hoje
    data_primeira_mensalidade = datetime.strptime(data_primeira_mensalidade, "%Y-%m-%d") if data_primeira_mensalidade else hoje
    data_material = datetime.strptime(data_material, "%Y-%m-%d") if data_material else hoje

    conn = conectar_banco()
    c = conn.cursor()

    # INSERE MATRÍCULA
    c.execute("""
        INSERT INTO matriculas
        (aluno_id, curso_id, tipo_curso, data_matricula, status,
         valor_matricula, valor_mensalidade, quantidade_parcelas,
         material_didatico, valor_material, observacao)
        VALUES (?, ?, ?, ?, 'ATIVA', ?, ?, ?, ?, ?, ?)
    """, (
        aluno_id,
        curso_id,
        tipo_curso,
        hoje.strftime("%Y-%m-%d"),
        valor_matricula,
        valor_mensal,
        parcelas,
        material_didatico,
        valor_material,
        observacao
    ))

    matricula_id = c.lastrowid

    # MATRÍCULA
    if valor_matricula > 0:
        c.execute("""
            INSERT INTO mensalidades
            (aluno_id, valor, vencimento, status, tipo, parcela_ref)
            VALUES (?, ?, ?, 'Pendente', 'Matrícula', '1/1')
        """, (aluno_id, valor_matricula, data_matricula.strftime("%Y-%m-%d")))

    # MENSALIDADES
    for i in range(parcelas):
        venc = data_primeira_mensalidade + relativedelta(months=i)
        ref = f"{i+1}/{parcelas}"

        c.execute("""
            INSERT INTO mensalidades
            (aluno_id, valor, vencimento, status, tipo, parcela_ref)
            VALUES (?, ?, ?, 'Pendente', 'Mensalidade', ?)
        """, (aluno_id, valor_mensal, venc.strftime("%Y-%m-%d"), ref))

    # MATERIAL
    if valor_material > 0:
        valor_parcela_material = valor_material / parcelas_material

        for i in range(parcelas_material):
            venc = data_material + relativedelta(months=i)
            ref = f"{i+1}/{parcelas_material}"

            c.execute("""
                INSERT INTO mensalidades
                (aluno_id, valor, vencimento, status, tipo, parcela_ref)
                VALUES (?, ?, ?, 'Pendente', 'Material', ?)
            """, (
                aluno_id,
                round(valor_parcela_material, 2),
                venc.strftime("%Y-%m-%d"),
                ref
            ))

    conn.commit()
    conn.close()

    return redirect(f"/movimentacao?matricula_id={matricula_id}")


@app.route("/recibo/<int:mensalidade_id>")
def recibo(mensalidade_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # busca dados da mensalidade
    c.execute("""
    SELECT 
        m.valor, m.tipo, m.parcela_ref, m.data_pagamento,
        m.forma_pagamento,
        a.nome,
        a.cpf,
        a.responsavel_nome,
        c2.nome
    FROM mensalidades m
    JOIN alunos a ON a.id = m.aluno_id
    JOIN cursos c2 ON c2.id = a.curso_id
    WHERE m.id = ?
""", (mensalidade_id,))
    r = c.fetchone()

    conn.close()

    if not r:
        return "Recibo não encontrado"

    valor, tipo, parcela, data_pg, forma, aluno, cpf, responsavel, curso = r

    # cria PDF em memória
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    pdf.setFont("Helvetica", 12)

    pdf.drawString(50, 800, "RECIBO DE PAGAMENTO")
    pdf.drawString(50, 770, f"Aluno: {aluno}")
    pdf.drawString(50, 750, f"CPF: {cpf or ''}")
    pdf.drawString(50, 730, f"Curso: {curso}")

    pdf.drawString(50, 700, f"Tipo: {tipo}")
    pdf.drawString(50, 680, f"Parcela: {parcela}")
    pdf.drawString(50, 660, f"Valor: R$ {valor:.2f}")
    pdf.drawString(50, 640, f"Forma de pagamento: {forma}")
    pdf.drawString(50, 620, f"Data do pagamento: {data_pg}")

    pdf.drawString(50, 580, "Declaro que recebi o valor acima descrito.")
    pdf.drawString(50, 540, "Assinatura: ______________________________")

    pdf.showPage()
    pdf.save()

    buffer.seek(0)

    response = make_response(buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=recibo.pdf'

    return response
@app.route("/carne/<int:aluno_id>")
def carne(aluno_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # dados do aluno
    c.execute("SELECT nome FROM alunos WHERE id=?", (aluno_id,))
    aluno = c.fetchone()
    if not aluno:
        conn.close()
        return "Aluno não encontrado"

    nome_aluno = aluno[0]

    # parcelas do aluno
    c.execute("""
        SELECT valor, vencimento, tipo, parcela_ref
        FROM mensalidades
        WHERE aluno_id=?
        ORDER BY vencimento
    """, (aluno_id,))
    parcelas = c.fetchall()

    conn.close()

    if not parcelas:
        return "Nenhuma parcela encontrada."

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    for p in parcelas:
        valor, venc, tipo, ref = p

        # CABEÇALHO PADRÃO DO SISTEMA
        y = cabecalho_pdf(pdf, largura, altura, "CARNÊ DE PAGAMENTO")

        y -= 40
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, y, f"Aluno: {nome_aluno}")

        y -= 30
        pdf.drawString(50, y, f"Tipo: {tipo}")

        y -= 30
        pdf.drawString(50, y, f"Parcela: {ref}")

        y -= 30
        pdf.drawString(50, y, f"Vencimento: {venc}")

        y -= 30
        pdf.drawString(50, y, f"Valor: R$ {valor:.2f}")

        y -= 50
        pdf.drawString(50, y, "Pagamento realizado em: ____/____/______")

        y -= 40
        pdf.drawString(50, y, "Assinatura: ______________________________")

        pdf.showPage()

    pdf.save()
    buffer.seek(0)

    return send_file(buffer, mimetype="application/pdf", as_attachment=False)

@app.route("/aluno/<int:aluno_id>")
def ficha_aluno(aluno_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # 🔹 DADOS DO ALUNO (MANTIDO COMO ESTÁ)
    c.execute("""
        SELECT 
            a.id,
            a.nome,
            a.cpf,
            a.rg,
            a.data_nascimento,
            a.telefone,
            a.telefone_contato,
            a.endereco,
            a.status,
            c.nome
        FROM alunos a
        LEFT JOIN cursos c ON c.id = a.curso_id
        WHERE a.id = ?
    """, (aluno_id,))
    aluno = c.fetchone()

    if not aluno:
        conn.close()
        return redirect("/cadastro")

    # 🔹 CURSOS MATRICULADOS (NOVO – SEM QUEBRAR NADA)
    c.execute("""
        SELECT c2.nome
        FROM matriculas m
        JOIN cursos c2 ON c2.id = m.curso_id
        WHERE m.aluno_id = ?
          AND m.status = 'ATIVA'
        ORDER BY m.id DESC
    """, (aluno_id,))
    cursos_matriculados = c.fetchall()

    conn.close()

    return render_template(
        "ficha_aluno.html",
        aluno=aluno,
        cursos_matriculados=cursos_matriculados
    )


@app.route("/ficha_matricula/<int:matricula_id>")
def ficha_matricula(matricula_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT 
            m.*, 
            a.nome AS aluno_nome,
            a.cpf,
            a.data_nascimento,
            a.telefone,
            a.telefone_contato,
            c.nome AS curso_nome,
            NULL AS duracao_curso
        FROM matriculas m
        JOIN alunos a ON a.id = m.aluno_id
        JOIN cursos c ON c.id = m.curso_id
        WHERE m.id = ?
    """, (matricula_id,))

    dados = c.fetchone()
    conn.close()

    if not dados:
        return redirect("/movimentacao")

    # RESPONSÁVEL AUTOMÁTICO
    responsavel = dados["aluno_nome"]
    tel_resp = dados["telefone"]

    if dados["data_nascimento"]:
        nasc = datetime.strptime(dados["data_nascimento"], "%Y-%m-%d").date()
        idade = (date.today() - nasc).days // 365
        if idade < 18:
            responsavel = "Responsável legal"
            tel_resp = dados["telefone_contato"] or ""

    # TOTAL (FORMA BLINDADA)
    valor_matricula = dados["valor_matricula"] or 0
    valor_mensal = (dados["valor_mensalidade"] or 0) * (dados["quantidade_parcelas"] or 0)
    valor_material = dados["valor_material"] or 0
    total = valor_matricula + valor_mensal + valor_material

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

        # ================= CABEÇALHO COMPLETO =================
    logo = os.path.join(app.root_path, "static", "logo_escola.png")

    topo = altura - 90

    # logo à esquerda
    if os.path.exists(logo):
        pdf.drawImage(
            logo,
            50,
            topo - 50,
            width=80,
            height=60,
            preserveAspectRatio=True,
            mask='auto'
        )

    # texto da escola
    texto_x = 140

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(texto_x, topo, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL CQP")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(texto_x, topo - 16, "CNPJ: 39.368.679/0001-01")
    pdf.drawString(texto_x, topo - 30, "Rua: Prata Mancebo nº 148 - Centro")
    pdf.drawString(texto_x, topo - 44, "Carapebus - RJ  CEP 27998-000")
    pdf.drawString(texto_x, topo - 58, "Tel.: (22) 99868-4334")
    pdf.drawString(texto_x, topo - 72, "E-mail: Centrodequalificacao@cqpcursos.com.br")

    # linha divisória
    pdf.line(50, topo - 85, largura - 50, topo - 85)

    # título
    y = topo - 120
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, "CONFIRMAÇÃO DE PRÉ-MATRÍCULA")

    # linha divisória
    pdf.line(50, topo - 75, largura - 50, topo - 75)

    # título do documento
    y = topo - 100
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, "CONFIRMAÇÃO DE PRÉ-MATRÍCULA")

    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "DADOS DO ALUNO")

    y -= 25
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "DADOS DO CURSO")

    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Curso: {dados['curso_nome']}")
    pdf.drawString(300, y, "Duração: Conforme cronograma")

    y -= 25
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "DADOS FINANCEIROS")

    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Matrícula: R$ {valor_matricula:.2f}")
    y -= 15
    pdf.drawString(50, y, f"Mensalidade: R$ {dados['valor_mensalidade']:.2f}")
    y -= 15
    pdf.drawString(50, y, f"Parcelas: {dados['quantidade_parcelas']}x")
    y -= 15
    pdf.drawString(50, y, f"Material Didático: {dados['material_didatico'] or 'Não informado'}")
    y -= 15
    pdf.drawString(50, y, f"Valor do Material Didático: R$ {valor_material:.2f}")
    y -= 15
    pdf.drawString(50, y, f"Valor Total do Curso: R$ {total:.2f}")

    # OBSERVAÇÕES
    if dados["observacao"]:
        y -= 25
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(50, y, "OBSERVAÇÕES")
        y -= 15
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, dados["observacao"])

    y -= 50
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, "Assinatura do Aluno/Responsável: ______________________________")
    y -= 30
    pdf.drawString(50, y, "Assinatura da Escola: ________________________________________")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, mimetype="application/pdf", as_attachment=False)

@app.route('/materias', methods=['GET', 'POST'])
def materias():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    cursor = conn.cursor()

    # ================= CADASTRAR MATÉRIA =================
    if request.method == 'POST' and 'nova_materia' in request.form:
        nome = request.form['nome'].strip()
        curso_id = request.form['curso_id']

        if nome and curso_id:
            # cria a matéria
            cursor.execute("""
                INSERT INTO materias (nome, ativa)
                VALUES (?, 1)
            """, (nome,))
            materia_id = cursor.lastrowid

            # vincula ao curso
            cursor.execute("""
                INSERT INTO cursos_materias (curso_id, materia_id)
                VALUES (?, ?)
            """, (curso_id, materia_id))

            conn.commit()
            flash('Matéria cadastrada com sucesso!', 'success')

    # ================= EXCLUIR MATÉRIA =================
    if request.method == 'POST' and 'excluir_materia' in request.form:
        materia_id = request.form['materia_id']

        cursor.execute("""
            UPDATE materias SET ativa = 0 WHERE id = ?
        """, (materia_id,))

        cursor.execute("""
            DELETE FROM cursos_materias WHERE materia_id = ?
        """, (materia_id,))

        conn.commit()
        flash('Matéria excluída!', 'success')

    # ================= EDITAR MATÉRIA =================
    if request.method == 'POST' and 'editar_materia' in request.form:
        materia_id = request.form['materia_id']
        novo_nome = request.form['novo_nome'].strip()

        if novo_nome:
            cursor.execute("""
                UPDATE materias SET nome = ?
                WHERE id = ?
            """, (novo_nome, materia_id))
            conn.commit()
            flash('Matéria atualizada!', 'success')

    # ================= CURSOS =================
    cursor.execute("""
        SELECT id, nome
        FROM cursos
        ORDER BY nome
    """)
    cursos = cursor.fetchall()

    # ================= MATÉRIAS POR CURSO =================
    cursor.execute("""
        SELECT 
            c.id,
            c.nome,
            m.id,
            m.nome
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
            materias_por_curso[(curso_id, curso_nome)].append(
                (materia_id, materia_nome)
            )

    conn.close()

    return render_template(
        'materias.html',
        cursos=cursos,
        materias_por_curso=materias_por_curso
    )


@app.route("/notas", methods=["GET", "POST"])
def notas():
    if not logado():
        return redirect("/login")

    termo = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)

    conn = conectar_banco()
    c = conn.cursor()

    alunos = []
    cursos_matriculados = []
    materias = []
    aluno_nome = ""

    # ================= BUSCAR ALUNOS =================
    if termo:
        c.execute(
            "SELECT id, nome FROM alunos WHERE nome LIKE ? ORDER BY nome",
            (f"%{termo}%",)
        )
        alunos = c.fetchall()

    # ================= DADOS DO ALUNO =================
    if aluno_id:
        c.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,))
        row = c.fetchone()
        if row:
            aluno_nome = row[0]

        # cursos em que o aluno está matriculado
        c.execute("""
            SELECT c.id, c.nome
            FROM cursos c
            JOIN matriculas m ON m.curso_id = c.id
            WHERE m.aluno_id = ?
            ORDER BY c.nome
        """, (aluno_id,))
        cursos_matriculados = c.fetchall()

      # ================= MATÉRIAS =================
    c.execute("""
    SELECT m.id, m.nome, cm.curso_id
    FROM materias m
    JOIN cursos_materias cm ON cm.materia_id = m.id
    ORDER BY m.nome
    """)
    materias = c.fetchall()

    # ================= SALVAR NOTAS =================
    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        curso_id = request.form.get("curso_id", type=int)

        for materia_id, _ in materias:
            nota = request.form.get(f"nota_{materia_id}")
            resultado = request.form.get(f"resultado_{materia_id}")

            if nota == "":
                nota = None

            c.execute("""
                INSERT INTO notas (aluno_id, curso_id, materia_id, nota, resultado)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(aluno_id, curso_id, materia_id)
                DO UPDATE SET
                    nota = excluded.nota,
                    resultado = excluded.resultado
            """, (aluno_id, curso_id, materia_id, nota, resultado))

        conn.commit()
        conn.close()
        return redirect(f"/notas?aluno_id={aluno_id}&curso_id={curso_id}")

    conn.close()

    return render_template(
        "notas.html",
        alunos=alunos,
        termo=termo,
        aluno_id=aluno_id,
        aluno_nome=aluno_nome,
        cursos_matriculados=cursos_matriculados,
        curso_id=curso_id,
        materias=materias
    )



@app.route("/notas_visualizar/<int:aluno_id>")
def notas_visualizar(aluno_id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    curso_id = request.args.get("curso_id", type=int)

    # Se não veio curso_id, tenta descobrir pela matrícula
    if not curso_id:
        c.execute("""
            SELECT curso_id
            FROM matriculas
            WHERE aluno_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (aluno_id,))
        mat = c.fetchone()
        if mat:
            curso_id = mat["curso_id"]

    # Nome do aluno
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
            SELECT
                m.nome,
                n.nota,
                n.resultado
            FROM cursos_materias cm
            JOIN materias m
                ON m.id = cm.materia_id
            LEFT JOIN notas n
                ON n.materia_id = m.id
               AND n.aluno_id = ?
               AND n.curso_id = ?
            WHERE cm.curso_id = ?
            ORDER BY m.nome
        """, (aluno_id, curso_id, curso_id))

        boletim = c.fetchall()

    conn.close()

    return render_template(
        "notas_visualizar.html",
        aluno_nome=aluno_nome,
        curso_nome=curso_nome,
        boletim=boletim
    )





@app.route('/cursos', methods=['GET', 'POST'])
def cursos_view():
    conn = conectar_banco()
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome'].strip()
        if nome:
            cursor.execute(
                "INSERT INTO cursos (nome) VALUES (?)",
                (nome,)
            )
            conn.commit()
            flash('Curso cadastrado com sucesso!', 'success')

    cursor.execute("SELECT id, nome, valor_mensal, valor_matricula, parcelas FROM cursos ORDER BY nome")
    cursos = cursor.fetchall()

    conn.close()

    return render_template(
        'cursos.html',
        cursos=cursos
    )

@app.route("/notas_pdf/<int:aluno_id>/<int:curso_id>")
def notas_pdf(aluno_id, curso_id):
    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ================= DADOS BÁSICOS =================
    aluno = cur.execute(
        "SELECT nome FROM alunos WHERE id = ?",
        (aluno_id,)
    ).fetchone()

    curso = cur.execute(
        "SELECT nome FROM cursos WHERE id = ?",
        (curso_id,)
    ).fetchone()

    # ================= BOLETIM (REGRA CORRETA) =================
    notas = cur.execute("""
        SELECT
            m.nome AS materia,
            n.nota,
            n.resultado,
            CASE
                WHEN n.resultado IS NULL THEN 'CURSANDO'
                WHEN n.resultado = 'NAO_CURSOU' THEN 'NÃO CURSADA'
                ELSE 'CONCLUÍDA'
            END AS situacao
        FROM cursos_materias cm
        JOIN materias m
            ON m.id = cm.materia_id
        LEFT JOIN notas n
            ON n.materia_id = m.id
           AND n.aluno_id = ?
           AND n.curso_id = ?
        WHERE cm.curso_id = ?
        ORDER BY m.nome
    """, (aluno_id, curso_id, curso_id)).fetchall()

    conn.close()

    # ================= PDF =================
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # ================= CABEÇALHO =================
    logo_path = os.path.join(app.root_path, "static", "logo_escola.png")
    topo = altura - 80

    if os.path.exists(logo_path):
        pdf.drawImage(
            logo_path,
            50,
            topo - 40,
            width=100,
            height=45,
            preserveAspectRatio=True,
            mask='auto'
        )

    texto_x = 170
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(texto_x, topo, "Centro de Qualificação Profissional")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(texto_x, topo - 18, "Endereço: Rua Prata Mancebo, 148 - Centro, Carapebus-RJ")
    pdf.drawString(texto_x, topo - 32, "Telefone: (22) 99868-4334")
    pdf.drawString(texto_x, topo - 46, "CNPJ: 39.368.679/0001-01")


    pdf.line(50, topo - 65, largura - 50, topo - 65)

    # ================= IDENTIFICAÇÃO =================
    y = topo - 80
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Aluno: {aluno['nome']}")
    y -= 15
    pdf.drawString(50, y, f"Curso: {curso['nome']}")
    y -= 15
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data: {date.today().strftime('%d/%m/%Y')}")

    # ================= TABELA =================
    y -= 30
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Matéria")
    pdf.drawString(260, y, "Nota")
    pdf.drawString(330, y, "Resultado")
    pdf.drawString(440, y, "Situação")

    y -= 8
    pdf.line(50, y, largura - 50, y)

    pdf.setFont("Helvetica", 10)
    y -= 20

    # ================= ASSINATURA =================
    y -= 30
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(largura / 2, y, "Assinatura da Escola")

    assinatura_path = os.path.join(app.root_path, "static", "assinatura.png")
    if os.path.exists(assinatura_path):
        pdf.drawImage(
            assinatura_path,
            largura / 2 - 80,
            y - 50,
            width=160,
            height=40,
            preserveAspectRatio=True,
            mask='auto'
        )
    else:
        pdf.line(largura / 2 - 100, y - 30, largura / 2 + 100, y - 30)


    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="boletim_notas.pdf",
        mimetype="application/pdf"
    )

@app.route("/frequencia", methods=["GET", "POST"])
def frequencia():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    termo = request.args.get("q", "")
    aluno_id = request.args.get("aluno_id", type=int)

    alunos = []
    aluno_nome = None
    cursos_matriculados = []
    curso_id = None

    # ===== BUSCAR ALUNOS =====
    if termo:
        c.execute(
            "SELECT id, nome FROM alunos WHERE nome LIKE ? ORDER BY nome",
            (f"%{termo}%",)
        )
        alunos = c.fetchall()

    # ===== DADOS DO ALUNO =====
    if aluno_id:
        c.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,))
        row = c.fetchone()
        if row:
            aluno_nome = row["nome"]

        c.execute("""
            SELECT c.id, c.nome
            FROM cursos c
            JOIN matriculas m ON m.curso_id = c.id
            WHERE m.aluno_id = ?
              AND m.status = 'ATIVA'
            ORDER BY c.nome
        """, (aluno_id,))
        cursos_matriculados = c.fetchall()

        c.execute("""
            SELECT curso_id
            FROM matriculas
            WHERE aluno_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (aluno_id,))
        mat = c.fetchone()

        if mat:
            curso_id = mat["curso_id"]

    # ===== SALVAR FREQUÊNCIA =====
    if request.method == "POST":
        aluno_id = request.form.get("aluno_id", type=int)
        curso_id = request.form.get("curso_id", type=int)
        data_aula = request.form.get("data")
        status = request.form.get("status")

        if aluno_id and curso_id and data_aula and status:
            c.execute("""
                INSERT INTO frequencias (aluno_id, curso_id, data, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(aluno_id, curso_id, data)
                DO UPDATE SET status = excluded.status
            """, (aluno_id, curso_id, data_aula, status))

            conn.commit()
            flash("✅ Frequência salva com sucesso.", "sucesso")

            return redirect(f"/frequencia?aluno_id={aluno_id}&curso_id={curso_id}&data={data_aula}")

    conn.close()

    return render_template(
        "frequencia.html",
        alunos=alunos,
        aluno_id=aluno_id,
        aluno_nome=aluno_nome,
        cursos_matriculados=cursos_matriculados,
        curso_id=curso_id,
        termo=termo
    )
@app.route("/frequencia_historico")
def frequencia_historico():
    if not logado():
        return redirect("/login")

    aluno_id = request.args.get("aluno_id", type=int)
    curso_id = request.args.get("curso_id", type=int)

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    aluno = None
    curso = None
    historico = []

    if aluno_id and curso_id:
        c.execute("SELECT id, nome FROM alunos WHERE id = ?", (aluno_id,))
        aluno = c.fetchone()

        c.execute("SELECT id, nome FROM cursos WHERE id = ?", (curso_id,))
        curso = c.fetchone()

        c.execute("""
            SELECT data, status
            FROM frequencias
            WHERE aluno_id = ? AND curso_id = ?
            ORDER BY data
        """, (aluno_id, curso_id))
        historico = c.fetchall()

    conn.close()

    return render_template(
        "frequencia_historico.html",
        aluno=aluno,
        curso=curso,
        historico=historico
    )
@app.route("/frequencia_historico_pdf/<aluno_id>/<curso_id>")
def frequencia_historico_pdf(aluno_id, curso_id):

    aluno_id = int(aluno_id)
    curso_id = int(curso_id)

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT nome FROM alunos WHERE id = ?", (aluno_id,))
    aluno = c.fetchone()

    c.execute("SELECT nome FROM cursos WHERE id = ?", (curso_id,))
    curso = c.fetchone()

    if not aluno or not curso:
        return "Aluno ou curso não encontrado"

    c.execute("""
        SELECT data, status
        FROM frequencias
        WHERE aluno_id = ? AND curso_id = ?
        ORDER BY data
    """, (aluno_id, curso_id))

    historico = c.fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    # ================= CABEÇALHO =================
    logo_path = os.path.join(app.root_path, "static", "logo_escola.png")
    topo = altura - 80

    if os.path.exists(logo_path):
        pdf.drawImage(
            logo_path,
            50,
            topo - 40,
            width=100,
            height=45,
            preserveAspectRatio=True,
            mask='auto'
        )

    texto_x = 170
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(texto_x, topo, "Centro de Qualificação Profissional")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(texto_x, topo - 18, "Endereço: Rua Prata Mancebo, 148 - Centro, Carapebus-RJ")
    pdf.drawString(texto_x, topo - 32, "Telefone: (22) 99868-4334")
    pdf.drawString(texto_x, topo - 46, "CNPJ: 39.368.679/0001-01")

    pdf.line(50, topo - 65, largura - 50, topo - 65)

    # ================= TÍTULO =================
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

    # ================= LISTA =================
    for h in historico:
        status = "Presente" if h["status"] == "P" else "Falta"
        pdf.drawString(50, y, f"{h['data']} - {status}")
        y -= 20

        if y < 150:
            pdf.showPage()
            y = altura - 60

    # ================= RODAPÉ CENTRALIZADO =================
    centro = largura / 2
    assinatura_path = os.path.join(app.root_path, "static", "assinatura.png")
    if os.path.exists(assinatura_path):
        pdf.drawImage(
            assinatura_path,
            centro - 80,
            90,
            width=160,
            height=40,
            preserveAspectRatio=True,
            mask='auto'
        )
    else:
        pdf.line(centro - 100, 105, centro + 100, 105)

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(centro, 75, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL CQP")

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(centro, 60, "CNPJ: 39.368.679/0001-01")

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="historico_frequencia.pdf",
        mimetype="application/pdf"
    )
@app.route("/pre_matricula", methods=["POST"])
def pre_matricula():
    if not logado():
        return redirect("/login")

    aluno_id = int(request.form.get("aluno_id"))
    curso_id = int(request.form.get("curso_id"))

    valor_matricula = float(request.form.get("valor_matricula") or 0)
    valor_mensal = float(request.form.get("valor_mensal") or 0)
    parcelas = int(request.form.get("parcelas") or 1)

    valor_material = float(request.form.get("valor_material") or 0)
    parcelas_material = int(request.form.get("parcelas_material") or 1)

    material_didatico = request.form.get("material_didatico")
    observacao = request.form.get("observacao")

    data_matricula = request.form.get("data_matricula") or "-"
    data_primeira = request.form.get("data_primeira_mensalidade") or "-"

    # cálculos
    total_mensalidades = valor_mensal * parcelas
    parcela_material = 0
    if parcelas_material > 0:
        parcela_material = valor_material / parcelas_material

    total_geral = total_mensalidades + valor_material

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM alunos WHERE id = ?", (aluno_id,))
    aluno = c.fetchone()

    c.execute("SELECT * FROM cursos WHERE id = ?", (curso_id,))
    curso = c.fetchone()

    conn.close()

    # idade
    idade = 0
    if aluno["data_nascimento"]:
        try:
           nasc = datetime.strptime(aluno["data_nascimento"], "%Y-%m-%d").date()
           idade = (date.today() - nasc).days // 365
        except:
            idade = 0
            
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

      # cabeçalho padrão
    y = cabecalho_pdf(pdf, largura, altura, "CONFIRMAÇÃO DE PRÉ-MATRÍCULA")
    # linha
    pdf.line(50, altura - 150, largura - 50, altura - 150)

    # título
    y = altura - 180
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, "CONFIRMAÇÃO DE PRÉ-MATRÍCULA")

    # DADOS DO ALUNO
            # ================= TABELA DADOS DO CANDIDATO =================
    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "DADOS DO CANDIDATO:")

    y -= 20

    linhas = [
        ("Nome do aluno", aluno["nome"]),
        ("Idade", str(idade)),
        ("Endereço", aluno["endereco"] or "")
    ]

    # dados do responsável se for menor
    if idade < 18 and aluno["responsavel_nome"]:
        linhas.append(("Responsável", aluno["responsavel_nome"]))
        if aluno["responsavel_cpf"]:
            linhas.append(("CPF", aluno["responsavel_cpf"]))
        if aluno["responsavel_telefone"]:
            linhas.append(("WhatsApp", aluno["responsavel_telefone"]))

    x_col1 = 50
    x_col2 = 220
    largura1 = 170
    largura2 = 360
    altura_linha = 20

    for campo, valor in linhas:
        # fundo cinza no campo
        pdf.setFillGray(0.9)
        pdf.rect(x_col1, y - 5, largura1, altura_linha, stroke=1, fill=1)
        pdf.setFillGray(0)

        # coluna do valor
        pdf.rect(x_col2, y - 5, largura2, altura_linha, stroke=1, fill=0)

        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x_col1 + 5, y, campo)

        pdf.setFont("Helvetica", 10)
        pdf.drawString(x_col2 + 5, y, valor)

        y -= altura_linha


    
       # ================= TABELA FINANCEIRA =================
    y -= 30
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "DADOS FINANCEIROS:")

    y -= 20

    linhas = [
        ("Taxa de matrícula", f"R$ {valor_matricula:.2f}"),
        ("Valor da mensalidade", f"R$ {valor_mensal:.2f}"),
        ("Parcelas do curso", f"{parcelas}x"),
        ("Material didático", material_didatico or "Não informado"),
        ("Valor do material didático", f"R$ {valor_material:.2f}")
    ]

    if valor_material > 0:
        linhas.append(
            ("Parcelas do material", f"{parcelas_material}x de R$ {parcela_material:.2f}")
        )

    # TOTAL FINAL
    linhas.append(
        ("TOTAL DO CURSO + MATERIAL", f"R$ {total_geral:.2f}")
    )


    x_col1 = 50
    x_col2 = 220
    largura1 = 170
    largura2 = 360
    altura_linha = 18

    for campo, valor in linhas:
        # destaque especial para o total
        if "TOTAL" in campo:
            pdf.setFont("Helvetica-Bold", 9)
        else:
            pdf.setFont("Helvetica", 10)

        # fundo cinza na descrição
        pdf.setFillGray(0.9)
        pdf.rect(x_col1, y - 5, largura1, altura_linha, stroke=1, fill=1)
        pdf.setFillGray(0)

        # coluna do valor
        pdf.rect(x_col2, y - 5, largura2, altura_linha, stroke=1, fill=0)

        pdf.drawString(x_col1 + 5, y, campo)
        pdf.drawRightString(x_col2 + largura2 - 5, y, valor)

        y -= altura_linha


    # ================= TABELA DATAS =================
    y -= 25

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "DATAS DE PAGAMENTO")

    y -= 20

    # converter datas para formato brasileiro
    def formatar_data(data_str):
        try:
            d = datetime.strptime(data_str, "%Y-%m-%d")
            return d.strftime("%d/%m/%Y")
        except:
            return data_str

    data_matricula_br = formatar_data(data_matricula)
    data_primeira_br = formatar_data(data_primeira)

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data do pagamento da matrícula: {data_matricula_br}")

    y -= 15
    pdf.drawString(50, y, f"Primeira mensalidade: {data_primeira_br}")

    y -= 20

    # valor da parcela final
    if valor_material > 0:
        parcela_total = valor_mensal + parcela_material
        texto_parcela = f"Mensalidade + Apostila: R$ {parcela_total:.2f}"
    else:
        texto_parcela = f"Mensalidade: R$ {valor_mensal:.2f}"

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, texto_parcela)
    # ASSINATURA
        # ================= RODAPÉ PADRONIZADO =================
    y = 150

    # data de emissão
    data_emissao = date.today().strftime("%d/%m/%Y")
    numero_pre = f"{aluno_id:04d}"

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data de emissão: {data_emissao}")
    y -= 15
    pdf.drawString(50, y, f"Pré-matrícula nº: {numero_pre}")

    # linhas de assinatura
    y -= 50
    pdf.line(50, y, 250, y)
    pdf.line(330, y, 530, y)

    pdf.setFont("Helvetica", 10)
    pdf.drawString(89, y - 15, "Assinatura do responsável")
    pdf.drawString(360, y - 15, "Centro de Qualificação Profissional")

    # assinatura da escola (imagem opcional)
    assinatura = os.path.join(app.root_path, "static", "assinatura.png")
    if os.path.exists(assinatura):
        pdf.drawImage(assinatura, 360, y + 10, width=140, height=40, preserveAspectRatio=True)


    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, mimetype="application/pdf", as_attachment=False)
@app.route("/dashboard")
def dashboard():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    # ===== VENDAS POR TIPO (USADO NO GRÁFICO) =====
    c.execute("""
        SELECT 
            COALESCE(tipo_curso, 'Não definido'),
            COUNT(*)
        FROM matriculas
        WHERE status = 'ATIVA'
        GROUP BY tipo_curso
    """)
    vendas_tipo = c.fetchall()


    conn = conectar_banco()
    c = conn.cursor()

    hoje = datetime.today()
    mes_atual = hoje.strftime("%Y-%m")
    mes = request.args.get("mes") or mes_atual

    # ================= DESPESAS DO MÊS (PROFISSIONAL CORRIGIDO) =================
    despesas_mes = 0

    if mes:
        inicio_mes = f"{mes}-01"
        fim_mes = f"{mes}-31"
  
    # ================= VARIÁVEIS (NÃO RECORRENTES) =================
    c.execute("""
        SELECT SUM(valor)
        FROM despesas
        WHERE recorrente = 0
        AND strftime('%Y-%m', data) = ?
    """, (mes,))
    
    variaveis = c.fetchone()[0] or 0

    # ================= RECORRENTES =================
    c.execute("""
        SELECT valor, dia_vencimento, data
        FROM despesas
        WHERE recorrente = 1
    """)

    fixas = 0

    for valor, dia, data_inicio in c.fetchall():

        if not dia:
            continue

        data_inicio = str(data_inicio)[:7]

        # só entra se já começou até esse mês
        if data_inicio <= mes:
            try:
                fixas += float(valor or 0)
            except:
                continue

    despesas_mes = variaveis + fixas

    inicio = f"{mes}-01"
    fim = f"{mes}-31"
    # RECEBIDO NO MÊS
    c.execute("""
        SELECT SUM(valor)
        FROM mensalidades
        WHERE status='Pago'
        AND data_pagamento BETWEEN ? AND ?
    """, (inicio, fim))
    recebido_mes = c.fetchone()[0] or 0

    # A RECEBER
    c.execute("""
        SELECT SUM(valor)
        FROM mensalidades
        WHERE status='Pendente'
        AND vencimento BETWEEN ? AND ?
    """, (inicio, fim))
    a_receber_mes = c.fetchone()[0] or 0

    # ATRASO
    c.execute("""
        SELECT SUM(valor)
        FROM mensalidades
        WHERE status='Pendente'
        AND vencimento < ?
    """, (inicio,))
    total_atraso = c.fetchone()[0] or 0

    # INADIMPLENTES
    c.execute("""
        SELECT COUNT(DISTINCT aluno_id)
        FROM mensalidades
        WHERE status='Pendente'
        AND vencimento < ?
    """, (inicio,))
    inadimplentes = c.fetchone()[0] or 0

    # ALUNOS ATIVOS
    c.execute("SELECT COUNT(*) FROM alunos WHERE status='Ativo'")
    alunos_ativos = c.fetchone()[0] or 0

    # MATRÍCULAS NO MÊS (A PARTIR DE JAN/2026)
    inicio_base = "2026-01-01"
    c.execute("""
        SELECT COUNT(*)
        FROM matriculas
        WHERE data_matricula BETWEEN ? AND ?
        AND data_matricula >= ?
    """, (inicio, fim, inicio_base))
    matriculas_mes = c.fetchone()[0] or 0

    # PARCELAS VENCENDO
    c.execute("""
        SELECT COUNT(*)
        FROM mensalidades
        WHERE status='Pendente'
        AND vencimento BETWEEN ? AND ?
    """, (inicio, fim))
    vencendo = c.fetchone()[0] or 0

    # ===== MATRÍCULAS FUTURAS (PENDENTES) =====
    c.execute("""
        SELECT SUM(valor)
        FROM mensalidades
        WHERE status='Pendente'
        AND tipo='Matrícula'
    """)
    matriculas_futuras = c.fetchone()[0] or 0


    # INDICADORES
    receita_projetada = recebido_mes + a_receber_mes
    ticket_medio = recebido_mes / alunos_ativos if alunos_ativos > 0 else 0

    total_carteira = a_receber_mes + total_atraso
    taxa_inadimplencia = (total_atraso / total_carteira) * 100 if total_carteira > 0 else 0

    # CANCELAMENTOS
    c.execute("""
        SELECT COUNT(*)
        FROM alunos
        WHERE LOWER(status) = 'cancelado'
    """)
    cancelamentos = c.fetchone()[0] or 0

    # RECEITA MÉDIA
    receita_media = recebido_mes / matriculas_mes if matriculas_mes > 0 else 0

    # META
    meta_por_aluno = 200
    meta_mensal = alunos_ativos * meta_por_aluno

    # EVASÃO
    total_alunos = alunos_ativos + cancelamentos
    taxa_evasao = (cancelamentos / total_alunos) * 100 if total_alunos > 0 else 0

    # ===== ANALISE COMERCIAL (RELATORIO) =====
    rel = buscar_relatorio_mes(mes)

    rel_meta = rel["meta"]
    rel_realizado = rel["realizado"]
    rel_matriculas = rel["matriculas"]
    rel_vendas = rel["vendas"]

    
   # ===== GRÁFICO RECEITA (DESDE JAN DO ANO ATUAL) =====
    meses = []
    valores = []
    meses_pt = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    for m in range(1, hoje.month + 1):
        inicio_mes = f"{hoje.year}-{m:02d}-01"
        fim_mes = f"{hoje.year}-{m:02d}-31"

        c.execute("""
            SELECT SUM(valor)
            FROM mensalidades
            WHERE status='Pago'
            AND data_pagamento BETWEEN ? AND ?
        """, (inicio_mes, fim_mes))

        total = c.fetchone()[0] or 0
        meses.append(f"{meses_pt[m-1]}/{str(hoje.year)[2:]}")
        valores.append(total)

        # ===== RANKING DE CURSOS =====
        c.execute("""
            SELECT c.nome, SUM(m.valor) as total
            FROM mensalidades m
            JOIN matriculas mat ON mat.aluno_id = m.aluno_id
            JOIN cursos c ON c.id = mat.curso_id
            WHERE m.status = 'Pago'
            AND m.data_pagamento BETWEEN ? AND ?
            GROUP BY c.nome
            ORDER BY total DESC
            LIMIT 5
        """, (inicio, fim))
        ranking_cursos = c.fetchall()


     # ===== RECEBIMENTO DE MATRÍCULAS NO MÊS (APÓS DATA BASE) =====
    inicio_base = "18-02-2026"  # data de início do controle real

    c.execute("""
        SELECT SUM(valor)
        FROM mensalidades
        WHERE status = 'Pago'
        AND tipo = 'Matrícula'
        AND data_pagamento BETWEEN ? AND ?
    """, (inicio, fim))
    
    recebimento_matricula = c.fetchone()[0] or 0
 
            # ================= DESPESAS DO MÊS (PROFISSIONAL) =================
    despesas_mes = 0

    if mes:
        inicio_mes = f"{mes}-01"
        fim_mes = f"{mes}-31"

        # VARIÁVEIS
        c.execute(
            "SELECT SUM(valor) FROM despesas WHERE recorrente = 0 AND data BETWEEN ? AND ?",
            (inicio_mes, fim_mes)
        )
        variaveis = c.fetchone()[0] or 0

        # RECORRENTES
        c.execute(
            "SELECT valor, dia_vencimento, data FROM despesas WHERE recorrente = 1"
        )

        fixas = 0
        for valor, dia, data_inicio in c.fetchall():

            if not dia:
                continue

            data_inicio = str(data_inicio)

            if data_inicio[:7] <= mes:
                try:
                    fixas += float(valor or 0)
                except:
                    continue

        despesas_mes = variaveis + fixas

   
    # ================= LUCRO =================
    lucro_liquido = recebido_mes - despesas_mes

    margem_lucro = 0
    if recebido_mes > 0:
        margem_lucro = (lucro_liquido / recebido_mes) * 100
    
    # ================= DADOS DO GRÁFICO RECEITA x DESPESA =================
    grafico_financeiro = [
        ("Receita", recebido_mes),
        ("Despesas", despesas_mes),
        ("Lucro", lucro_liquido if lucro_liquido > 0 else 0)
    ]

    # ===== ANALISE COMERCIAL (RELATORIO) =====
    rel = buscar_relatorio_mes(mes)

    rel_meta = rel["meta"]
    rel_realizado = rel["realizado"]
    rel_matriculas = rel["matriculas"]
    rel_vendas = rel["vendas"]

    conn.close()

    return render_template(
        "dashboard.html",
        mes=mes,
        recebido_mes=recebido_mes,
        a_receber_mes=a_receber_mes,
        total_atraso=total_atraso,
        inadimplentes=inadimplentes,
        alunos_ativos=alunos_ativos,
        despesas_mes=despesas_mes,
        lucro_liquido=lucro_liquido,
        margem_lucro=margem_lucro,
        matriculas_mes=matriculas_mes,
        vencendo=vencendo,
        matriculas_futuras=matriculas_futuras,
        receita_projetada=receita_projetada,
        ticket_medio=ticket_medio,
        taxa_inadimplencia=taxa_inadimplencia,
        cancelamentos=cancelamentos,
        receita_media=receita_media,
        meta_mensal=meta_mensal,
        taxa_evasao=taxa_evasao,
        grafico_financeiro=grafico_financeiro,
        meses=meses,
        valores=valores,
        ranking_cursos=ranking_cursos,
        vendas_tipo=vendas_tipo,
        recebimento_matricula=recebimento_matricula,
        rel_meta=rel_meta,
        rel_realizado=rel_realizado,
        rel_matriculas=rel_matriculas,
        rel_vendas=rel_vendas
    )
 
            # ================= DESPESAS DO MÊS (PROFISSIONAL) =================
    despesas_mes = 0

    if mes:
        inicio_mes = f"{mes}-01"
        fim_mes = f"{mes}-31"

        # VARIÁVEIS
        c.execute(
            "SELECT SUM(valor) FROM despesas WHERE recorrente = 0 AND data BETWEEN ? AND ?",
            (inicio_mes, fim_mes)
        )
        variaveis = c.fetchone()[0] or 0

        # RECORRENTES
        c.execute(
            "SELECT valor, dia_vencimento, data FROM despesas WHERE recorrente = 1"
        )

        fixas = 0
        for valor, dia, data_inicio in c.fetchall():

            if not dia:
                continue

            data_inicio = str(data_inicio)

            if data_inicio[:7] <= mes:
                try:
                    fixas += float(valor or 0)
                except:
                    continue

        despesas_mes = variaveis + fixas

   
    # ================= LUCRO =================
    lucro_liquido = recebido_mes - despesas_mes

    margem_lucro = 0
    if recebido_mes > 0:
        margem_lucro = (lucro_liquido / recebido_mes) * 100
    
    # ================= DADOS DO GRÁFICO RECEITA x DESPESA =================
    grafico_financeiro = [
        ("Receita", recebido_mes),
        ("Despesas", despesas_mes),
        ("Lucro", lucro_liquido if lucro_liquido > 0 else 0)
    ]

    # ===== ANALISE COMERCIAL (RELATORIO) =====
    rel = buscar_relatorio_mes(mes)

    rel_meta = rel["meta"]
    rel_realizado = rel["realizado"]
    rel_matriculas = rel["matriculas"]
    rel_vendas = rel["vendas"]

    conn.close()

    return render_template(
        "dashboard.html",
        mes=mes,
        recebido_mes=recebido_mes,
        a_receber_mes=a_receber_mes,
        total_atraso=total_atraso,
        inadimplentes=inadimplentes,
        alunos_ativos=alunos_ativos,
        despesas_mes=despesas_mes,
        lucro_liquido=lucro_liquido,
        margem_lucro=margem_lucro,
        matriculas_mes=matriculas_mes,
        vencendo=vencendo,
        matriculas_futuras=matriculas_futuras,
        receita_projetada=receita_projetada,
        ticket_medio=ticket_medio,
        taxa_inadimplencia=taxa_inadimplencia,
        cancelamentos=cancelamentos,
        receita_media=receita_media,
        meta_mensal=meta_mensal,
        taxa_evasao=taxa_evasao,
        grafico_financeiro=grafico_financeiro,
        meses=meses,
        valores=valores,
        ranking_cursos=ranking_cursos,
        vendas_tipo=vendas_tipo,
        recebimento_matricula=recebimento_matricula,
        rel_meta=rel_meta,
        rel_realizado=rel_realizado,
        rel_matriculas=rel_matriculas,
        rel_vendas=rel_vendas
    )

   # ================== DESPESAS ==================

@app.route("/despesas", methods=["GET", "POST"])
def despesas():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # CADASTRAR DESPESA
    if request.method == "POST":
        descricao = request.form["descricao"]

        try:
            valor = float(request.form.get("valor", 0))
        except:
            valor = 0

        tipo = request.form["tipo"]
        categoria = request.form.get("categoria")
        data = request.form["data"]
        observacao = request.form.get("observacao")
 
        # 🔹 NOVOS CAMPOS
        recorrente = request.form.get("recorrente", 0)
        dia_vencimento = request.form.get("dia_vencimento")

        # segurança
        recorrente = int(recorrente) if recorrente else 0
        dia_vencimento = int(dia_vencimento) if dia_vencimento else None

        if descricao and valor > 0 and data:
            c.execute("""
                INSERT INTO despesas (
                    descricao, valor, tipo, categoria, data, observacao,
                    recorrente, dia_vencimento
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
               descricao,
               valor,
               tipo,
               categoria,
               data,
               observacao,
               recorrente,
               dia_vencimento
            ))
            conn.commit()
            flash("Despesa cadastrada com sucesso.", "sucesso")
            return redirect("/despesas")

    # LISTAR DESPESAS
    c.execute("""
        SELECT * FROM despesas
        ORDER BY data DESC
    """)
    despesas = c.fetchall()

    conn.close()

    return render_template("despesas.html", despesas=despesas)
@app.route("/excluir_despesa/<int:id>")
def excluir_despesa(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("DELETE FROM despesas WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    flash("Despesa excluída com sucesso.", "sucesso")
    return redirect("/despesas")


@app.route("/editar_despesa/<int:id>", methods=["GET", "POST"])
def editar_despesa(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == "POST":
        descricao = request.form.get("descricao")
        valor = float(request.form.get("valor") or 0)
        tipo = request.form.get("tipo")
        categoria = request.form.get("categoria")
        data = request.form.get("data")
        observacao = request.form.get("observacao")

        c.execute("""
            UPDATE despesas
            SET descricao=?, valor=?, tipo=?, categoria=?, data=?, observacao=?
            WHERE id=?
        """, (descricao, valor, tipo, categoria, data, observacao, id))

        conn.commit()
        conn.close()

        flash("Despesa atualizada com sucesso.", "sucesso")
        return redirect("/despesas")

    c.execute("SELECT * FROM despesas WHERE id = ?", (id,))
    despesa = c.fetchone()

    conn.close()

    return render_template("editar_despesa.html", despesa=despesa)
# ================= FUNCIONÁRIOS =================

@app.route("/novo_funcionario")
def novo_funcionario():
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        SELECT id, nome, usuario, perfil
        FROM usuarios
        ORDER BY nome
    """)
    funcionarios = c.fetchall()

    conn.close()

    return render_template("funcionario.html", funcionarios=funcionarios)


@app.route("/salvar_funcionario", methods=["POST"])
def salvar_funcionario():
    if not logado():
        return redirect("/login")

    if session.get("perfil") != "Administrador":
        flash("Acesso restrito.", "erro")
        return redirect("/")

    nome = request.form.get("nome")
    cpf = request.form.get("cpf")
    data_nascimento = request.form.get("data_nascimento")
    status = request.form.get("status")
    telefone = request.form.get("telefone")
    email = request.form.get("email")

    cep = request.form.get("cep")
    bairro = request.form.get("bairro")
    cidade = request.form.get("cidade")
    estado = request.form.get("estado")
    endereco = request.form.get("endereco")
    complemento = request.form.get("complemento")

    usuario = request.form.get("usuario")
    senha = request.form.get("senha")
    perfil = request.form.get("perfil")

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        INSERT INTO usuarios (
            nome, cpf, data_nascimento, status,
            telefone, email,
            cep, bairro, cidade, estado, endereco, complemento,
            usuario, senha, perfil
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nome, cpf, data_nascimento, status,
        telefone, email,
        cep, bairro, cidade, estado, endereco, complemento,
        usuario, senha, perfil
    ))

    conn.commit()
    conn.close()

    flash("Funcionário cadastrado com sucesso.", "sucesso")
    return redirect("/cadastro")
# ================= EDITAR FUNCIONÁRIO =================
@app.route("/editar_funcionario/<int:id>", methods=["GET", "POST"])
def editar_funcionario(id):
    if not logado():
        return redirect("/login")

    if session.get("perfil") != "Administrador":
        flash("Acesso restrito.", "erro")
        return redirect("/")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == "POST":
        nome = request.form.get("nome")
        usuario = request.form.get("usuario")
        perfil = request.form.get("perfil")

        c.execute("""
            UPDATE usuarios
            SET nome=?, usuario=?, perfil=?
            WHERE id=?
        """, (nome, usuario, perfil, id))

        conn.commit()
        conn.close()

        flash("Funcionário atualizado.", "sucesso")
        return redirect("/novo_funcionario")

    c.execute("SELECT * FROM usuarios WHERE id=?", (id,))
    funcionario = c.fetchone()
    conn.close()

    return render_template("editar_funcionario.html", funcionario=funcionario)


# ================= EXCLUIR FUNCIONÁRIO =================
@app.route("/excluir_funcionario/<int:id>")
def excluir_funcionario(id):
    if not logado():
        return redirect("/login")

    if session.get("perfil") != "Administrador":
        flash("Acesso restrito.", "erro")
        return redirect("/")

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("DELETE FROM usuarios WHERE id=?", (id,))

    conn.commit()
    conn.close()

    flash("Funcionário excluído.", "sucesso")
    return redirect("/novo_funcionario")
# ================= VER FUNCIONÁRIO =================
@app.route("/ver_funcionario/<int:id>")
def ver_funcionario(id):
    if not logado():
        return redirect("/login")

    conn = conectar_banco()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM usuarios WHERE id=?", (id,))
    funcionario = c.fetchone()

    conn.close()

    return render_template("ver_funcionario.html", funcionario=funcionario)

# ================== RELATORIO BANCO ==================

@app.route("/salvar_relatorio", methods=["POST"])
def salvar_relatorio():
    dados = request.get_json()

    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes TEXT UNIQUE,
            meta INTEGER,
            realizado INTEGER,
            matriculas INTEGER,
            matriculas_venda INTEGER
        )
    """)

    c.execute("""
        INSERT INTO relatorios (mes, meta, realizado, matriculas, matriculas_venda)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(mes) DO UPDATE SET
            meta=excluded.meta,
            realizado=excluded.realizado,
            matriculas=excluded.matriculas,
            matriculas_venda=excluded.matriculas_venda
    """, (
        dados.get("mes"),
        dados.get("meta"),
        dados.get("realizado"),
        dados.get("matriculas"),
        dados.get("matriculas_venda")
    ))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/carregar_relatorio/<mes>")
def carregar_relatorio(mes):
    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        SELECT meta, realizado, matriculas, matriculas_venda
        FROM relatorios
        WHERE mes=?
    """, (mes,))

    row = c.fetchone()
    conn.close()

    if row:
        return jsonify({
            "meta": row[0],
            "realizado": row[1],
            "matriculas": row[2],
            "matriculas_venda": row[3]
        })
    else:
        return jsonify({})
@app.route("/relatorio_trimestre/<ano>/<tri>")
def relatorio_trimestre(ano, tri):

    meses = {
        "1": ["01","02","03"],
        "2": ["04","05","06"],
        "3": ["07","08","09"],
        "4": ["10","11","12"]
    }

    lista = [f"{ano}-{m}" for m in meses[tri]]

    conn = conectar_banco()
    c = conn.cursor()

    total_meta = 0
    total_realizado = 0
    total_matriculas = 0
    total_vendas = 0

    for mes in lista:
        c.execute("""
            SELECT meta, realizado, matriculas, matriculas_venda
            FROM relatorios
            WHERE mes=?
        """, (mes,))
        row = c.fetchone()

        if row:
            total_meta += row[0] or 0
            total_realizado += row[1] or 0
            total_matriculas += row[2] or 0
            total_vendas += row[3] or 0

    conn.close()

    return jsonify({
        "meta": total_meta,
        "realizado": total_realizado,
        "matriculas": total_matriculas,
        "matriculas_venda": total_vendas
    })
def buscar_relatorio_mes(mes):
    conn = conectar_banco()
    c = conn.cursor()

    c.execute("""
        SELECT meta, realizado, matriculas, matriculas_venda
        FROM relatorios
        WHERE mes = ?
    """, (mes,))

    r = c.fetchone()
    conn.close()

    if r:
        return {
            "meta": r[0] or 0,
            "realizado": r[1] or 0,
            "matriculas": r[2] or 0,
            "vendas": r[3] or 0
        }

    return {"meta":0,"realizado":0,"matriculas":0,"vendas":0}
# ================= START =================

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)


