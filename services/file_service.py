"""Serviço de arquivos — headers padronizados para PDF.js e proxy Cloudinary."""
import os
import logging
import re
import requests
from flask import Response

logger = logging.getLogger(__name__)

# ── Headers base para compatibilidade máxima com PDF.js ────────────────────
# PDF.js faz fetch() same-origin e renderiza em <canvas> — não usa iframe.
# Portanto X-Frame-Options precisa ser SAMEORIGIN (valor RFC-7034 válido)
# para não bloquear possíveis previews em iframe em telas de admin,
# mas o header crítico aqui é Content-Disposition: inline.
_PDFJS_HEADERS = {
    "Content-Disposition":    "inline",
    "X-Frame-Options":        "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control":          "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma":                 "no-cache",
    "Accept-Ranges":          "bytes",
}


def build_pdf_response(content: bytes, mimetype: str = "application/pdf",
                       extra_headers: dict = None) -> Response:
    """Constrói um Response Flask com headers otimizados para PDF.js.

    Os headers padrão garantem:
    - Renderização inline (sem disparar download)
    - Permissão de embedding em iframe/object (X-Frame-Options: SAMEORIGIN)
    - Bloqueio de sniffing (X-Content-Type-Options: nosniff)
    - Sem cache (Cache-Control + Pragma)
    - Suporte a range requests (Accept-Ranges: bytes)

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

    Força mimetype application/pdf para arquivos .pdf (em vez de depender
    de mimetypes.guess_type que pode retornar None em servidores Linux
    sem banco de dados MIME configurado).

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
            # Força application/pdf para .pdf independente do SO
            if candidato.lower().endswith(".pdf"):
                mime = "application/pdf"
            else:
                import mimetypes
                mime, _ = mimetypes.guess_type(candidato)
                mime = mime or "application/octet-stream"

            with open(candidato, "rb") as f:
                dados = f.read()
            return build_pdf_response(dados, mimetype=mime,
                                      extra_headers=extra_headers)
    raise FileNotFoundError(
        f"Nenhum arquivo encontrado nos caminhos: {candidatos}"
    )


def _cloudinary_signed_url(url: str, delivery_type: str = "upload") -> str:
    """Gera uma URL assinada do Cloudinary a partir de uma URL crua.

    URLs cruas (secure_url) de contas com "Signed URLs" habilitado retornam
    401 Unauthorized em GET direto. Esta função extrai o public_id e o
    resource_type da URL e usa o SDK (que tem o api_secret) para gerar uma
    URL assinada válida.

    A config do Cloudinary é carregada explicitamente a partir do
    current_app (não depende do estado global), garantindo que o api_secret
    esteja disponível mesmo se o módulo for importado antes da inicialização.

    Args:
        url:            URL crua do Cloudinary.
        delivery_type:  "upload" (público) ou "private" (asset privado).

    Retorna a URL original se não for possível identificar o Cloudinary.
    """
    if "cloudinary.com" not in url:
        return url

    try:
        import cloudinary
        from cloudinary.utils import cloudinary_url
        from flask import current_app

        # Garante que a config do Cloudinary está carregada a partir do app.
        cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
        api_key    = current_app.config.get("CLOUDINARY_API_KEY")
        api_secret = current_app.config.get("CLOUDINARY_API_SECRET")
        if not (cloud_name and api_key and api_secret):
            logger.warning(
                "[file_service] Cloudinary não configurado (faltam credenciais) "
                "— usando URL original."
            )
            return url

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

        # Extrai resource_type (image|raw|video) e public_id da URL.
        # Formato: https://res.cloudinary.com/<cloud>/<resource>/upload/v<ver>/<public_id>
        m = re.search(
            r"res\.cloudinary\.com/[^/]+/(?P<type>image|raw|video)/upload/"
            r"v\d+/(?P<public_id>.+)$",
            url,
        )
        if not m:
            logger.warning(
                f"[file_service] Não foi possível extrair public_id da URL: {url}"
            )
            return url

        resource_type = m.group("type")
        public_id = m.group("public_id")

        # Gera URL assinada (sign_url=True) usando o api_secret configurado.
        signed, _ = cloudinary_url(
            public_id,
            resource_type=resource_type,
            type=delivery_type,
            sign_url=True,
            secure=True,
        )
        return signed
    except Exception as e:
        logger.warning(
            f"[file_service] Falha ao gerar URL assinada Cloudinary, "
            f"usando URL original: {e}",
            exc_info=True,
        )
        return url


def proxy_remote_file(url: str, timeout: int = 20,
                      extra_headers: dict = None) -> Response:
    """Baixa um arquivo remoto e retorna como Response para PDF.js.

    Aplica correção automática: se a URL do Cloudinary tiver
    /image/upload/ troca para /raw/upload/ (PDFs salvos erroneamente).

    Para URLs do Cloudinary, gera uma URL assinada via SDK (sign_url=True)
    antes do GET — contas com "Signed URLs" habilitado retornam 401 em
    URLs cruas.

    Estratégia de fallback para assets privados: tenta primeiro a URL
    assinada com delivery type "upload"; se o Cloudinary retornar 401,
    tenta com delivery type "private" (assets com access_mode=private
    exigem /private/ na URL, mesmo assinados).

    Força Content-Type para application/pdf quando o upstream retorna
    um tipo genérico (octet-stream, binary, etc.).

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

    # Para URLs do Cloudinary, tenta estratégias em ordem:
    # 1. URL assinada com delivery type "upload"
    # 2. URL assinada com delivery type "private" (se 401)
    if "cloudinary.com" in url_para_requisicao:
        candidatas = [
            _cloudinary_signed_url(url_para_requisicao, delivery_type="upload"),
            _cloudinary_signed_url(url_para_requisicao, delivery_type="private"),
        ]
        # Remove duplicatas preservando ordem
        vistas = set()
        candidatas_unicas = []
        for c in candidatas:
            if c not in vistas:
                vistas.add(c)
                candidatas_unicas.append(c)

        ultimo_erro = None
        for candidata in candidatas_unicas:
            try:
                r = requests.get(candidata, headers=req_headers, timeout=timeout)
                if r.status_code == 401:
                    ultimo_erro = requests.exceptions.HTTPError(
                        f"401 Client Error: Unauthorized for url: {candidata}",
                        response=r,
                    )
                    continue  # tenta a próxima estratégia
                r.raise_for_status()

                # Detecta Content-Type real do upstream
                upstream_mime = r.headers.get("Content-Type", "application/pdf")
                if ";" in (upstream_mime or ""):
                    upstream_mime = upstream_mime.split(";")[0].strip()

                # Fallback: se o upstream devolveu tipo genérico, força application/pdf
                generic_types = {"application/octet-stream", "binary/octet-stream",
                                 "application/binary", ""}
                if (upstream_mime or "").lower() in generic_types:
                    upstream_mime = "application/pdf"

                return build_pdf_response(r.content, mimetype=upstream_mime,
                                          extra_headers=extra_headers)
            except requests.exceptions.RequestException as e:
                ultimo_erro = e
                continue

        # Todas as estratégias falharam
        if ultimo_erro:
            raise ultimo_erro
        raise requests.exceptions.RequestException(
            f"Falha ao baixar arquivo Cloudinary: {url_para_requisicao}"
        )

    # URL não-Cloudinary: GET direto
    r = requests.get(url_para_requisicao, headers=req_headers, timeout=timeout)
    r.raise_for_status()

    # Detecta Content-Type real do upstream
    upstream_mime = r.headers.get("Content-Type", "application/pdf")
    if ";" in (upstream_mime or ""):
        upstream_mime = upstream_mime.split(";")[0].strip()

    # Fallback: se o upstream devolveu tipo genérico, força application/pdf
    generic_types = {"application/octet-stream", "binary/octet-stream",
                     "application/binary", ""}
    if (upstream_mime or "").lower() in generic_types:
        upstream_mime = "application/pdf"

    return build_pdf_response(r.content, mimetype=upstream_mime,
                              extra_headers=extra_headers)
