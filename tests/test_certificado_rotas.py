"""Testes das rotas de certificados (Flask test client)."""
from __future__ import annotations

import hashlib

import pytest


@pytest.fixture()
def cliente(app):
    return app.test_client()


@pytest.fixture()
def logado(cliente):
    """Sessão de secretaria ativa — ``login_required`` só exige usuario_id."""
    with cliente.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nome"] = "Secretaria Teste"
        sess["perfil"] = "secretaria"
    return cliente


def _criar_aluno_curso(db_session, *, nome="Maria Silva Santos"):
    from models import Aluno, Curso, Matricula

    curso = Curso(nome="Informática Básica", tipo="Profissionalizante")
    db_session.add(curso)
    db_session.flush()

    aluno = Aluno(nome=nome, cpf="133.992.517-69", curso_id=curso.id)
    db_session.add(aluno)
    db_session.flush()

    matricula = Matricula(
        aluno_id=aluno.id, curso_id=curso.id,
        data_matricula="2026-01-15", status="CONCLUIDA",
    )
    db_session.add(matricula)
    db_session.flush()
    return aluno, curso, matricula


def _form(matricula_id, **over):
    base = {
        "matricula_id": str(matricula_id),
        "carga_horaria": "180",
        "aproveitamento": "90",
        "data_inicio": "2026-01-15",
        "data_fim": "2026-12-20",
    }
    base.update(over)
    return base


class TestAutenticacao:
    def test_historico_exige_login(self, cliente, db_session):
        aluno, _, _ = _criar_aluno_curso(db_session)
        resp = cliente.get(f"/aluno/{aluno.id}/certificados")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_emissao_exige_login(self, cliente, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        resp = cliente.post(f"/aluno/{aluno.id}/certificados",
                            data=_form(matricula.id))
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_pdf_exige_login(self, cliente, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        from services.certificado_service import emitir_certificado
        from datetime import date

        cert, _ = emitir_certificado(
            aluno_id=aluno.id, matricula_id=matricula.id, carga_horaria=180,
            aproveitamento=90, data_inicio=date(2026, 1, 15),
            data_fim=date(2026, 12, 20), emitido_por="x",
        )
        resp = cliente.get(f"/certificados/{cert.id}/pdf")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestPaginaHistorico:
    def test_renderiza_formulario(self, logado, db_session):
        aluno, _, _ = _criar_aluno_curso(db_session)
        resp = logado.get(f"/aluno/{aluno.id}/certificados")
        assert resp.status_code == 200
        corpo = resp.get_data(as_text=True)
        assert "Emitir novo certificado" in corpo
        assert "Informática Básica" in corpo
        assert "carga_horaria" in corpo

    def test_aluno_inexistente_404(self, logado, db_session):
        assert logado.get("/aluno/99999/certificados").status_code == 404

    def test_aluno_sem_matricula_avisa(self, logado, db_session):
        from models import Aluno

        aluno = Aluno(nome="Sem Matrícula", cpf="")
        db_session.add(aluno)
        db_session.flush()

        resp = logado.get(f"/aluno/{aluno.id}/certificados")
        assert resp.status_code == 200
        assert "não possui matrícula" in resp.get_data(as_text=True)


class TestEmissao:
    def test_emite_e_redireciona(self, logado, db_session):
        from models import Certificado

        aluno, _, matricula = _criar_aluno_curso(db_session)
        resp = logado.post(f"/aluno/{aluno.id}/certificados",
                           data=_form(matricula.id), follow_redirects=True)

        assert resp.status_code == 200
        assert "Certificado emitido" in resp.get_data(as_text=True)
        assert Certificado.query.filter_by(aluno_id=aluno.id).count() == 1

    def test_dados_invalidos_nao_persistem(self, logado, db_session):
        from models import Certificado

        aluno, _, matricula = _criar_aluno_curso(db_session)
        resp = logado.post(f"/aluno/{aluno.id}/certificados",
                           data=_form(matricula.id, carga_horaria="0"),
                           follow_redirects=True)

        assert "entre 1 e" in resp.get_data(as_text=True)
        assert Certificado.query.filter_by(aluno_id=aluno.id).count() == 0

    def test_conclusao_antes_do_inicio(self, logado, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        resp = logado.post(
            f"/aluno/{aluno.id}/certificados",
            data=_form(matricula.id, data_inicio="2026-12-20",
                       data_fim="2026-01-15"),
            follow_redirects=True,
        )
        assert "não pode ser anterior" in resp.get_data(as_text=True)

    def test_matricula_de_outro_aluno(self, logado, db_session):
        aluno_a, _, _ = _criar_aluno_curso(db_session, nome="Aluno A")
        _, _, matricula_b = _criar_aluno_curso(db_session, nome="Aluno B")

        resp = logado.post(f"/aluno/{aluno_a.id}/certificados",
                           data=_form(matricula_b.id), follow_redirects=True)
        assert "não pertence a este aluno" in resp.get_data(as_text=True)


class TestDownloadPDF:
    def test_baixa_pdf_valido(self, logado, db_session):
        from datetime import date
        from services.certificado_service import emitir_certificado

        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, pdf = emitir_certificado(
            aluno_id=aluno.id, matricula_id=matricula.id, carga_horaria=180,
            aproveitamento=90, data_inicio=date(2026, 1, 15),
            data_fim=date(2026, 12, 20), emitido_por="x",
        )

        resp = logado.get(f"/certificados/{cert.id}/pdf")
        assert resp.status_code == 200
        assert resp.mimetype == "application/pdf"
        assert resp.data.startswith(b"%PDF-")
        assert hashlib.sha256(resp.data).hexdigest() == cert.hash_sha256

    def test_nome_do_arquivo_legivel(self, logado, db_session):
        from datetime import date
        from services.certificado_service import emitir_certificado

        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = emitir_certificado(
            aluno_id=aluno.id, matricula_id=matricula.id, carga_horaria=180,
            aproveitamento=90, data_inicio=date(2026, 1, 15),
            data_fim=date(2026, 12, 20), emitido_por="x",
        )

        resp = logado.get(f"/certificados/{cert.id}/pdf")
        assert f"certificado_maria_{cert.codigo_verificacao}.pdf" in \
            resp.headers["Content-Disposition"]

    def test_certificado_inexistente_404(self, logado, db_session):
        assert logado.get("/certificados/99999/pdf").status_code == 404


class TestCancelamento:
    def test_cancela_e_mantem_historico(self, logado, db_session):
        from datetime import date
        from services.certificado_service import emitir_certificado

        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = emitir_certificado(
            aluno_id=aluno.id, matricula_id=matricula.id, carga_horaria=180,
            aproveitamento=90, data_inicio=date(2026, 1, 15),
            data_fim=date(2026, 12, 20), emitido_por="x",
        )

        resp = logado.post(f"/certificados/{cert.id}/cancelar",
                           data={"motivo": "Carga horária incorreta"},
                           follow_redirects=True)

        assert "Certificado cancelado" in resp.get_data(as_text=True)
        assert "Carga horária incorreta" in resp.get_data(as_text=True)

        db_session.refresh(cert)
        assert cert.status == "CANCELADO"

    def test_cancelar_duas_vezes(self, logado, db_session):
        from datetime import date
        from services.certificado_service import emitir_certificado

        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = emitir_certificado(
            aluno_id=aluno.id, matricula_id=matricula.id, carga_horaria=180,
            aproveitamento=90, data_inicio=date(2026, 1, 15),
            data_fim=date(2026, 12, 20), emitido_por="x",
        )
        logado.post(f"/certificados/{cert.id}/cancelar", data={"motivo": "a"})
        resp = logado.post(f"/certificados/{cert.id}/cancelar",
                           data={"motivo": "b"}, follow_redirects=True)

        assert "já está cancelado" in resp.get_data(as_text=True)
