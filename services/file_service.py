"""Serviço de arquivos — headers padronizados para PDF.js e proxy Cloudinary."""
import os
import logging
import mimetypes
import re
import requests
from dataclasses import dataclass
from flask import Response
from urllib.parse import unquote, urlsplit, urlunsplit

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


@dataclass(frozen=True)
class _CloudinaryAsset:
    """Metadados recuperados de uma URL de delivery do Cloudinary.

    O banco legado salva apenas ``secure_url``. Por isso a URL é a fonte de
    verdade nesta camada. Uploads futuros devem persistir também
    ``public_id``, ``resource_type``, ``type`` e ``version`` retornados pelo
    upload API.
    """

    cloud_name: str
    resource_type: str
    source_delivery_type: str
    public_id: str
    version: int | None
    transformation: str | None
    format: str | None


_CLOUDINARY_HOST_RE = re.compile(r"(^|\.)res\.cloudinary\.com$", re.I)
_CLOUDINARY_VERSION_RE = re.compile(r"^v(\d+)$")
_CLOUDINARY_SIGNATURE_RE = re.compile(r"^s--[^/]+--$")
_CLOUDINARY_RESOURCE_TYPES = {"image", "raw", "video"}
_CLOUDINARY_DELIVERY_TYPES = {"upload", "private", "authenticated"}


def _parse_cloudinary_url(url: str) -> _CloudinaryAsset | None:
    """Extrai o descriptor de uma URL Cloudinary, sem perder ``version``.

    URLs de raw têm a extensão dentro do próprio ``public_id``. Para image e
    video a extensão é tratada como ``format`` e removida do public ID, como
    exige o SDK Cloudinary.
    """
    parsed = urlsplit(url)
    if not _CLOUDINARY_HOST_RE.match(parsed.hostname or ""):
        return None

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 4:
        return None

    cloud_name, resource_type, delivery_type = parts[:3]
    if resource_type not in _CLOUDINARY_RESOURCE_TYPES:
        return None
    if delivery_type not in _CLOUDINARY_DELIVERY_TYPES:
        return None

    remainder = parts[3:]
    # Assinaturas de delivery aparecem antes das transformações/versão.
    remainder = [part for part in remainder
                 if not _CLOUDINARY_SIGNATURE_RE.match(part)]

    version_index = next(
        (index for index, part in enumerate(remainder)
         if _CLOUDINARY_VERSION_RE.match(part)),
        None,
    )
    if version_index is None:
        transformation_parts = []
        asset_parts = remainder
        version = None
    else:
        transformation_parts = remainder[:version_index]
        asset_parts = remainder[version_index + 1:]
        version = int(_CLOUDINARY_VERSION_RE.match(
            remainder[version_index]
        ).group(1))

    if not asset_parts:
        return None

    public_id = "/".join(asset_parts)
    asset_format = None
    if resource_type != "raw":
        # O formato de image/video normalmente é o último sufixo da URL.
        # Não remove nomes sem extensão nem extensões com caracteres estranhos.
        match = re.match(r"^(?P<id>.+)\.(?P<format>[A-Za-z0-9]{1,10})$",
                         public_id)
        if match:
            public_id = match.group("id")
            asset_format = match.group("format")

    return _CloudinaryAsset(
        cloud_name=cloud_name,
        resource_type=resource_type,
        source_delivery_type=delivery_type,
        public_id=public_id,
        version=version,
        transformation="/".join(transformation_parts) or None,
        format=asset_format,
    )


def _configure_cloudinary_for_delivery() -> bool:
    """Carrega explicitamente as credenciais do Flask no SDK Cloudinary."""
    try:
        import cloudinary
        from flask import current_app

        cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
        api_key = current_app.config.get("CLOUDINARY_API_KEY")
        api_secret = current_app.config.get("CLOUDINARY_API_SECRET")
        if not (cloud_name and api_key and api_secret):
            logger.error(
                "[file_service] Cloudinary sem configuração completa: "
                "cloud_name=%s api_key=%s api_secret=%s",
                bool(cloud_name), bool(api_key), bool(api_secret),
            )
            return False

        options = {
            "cloud_name": cloud_name,
            "api_key": api_key,
            "api_secret": api_secret,
            "secure": True,
        }
        signature_algorithm = current_app.config.get(
            "CLOUDINARY_SIGNATURE_ALGORITHM"
        )
        if signature_algorithm:
            options["signature_algorithm"] = signature_algorithm
        cloudinary.config(**options)
        return True
    except Exception:
        logger.exception(
            "[file_service] Não foi possível configurar o SDK Cloudinary"
        )
        return False


def _cloudinary_signed_url(asset: _CloudinaryAsset,
                           delivery_type: str = "upload") -> str:
    """Gera uma URL de delivery assinada preservando a versão original."""
    import cloudinary
    from cloudinary.utils import cloudinary_url
    from flask import current_app

    options = {
        "resource_type": asset.resource_type,
        "type": delivery_type,
        "sign_url": True,
        "secure": True,
        # Sem version, o SDK pode inventar v1 para public IDs com barras.
        "force_version": asset.version is not None,
    }
    if asset.version is not None:
        options["version"] = asset.version
    if asset.transformation:
        options["transformation"] = asset.transformation
    if asset.format:
        options["format"] = asset.format

    configured_cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    if configured_cloud_name != asset.cloud_name:
        raise ValueError(
            f"cloud_name da URL ({asset.cloud_name}) difere da configuração "
            f"da aplicação ({configured_cloud_name})"
        )

    signed, _ = cloudinary_url(asset.public_id, **options)
    return signed


def _cloudinary_private_download_url(asset: _CloudinaryAsset,
                                     delivery_type: str) -> str:
    """Gera o download API assinado para asset private/authenticated.

    Para raw, a extensão já está no public_id; portanto ``format`` deve ser
    vazio. Passar ``pdf`` aqui criaria um nome incorreto como ``file.pdf.pdf``.
    """
    from cloudinary.utils import private_download_url

    options = {
        "resource_type": asset.resource_type,
        "type": delivery_type,
    }
    return private_download_url(
        asset.public_id,
        asset.format or "",
        **options,
    )


def _safe_cloudinary_url(url: str) -> str:
    """Remove assinaturas e query strings dos logs sem ocultar o diagnóstico."""
    parsed = urlsplit(url)
    path = re.sub(r"/s--[^/]+--/", "/s--<redacted>--/", parsed.path)
    query = "<redacted>" if parsed.query else ""
    return urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))


def _log_cloudinary_response(label: str, response: requests.Response) -> None:
    """Registra status, headers relevantes e amostra do corpo do upstream."""
    body = response.content[:4096].decode("utf-8", errors="replace")
    logger.warning(
        "[file_service] Cloudinary tentativa=%s status=%s content_type=%s "
        "x_cld_error=%s body=%r",
        label,
        response.status_code,
        response.headers.get("Content-Type"),
        response.headers.get("X-Cld-Error"),
        body,
    )


def _response_mimetype(response: requests.Response, source_url: str) -> str:
    """Determina o MIME sem transformar DOCX/imagens em PDF por engano."""
    content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip()
    if content_type and content_type.lower() not in {
        "application/octet-stream", "binary/octet-stream", "application/binary"
    }:
        return content_type

    mime, _ = mimetypes.guess_type(urlsplit(source_url).path)
    if mime:
        return mime
    return "application/pdf"


def proxy_remote_file(url: str, timeout: int = 20,
                      extra_headers: dict = None) -> Response:
    """Baixa um arquivo remoto e retorna como Response para PDF.js.

    Para Cloudinary, as tentativas são deliberadamente explícitas:

    1. delivery ``upload`` assinado;
    2. delivery ``private`` assinado;
    3. delivery ``authenticated`` assinado;
    4. ``private_download_url`` para ``private``;
    5. ``private_download_url`` para ``authenticated``.

    A primeira tentativa não altera ``image`` para ``raw``. O
    ``resource_type`` real do asset é parte da identidade do recurso e uma
    troca cega pode produzir 401/404. Também preserva ``v<timestamp>`` da
    URL original; sem isso o SDK pode gerar ``v1`` para IDs com pastas.

    Cada tentativa registra status HTTP, ``X-Cld-Error`` e uma amostra do
    corpo retornado. Assinaturas/query strings são redigidas nos logs.

    Args:
        url:           URL do arquivo remoto.
        timeout:       timeout HTTP em segundos.
        extra_headers: headers adicionais (opcional).

    Returns:
        flask.Response com o conteúdo do arquivo.

    Raises:
        requests.RequestException em caso de falha na requisição.
    """
    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    asset = _parse_cloudinary_url(url)
    if asset is not None:
        if not _configure_cloudinary_for_delivery():
            raise requests.exceptions.RequestException(
                "Cloudinary não está configurado para gerar URL de delivery"
            )

        candidatas = []
        for delivery_type in ("upload", "private", "authenticated"):
            try:
                candidatas.append((
                    f"signed-delivery/{delivery_type}",
                    _cloudinary_signed_url(asset, delivery_type),
                ))
            except Exception as exc:
                logger.exception(
                    "[file_service] Falha ao gerar URL assinada "
                    "delivery_type=%s asset=%s: %s",
                    delivery_type, asset.public_id, exc,
                )

        for delivery_type in ("private", "authenticated"):
            try:
                candidatas.append((
                    f"private-download/{delivery_type}",
                    _cloudinary_private_download_url(asset, delivery_type),
                ))
            except Exception as exc:
                logger.exception(
                    "[file_service] Falha ao gerar private_download_url "
                    "delivery_type=%s asset=%s: %s",
                    delivery_type, asset.public_id, exc,
                )

        # Remove duplicatas sem perder o nome da estratégia para o log.
        vistas = set()
        candidatas_unicas = []
        for label, candidata in candidatas:
            if candidata not in vistas:
                vistas.add(candidata)
                candidatas_unicas.append((label, candidata))

        ultimo_erro = None
        for label, candidata in candidatas_unicas:
            logger.info(
                "[file_service] Tentando Cloudinary strategy=%s url=%s "
                "resource_type=%s source_type=%s public_id=%s version=%s",
                label,
                _safe_cloudinary_url(candidata),
                asset.resource_type,
                asset.source_delivery_type,
                asset.public_id,
                asset.version,
            )
            try:
                response = requests.get(
                    candidata, headers=req_headers, timeout=timeout
                )
                _log_cloudinary_response(label, response)
                if 200 <= response.status_code < 300:
                    return build_pdf_response(
                        response.content,
                        mimetype=_response_mimetype(response, url),
                        extra_headers=extra_headers,
                    )

                ultimo_erro = requests.exceptions.HTTPError(
                    f"{response.status_code} upstream Cloudinary para "
                    f"{_safe_cloudinary_url(candidata)}",
                    response=response,
                )
            except requests.exceptions.RequestException as exc:
                ultimo_erro = exc
                logger.warning(
                    "[file_service] Exceção na tentativa Cloudinary "
                    "strategy=%s: %s",
                    label, exc, exc_info=True,
                )

        if ultimo_erro:
            raise ultimo_erro
        raise requests.exceptions.RequestException(
            f"Nenhuma estratégia Cloudinary foi gerada para {_safe_cloudinary_url(url)}"
        )

    # URL não-Cloudinary: mantém o comportamento legado (GET direto).
    r = requests.get(url, headers=req_headers, timeout=timeout)
    r.raise_for_status()
    return build_pdf_response(r.content, mimetype=_response_mimetype(r, url),
                              extra_headers=extra_headers)
