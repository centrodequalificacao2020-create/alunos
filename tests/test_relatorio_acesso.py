"""Testes de controle de acesso à página de relatórios comerciais."""
from __future__ import annotations

import pytest


@pytest.fixture()
def cliente(app):
    return app.test_client()


def _logar(cliente, perfil: str):
    with cliente.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nome"] = f"Usuario {perfil}"
        sess["perfil"] = perfil
    return cliente


class TestAcessoRelatorio:
    @pytest.mark.parametrize("perfil", ["admin", "administrador", "financeiro", "secretaria"])
    def test_perfis_autorizados_acessam_pagina(self, cliente, perfil):
        _logar(cliente, perfil)
        resp = cliente.get("/relatorio")
        assert resp.status_code == 200

    @pytest.mark.parametrize("perfil", ["instrutor", "aluno"])
    def test_perfis_nao_autorizados_sao_redirecionados(self, cliente, perfil):
        _logar(cliente, perfil)
        resp = cliente.get("/relatorio")
        assert resp.status_code == 302

    def test_sem_login_redireciona_para_login(self, cliente):
        resp = cliente.get("/relatorio")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_secretaria_carrega_e_salva_relatorio(self, cliente, db_session):
        from models import Relatorio

        _logar(cliente, "secretaria")

        resp = cliente.get("/carregar_relatorio/2026-03")
        assert resp.status_code == 200

        resp = cliente.post(
            "/salvar_relatorio",
            json={"mes": "2026-03", "meta": 10, "realizado": 8,
                  "matriculas": 4, "matriculas_venda": 3},
        )
        assert resp.status_code == 200
        assert Relatorio.query.filter_by(mes="2026-03").one().meta == 10

        resp = cliente.get("/carregar_relatorio/2026-03")
        assert resp.get_json()["realizado"] == 8

    def test_secretaria_carrega_trimestre(self, cliente):
        _logar(cliente, "secretaria")
        resp = cliente.get("/relatorio_trimestre/2026/1")
        assert resp.status_code == 200
        assert "matriculas_venda" in resp.get_json()

    def test_instrutor_recebe_403_json(self, cliente):
        _logar(cliente, "instrutor")
        resp = cliente.get("/carregar_relatorio/2026-03",
                           headers={"Accept": "application/json"})
        assert resp.status_code == 403
