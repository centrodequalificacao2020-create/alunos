import logging
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)


def upload_arquivo(file_object, pasta: str, nome_publico: str = None) -> dict:
    """
    Faz upload de um arquivo para o Cloudinary.
    A pasta final é: {CLOUDINARY_PASTA_PREFIXO}/{pasta}
    Ex: pasta="entregas" → "cliente_abc/entregas"
    """
    from flask import current_app
    prefixo     = current_app.config.get('CLOUDINARY_PASTA_PREFIXO', 'default')
    pasta_final = f"{prefixo}/{pasta}"

    try:
        params = {
            "folder":          pasta_final,
            "resource_type":   "auto",
            "use_filename":    True,
            "unique_filename": True,
        }
        if nome_publico:
            params["public_id"]    = nome_publico
            params["use_filename"] = False

        resultado = cloudinary.uploader.upload(file_object, **params)
        return {
            "url":       resultado.get("secure_url"),
            "public_id": resultado.get("public_id"),
        }
    except Exception as e:
        logger.error(
            f"[storage_service] Erro no upload para Cloudinary (pasta={pasta_final}): {e}",
            exc_info=True
        )
        raise RuntimeError(f"Falha no upload do arquivo para armazenamento externo: {e}") from e


def deletar_arquivo(public_id: str) -> bool:
    """
    Tenta deletar um arquivo do Cloudinary nos três resource_types possíveis.
    Retorna True se confirmado, False caso contrário.
    """
    try:
        for resource_type in ("raw", "image", "video"):
            resultado = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            if resultado.get("result") == "ok":
                return True
        logger.warning(
            f"[storage_service] Cloudinary não confirmou deleção de public_id={public_id}"
        )
        return False
    except Exception as e:
        logger.error(
            f"[storage_service] Erro ao deletar public_id={public_id}: {e}",
            exc_info=True
        )
        return False
