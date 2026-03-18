"""Serviço centralizado de geração de PDFs.

Consolidado: recibo, carnê, boletim de notas e histórico de frequência.
As rotas em academico.py delegam para cá — zero lógica de PDF nas rotas.
"""
import io
import os
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

ESCOLA = {
    "nome":     "CENTRO DE QUALIFICAÇÃO PROFISSIONAL",
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
    """Desenha cabeçalho institucional e retorna y disponível."""
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


def _rodape_assinatura(pdf, largura: float, root_path: str = ""):
    """Desenha linha / imagem de assinatura no rodapé."""
    centro = largura / 2
    assin  = os.path.join(root_path, "static", "assinatura.png")
    if os.path.exists(assin):
        pdf.drawImage(assin, centro - 80, 90, width=160, height=40,
                      preserveAspectRatio=True, mask="auto")
    else:
        pdf.line(centro - 100, 105, centro + 100, 105)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(centro, 75, ESCOLA["nome"])
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(centro, 60, f"CNPJ: {ESCOLA['cnpj']}")


# ─────────────────────────── RECIBO ───────────────────────────

def gerar_recibo(mensalidade, root_path: str = "") -> io.BytesIO:
    """Recebe objeto Mensalidade e retorna BytesIO com PDF."""
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
    """Retorna BytesIO com carnê completo."""
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
    """Gera boletim de notas; recebe dict {materia_id: Nota}."""
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
    """Gera PDF do histórico de frequência."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    y = _cabecalho(pdf, larg, alt, "HISTÓRICO DE FREQUÊNCIA", root_path)
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
    _rodape_assinatura(pdf, larg, root_path)
    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf
