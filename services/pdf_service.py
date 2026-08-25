"""Serviço centralizado de geração de PDFs.

Consolidado: recibo, carnê, boletim de notas, histórico de frequência,
declaração de conclusão, confirmação de pré-matrícula e declaração de matrícula.
As rotas delegam para cá — zero lógica de PDF nas rotas.
"""
import io
import os
from datetime import date
from textwrap import wrap
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth

ESCOLA = {
    "nome":     "CENTRO DE QUALIFICAÇÃO PROFISSIONAL",
    "sigla":    "CQP",
    "cnpj":     "39.368.679/0001-01",
    "endereco": "Rua Prata Mancebo, 148 — Centro, Carapebus-RJ",
    "cidade":   "CEP 27998-000",
    "telefone": "(22) 99868-4334",
    "email":    "centrodequalificacao@cqpcursos.com.br",
}

_TIPO_LABEL = {
    "matricula":   "Matrícula",
    "mensalidade": "Mensalidade",
    "material":    "Material",
    "outros":      "Outros",
}


def _label_tipo(tipo: str) -> str:
    """Retorna rótulo legível para o campo tipo, independente de caixa."""
    return _TIPO_LABEL.get((tipo or "").lower(), (tipo or "").capitalize())


def _logo_path(root_path: str) -> str:
    p1 = os.path.join(root_path, "static", "logo_escola.png")
    p2 = os.path.join(root_path, "static", "uploads", "logo_escola.png")
    return p1 if os.path.exists(p1) else p2


def _assinatura_path(root_path: str) -> str:
    p1 = os.path.join(root_path, "static", "assinatura.png")
    p2 = os.path.join(root_path, "static", "uploads", "assinatura.png")
    return p1 if os.path.exists(p1) else p2


def _cabecalho(pdf, largura: float, altura: float, titulo: str,
               root_path: str = "") -> float:
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
    centro = largura / 2
    assin  = _assinatura_path(root_path)
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
    pdf.setFont(font, size)
    for line in wrap(text, max_width_chars):
        pdf.drawString(x, y, line)
        y -= line_height
    return y


def _truncar(texto: str, font_name: str, font_size: int, max_px: float) -> str:
    if stringWidth(texto, font_name, font_size) <= max_px:
        return texto
    while texto and stringWidth(texto + "…", font_name, font_size) > max_px:
        texto = texto[:-1]
    return texto + "…"


def _capitalizar_nome(nome: str) -> str:
    preposicoes = {"de", "da", "do", "das", "dos", "e", "em", "com"}
    partes = nome.strip().split()
    return " ".join(
        p if p.lower() in preposicoes else p.capitalize()
        for p in partes
    )


# ────────────────────────────────────────────────────────────────── RECIBO

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
        ("Tipo",               _label_tipo(mensalidade.tipo)),
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


# ────────────────────────────────────────────────────────────────── CARNÊ

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
            ("Tipo",       _label_tipo(p.tipo)),
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


# ────────────────────────────────────────────────────────────────── BOLETIM

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
        # DT-01 FIX: `is not None` em vez de truthiness — nota 0.0 é legítima
        # e deve aparecer no boletim (reprovação não pode ficar invisível).
        # Trunca o nome da matéria para caber entre a coluna Matéria (x=50)
        # e a coluna Nota (x=270), evitando sobreposição com nomes longos.
        nome_mat = _truncar(m.nome, "Helvetica", 10, 270 - 50 - 10)
        pdf.drawString(50,  y, nome_mat)
        pdf.drawString(270, y, str(n.nota      if n is not None and n.nota is not None else ""))
        pdf.drawString(340, y, str(n.resultado if n is not None and n.resultado else ""))
        y -= 18
        if y < 100:
            pdf.showPage()
            y = alt - 60
    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ────────────────────────────────────────────────────────────────── FREQUÊNCIA

def gerar_historico_frequencia(aluno, curso, historico,
                               root_path: str = "") -> io.BytesIO:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    y = _cabecalho(pdf, larg, alt, "HISTÓRICO DE FREQUÊNCIA", root_path)
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


# ────────────────────────────────────────────────────────────────── DECLARAÇÃO DE CONCLUSÃO

def _draw_rich_paragraph(pdf, partes, x: float, y: float,
                         max_largura_px: float, line_height: float,
                         font_size: int = 11) -> float:
    tokens = []
    for texto, negrito in partes:
        fonte = "Helvetica-Bold" if negrito else "Helvetica"
        for palavra in texto.split(" "):
            if palavra:
                tokens.append((palavra, fonte))

    espaco = stringWidth(" ", "Helvetica", font_size)
    linhas = []
    linha_atual = []
    largura_atual = 0.0

    for palavra, fonte in tokens:
        w = stringWidth(palavra, fonte, font_size)
        extra = espaco if linha_atual else 0.0
        if largura_atual + extra + w > max_largura_px and linha_atual:
            linhas.append(linha_atual)
            linha_atual = [(palavra, fonte)]
            largura_atual = w
        else:
            linha_atual.append((palavra, fonte))
            largura_atual += extra + w

    if linha_atual:
        linhas.append(linha_atual)

    for linha in linhas:
        cursor = x
        for i, (palavra, fonte) in enumerate(linha):
            if i > 0:
                cursor += espaco
            pdf.setFont(fonte, font_size)
            pdf.drawString(cursor, y, palavra)
            cursor += stringWidth(palavra, fonte, font_size)
        y -= line_height

    return y


def gerar_declaracao_conclusao(aluno, curso, modalidade: str = "EAD",
                               parceiro_nome: str = "",
                               parceiro_cnpj: str = "",
                               root_path: str = "") -> io.BytesIO:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    margem = 65
    max_largura_px = larg - margem * 2
    line_height = 18
    font_size = 11

    tipo_curso = curso.tipo.upper() if curso.tipo else "PROFISSIONAL"
    titulo = f"DECLARAÇÃO DE CONCLUSÃO - {tipo_curso}"

    logo = _logo_path(root_path)
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, alt - 120, width=80, height=60,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, alt - 60, f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, alt - 75,  f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawString(140, alt - 90,
                   "Rua: Prata Mancebo nº 148. Centro – Carapebus – RJ CEP 27998-000")
    pdf.drawString(140, alt - 105, f"E-mail: {ESCOLA['email']}")
    pdf.drawString(140, alt - 120, f"Tel.: {ESCOLA['telefone']}")
    pdf.line(50, alt - 135, larg - 50, alt - 135)

    y = alt - 165
    pdf.setFont("Helvetica-Bold", 14)
    titulo_w = stringWidth(titulo, "Helvetica-Bold", 14)
    titulo_x = (larg - titulo_w) / 2
    pdf.drawString(titulo_x, y, titulo)
    pdf.line(titulo_x, y - 3, titulo_x + titulo_w, y - 3)
    y -= 38

    pdf.setFont("Helvetica", font_size)
    pdf.drawString(margem, y, "A quem posso interessar,")
    y -= line_height * 1.8

    nome_fmt = _capitalizar_nome(aluno.nome)
    cpf_fmt  = aluno.cpf if aluno.cpf else "não informado"

    if parceiro_nome and parceiro_cnpj:
        partes_p1 = [
            ("Certificamos, para os devidos fins, que ", False),
            (nome_fmt, True),
            (", portador do CPF nº ", False),
            (cpf_fmt, True),
            (", concluiu com êxito o curso ", False),
            (curso.nome, True),
            (", oferecido pelo ", False),
            (f"{ESCOLA['nome']} – {ESCOLA['sigla']}", True),
            (", inscrito no ", False),
            (f"CNPJ nº {ESCOLA['cnpj']}", True),
            (", em parceria com a ", False),
            (parceiro_nome, True),
            (", inscrito no ", False),
            (f"CNPJ nº {parceiro_cnpj}", True),
            (".", False),
        ]
    else:
        partes_p1 = [
            ("Certificamos, para os devidos fins, que ", False),
            (nome_fmt, True),
            (", portador do CPF nº ", False),
            (cpf_fmt, True),
            (", concluiu com êxito o curso ", False),
            (curso.nome, True),
            (", oferecido pelo ", False),
            (f"{ESCOLA['nome']} – {ESCOLA['sigla']}", True),
            (", inscrito no ", False),
            (f"CNPJ nº {ESCOLA['cnpj']}", True),
            (".", False),
        ]

    y = _draw_rich_paragraph(pdf, partes_p1, margem, y,
                             max_largura_px, line_height, font_size)
    y -= line_height

    p2 = (
        "O aluno cumpriu integralmente todas as atividades acadêmicas previstas, "
        "atendendo às exigências e etapas estabelecidas no processo de formação."
    )
    pdf.setFont("Helvetica", font_size)
    for line in wrap(p2, 85):
        pdf.drawString(margem, y, line)
        y -= line_height
    y -= line_height

    p3 = (
        f"Este documento é emitido para atestar a conclusão e certificação da referida "
        f"formação {tipo_curso.lower()}, na modalidade {modalidade}"
    )
    pdf.setFont("Helvetica", font_size)
    for line in wrap(p3, 85):
        pdf.drawString(margem, y, line)
        y -= line_height

    assin_y_base = 150
    assin_path   = _assinatura_path(root_path)
    col_esq_centro = margem + 95
    pdf.line(margem, assin_y_base, margem + 190, assin_y_base)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(col_esq_centro, assin_y_base - 14, "Diretor Geral")
    pdf.drawCentredString(col_esq_centro, assin_y_base - 26,
                          "Randermei Marinho de Almeida Oliveira")
    col_dir_centro = larg - margem - 95
    if os.path.exists(assin_path):
        pdf.drawImage(assin_path,
                      col_dir_centro - 60, assin_y_base + 5,
                      width=120, height=35,
                      preserveAspectRatio=True, mask="auto")
    pdf.line(larg - margem - 190, assin_y_base, larg - margem, assin_y_base)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(col_dir_centro, assin_y_base - 14,
                          f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.drawCentredString(col_dir_centro, assin_y_base - 26, "Alex de Assis Pessanha")
    pdf.drawCentredString(col_dir_centro, assin_y_base - 38, f"CNPJ: {ESCOLA['cnpj']}")

    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ────────────────────────────────────────────────────────────────── DECLARAÇÃO DE MATRÍCULA

def gerar_declaracao_matricula(aluno, matricula, curso,
                               root_path: str = "") -> io.BytesIO:
    """Gera PDF de Declaração de Matrícula com cabeçalho idêntico ao de gerar_declaracao_conclusao."""
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    margem = 65
    max_largura_px = larg - margem * 2
    line_height = 18
    font_size = 11

    logo = _logo_path(root_path)
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, alt - 120, width=80, height=60,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, alt - 60, f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, alt - 75,  f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawString(140, alt - 90,
                   "Rua: Prata Mancebo nº 148. Centro – Carapebus – RJ CEP 27998-000")
    pdf.drawString(140, alt - 105, f"E-mail: {ESCOLA['email']}")
    pdf.drawString(140, alt - 120, f"Tel.: {ESCOLA['telefone']}")
    pdf.line(50, alt - 135, larg - 50, alt - 135)

    titulo = "DECLARAÇÃO DE MATRÍCULA"
    y = alt - 165
    pdf.setFont("Helvetica-Bold", 14)
    titulo_w = stringWidth(titulo, "Helvetica-Bold", 14)
    titulo_x = (larg - titulo_w) / 2
    pdf.drawString(titulo_x, y, titulo)
    pdf.line(titulo_x, y - 3, titulo_x + titulo_w, y - 3)
    y -= 38

    pdf.setFont("Helvetica", font_size)
    pdf.drawString(margem, y, "A quem possa interessar,")
    y -= line_height * 1.8

    nome_fmt   = _capitalizar_nome(aluno.nome)
    cpf_fmt    = aluno.cpf if aluno.cpf else "não informado"
    status_fmt = (matricula.status or "não informado").capitalize()

    data_raw = matricula.data_cadastro
    if data_raw:
        data_str    = str(data_raw)[:10]
        partes_data = data_str.split("-")
        data_fmt = f"{partes_data[2]}/{partes_data[1]}/{partes_data[0]}" \
            if len(partes_data) == 3 else data_str
    else:
        data_fmt = "não informada"

    partes_corpo = [
        ("Declaramos que o(a) Sr(a). ", False),
        (nome_fmt, True),
        (", portador(a) do CPF ", False),
        (cpf_fmt, True),
        (", encontra-se regularmente matriculado(a) no curso ", False),
        (curso.nome, True),
        (" desde ", False),
        (data_fmt, True),
        (", com matrícula em situação ", False),
        (status_fmt, True),
        (".", False),
    ]
    y = _draw_rich_paragraph(pdf, partes_corpo, margem, y,
                             max_largura_px, line_height, font_size)
    y -= line_height * 1.5

    dados_adicionais = [
        ("Nome completo",       nome_fmt),
        ("CPF",                 cpf_fmt),
        ("Curso",               curso.nome),
        ("Status da matrícula", status_fmt),
        ("Data de início",      data_fmt),
        ("Data de emissão",     date.today().strftime("%d/%m/%Y")),
    ]
    for label, valor in dados_adicionais:
        pdf.setFont("Helvetica-Bold", font_size)
        lw = stringWidth(f"{label}: ", "Helvetica-Bold", font_size)
        pdf.drawString(margem, y, f"{label}: ")
        pdf.setFont("Helvetica", font_size)
        pdf.drawString(margem + lw, y, valor)
        y -= line_height
    y -= line_height

    hoje = date.today()
    meses_pt = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    data_extenso = f"{hoje.day} de {meses_pt[hoje.month]} de {hoje.year}"
    pdf.setFont("Helvetica", font_size)
    pdf.drawString(margem, y, f"Carapebus-RJ, {data_extenso}.")

    assin_y_base   = 150
    assin_path     = _assinatura_path(root_path)
    col_esq_centro = margem + 95
    pdf.line(margem, assin_y_base, margem + 190, assin_y_base)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(col_esq_centro, assin_y_base - 14, "Diretor Geral")
    pdf.drawCentredString(col_esq_centro, assin_y_base - 26,
                          "Randermei Marinho de Almeida Oliveira")
    col_dir_centro = larg - margem - 95
    if os.path.exists(assin_path):
        pdf.drawImage(assin_path,
                      col_dir_centro - 60, assin_y_base + 5,
                      width=120, height=35,
                      preserveAspectRatio=True, mask="auto")
    pdf.line(larg - margem - 190, assin_y_base, larg - margem, assin_y_base)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(col_dir_centro, assin_y_base - 14,
                          f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.drawCentredString(col_dir_centro, assin_y_base - 26, "Alex de Assis Pessanha")
    pdf.drawCentredString(col_dir_centro, assin_y_base - 38, f"CNPJ: {ESCOLA['cnpj']}")

    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ────────────────────────────────────────────────────────────────── CONTRATO ASSINADO

def gerar_contrato_assinado(aluno, aceite, root_path: str = "") -> io.BytesIO:
    """Gera PDF comprovante de aceite de contrato digital.

    Exibe os dados do aluno e a evidência do aceite registrado em
    ContratoAceite (versão, hash SHA-256, data/hora, IP e user-agent).
    Usa apenas o último aceite (registro mais recente).
    """
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    margem = 65
    line_height = 18
    font_size = 11
    max_largura_px = larg - margem * 2

    logo = _logo_path(root_path)
    if os.path.exists(logo):
        pdf.drawImage(logo, 50, alt - 120, width=80, height=60,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(140, alt - 60, f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(140, alt - 75,  f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawString(140, alt - 90,
                   "Rua: Prata Mancebo nº 148. Centro – Carapebus – RJ CEP 27998-000")
    pdf.drawString(140, alt - 105, f"E-mail: {ESCOLA['email']}")
    pdf.drawString(140, alt - 120, f"Tel.: {ESCOLA['telefone']}")
    pdf.line(50, alt - 135, larg - 50, alt - 135)

    titulo = "COMPROVANTE DE ACEITE DE CONTRATO"
    y = alt - 165
    pdf.setFont("Helvetica-Bold", 14)
    titulo_w = stringWidth(titulo, "Helvetica-Bold", 14)
    titulo_x = (larg - titulo_w) / 2
    pdf.drawString(titulo_x, y, titulo)
    pdf.line(titulo_x, y - 3, titulo_x + titulo_w, y - 3)
    y -= 38

    pdf.setFont("Helvetica", font_size)
    pdf.drawString(margem, y, "Declaramos que o(a) aluno(a) abaixo aceitou eletronicamente o contrato de prestação de serviços educacionais, nos termos registrados a seguir:")
    y -= line_height * 1.8

    # ── Dados do aluno ──────────────────────────────────────────────
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margem, y, "DADOS DO ALUNO:")
    y -= 16

    nome_fmt = _capitalizar_nome(aluno.nome)
    dados_aluno = [
        ("Nome completo",       nome_fmt),
        ("CPF",                 aluno.cpf or "não informado"),
        ("RG",                  aluno.rg or "não informado"),
        ("Data de nascimento",  aluno.data_nascimento or "não informado"),
        ("E-mail",              aluno.email or "não informado"),
        ("Telefone/WhatsApp",   aluno.telefone or "não informado"),
    ]
    for label, valor in dados_aluno:
        pdf.setFont("Helvetica-Bold", font_size)
        lw = stringWidth(f"{label}: ", "Helvetica-Bold", font_size)
        pdf.drawString(margem, y, f"{label}: ")
        pdf.setFont("Helvetica", font_size)
        pdf.drawString(margem + lw, y, valor)
        y -= line_height
    y -= line_height

    # ── Evidência do aceite ─────────────────────────────────────────
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margem, y, "EVIDÊNCIA DO ACEITE ELETRÔNICO:")
    y -= 16

    versao = getattr(aceite, "versao", "") or "—"
    hash_contrato = getattr(aceite, "hash_contrato", "") or "—"
    aceito_em = getattr(aceite, "aceito_em", "") or "—"
    ip = getattr(aceite, "ip", "") or "—"
    ua = getattr(aceite, "user_agent", "") or "—"

    if aceito_em != "—":
        a_str = str(aceito_em)[:19]
        partes = a_str.split(" ")
        data_p = partes[0].split("-")
        data_fmt = f"{data_p[2]}/{data_p[1]}/{data_p[0]}" \
            if len(data_p) == 3 else partes[0]
        hora_fmt = partes[1] if len(partes) > 1 else ""
        aceito_fmt = f"{data_fmt} {hora_fmt}".strip()
    else:
        aceito_fmt = "—"

    dados_aceite = [
        ("Versão do contrato",  versao),
        ("Hash SHA-256",        hash_contrato),
        ("Aceito em",           aceito_fmt),
        ("Endereço IP",         ip),
    ]
    for label, valor in dados_aceite:
        pdf.setFont("Helvetica-Bold", font_size)
        lw = stringWidth(f"{label}: ", "Helvetica-Bold", font_size)
        pdf.drawString(margem, y, f"{label}: ")
        pdf.setFont("Helvetica", font_size)
        pdf.drawString(margem + lw, y, valor)
        y -= line_height

    # ── User-Agent (quebrado em linhas) ─────────────────────────────
    y -= line_height
    pdf.setFont("Helvetica-Bold", font_size)
    pdf.drawString(margem, y, "Dispositivo/Navegador (User-Agent):")
    y -= line_height
    pdf.setFont("Helvetica", 9)
    for line in wrap(ua, 90):
        if y < 80:
            break
        pdf.drawString(margem, y, line)
        y -= 13
    y -= 20

    hoje = date.today()
    meses_pt = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    data_extenso = f"{hoje.day} de {meses_pt[hoje.month]} de {hoje.year}"
    pdf.setFont("Helvetica", font_size)
    pdf.drawString(margem, y, f"Carapebus-RJ, {data_extenso}.")

    # ── Assinatura institucional ────────────────────────────────────
    assin_y_base = 150
    assin_path = _assinatura_path(root_path)
    col_esq_centro = margem + 95
    pdf.line(margem, assin_y_base, margem + 190, assin_y_base)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(col_esq_centro, assin_y_base - 14, "Diretor Geral")
    pdf.drawCentredString(col_esq_centro, assin_y_base - 26,
                          "Randermei Marinho de Almeida Oliveira")
    col_dir_centro = larg - margem - 95
    if os.path.exists(assin_path):
        pdf.drawImage(assin_path,
                      col_dir_centro - 60, assin_y_base + 5,
                      width=120, height=35,
                      preserveAspectRatio=True, mask="auto")
    pdf.line(larg - margem - 190, assin_y_base, larg - margem, assin_y_base)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(col_dir_centro, assin_y_base - 14,
                          f"{ESCOLA['nome']} {ESCOLA['sigla']}")
    pdf.drawCentredString(col_dir_centro, assin_y_base - 26, "Alex de Assis Pessanha")
    pdf.drawCentredString(col_dir_centro, assin_y_base - 38, f"CNPJ: {ESCOLA['cnpj']}")

    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


# ────────────────────────────────────────────────────────────────── CONFIRMAÇÃO DE PRÉ-MATRÍCULA

def gerar_pre_matricula(dados: dict, root_path: str = "") -> io.BytesIO:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    larg, alt = A4
    margem_esq = 50
    margem_dir = larg - 50

    logo = _logo_path(root_path)
    if os.path.exists(logo):
        pdf.drawImage(logo, margem_esq, alt - 110, width=70, height=55,
                      preserveAspectRatio=True, mask="auto")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(130, alt - 55, "CENTRO DE QUALIFICAÇÃO PROFISSIONAL CQP")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(130, alt - 69,  f"CNPJ: {ESCOLA['cnpj']}")
    pdf.drawString(130, alt - 82,  "Rua: Prata Mancebo nº 148 - Centro")
    pdf.drawString(130, alt - 95,  "Carapebus - RJ  CEP 27998-000")
    pdf.drawString(130, alt - 108, f"Tel.: {ESCOLA['telefone']}")
    pdf.drawString(130, alt - 121, f"E-mail: {ESCOLA['email']}")
    pdf.line(margem_esq, alt - 132, margem_dir, alt - 132)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(larg / 2, alt - 158, "CONFIRMAÇÃO DE PRÉ-MATRÍCULA")

    y = alt - 185
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margem_esq, y, "DADOS DO CANDIDATO:")
    y -= 14

    col_label      = margem_esq
    col_valor_cand = 185
    col_valor_fin  = 215
    linha_h        = 18
    largura_tabela = margem_dir - margem_esq

    linhas_candidato = [
        ("Nome do aluno",  dados.get("aluno_nome", "")),
        ("Idade",          str(dados.get("aluno_idade", ""))),
        ("Endereço",       dados.get("aluno_endereco", "")),
        ("Responsável",    dados.get("aluno_responsavel", "")),
        ("CPF",            dados.get("aluno_cpf", "")),
        ("WhatsApp",       dados.get("aluno_whatsapp", "")),
    ]

    def _draw_tabela(pdf, y, linhas, col_label, col_valor,
                     larg_tabela, linha_h, margem_esq, negrito_ultima=False):
        max_label_px = col_valor - col_label - 8
        max_valor_px = (margem_esq + larg_tabela) - col_valor - 8
        for i, (label, valor) in enumerate(linhas):
            negrito = negrito_ultima and i == len(linhas) - 1
            pdf.rect(col_label, y - linha_h + 3, larg_tabela, linha_h, stroke=1, fill=0)
            pdf.line(col_valor, y - linha_h + 3, col_valor, y + 3)
            pdf.setFont("Helvetica-Bold", 9)
            label_safe = _truncar(label, "Helvetica-Bold", 9, max_label_px)
            pdf.drawString(col_label + 4, y - 9, label_safe)
            fonte_val = "Helvetica-Bold" if negrito else "Helvetica"
            pdf.setFont(fonte_val, 9)
            valor_safe = _truncar(str(valor), fonte_val, 9, max_valor_px)
            pdf.drawString(col_valor + 4, y - 9, valor_safe)
            y -= linha_h
        return y

    y = _draw_tabela(pdf, y, linhas_candidato, col_label, col_valor_cand,
                     largura_tabela, linha_h, margem_esq)

    y -= 14
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margem_esq, y, "DADOS FINANCEIROS:")
    y -= 14

    vm   = dados.get("valor_mensalidade", 0.0)
    parc = dados.get("parcelas", 1)
    vmat = dados.get("valor_material", 0.0)
    pmat = dados.get("parcelas_material", 1)
    total = vm * parc + vmat

    linhas_financeiro = [
        ("Taxa de matrícula",    f"R$ {dados.get('taxa_matricula', 0.0):.2f}"),
        ("Valor da mensalidade", f"R$ {vm:.2f}"),
        ("Parcelas do curso",    f"{parc}x"),
        ("Material didático",    dados.get("material_didatico", "")),
        ("Valor do material",    f"R$ {vmat:.2f}"),
        ("Parcelas do material", f"{pmat}x de R$ {vmat:.2f}"),
        ("TOTAL CURSO + MATERIAL", f"R$ {total:.2f}"),
    ]

    y = _draw_tabela(pdf, y, linhas_financeiro, col_label, col_valor_fin,
                     largura_tabela, linha_h, margem_esq, negrito_ultima=True)

    y -= 18
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margem_esq, y, "DATAS DE PAGAMENTOS")
    y -= 16
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margem_esq, y,
                   f"Data do pagamento da matrícula: {dados.get('data_pagamento_matricula', '')}")
    y -= 14
    pdf.drawString(margem_esq, y,
                   f"Primeira mensalidade: {dados.get('data_primeira_mensalidade', '')}")
    y -= 18
    pdf.setFont("Helvetica-Bold", 11)
    mensalidade_apostila = vm + vmat if pmat == 1 else vm
    pdf.drawString(margem_esq, y,
                   f"Mensalidade + Apostila: R$ {mensalidade_apostila:.2f}")

    y_rodape = 160
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margem_esq, y_rodape,
                   f"Data de emissão: {date.today().strftime('%d/%m/%Y')}")
    pdf.drawString(margem_esq, y_rodape - 14,
                   f"Pré-matrícula nº: {dados.get('numero_pre_matricula', '')}")

    assin_y    = 95
    assin_path = _assinatura_path(root_path)
    pdf.line(margem_esq, assin_y, margem_esq + 190, assin_y)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(margem_esq + 95, assin_y - 14, "Assinatura do responsável")

    centro_dir = margem_dir - 95
    if os.path.exists(assin_path):
        pdf.drawImage(assin_path, centro_dir - 80, assin_y + 5,
                      width=160, height=38,
                      preserveAspectRatio=True, mask="auto")
    pdf.line(centro_dir - 95, assin_y, centro_dir + 95, assin_y)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(centro_dir, assin_y - 14, "Centro de Qualificação Profissional")

    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf
