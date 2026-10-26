"""Emissão, cancelamento e consulta de certificados de conclusão.

Camada de domínio entre as rotas e o renderer. Concentra aqui o que precisa
ser testável sem Flask: validação dos dados informados, geração do código de
verificação, cálculo do hash e montagem do snapshot.

O renderer (``certificado_pdf``) continua puro — recebe dados e devolve bytes.
Este módulo é quem decide *o que* renderizar e *o que* persistir.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime

from db import db
from enums import StatusCertificado
from models import Aluno, Certificado, Curso, Matricula
from services.certificado_pdf import (
    DadosCertificado,
    carregar_layout_padrao,
    gerar_certificado,
)

__all__ = [
    "ErroEmissao",
    "emitir_certificado",
    "cancelar_certificado",
    "certificados_do_aluno",
    "buscar_por_codigo",
    "pdf_do_certificado",
    "gerar_codigo_verificacao",
    "normalizar_cpf",
    "validar_emissao",
    "CARGA_HORARIA_MAXIMA",
    "CARGA_HORARIA_MINIMA",
]

CARGA_HORARIA_MINIMA = 1
CARGA_HORARIA_MAXIMA = 10_000

# Sem 0/O, 1/I/L: o código é lido em voz alta e digitado à mão na validação.
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_TAMANHO_CODIGO = 10


class ErroEmissao(ValueError):
    """Dados inválidos para emitir o certificado. A mensagem é para o usuário."""


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalizar_cpf(valor: str | None) -> str:
    """Mantém apenas dígitos e devolve no formato 000.000.000-00.

    Devolve string vazia quando não há 11 dígitos — CPF é opcional no
    certificado (o corpo imprime "não informado").
    """
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) != 11:
        return ""
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def gerar_codigo_verificacao() -> str:
    """Código curto, sem caracteres ambíguos, para consulta pública."""
    return "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(_TAMANHO_CODIGO))


def _parse_data(valor: str | None, campo: str) -> date:
    texto = (valor or "").strip()
    if not texto:
        raise ErroEmissao(f"Informe a {campo}.")
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    raise ErroEmissao(f"{campo.capitalize()} inválida. Use o formato DD/MM/AAAA.")


def validar_emissao(dados) -> dict:
    """Valida o formulário de emissão e devolve valores normalizados.

    ``dados`` é qualquer mapeamento (``request.form`` serve). Levanta
    :class:`ErroEmissao` com mensagem pronta para o usuário.
    """
    try:
        carga = int(str(dados.get("carga_horaria") or "").strip())
    except (TypeError, ValueError):
        raise ErroEmissao("Carga horária inválida. Informe um número inteiro de horas.")
    if not (CARGA_HORARIA_MINIMA <= carga <= CARGA_HORARIA_MAXIMA):
        raise ErroEmissao(
            f"A carga horária deve estar entre {CARGA_HORARIA_MINIMA} e "
            f"{CARGA_HORARIA_MAXIMA} horas."
        )

    try:
        aproveitamento = float(str(dados.get("aproveitamento") or "").strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ErroEmissao("Aproveitamento inválido. Informe um número entre 0 e 100.")
    if not (0.0 <= aproveitamento <= 100.0):
        raise ErroEmissao("O aproveitamento deve estar entre 0 e 100%.")

    inicio = _parse_data(dados.get("data_inicio"), "data de início")
    fim = _parse_data(dados.get("data_fim"), "data de conclusão")
    if fim < inicio:
        raise ErroEmissao("A data de conclusão não pode ser anterior à data de início.")

    return {
        "carga_horaria": carga,
        "aproveitamento": round(aproveitamento, 2),
        "data_inicio": inicio,
        "data_fim": fim,
    }


def _dados_para_render(certificado: Certificado) -> DadosCertificado:
    """Reconstrói os dados de render a partir do snapshot persistido."""
    return DadosCertificado(
        nome=certificado.nome_aluno,
        cpf=certificado.cpf_aluno or "",
        curso=certificado.nome_curso,
        carga_horaria=int(certificado.carga_horaria),
        aproveitamento=float(certificado.aproveitamento),
        data_inicio=date.fromisoformat(certificado.data_inicio),
        data_fim=date.fromisoformat(certificado.data_fim),
    )


def emitir_certificado(*, aluno_id: int, matricula_id: int | None,
                       carga_horaria: int, aproveitamento: float,
                       data_inicio: date, data_fim: date,
                       emitido_por: str) -> tuple[Certificado, bytes]:
    """Gera o PDF, persiste o snapshot e devolve ``(certificado, pdf_bytes)``.

    O PDF é devolvido em memória para que a rota decida entre enviá-lo
    diretamente ao navegador ou enviá-lo ao Cloudinary. A rota é responsável
    por gravar ``arquivo_url``/``arquivo_public_id`` depois do upload.
    """
    aluno = db.session.get(Aluno, aluno_id)
    if aluno is None:
        raise ErroEmissao("Aluno não encontrado.")

    matricula = None
    if matricula_id:
        matricula = db.session.get(Matricula, matricula_id)
        if matricula is None or matricula.aluno_id != aluno.id:
            raise ErroEmissao("Matrícula não pertence a este aluno.")

    curso_id = matricula.curso_id if matricula else aluno.curso_id
    curso = db.session.get(Curso, curso_id) if curso_id else None
    if curso is None:
        raise ErroEmissao("Aluno sem curso vinculado. Selecione uma matrícula.")

    layout = carregar_layout_padrao()
    dados = DadosCertificado(
        nome=(aluno.nome or "").strip(),
        cpf=normalizar_cpf(aluno.cpf),
        curso=(curso.nome or "").strip(),
        carga_horaria=int(carga_horaria),
        aproveitamento=float(aproveitamento),
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    pdf_bytes = gerar_certificado(dados, layout)

    certificado = Certificado(
        aluno_id=aluno.id,
        matricula_id=matricula.id if matricula else None,
        curso_id=curso.id,
        nome_aluno=dados.nome,
        cpf_aluno=dados.cpf or None,
        nome_curso=dados.curso,
        carga_horaria=dados.carga_horaria,
        aproveitamento=dados.aproveitamento,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
        codigo_verificacao=gerar_codigo_verificacao(),
        hash_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        layout_id=layout.id,
        status=StatusCertificado.EMITIDO.value,
        emitido_em=_agora(),
        emitido_por=emitido_por,
    )
    db.session.add(certificado)
    db.session.commit()
    return certificado, pdf_bytes


def cancelar_certificado(certificado_id: int, *, motivo: str,
                         cancelado_por: str) -> Certificado:
    """Cancelamento LÓGICO — o registro e o código de verificação permanecem."""
    certificado = db.session.get(Certificado, certificado_id)
    if certificado is None:
        raise ErroEmissao("Certificado não encontrado.")
    if certificado.cancelado:
        raise ErroEmissao("Este certificado já está cancelado.")

    certificado.status = StatusCertificado.CANCELADO.value
    certificado.cancelado_em = _agora()
    certificado.cancelado_por = cancelado_por
    certificado.motivo_cancelamento = (motivo or "").strip()[:200] or None
    db.session.commit()
    return certificado


def certificados_do_aluno(aluno_id: int) -> list[Certificado]:
    """Histórico do aluno, mais recente primeiro."""
    return (
        Certificado.query
        .filter_by(aluno_id=aluno_id)
        .order_by(Certificado.emitido_em.desc(), Certificado.id.desc())
        .all()
    )


def buscar_por_codigo(codigo: str) -> Certificado | None:
    """Consulta pelo código de verificação (normalizado para maiúsculas)."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    return Certificado.query.filter_by(codigo_verificacao=codigo).first()


def pdf_do_certificado(certificado: Certificado) -> bytes:
    """Re-renderiza o PDF a partir do snapshot (usado quando não há arquivo)."""
    return gerar_certificado(_dados_para_render(certificado), carregar_layout_padrao())
