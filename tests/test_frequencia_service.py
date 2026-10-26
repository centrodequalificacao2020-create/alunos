"""Testes da correção DT-02 — status de frequência.

Cobre o bug real: o formulário grava ``P``/``F``, o model declara default
``Presente`` e o service comparava apenas ``"Presente"``, retornando 0,0%.
"""
from __future__ import annotations

import pytest

from services.frequencia_service import (
    is_presente,
    normalizar_status,
    percentual_presenca,
)


class TestNormalizarStatus:
    @pytest.mark.parametrize("entrada", ["P", "p", "Presente", "presente", " PRESSENTE".replace("SS", "S")])
    def test_reconhece_presente_em_qualquer_grafia(self, entrada):
        assert normalizar_status(entrada) == "P"

    @pytest.mark.parametrize("entrada", ["F", "f", "Falta", "falta", "AUSENTE"])
    def test_reconhece_falta(self, entrada):
        assert normalizar_status(entrada) == "F"

    @pytest.mark.parametrize("entrada", ["J", "Justificada", "justificado"])
    def test_reconhece_justificada(self, entrada):
        assert normalizar_status(entrada) == "J"

    @pytest.mark.parametrize("entrada", ["", None, "X", 0, "abc"])
    def test_desconhecido_retorna_vazio(self, entrada):
        assert normalizar_status(entrada) == ""


class TestIsPresente:
    @pytest.mark.parametrize("entrada", ["P", "Presente", "p", "presente"])
    def test_presente(self, entrada):
        assert is_presente(entrada) is True

    @pytest.mark.parametrize("entrada", ["F", "Falta", "J", "Justificada", "", None])
    def test_nao_presente(self, entrada):
        assert is_presente(entrada) is False


class TestPercentualPresenca:
    """O bug: comparar só 'Presente' devolvia 0.0 para dados 'P'."""

    def test_dados_no_formato_do_formulario(self):
        """1087 P + 265 F = 80,4% — exatamente os dados reais do cqp.db."""
        statuses = ["P"] * 1087 + ["F"] * 265
        assert percentual_presenca(statuses) == 80.4

    def test_dados_no_formato_do_model(self):
        statuses = ["Presente"] * 1087 + ["Falta"] * 265
        assert percentual_presenca(statuses) == 80.4

    def test_grafias_misturadas(self):
        """Registros antigos e novos convivem na mesma tabela."""
        assert percentual_presenca(["P", "Presente"]) == 100.0
        assert percentual_presenca(["P", "Falta"]) == 50.0

    def test_sem_registros(self):
        assert percentual_presenca([]) == 0.0

    def test_todos_presentes(self):
        assert percentual_presenca(["P", "P", "P"]) == 100.0

    def test_todas_faltas(self):
        assert percentual_presenca(["F", "F"]) == 0.0

    def test_justificada_nao_conta_como_presenca(self):
        """Preserva a regra original: só presença efetiva conta."""
        assert percentual_presenca(["P", "J"]) == 50.0

    def test_arredondamento_uma_casa(self):
        assert percentual_presenca(["P", "P", "F"]) == 66.7

    def test_status_desconhecido_conta_no_denominador(self):
        """Registro corrompido não deve inflar o percentual."""
        assert percentual_presenca(["P", "X"]) == 50.0


class TestNaoRegressao:
    def test_estrutura_de_retorno(self):
        resultado = percentual_presenca(["P", "F"])
        assert isinstance(resultado, float)
        assert 0.0 <= resultado <= 100.0

    def test_aceita_gerador(self):
        """calcular_percentual passa um generator — não pode exigir len()."""
        assert percentual_presenca(f.status for f in [
            type("F", (), {"status": "P"})(),
            type("F", (), {"status": "F"})(),
        ]) == 50.0
