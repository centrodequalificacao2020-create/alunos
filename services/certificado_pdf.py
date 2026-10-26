"""Gerador do certificado de conclusão em PDF.

Módulo irmão de ``pdf_service.py`` por uma razão concreta: os demais PDFs são
documentos de fluxo (A4 retrato, texto corrido), enquanto o certificado é um
layout absoluto sobre uma moldura gráfica em A4 paisagem. Misturar os dois
padrões no mesmo arquivo tornaria ambos mais frágeis.

O renderer é puro: ``gerar_certificado(dados, layout) -> bytes``. Não importa
Flask, não lê ``request`` e não grava em disco — quem persiste é a rota,
reaproveitando ``storage_service`` (Cloudinary).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from services.certificado_layout import Layout, carregar_layout

__all__ = [
    "DadosCertificado",
    "gerar_certificado",
    "quebrar_em_linhas",
    "carregar_layout_padrao",
]

_FONTES_REGISTRADAS: set[Path] = set()

# Piso de legibilidade ao reduzir o nome para caber na largura útil.
_TAMANHO_MINIMO_NOME = 12.0

_LAYOUT_PADRAO = "certificado_cqp.toml"


@dataclass(frozen=True, slots=True)
class DadosCertificado:
    """Dados já validados de um certificado pronto para render."""

    nome: str
    cpf: str
    curso: str
    carga_horaria: int
    aproveitamento: float
    data_inicio: date
    data_fim: date

    def formatar_data(self, valor: date, formato: str = "%d/%m/%Y") -> str:
        return valor.strftime(formato)

    def text_corpo(self, formato_data: str = "%d/%m/%Y") -> str:
        # Vírgula decimal: o documento é impresso em português (92,5%).
        carga = f"{self.carga_horaria:g}".replace(".", ",")
        nota = f"{self.aproveitamento:g}".replace(".", ",")
        return (
            f"CPF: {self.cpf or 'não informado'}, concluiu, com êxito, o curso: "
            f"{self.curso.upper()}, com carga horária de {carga} horas, "
            f"com início em {self.formatar_data(self.data_inicio, formato_data)} "
            f"e término em {self.formatar_data(self.data_fim, formato_data)}, "
            f"obtendo aproveitamento de {nota}%."
        )


def _parse_data(valor, padrao: date | None = None) -> date:
    """Aceita date, datetime ou string ISO/brasileira."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    if padrao is not None:
        return padrao
    raise ValueError(f"Data inválida: {valor!r}")


def dados_de_matricula(aluno, curso, *,
                       carga_horaria: int,
                       aproveitamento: float,
                       data_inicio=None,
                       data_fim=None) -> DadosCertificado:
    """Monta :class:`DadosCertificado` a partir dos models do sistema escolar.

    ``carga_horaria`` e ``aproveitamento`` são informados na emissão porque
    ``Curso`` não possui carga horária e as notas históricas não estão
    publicadas (ver SYSTEM_CONTEXT).
    """
    matricula = getattr(aluno, "matriculas", None) or []
    matricula = next(
        (m for m in matricula if getattr(m, "curso_id", None) == getattr(curso, "id", None)),
        matricula[0] if matricula else None,
    )

    inicio = data_inicio or getattr(matricula, "data_matricula", None)
    fim = data_fim or date.today()

    return DadosCertificado(
        nome=(aluno.nome or "").strip(),
        cpf=(getattr(aluno, "cpf", "") or "").strip(),
        curso=(curso.nome or "").strip(),
        carga_horaria=int(carga_horaria),
        aproveitamento=float(aproveitamento),
        data_inicio=_parse_data(inicio, padrao=fim),
        data_fim=_parse_data(fim),
    )


def carregar_layout_padrao() -> Layout:
    """Carrega ``layouts/certificado_cqp.toml``."""
    return carregar_layout(_LAYOUT_PADRAO)


def _registrar_fontes(layout: Layout) -> dict[str, str]:
    """Registra as fontes do layout uma única vez e devolve chave -> nome ReportLab."""
    nomes: dict[str, str] = {}
    for chave, arquivo in layout.fontes.items():
        arquivo = arquivo.resolve()
        nome_pdf = f"CQP-{arquivo.stem}"
        if arquivo not in _FONTES_REGISTRADAS:
            pdfmetrics.registerFont(TTFont(nome_pdf, str(arquivo)))
            _FONTES_REGISTRADAS.add(arquivo)
        nomes[chave] = nome_pdf
    return nomes


def _medir(texto: str, font: str, size: float) -> float:
    return pdfmetrics.stringWidth(texto, font, size)


def quebrar_em_linhas(texto: str, font: str, size: float, largura: float) -> list[str]:
    """Quebra por largura medida em pontos — não por contagem de caracteres."""
    palavras = texto.split()
    if not palavras:
        return []

    linhas: list[str] = []
    atual = palavras[0]
    for palavra in palavras[1:]:
        candidata = f"{atual} {palavra}"
        if _medir(candidata, font, size) <= largura:
            atual = candidata
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


def _reduzir_para_caber(texto: str, font: str, size: float, largura: float,
                        minimo: float) -> float:
    while size > minimo and _medir(texto, font, size) > largura:
        size -= 0.5
    return size


def gerar_certificado(dados: DadosCertificado, layout: Layout | None = None) -> bytes:
    """Gera o PDF do certificado e devolve os bytes."""
    layout = layout or carregar_layout_padrao()
    nomes = _registrar_fontes(layout)

    fonte_titulo = nomes[layout.titulo.font]
    fonte_nome = nomes[layout.nome.font]
    fonte_corpo = nomes[layout.corpo.font]
    fonte_rodape = nomes[layout.rodape.font]

    buffer = io.BytesIO()
    # invariant=1 remove data de criação e ID aleatório do PDF: a mesma entrada
    # gera sempre os mesmos bytes. Sem isso o hash_sha256 gravado no banco não
    # serviria para detectar adulteração do arquivo.
    pdf = canvas.Canvas(buffer, pagesize=(layout.page_width, layout.page_height),
                        invariant=1)

    pdf.drawImage(
        ImageReader(str(layout.background_image)),
        0, 0,
        width=layout.page_width,
        height=layout.page_height,
        preserveAspectRatio=False,
        mask="auto",
    )

    largura_util = layout.largura_util
    centro = layout.page_width / 2

    pdf.setFillColorRGB(*layout.titulo.color)
    pdf.setFont(fonte_titulo, layout.titulo.size)
    pdf.drawCentredString(centro, layout.titulo.y, layout.titulo_texto)

    nome = dados.nome.upper() if layout.nome_uppercase else dados.nome
    tamanho_nome = layout.tamanho_nome(dados.nome)
    tamanho_nome = _reduzir_para_caber(
        nome, fonte_nome, tamanho_nome, largura_util, _TAMANHO_MINIMO_NOME
    )
    pdf.setFillColorRGB(*layout.nome.color)
    pdf.setFont(fonte_nome, tamanho_nome)
    pdf.drawCentredString(centro, layout.nome.y, nome)

    linhas = quebrar_em_linhas(
        dados.text_corpo(layout.date_format), fonte_corpo,
        layout.corpo.size, largura_util,
    )
    pdf.setFillColorRGB(*layout.corpo.color)
    pdf.setFont(fonte_corpo, layout.corpo.size)
    y = layout.corpo.y
    for linha in linhas:
        pdf.drawString(layout.corpo_x, y, linha)
        y -= layout.corpo_line_height

    pdf.setFillColorRGB(*layout.rodape.color)
    pdf.setFont(fonte_rodape, layout.rodape.size)
    pdf.drawCentredString(
        centro, layout.rodape.y,
        f"{layout.rodape_cidade}, "
        f"{dados.formatar_data(dados.data_fim, layout.date_format)}",
    )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
