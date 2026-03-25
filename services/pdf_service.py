"""Serviço centralizado de geração de PDFs.

Consolidado: recibo, carnê, boletim de notas, histórico de frequência
e declaração de conclusão.
As rotas em academico.py delegam para cá — zero lógica de PDF nas rotas.
"""
import io
import os
from datetime import date
from textwrap import wrap
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

ESCOLA = {
    "nome":     "CENTRO DE QUALIFICAÇÃO PROFISSIONAL",
    "sigla":    "CQP",
    "cnpj":     "39.368.679/0001-01",
    "endereco": "Rua Prata Mancebo, 148 — Centro, Carapebus-RJ",
    "cidade":   "CEP 27998-000",
    "telefone": "(22) 99868-4334",
    "email":    "centrodequalificacao@cqpcursos.com.br",
}


def _logo_path(root_path: str) -> str:
    return os.path.join(root_path, "static", "logo_escola.png")


def _cabecalho(pdf, largura: float, altura: float, titulo: str,
               root_path: str = "") -> float:
    """Cabeçalho com logo + dados institucionais. Retorna y disponível."""
    logo = _logo_path(root_path)
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, altura - 120, width=80, height=60,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, altura - 60, ESCOLA["nome"])
    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, altura - 75,  f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawString(140, altura - 90,  ESCOLA["endereco"])
    pdf.drawString(140, altura - 105, ESCOLA["cidade"])
    pdf.drawString(140, altura - 120, f"Tel.: {ESCOLA['telefone']}")
    pdf.drawString(140, altura - 135, f"E-mail: {ESCOLA['email']}")
    pdf.line(50, altura - 150, largura - 50, altura - 150)
    y = altura - 180
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, titulo)
    return y


def _cabecalho_texto(pdf, largura: float, altura: float, titulo: str) -> float:
    """Cabeçalho apenas textual (sem logo), estilo do histórico de frequência real.
    Retorna y disponível."""
    y = altura - 50
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(largura / 2, y, ESCOLA["nome"])
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(largura / 2, y, f"Endereço: {ESCOLA['endereco']}")
    y -= 14
    pdf.drawCentredString(largura / 2, y, f"Telefone: {ESCOLA['telefone']}")
    y -= 14
    pdf.drawCentredString(largura / 2, y, f"CNPJ: {ESCOLA['cnpj']}")
    y -= 20
    pdf.line(50, y, largura - 50, y)
    y -= 22
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura / 2, y, titulo)
    return y


def _rodape_assinatura(pdf, largura: float, root_path: str = ""):
    """Rodapé com imagem de assinatura (ou linha) + nome e CNPJ da escola."""
    centro = largura / 2
    assin  = os.path.join(root_path, "static", "assinatura.png")
    if os.path.exists(assin):
        pdf.drawImage(assin, centro - 80, 90, width=160, height=40,
                      preserveAspectRatio=True, mask="auto")
    else:
        pdf.line(centro - 100, 105, centro + 100, 105)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(centro, 75, f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(centro, 60, f"CNPJ: {ESCOLA['cnpj']}")


def _rodape_institucional_texto(pdf, largura: float):
    """Rodapé textual completo conforme modelo da declaração real."""
    cx = largura / 2
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(cx, 95, f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(cx, 80, f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawCentredString(cx, 67, f"Rua: Prata Mancebo nº 148. Centro – Carapebus – RJ {ESCOLA['cidade']}")
    pdf.drawCentredString(cx, 54, f"E-mail: {ESCOLA['email']}")
    pdf.drawCentredString(cx, 41, f"Tel.: {ESCOLA['telefone']}")


def _draw_wrapped_text(pdf, text: str, x: float, y: float,
                       max_width_chars: int, line_height: float,
                       font: str = "Helvetica", size: int = 11) -> float:
    """Quebra texto em múltiplas linhas e retorna novo y."""
    pdf.setFont(font, size)
    for line in wrap(text, max_width_chars):
        pdf.drawString(x, y, line)
        y -= line_height
    return y


# ─────────────────────────── RECIBO ───────────────────────────

def gerar_recibo(mensalidade, root_path: str = "") -> io.BytesIO:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    y = _cabecalho(pdf, larg, alt, "RECIBO DE PAGAMENTO", root_path)
    aluno = mensalidade.aluno
    curso = aluno.curso.nome if aluno.curso else "-"
    y -= 40
    pdf.setFont("Helvetica", 12)
    for label, valor in [
        ("Aluno",              aluno.nome),
        ("CPF",                aluno.cpf or "-"),
        ("Curso",              curso),
        ("Tipo",               mensalidade.tipo),
        ("Parcela",            mensalidade.parcela_ref),
        ("Valor",              f"R$ {mensalidade.valor:.2f}"),
        ("Forma de pagamento", mensalidade.forma_pagamento or "-"),
        ("Data do pagamento",  mensalidade.data_pagamento  or "-"),
    ]:
        pdf.drawString(50, y, f"{label}: {valor}")
        y -= 25
    y -= 20
    pdf.drawString(50, y, "Declaro que recebi o valor acima descrito.")
    y -= 40
    pdf.drawString(50, y, "Assinatura: ______________________________")
    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ─────────────────────────── CARNÊ ───────────────────────────

def gerar_carne(aluno, parcelas, root_path: str = "") -> io.BytesIO:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    for p in parcelas:
        y = _cabecalho(pdf, larg, alt, "CARNÊ DE PAGAMENTO", root_path)
        y -= 40
        pdf.setFont("Helvetica", 12)
        for label, valor in [
            ("Aluno",      aluno.nome),
            ("Tipo",       p.tipo),
            ("Parcela",    p.parcela_ref),
            ("Vencimento", p.vencimento),
            ("Valor",      f"R$ {p.valor:.2f}"),
        ]:
            pdf.drawString(50, y, f"{label}: {valor}")
            y -= 25
        y -= 30
        pdf.drawString(50, y, "Pagamento realizado em: ____/____/______")
        y -= 30
        pdf.drawString(50, y, "Assinatura: ______________________________")
        pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ─────────────────────────── BOLETIM ───────────────────────────

def gerar_boletim_notas(aluno, curso, materias, notas_map,
                        root_path: str = "") -> io.BytesIO:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    y = _cabecalho(pdf, larg, alt, "BOLETIM DE NOTAS", root_path)
    y -= 30
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
    for m in materias:
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
    buf.seek(0)
    return buf


# ─────────────────────────── FREQUÊNCIA ───────────────────────────

def gerar_historico_frequencia(aluno, curso, historico,
                               root_path: str = "") -> io.BytesIO:
    """Gera PDF do histórico de frequência conforme modelo real (cabeçalho textual)."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4

    y = _cabecalho_texto(pdf, larg, alt, "HISTÓRICO DE FREQUÊNCIA")
    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Aluno: {aluno.nome.upper()}")
    y -= 16
    pdf.drawString(50, y, f"Curso: {curso.nome}")
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, y, f"Data: {date.today().strftime('%d/%m/%Y')}")
    y -= 28

    pdf.setFont("Helvetica", 11)
    for h in historico:
        txt = "Presente" if h.status == "P" else "Falta"
        data_fmt = h.data.strftime("%d/%m/%Y") if hasattr(h.data, "strftime") else str(h.data)
        pdf.drawString(50, y, f"{data_fmt}  -  {txt}")
        y -= 18
        if y < 120:
            pdf.showPage()
            y = alt - 60

    _rodape_assinatura(pdf, larg, root_path)
    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ─────────────────────────── DECLARAÇÃO DE CONCLUSÃO ───────────────────────────

def gerar_declaracao_conclusao(aluno, curso, modalidade: str = "EAD",
                               parceiro_nome: str = "",
                               parceiro_cnpj: str = "",
                               root_path: str = "") -> io.BytesIO:
    """Gera declaração de conclusão conforme modelo institucional real.

    Args:
        aluno: objeto Aluno (nome, cpf).
        curso: objeto Curso (nome, tipo).
        modalidade: ex. 'EAD', 'Presencial'.
        parceiro_nome: nome da instituição parceira (opcional).
        parceiro_cnpj: CNPJ da instituição parceira (opcional).
    """
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    margem = 65
    max_chars = 78

    # --- Título centralizado ---
    tipo_curso = curso.tipo.upper() if curso.tipo else "PROFISSIONAL"
    y = alt - 80
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(larg / 2, y, f"DECLARAÇÃO DE CONCLUSÃO - {tipo_curso}")
    y -= 50

    # --- Parágrafo 1: identificação ---
    cpf_fmt = aluno.cpf if aluno.cpf else "não informado"
    if parceiro_nome and parceiro_cnpj:
        p1 = (
            f"Certificamos, para os devidos fins, que {aluno.nome}, portador "
            f"do CPF nº {cpf_fmt}, concluiu com êxito o curso {curso.nome}, "
            f"oferecido pelo {ESCOLA['nome']} – {ESCOLA['sigla']}, inscrito no CNPJ nº "
            f"{ESCOLA['cnpj']}, em parceria com a {parceiro_nome}, inscrito no "
            f"CNPJ nº {parceiro_cnpj}."
        )
    else:
        p1 = (
            f"Certificamos, para os devidos fins, que {aluno.nome}, portador "
            f"do CPF nº {cpf_fmt}, concluiu com êxito o curso {curso.nome}, "
            f"oferecido pelo {ESCOLA['nome']} – {ESCOLA['sigla']}, inscrito no CNPJ nº "
            f"{ESCOLA['cnpj']}."
        )

    pdf.setFont("Helvetica", 11)
    pdf.drawString(margem, y, "A quem possa interessar,")
    y -= 28

    for line in wrap(p1, max_chars):
        pdf.drawString(margem, y, line)
        y -= 18
    y -= 18

    # --- Parágrafo 2: cumprimento das atividades ---
    p2 = (
        "O aluno cumpriu integralmente todas as atividades acadêmicas previstas, "
        "atendendo às exigências e etapas estabelecidas no processo de formação."
    )
    for line in wrap(p2, max_chars):
        pdf.drawString(margem, y, line)
        y -= 18
    y -= 18

    # --- Parágrafo 3: finalidade ---
    p3 = (
        f"Este documento é emitido para atestar a conclusão e certificação da referida "
        f"formação {tipo_curso.lower()}, na modalidade {modalidade}."
    )
    for line in wrap(p3, max_chars):
        pdf.drawString(margem, y, line)
        y -= 18

    # --- Assinatura ---
    y -= 50
    assin = os.path.join(root_path, "static", "assinatura.png")
    if os.path.exists(assin):
        pdf.drawImage(assin, larg / 2 - 80, y - 10, width=160, height=40,
                      preserveAspectRatio=True, mask="auto")
        y -= 50
    else:
        pdf.line(larg / 2 - 100, y, larg / 2 + 100, y)
        y -= 20

    # --- Rodapé institucional ---
    _rodape_institucional_texto(pdf, larg)

    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf
