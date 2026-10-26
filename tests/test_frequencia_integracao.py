"""Integração de ``calcular_percentual`` com o banco (SQLite em memória)."""
from __future__ import annotations

import pytest

from services import frequencia_service as svc


def _criar_aluno_curso(db_session):
    from models import Aluno, Curso

    curso = Curso(nome="Curso de Teste", tipo="Profissionalizante")
    db_session.add(curso)
    db_session.flush()

    aluno = Aluno(nome="Aluno de Teste", cpf="133.992.517-69", curso_id=curso.id)
    db_session.add(aluno)
    db_session.flush()
    return aluno, curso


def _add_frequencias(db_session, aluno, curso, statuses):
    from models import Frequencia

    for i, status in enumerate(statuses):
        db_session.add(Frequencia(
            aluno_id=aluno.id, curso_id=curso.id,
            data=f"2026-01-{i + 1:02d}", status=status,
        ))
    db_session.flush()


class TestCalcularPercentual:
    def test_formato_real_do_banco_p_f(self, db_session):
        aluno, curso = _criar_aluno_curso(db_session)
        _add_frequencias(db_session, aluno, curso, ["P", "P", "P", "F"])

        # O bug: retornava 0.0 porque comparava apenas "Presente"
        assert svc.calcular_percentual(aluno.id, curso.id) == 75.0

    def test_formato_do_default_do_model(self, db_session):
        aluno, curso = _criar_aluno_curso(db_session)
        _add_frequencias(db_session, aluno, curso, ["Presente", "Presente", "Falta"])

        assert svc.calcular_percentual(aluno.id, curso.id) == 66.7

    def test_sem_registros_retorna_zero(self, db_session):
        aluno, curso = _criar_aluno_curso(db_session)
        assert svc.calcular_percentual(aluno.id, curso.id) == 0.0

    def test_nao_mistura_cursos(self, db_session):
        from models import Curso

        aluno, curso_a = _criar_aluno_curso(db_session)
        curso_b = Curso(nome="Outro Curso")
        db_session.add(curso_b)
        db_session.flush()

        _add_frequencias(db_session, aluno, curso_a, ["P", "P"])
        _add_frequencias(db_session, aluno, curso_b, ["F", "F"])

        assert svc.calcular_percentual(aluno.id, curso_a.id) == 100.0
        assert svc.calcular_percentual(aluno.id, curso_b.id) == 0.0


class TestRegistrarFrequencia:
    def test_rejeita_data_futura(self, db_session):
        aluno, curso = _criar_aluno_curso(db_session)
        with pytest.raises(ValueError, match="futura"):
            svc.registrar_frequencia(aluno.id, curso.id, "2099-01-01", "P")

    def test_rejeita_formato_invalido(self, db_session):
        aluno, curso = _criar_aluno_curso(db_session)
        with pytest.raises(ValueError, match="Data inválida"):
            svc.registrar_frequencia(aluno.id, curso.id, "01/01/2026", "P")

    def test_grava_e_atualiza_sem_duplicar(self, db_session):
        aluno, curso = _criar_aluno_curso(db_session)

        svc.registrar_frequencia(aluno.id, curso.id, "2026-01-05", "P")
        primeiro = svc.get_historico(aluno.id, curso.id)
        assert len(primeiro) == 1
        assert primeiro[0].status == "P"

        svc.registrar_frequencia(aluno.id, curso.id, "2026-01-05", "F")
        segundo = svc.get_historico(aluno.id, curso.id)
        assert len(segundo) == 1, "deve atualizar, não duplicar"
        assert segundo[0].status == "F"
