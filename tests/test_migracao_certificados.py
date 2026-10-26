"""Testes da migração ``f7a8b9c0d1e2`` (tabela ``certificados``).

O cenário que importa não é o banco vazio: ``db.init_db()`` chama
``db.create_all()`` em todo startup, então em produção a tabela já existe
quando a migração roda — criada pelo ORM, com as FKs sem ``ON DELETE SET
NULL``. A migração precisa detectar isso e reconstruir a tabela sem perder
linhas, senão excluir aluno/matrícula passa a falhar.
"""
from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from migrations.versions import f7a8b9c0d1e2_add_certificados as migracao


def _conexao(tmp_path):
    """Conexão SQLAlchemy (Alembic não aceita ``sqlite3.Connection``)."""
    caminho = tmp_path / "teste.db"
    engine = create_engine(f"sqlite:///{caminho}")
    con = engine.connect()
    for sql in (
        "CREATE TABLE alunos     (id INTEGER PRIMARY KEY)",
        "CREATE TABLE cursos     (id INTEGER PRIMARY KEY)",
        "CREATE TABLE matriculas (id INTEGER PRIMARY KEY,"
        " aluno_id INTEGER REFERENCES alunos(id),"
        " curso_id INTEGER REFERENCES cursos(id))",
        "INSERT INTO alunos VALUES (1)",
        "INSERT INTO cursos VALUES (1)",
        "INSERT INTO matriculas VALUES (1, 1, 1)",
    ):
        con.exec_driver_sql(sql)
    con.commit()
    return con


def _criar_tabela_como_o_orm_faria(con):
    """Reproduz o schema que ``db.create_all()`` gera: FKs sem ON DELETE."""
    for sql in (
        """CREATE TABLE certificados (
            id INTEGER NOT NULL PRIMARY KEY,
            aluno_id INTEGER REFERENCES alunos(id),
            matricula_id INTEGER REFERENCES matriculas(id),
            curso_id INTEGER REFERENCES cursos(id),
            nome_aluno VARCHAR(120) NOT NULL,
            cpf_aluno VARCHAR(14),
            nome_curso VARCHAR(120) NOT NULL,
            carga_horaria INTEGER NOT NULL,
            aproveitamento FLOAT NOT NULL,
            data_inicio VARCHAR(10),
            data_fim VARCHAR(10),
            codigo_verificacao VARCHAR(20) NOT NULL,
            hash_sha256 VARCHAR(64) NOT NULL,
            layout_id VARCHAR(60),
            arquivo_url VARCHAR(500),
            arquivo_public_id VARCHAR(500),
            status VARCHAR(20) NOT NULL,
            emitido_em VARCHAR(19) NOT NULL,
            emitido_por VARCHAR(80),
            cancelado_em VARCHAR(19),
            cancelado_por VARCHAR(80),
            motivo_cancelamento VARCHAR(200),
            CONSTRAINT uq_certificados_codigo UNIQUE (codigo_verificacao)
        )""",
        """INSERT INTO certificados VALUES (
            1, 1, 1, 1, 'Maria Silva', '133.992.517-69', 'Informática',
            180, 90.0, '2026-01-01', '2026-12-01', 'ABCDEFGHJK',
            'hash-de-teste', 'cqp-certificado-v1', NULL, NULL, 'EMITIDO',
            '2026-10-26 10:00:00', 'Secretaria', NULL, NULL, NULL
        )""",
    ):
        con.exec_driver_sql(sql)
    con.commit()


def _rodar_upgrade(con):
    contexto = MigrationContext.configure(con)
    with Operations.context(contexto):
        migracao.upgrade()


def _fks(con):
    return {
        linha[3]: linha[6]
        for linha in con.exec_driver_sql("PRAGMA foreign_key_list(certificados)")
    }


class TestMigracao:
    def test_cria_tabela_quando_nao_existe(self, tmp_path):
        con = _conexao(tmp_path)
        _rodar_upgrade(con)

        assert _fks(con) == {
            "aluno_id": "SET NULL",
            "matricula_id": "SET NULL",
            "curso_id": "SET NULL",
        }

    def test_reconstroi_tabela_criada_pelo_create_all(self, tmp_path):
        """O caso real: tabela já existe com FKs NO ACTION."""
        con = _conexao(tmp_path)
        _criar_tabela_como_o_orm_faria(con)
        assert set(_fks(con).values()) == {"NO ACTION"}

        _rodar_upgrade(con)

        assert _fks(con) == {
            "aluno_id": "SET NULL",
            "matricula_id": "SET NULL",
            "curso_id": "SET NULL",
        }

    def test_reconstrucao_preserva_dados(self, tmp_path):
        con = _conexao(tmp_path)
        _criar_tabela_como_o_orm_faria(con)

        _rodar_upgrade(con)

        linha = con.exec_driver_sql(
            "SELECT id, nome_aluno, codigo_verificacao, hash_sha256, status "
            "FROM certificados"
        ).fetchone()
        assert linha == (1, "Maria Silva", "ABCDEFGHJK", "hash-de-teste", "EMITIDO")

    def test_idempotente(self, tmp_path):
        con = _conexao(tmp_path)
        _criar_tabela_como_o_orm_faria(con)

        _rodar_upgrade(con)
        _rodar_upgrade(con)  # segunda execução não pode falhar nem duplicar

        assert con.exec_driver_sql("SELECT COUNT(*) FROM certificados").fetchone()[0] == 1
        assert set(_fks(con).values()) == {"SET NULL"}

    def test_cria_indices(self, tmp_path):
        con = _conexao(tmp_path)
        _rodar_upgrade(con)

        indices = {linha[1] for linha in con.exec_driver_sql("PRAGMA index_list(certificados)")}
        assert "ix_certificados_aluno_id" in indices
        assert "ix_certificados_codigo" in indices

    def test_set_null_libera_exclusao_do_aluno(self, tmp_path):
        """O objetivo final: excluir o aluno não pode ser bloqueado."""
        con = _conexao(tmp_path)
        _criar_tabela_como_o_orm_faria(con)
        _rodar_upgrade(con)

        # PRAGMA foreign_keys é no-op dentro de transação aberta.
        con.commit()
        con.exec_driver_sql("PRAGMA foreign_keys=ON")
        con.exec_driver_sql("DELETE FROM matriculas WHERE id = 1")
        con.exec_driver_sql("DELETE FROM alunos WHERE id = 1")
        con.commit()

        linha = con.exec_driver_sql(
            "SELECT aluno_id, matricula_id, nome_aluno FROM certificados"
        ).fetchone()
        assert linha == (None, None, "Maria Silva")

    def test_sem_set_null_a_exclusao_falharia(self, tmp_path):
        """Prova que a reconstrução é necessária, não cosmética.

        Usa uma conexão nova porque ``PRAGMA foreign_keys`` só tem efeito
        fora de uma transação aberta.
        """
        con = _conexao(tmp_path)
        _criar_tabela_como_o_orm_faria(con)
        con.commit()
        con.close()

        engine = create_engine(f"sqlite:///{tmp_path / 'teste.db'}")
        with engine.connect() as nova:
            nova.exec_driver_sql("PRAGMA foreign_keys=ON")
            with pytest.raises(IntegrityError):
                nova.exec_driver_sql("DELETE FROM alunos WHERE id = 1")
