"""Carregamento e validação da configuração visual do certificado.

O layout vive em ``layouts/*.toml`` para que ajustes de posição, cor e texto
institucional não exijam tocar no código de geração.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Layout", "LayoutInvalido", "carregar_layout"]

_RAIZ = Path(__file__).resolve().parent.parent
_DIRETORIO_LAYOUTS = _RAIZ / "layouts"


class LayoutInvalido(ValueError):
    """O arquivo de layout não pôde ser lido ou está inconsistente."""


@dataclass(frozen=True, slots=True)
class Bloco:
    font: str
    size: float
    y: float
    color: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Layout:
    id: str
    descricao: str
    page_width: float
    page_height: float
    margin_left: float
    margin_right: float
    background_image: Path
    titulo_texto: str
    titulo: Bloco
    nome: Bloco
    nome_size_steps: tuple[tuple[int, float], ...]
    nome_uppercase: bool
    corpo: Bloco
    corpo_x: float
    corpo_line_height: float
    rodape: Bloco
    rodape_cidade: str
    fontes: dict[str, Path]
    date_format: str = "%d/%m/%Y"

    @property
    def largura_util(self) -> float:
        return self.page_width - self.margin_left - self.margin_right

    def tamanho_nome(self, nome: str) -> float:
        """Reduz o corpo do nome conforme o comprimento (faixas do layout)."""
        for limite, tamanho in self.nome_size_steps:
            if limite == 0 or len(nome) <= limite:
                return tamanho
        return self.nome.size


def _cor(valor: object, campo: str) -> tuple[float, float, float]:
    if not isinstance(valor, list) or len(valor) != 3:
        raise LayoutInvalido(f"{campo}: cor deve ser [r, g, b]")
    try:
        return (float(valor[0]), float(valor[1]), float(valor[2]))
    except (TypeError, ValueError) as exc:
        raise LayoutInvalido(f"{campo}: componentes de cor inválidos") from exc


def _bloco(dados: dict, campo: str) -> Bloco:
    try:
        return Bloco(
            font=str(dados["font"]),
            size=float(dados["size"]),
            y=float(dados["y"]),
            color=_cor(dados.get("color", [0, 0, 0]), f"{campo}.color"),
        )
    except KeyError as exc:
        raise LayoutInvalido(f"{campo}: chave obrigatória ausente {exc}") from exc


def carregar_layout(caminho: str | Path) -> Layout:
    """Lê um layout TOML e devolve um :class:`Layout` pronto para uso."""
    caminho = Path(caminho)
    if not caminho.is_file() and not caminho.is_absolute():
        caminho = _DIRETORIO_LAYOUTS / caminho
    if not caminho.is_file():
        raise LayoutInvalido(f"layout não encontrado: {caminho}")

    try:
        dados = tomllib.loads(caminho.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise LayoutInvalido(f"TOML inválido em {caminho}: {exc}") from exc

    try:
        page = dados["page"]
        bg = dados["background"]
        corpo_dados = dados["body"]
        rodape_dados = dados["footer"]

        passos = tuple(
            (int(limite), float(tamanho))
            for limite, tamanho in dados["name"]["size_steps"]
        )
        if not passos:
            raise LayoutInvalido("name.size_steps não pode ser vazio")

        fontes = {
            chave: (_RAIZ / "static" / "fonts" / nome)
            for chave, nome in dados["fonts"].items()
        }
        for chave, arquivo in fontes.items():
            if not arquivo.is_file():
                raise LayoutInvalido(f"fonte '{chave}' não encontrada: {arquivo}")

        imagem = _RAIZ / bg["image"]
        if not imagem.is_file():
            raise LayoutInvalido(f"imagem de fundo não encontrada: {imagem}")

        return Layout(
            id=str(dados["id"]),
            descricao=str(dados.get("descricao", "")),
            page_width=float(page["width"]),
            page_height=float(page["height"]),
            margin_left=float(page["margin_left"]),
            margin_right=float(page["margin_right"]),
            background_image=imagem,
            titulo_texto=str(dados["title"]["text"]),
            titulo=_bloco(dados["title"], "title"),
            nome=_bloco(dados["name"], "name"),
            nome_size_steps=passos,
            nome_uppercase=bool(dados["name"].get("uppercase", True)),
            corpo=_bloco(corpo_dados, "body"),
            corpo_x=float(corpo_dados["x"]),
            corpo_line_height=float(corpo_dados["line_height"]),
            rodape=_bloco(rodape_dados, "footer"),
            rodape_cidade=str(rodape_dados["city"]),
            fontes=fontes,
            date_format=str(dados.get("date_format", "%d/%m/%Y")),
        )
    except KeyError as exc:
        raise LayoutInvalido(f"seção obrigatória ausente no layout: {exc}") from exc
