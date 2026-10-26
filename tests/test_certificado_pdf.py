"""Testes do renderizador de certificados e do layout."""
from __future__ import annotations

from datetime import date

import pytest
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from services.certificado_layout import LayoutInvalido, carregar_layout
from services.certificado_pdf import (
    DadosCertificado,
    carregar_layout_padrao,
    dados_de_matricula,
    gerar_certificado,
    quebrar_em_linhas,
)

LAYOUT = carregar_layout_padrao()


def _dados(**over):
    base = dict(
        nome="Maria Silva Santos", cpf="133.992.517-69",
        curso="Informática Básica", carga_horaria=180, aproveitamento=90,
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 12, 31),
    )
    base.update(over)
    return DadosCertificado(**base)


class TestLayout:
    def test_carrega_fontes_empacotadas(self):
        assert set(LAYOUT.fontes) == {"regular", "bold", "italic", "bold_italic"}
        for caminho in LAYOUT.fontes.values():
            assert caminho.is_file(), caminho

    def test_fontes_dentro_do_projeto(self):
        for caminho in LAYOUT.fontes.values():
            assert "static/fonts" in str(caminho).replace("\\", "/")

    def test_moldura_existe(self):
        assert LAYOUT.background_image.is_file()
        assert "static/certificados" in str(LAYOUT.background_image).replace("\\", "/")

    def test_pagina_a4_paisagem(self):
        assert LAYOUT.page_width == pytest.approx(841.89, abs=0.01)
        assert LAYOUT.page_height == pytest.approx(595.28, abs=0.01)
        assert LAYOUT.page_width > LAYOUT.page_height

    def test_largura_util(self):
        assert LAYOUT.largura_util == pytest.approx(
            LAYOUT.page_width - LAYOUT.margin_left - LAYOUT.margin_right, abs=0.01
        )

    def test_layout_inexistente(self):
        with pytest.raises(LayoutInvalido):
            carregar_layout("nao-existe.toml")

    def test_toml_corrompido(self, tmp_path):
        ruim = tmp_path / "ruim.toml"
        ruim.write_text("isto nao e toml valido [[[")
        with pytest.raises(LayoutInvalido):
            carregar_layout(ruim)


class TestTamanhoNome:
    @pytest.mark.parametrize("nome,tamanho", [
        ("Maria Silva", 30.0),
        ("Maria Eduarda de Oliveira Conceicao Santos", 26.0),  # 42 chars
        ("Maria Eduarda de Oliveira Conceicao Santos da Silva Costa", 22.0),
    ])
    def test_faixas_por_comprimento(self, nome, tamanho):
        assert LAYOUT.tamanho_nome(nome) == tamanho


class TestGeracaoPDF:
    def test_pdf_valido(self):
        conteudo = gerar_certificado(_dados(), LAYOUT)
        assert conteudo.startswith(b"%PDF-")
        assert conteudo.rstrip().endswith(b"%%EOF")
        assert len(conteudo) > 100_000

    def test_deterministico_em_tamanho(self):
        a = gerar_certificado(_dados(), LAYOUT)
        b = gerar_certificado(_dados(), LAYOUT)
        assert abs(len(a) - len(b)) < 3000

    def test_usa_layout_padrao_quando_omitido(self):
        assert gerar_certificado(_dados()).startswith(b"%PDF-")

    def test_acentuacao_preservada(self):
        """Fontes TTF embutidas suportam acentos — Helvetica built-in também,
        mas o layout usa Liberation Sans para garantir consistência."""
        conteudo = gerar_certificado(
            _dados(nome="JOÃO DA CONCEIÇÃO", curso="TÉCNICO EM ENFERMAGEM"), LAYOUT
        )
        assert len(conteudo) > 100_000


class TestTextCorpo:
    def test_contem_campos_obrigatorios(self):
        texto = _dados().text_corpo()
        assert "133.992.517-69" in texto
        assert "INFORMÁTICA BÁSICA" in texto
        assert "180 horas" in texto
        assert "01/01/2026" in texto
        assert "90%" in texto

    def test_sem_delimitadores_legados(self):
        texto = _dados().text_corpo()
        assert "<<" not in texto and ">>" not in texto

    def test_cpf_ausente_nao_quebra(self):
        assert "não informado" in _dados(cpf="").text_corpo()

    @pytest.mark.parametrize("nota,esperado", [
        (90, "90%"), (90.0, "90%"), (87.5, "87,5%"), (100, "100%"), (0, "0%"),
    ])
    def test_formata_aproveitamento_sem_casa_decimal_desnecessaria(self, nota, esperado):
        """Vírgula decimal: o certificado é impresso em português."""
        assert esperado in _dados(aproveitamento=nota).text_corpo()

    def test_formato_de_data_configuravel(self):
        assert "01/01/2026" in _dados().text_corpo("%d/%m/%Y")


class TestQuebraDeLinha:
    def _fonte(self):
        arquivo = LAYOUT.fontes["regular"].resolve()
        nome = f"TEST-{arquivo.stem}"
        pdfmetrics.registerFont(TTFont(nome, str(arquivo)))
        return nome

    def test_nenhuma_linha_excede_a_largura(self):
        fonte = self._fonte()
        texto = "palavra " * 60
        for linha in quebrar_em_linhas(texto.strip(), fonte, 13, 300):
            assert pdfmetrics.stringWidth(linha, fonte, 13) <= 300

    def test_curso_longo_nao_transborda(self):
        """Regressão do bug original: wrap(width=110) por caracteres."""
        fonte = self._fonte()
        longo = (
            "ELETRICISTA PREDIAL E RESIDENCIAL COM ÊNFASE EM ENERGIAS "
            "RENOVÁVEIS E AUTOMAÇÃO"
        )
        linhas = quebrar_em_linhas(longo, fonte, 13, LAYOUT.largura_util)
        for linha in linhas:
            assert pdfmetrics.stringWidth(linha, fonte, 13) <= LAYOUT.largura_util

    def test_texto_vazio(self):
        assert quebrar_em_linhas("   ", "Helvetica", 12, 100) == []


class TestDadosDeMatricula:
    def test_extrai_de_models(self):
        class Matricula:
            curso_id = 7
            data_matricula = "2026-03-20"

        class Curso:
            id = 7
            nome = "Técnico em Administração"

        class Aluno:
            nome = "  José da Silva  "
            cpf = "133.992.517-69"
            matriculas = [Matricula()]

        dados = dados_de_matricula(
            Aluno(), Curso(), carga_horaria=200, aproveitamento=88,
            data_fim=date(2026, 12, 1),
        )
        assert dados.nome == "José da Silva"
        assert dados.curso == "Técnico em Administração"
        assert dados.carga_horaria == 200
        assert dados.aproveitamento == 88.0
        assert dados.data_inicio == date(2026, 3, 20)
        assert dados.data_fim == date(2026, 12, 1)

    def test_sem_matricula_usa_data_fim_como_inicio(self):
        class Curso:
            id = 1
            nome = "Curso"

        class Aluno:
            nome = "Aluno"
            cpf = ""
            matriculas = []

        dados = dados_de_matricula(
            Aluno(), Curso(), carga_horaria=10, aproveitamento=100,
            data_fim=date(2026, 6, 1),
        )
        assert dados.data_inicio == date(2026, 6, 1)

    def test_matricula_de_outro_curso_nao_e_usada(self):
        class M1:
            curso_id = 99
            data_matricula = "2020-01-01"

        class M2:
            curso_id = 5
            data_matricula = "2026-02-02"

        class Curso:
            id = 5
            nome = "Curso Certo"

        class Aluno:
            nome = "Aluno"
            cpf = ""
            matriculas = [M1(), M2()]

        dados = dados_de_matricula(
            Aluno(), Curso(), carga_horaria=10, aproveitamento=100,
            data_fim=date(2026, 6, 1),
        )
        assert dados.data_inicio == date(2026, 2, 2)
