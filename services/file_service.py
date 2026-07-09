"""Serviço de arquivos — headers padronizados para PDF.js e proxy Cloudinary."""
import os
import mimetypes
import logging
import requests
from flask import Response

logger = logging.getLogger(__name__)

# ── Headers base para compatibilidade máxima com PDF.js ────────────────────
_PDFJS_HEADERS = {
    "Content-Disposition":   "inline",
    "X-Frame-Options":       "ALLOWALL",
    "X-Content-Type-Options":"nosniff",
    "Cache-Control":         "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma":                "no-cache",
}


def build_pdf_response(content: bytes, mimetype: str = "application/pdf",
                       extra_headers: dict = None) -> Response:
    """Constrói um Response Flask com headers otimizados para PDF.js.

    Os headers padrão garantem:
    - Renderização inline (sem disparar download)
    - Permissão de embedding em iframe/object (X-Frame-Options: ALLOWALL)
    - Bloqueio de sniffing (X-Content-Type-Options: nosniff)
    - Sem cache (Cache-Control + Pragma)

    Args:
        content:  bytes do arquivo.
        mimetype: MIME type (padrão application/pdf).
        extra_headers: headers adicionais/sobrescrita (opcional).

    Returns:
        flask.Response com os headers apropriados.
    """
    headers = dict(_PDFJS_HEADERS)
    if extra_headers:
        headers.update(extra_headers)

    resp = Response(content, mimetype=mimetype)
    for key, value in headers.items():
        resp.headers[key] = value
    return resp


def serve_local_file(candidatos: list, extra_headers: dict = None) -> Response:
    """Varre uma lista de caminhos candidatos e serve o primeiro encontrado.

    Args:
        candidatos:    lista de paths absolutos para tentar.
        extra_headers: headers adicionais (opcional).

    Returns:
        flask.Response com o arquivo encontrado.

    Raises:
        FileNotFoundError se nenhum candidato existir.
    """
    for candidato in candidatos:
        if os.path.isfile(candidato):
            mime, _ = mimetypes.guess_type(candidato)
            mime = mime or "application/octet-stream"
            with open(candidato, "rb") as f:
                dados = f.read()
            return build_pdf_response(dados, mimetype=mime,
                                      extra_headers=extra_headers)
    raise FileNotFoundError(
        f"Nenhum arquivo encontrado nos caminhos: {candidatos}"
    )


def proxy_remote_file(url: str, timeout: int = 20,
                      extra_headers: dict = None) -> Response:
    """Baixa um arquivo remoto e retorna como Response para PDF.js.

    Aplica correção automática: se a URL do Cloudinary tiver
    /image/upload/ troca para /raw/upload/ (PDFs salvos erroneamente).

    Args:
        url:           URL do arquivo remoto.
        timeout:       timeout HTTP em segundos.
        extra_headers: headers adicionais (opcional).

    Returns:
        flask.Response com o conteúdo do arquivo.

    Raises:
        requests.RequestException em caso de falha na requisição.
    """
    url_para_requisicao = url

    # Correção Cloudinary: /image/upload/ → /raw/upload/ para PDFs
    if "cloudinary.com" in url and "/image/upload/" in url:
        url_para_requisicao = url.replace("/image/upload/", "/raw/upload/")

    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    r = requests.get(url_para_requisicao, headers=req_headers,
                     timeout=timeout)
    r.raise_for_status()

    # Detecta Content-Type real do upstream (PDF.js precisa do MIME correto)
    upstream_mime = r.headers.get("Content-Type", "application/pdf")
    if ";" in (upstream_mime or ""):
        upstream_mime = upstream_mime.split(";")[0].strip()

    return build_pdf_response(r.content, mimetype=upstream_mime,
                              extra_headers=extra_headers)
