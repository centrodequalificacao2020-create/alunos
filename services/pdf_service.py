import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

ESCOLA = {
    "nome":    "CENTRO DE QUALIFICAÇÃO PROFISSIONAL",
    "cnpj":    "39.368.679/0001-01",
    "endereco":"Rua: Prata Mancebo nº 148 - Centro",
    "cidade":  "Carapebus - RJ  CEP 27998-000",
    "telefone":"(22) 99868-4334",
    "email":   "Centrodequalificacao@cqpcursos.com.br",
}

def _cabecalho(pdf, largura, altura, titulo):
    """Desenha cabeçalho padrão e retorna y inicial do conteúdo."""
    logo = os.path.join("static", "logo_escola.png")
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, altura-120, width=80, height=60,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, altura-60,  ESCOLA["nome"])
    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, altura-75,  f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawString(140, altura-90,  ESCOLA["endereco"])
    pdf.drawString(140, altura-105, ESCOLA["cidade"])
    pdf.drawString(140, altura-120, f"Tel.: {ESCOLA['telefone']}")
    pdf.drawString(140, altura-135, f"E-mail: {ESCOLA['email']}")
    pdf.line(50, altura-150, largura-50, altura-150)
    y = altura - 180
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(largura/2, y, titulo)
    return y

def gerar_recibo(mensalidade):
    """Recebe objeto Mensalidade e retorna BytesIO com PDF."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    largura, altura = A4
    y = _cabecalho(pdf, largura, altura, "RECIBO DE PAGAMENTO")

    aluno  = mensalidade.aluno
    curso  = aluno.curso.nome if aluno.curso else "-"

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

def gerar_carne(aluno, parcelas):
    """Retorna BytesIO com carnê completo."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    largura, altura = A4

    for p in parcelas:
        y = _cabecalho(pdf, largura, altura, "CARNÊ DE PAGAMENTO")
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
