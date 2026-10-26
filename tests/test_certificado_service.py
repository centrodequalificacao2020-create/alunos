"""Testes do serviço de emissão de certificados (sem Flask request)."""
from __future__ import annotations

import hashlib
from datetime import date

import pytest

from services import certificado_service as svc


def _criar_aluno_curso(db_session, *, nome="Maria Silva Santos",
                       cpf="133.992.517-69", status_matricula="CONCLUIDA"):
    from models import Aluno, Curso, Matricula

    curso = Curso(nome="Informática Básica", tipo="Profissionalizante")
    db_session.add(curso)
    db_session.flush()

    aluno = Aluno(nome=nome, cpf=cpf, curso_id=curso.id)
    db_session.add(aluno)
    db_session.flush()

    matricula = Matricula(
        aluno_id=aluno.id, curso_id=curso.id,
        data_matricula="2026-01-15", status=status_matricula,
    )
    db_session.add(matricula)
    db_session.flush()
    return aluno, curso, matricula


def _emitir(db_session, aluno, matricula, **over):
    kwargs = dict(
        aluno_id=aluno.id,
        matricula_id=matricula.id if matricula else None,
        carga_horaria=180,
        aproveitamento=90.0,
        data_inicio=date(2026, 1, 15),
        data_fim=date(2026, 12, 20),
        emitido_por="Secretaria",
    )
    kwargs.update(over)
    return svc.emitir_certificado(**kwargs)


class TestNormalizarCpf:
    @pytest.mark.parametrize("entrada,esperado", [
        ("13399251769", "133.992.517-69"),
        ("133.992.517-69", "133.992.517-69"),
        ("133 992 517 69", "133.992.517-69"),
        ("", ""),
        (None, ""),
        ("123", ""),
        ("123456789012", ""),
    ])
    def test_formata_ou_descarta(self, entrada, esperado):
        assert svc.normalizar_cpf(entrada) == esperado


class TestCodigoVerificacao:
    def test_tamanho_e_alfabeto(self):
        codigo = svc.gerar_codigo_verificacao()
        assert len(codigo) == 10
        assert all(c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for c in codigo)

    def test_sem_caracteres_ambiguos(self):
        for _ in range(50):
            codigo = svc.gerar_codigo_verificacao()
            assert not (set(codigo) & set("O0I1L"))

    def test_nao_repete(self):
        codigos = {svc.gerar_codigo_verificacao() for _ in range(200)}
        assert len(codigos) == 200


class TestValidarEmissao:
    def _form(self, **over):
        base = {
            "carga_horaria": "180",
            "aproveitamento": "90",
            "data_inicio": "2026-01-15",
            "data_fim": "2026-12-20",
        }
        base.update(over)
        return base

    def test_valores_validos(self):
        v = svc.validar_emissao(self._form())
        assert v["carga_horaria"] == 180
        assert v["aproveitamento"] == 90.0
        assert v["data_inicio"] == date(2026, 1, 15)
        assert v["data_fim"] == date(2026, 12, 20)

    def test_aceita_data_brasileira(self):
        v = svc.validar_emissao(self._form(data_inicio="15/01/2026"))
        assert v["data_inicio"] == date(2026, 1, 15)

    def test_aceita_virgula_decimal(self):
        v = svc.validar_emissao(self._form(aproveitamento="87,5"))
        assert v["aproveitamento"] == 87.5

    @pytest.mark.parametrize("campo,valor,mensagem", [
        ("carga_horaria", "", "Carga horária inválida"),
        ("carga_horaria", "abc", "Carga horária inválida"),
        ("carga_horaria", "0", "entre 1 e"),
        ("carga_horaria", "10001", "entre 1 e"),
        ("aproveitamento", "", "Aproveitamento inválido"),
        ("aproveitamento", "-1", "entre 0 e 100"),
        ("aproveitamento", "101", "entre 0 e 100"),
        ("data_inicio", "", "Informe a data de início"),
        ("data_fim", "31/02/2026", "Data de conclusão inválida"),
    ])
    def test_rejeita_invalidos(self, campo, valor, mensagem):
        with pytest.raises(svc.ErroEmissao, match=mensagem):
            svc.validar_emissao(self._form(**{campo: valor}))

    def test_rejeita_conclusao_antes_do_inicio(self):
        with pytest.raises(svc.ErroEmissao, match="não pode ser anterior"):
            svc.validar_emissao(self._form(
                data_inicio="2026-12-20", data_fim="2026-01-15"
            ))

    def test_aceita_mesmo_dia(self):
        v = svc.validar_emissao(self._form(
            data_inicio="2026-06-01", data_fim="2026-06-01"
        ))
        assert v["data_inicio"] == v["data_fim"]


class TestEmitirCertificado:
    def test_persiste_snapshot(self, db_session):
        aluno, curso, matricula = _criar_aluno_curso(db_session)
        cert, pdf = _emitir(db_session, aluno, matricula)

        assert cert.id is not None
        assert cert.nome_aluno == "Maria Silva Santos"
        assert cert.cpf_aluno == "133.992.517-69"
        assert cert.nome_curso == "Informática Básica"
        assert cert.carga_horaria == 180
        assert cert.aproveitamento == 90.0
        assert cert.data_inicio == "2026-01-15"
        assert cert.data_fim == "2026-12-20"
        assert cert.status == "EMITIDO"
        assert cert.emitido_por == "Secretaria"
        assert cert.layout_id == "cqp-certificado-v1"
        assert pdf.startswith(b"%PDF-")

    def test_hash_corresponde_ao_pdf(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, pdf = _emitir(db_session, aluno, matricula)
        assert cert.hash_sha256 == hashlib.sha256(pdf).hexdigest()

    def test_pdf_e_reproduzivel(self, db_session):
        """invariant=1 garante que o hash gravado continua válido."""
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, pdf = _emitir(db_session, aluno, matricula)
        assert svc.pdf_do_certificado(cert) == pdf

    def test_codigo_unico(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        a, _ = _emitir(db_session, aluno, matricula)
        b, _ = _emitir(db_session, aluno, matricula)
        assert a.codigo_verificacao != b.codigo_verificacao

    def test_snapshot_nao_muda_com_aluno_renomeado(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)

        aluno.nome = "Maria Silva Santos Oliveira"
        db_session.flush()

        assert cert.nome_aluno == "Maria Silva Santos"

    def test_snapshot_nao_muda_com_curso_renomeado(self, db_session):
        aluno, curso, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)

        curso.nome = "Informática Avançada"
        db_session.flush()

        assert cert.nome_curso == "Informática Básica"

    def test_cpf_ausente_vira_none(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session, cpf="")
        cert, _ = _emitir(db_session, aluno, matricula)
        assert cert.cpf_aluno is None

    def test_aluno_inexistente(self, db_session):
        with pytest.raises(svc.ErroEmissao, match="Aluno não encontrado"):
            svc.emitir_certificado(
                aluno_id=99999, matricula_id=None, carga_horaria=10,
                aproveitamento=100, data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 1, 2), emitido_por="x",
            )

    def test_matricula_de_outro_aluno(self, db_session):
        aluno_a, _, _ = _criar_aluno_curso(db_session, nome="Aluno A")
        aluno_b, _, matricula_b = _criar_aluno_curso(db_session, nome="Aluno B")

        with pytest.raises(svc.ErroEmissao, match="não pertence a este aluno"):
            _emitir(db_session, aluno_a, matricula_b)

    def test_sem_matricula_usa_curso_do_aluno(self, db_session):
        aluno, curso, _ = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, None, matricula_id=None)
        assert cert.curso_id == curso.id
        assert cert.matricula_id is None

    def test_aluno_sem_curso(self, db_session):
        from models import Aluno

        aluno = Aluno(nome="Sem Curso", cpf="")
        db_session.add(aluno)
        db_session.flush()

        with pytest.raises(svc.ErroEmissao, match="sem curso vinculado"):
            svc.emitir_certificado(
                aluno_id=aluno.id, matricula_id=None, carga_horaria=10,
                aproveitamento=100, data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 1, 2), emitido_por="x",
            )


class TestFormatacaoTexto:
    """O certificado é impresso em português: vírgula decimal, sem zeros à toa."""

    @pytest.mark.parametrize("valor,esperado", [
        (180, "180"), (180.0, "180"), (92.5, "92,5"), (100, "100"), (0, "0"),
    ])
    def test_carga_horaria_texto(self, db_session, valor, esperado):
        from models import Certificado

        assert Certificado(carga_horaria=valor).carga_horaria_texto == esperado

    @pytest.mark.parametrize("valor,esperado", [
        (90, "90"), (90.0, "90"), (92.5, "92,5"), (87.25, "87,25"), (0, "0"),
    ])
    def test_aproveitamento_texto(self, db_session, valor, esperado):
        from models import Certificado

        assert Certificado(aproveitamento=valor).aproveitamento_texto == esperado


class TestCancelamento:
    def test_cancelamento_logico(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)

        cancelado = svc.cancelar_certificado(
            cert.id, motivo="Emitido com carga horária errada", cancelado_por="Admin"
        )
        assert cancelado.status == "CANCELADO"
        assert cancelado.cancelado is True
        assert cancelado.motivo_cancelamento == "Emitido com carga horária errada"
        assert cancelado.cancelado_por == "Admin"
        assert cancelado.cancelado_em is not None

    def test_cancelamento_preserva_codigo(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)
        codigo = cert.codigo_verificacao

        svc.cancelar_certificado(cert.id, motivo="teste", cancelado_por="Admin")
        assert svc.buscar_por_codigo(codigo).codigo_verificacao == codigo

    def test_nao_cancela_duas_vezes(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)
        svc.cancelar_certificado(cert.id, motivo="a", cancelado_por="Admin")

        with pytest.raises(svc.ErroEmissao, match="já está cancelado"):
            svc.cancelar_certificado(cert.id, motivo="b", cancelado_por="Admin")

    def test_certificado_inexistente(self, db_session):
        with pytest.raises(svc.ErroEmissao, match="não encontrado"):
            svc.cancelar_certificado(99999, motivo="x", cancelado_por="y")


class TestExclusaoDeOrigem:
    """Excluir aluno/matrícula não pode ser bloqueado nem apagar o certificado.

    Regressão: as FKs nasceram sem ``ON DELETE SET NULL``, então excluir um
    aluno com certificado emitido estourava ``FOREIGN KEY constraint failed``.
    """

    def test_excluir_matricula_preserva_certificado(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, pdf = _emitir(db_session, aluno, matricula)
        cid, nome, codigo = cert.id, cert.nome_aluno, cert.codigo_verificacao

        db_session.delete(matricula)
        db_session.commit()

        sobrevivente = db_session.get(type(cert), cid)
        assert sobrevivente is not None
        assert sobrevivente.matricula_id is None
        assert sobrevivente.nome_aluno == nome
        assert sobrevivente.codigo_verificacao == codigo
        assert svc.pdf_do_certificado(sobrevivente) == pdf

    def test_excluir_aluno_preserva_certificado(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, pdf = _emitir(db_session, aluno, matricula)
        cid, nome, codigo = cert.id, cert.nome_aluno, cert.codigo_verificacao

        db_session.delete(matricula)
        db_session.delete(aluno)
        db_session.commit()

        sobrevivente = db_session.get(type(cert), cid)
        assert sobrevivente is not None
        assert sobrevivente.aluno_id is None
        assert sobrevivente.nome_aluno == nome
        assert sobrevivente.codigo_verificacao == codigo
        assert svc.pdf_do_certificado(sobrevivente) == pdf

    def test_certificado_orfao_continua_consultavel(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)
        codigo = cert.codigo_verificacao

        db_session.delete(matricula)
        db_session.delete(aluno)
        db_session.commit()

        encontrado = svc.buscar_por_codigo(codigo)
        assert encontrado is not None
        assert encontrado.aluno_id is None


class TestConsulta:
    def test_busca_por_codigo_normaliza_caixa(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        cert, _ = _emitir(db_session, aluno, matricula)

        assert svc.buscar_por_codigo(cert.codigo_verificacao.lower()).id == cert.id
        assert svc.buscar_por_codigo(f"  {cert.codigo_verificacao}  ").id == cert.id

    def test_busca_codigo_vazio(self, db_session):
        assert svc.buscar_por_codigo("") is None
        assert svc.buscar_por_codigo(None) is None

    def test_busca_codigo_inexistente(self, db_session):
        assert svc.buscar_por_codigo("ZZZZZZZZZZ") is None

    def test_historico_do_aluno(self, db_session):
        aluno, _, matricula = _criar_aluno_curso(db_session)
        _emitir(db_session, aluno, matricula)
        _emitir(db_session, aluno, matricula)

        assert len(svc.certificados_do_aluno(aluno.id)) == 2

    def test_historico_nao_mistura_alunos(self, db_session):
        aluno_a, _, mat_a = _criar_aluno_curso(db_session, nome="Aluno A")
        aluno_b, _, mat_b = _criar_aluno_curso(db_session, nome="Aluno B")

        _emitir(db_session, aluno_a, mat_a)
        _emitir(db_session, aluno_b, mat_b)

        assert len(svc.certificados_do_aluno(aluno_a.id)) == 1
        assert len(svc.certificados_do_aluno(aluno_b.id)) == 1
