"""Constantes de domínio centralizadas.

Importe daqui — nunca hardcode strings de status nas rotas.
"""
from enum import Enum


class PerfilUsuario(str, Enum):
    ADMIN         = "admin"
    ADMINISTRADOR = "administrador"
    SECRETARIA    = "secretaria"
    FINANCEIRO    = "financeiro"
    INSTRUTOR     = "instrutor"

    @classmethod
    def valores(cls):
        return {e.value for e in cls}


class StatusMatricula(str, Enum):
    ATIVA    = "ATIVA"
    INATIVA  = "INATIVA"
    TRANCADA = "TRANCADA"
    CONCLUIDA = "CONCLUIDA"

    @classmethod
    def valores(cls):
        return {e.value for e in cls}


class StatusMensalidade(str, Enum):
    PENDENTE  = "Pendente"
    PAGO      = "Pago"
    ATRASADO  = "Atrasado"
    CANCELADO = "Cancelado"

    @classmethod
    def valores(cls):
        return {e.value for e in cls}


class StatusAluno(str, Enum):
    ATIVO         = "Ativo"
    INATIVO       = "Inativo"
    TRANCADO      = "Trancado"
    CANCELADO     = "Cancelado"
    FINALIZADO    = "Finalizado"     # formaliza valor já usado nos templates
    PRE_MATRICULA = "Pré-Matrícula"  # novo: aluno aguardando confirmação

    @classmethod
    def valores(cls):
        return {e.value for e in cls}


class ResultadoNota(str, Enum):
    APROVADO  = "Aprovado"
    REPROVADO = "Reprovado"
    CURSANDO  = "Cursando"

    @classmethod
    def valores(cls):
        return {e.value for e in cls}


class StatusFrequencia(str, Enum):
    PRESENTE = "Presente"
    FALTA    = "Falta"
    JUSTIFICADA = "Justificada"

    @classmethod
    def valores(cls):
        return {e.value for e in cls}
