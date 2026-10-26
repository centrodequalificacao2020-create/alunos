"""add tabela certificados (snapshot de certificado de conclusão)

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-10-26

Nota sobre idempotência: ``db.init_db()`` chama ``db.create_all()`` em todo
startup, então esta tabela normalmente JÁ EXISTE quando a migração roda —
criada pelo ORM, com as FKs sem ``ON DELETE SET NULL``. Por isso a migração
não se limita a criar a tabela: se ela existir com as FKs erradas, reconstrói
preservando os dados. Sem isso, excluir um aluno/matrícula/curso passaria a
falhar com ``FOREIGN KEY constraint failed``.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None

_TABELA = 'certificados'

_COLUNAS = [
    ('id',                  sa.Integer(),   False),
    ('aluno_id',            sa.Integer(),   True),
    ('matricula_id',        sa.Integer(),   True),
    ('curso_id',            sa.Integer(),   True),
    ('nome_aluno',          sa.String(120), False),
    ('cpf_aluno',           sa.String(14),  True),
    ('nome_curso',          sa.String(120), False),
    ('carga_horaria',       sa.Integer(),   False),
    ('aproveitamento',      sa.Float(),     False),
    ('data_inicio',         sa.String(10),  True),
    ('data_fim',            sa.String(10),  True),
    ('codigo_verificacao',  sa.String(20),  False),
    ('hash_sha256',         sa.String(64),  False),
    ('layout_id',           sa.String(60),  True),
    ('arquivo_url',         sa.String(500), True),
    ('arquivo_public_id',   sa.String(500), True),
    ('status',              sa.String(20),  False),
    ('emitido_em',          sa.String(19),  False),
    ('emitido_por',         sa.String(80),  True),
    ('cancelado_em',        sa.String(19),  True),
    ('cancelado_por',       sa.String(80),  True),
    ('motivo_cancelamento', sa.String(200), True),
]

_FKS = [
    ('aluno_id',     'alunos.id'),
    ('matricula_id', 'matriculas.id'),
    ('curso_id',     'cursos.id'),
]


def _fks_estao_corretas(conn) -> bool:
    """True se as três FKs já usam ON DELETE SET NULL."""
    fks = sa.inspect(conn).get_foreign_keys(_TABELA)
    por_coluna = {fk['constrained_columns'][0]: fk for fk in fks}
    for coluna, _ in _FKS:
        fk = por_coluna.get(coluna)
        if fk is None:
            return False
        if (fk.get('options') or {}).get('ondelete', '').upper() != 'SET NULL':
            return False
    return True


def _criar_tabela(nome: str) -> None:
    op.create_table(
        nome,
        *[
            sa.Column(col, tipo, nullable=nulo)
            for col, tipo, nulo in _COLUNAS
        ],
        sa.ForeignKeyConstraint(['aluno_id'],     ['alunos.id'],     ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['matricula_id'], ['matriculas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['curso_id'],     ['cursos.id'],     ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('codigo_verificacao', name='uq_certificados_codigo'),
    )


def _reconstruir_com_set_null(conn) -> None:
    """Recria a tabela com ON DELETE SET NULL preservando todas as linhas.

    SQLite não suporta ALTER de FK, então o caminho é criar uma tabela nova,
    copiar os dados, dropar a antiga e renomear. ``PRAGMA foreign_keys`` é
    desligado durante a operação para que o DROP não dispare cascatas.
    """
    colunas = ', '.join(col for col, _, _ in _COLUNAS)
    temporaria = f'{_TABELA}__novo'

    conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
    try:
        if temporaria in sa.inspect(conn).get_table_names():
            op.drop_table(temporaria)
        _criar_tabela(temporaria)
        conn.exec_driver_sql(
            f'INSERT INTO {temporaria} ({colunas}) SELECT {colunas} FROM {_TABELA}'
        )
        op.drop_table(_TABELA)
        conn.exec_driver_sql(f'ALTER TABLE {temporaria} RENAME TO {_TABELA}')
    finally:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _TABELA not in inspector.get_table_names():
        _criar_tabela(_TABELA)
    elif not _fks_estao_corretas(conn):
        _reconstruir_com_set_null(conn)

    indices = {i['name'] for i in sa.inspect(conn).get_indexes(_TABELA)}
    if 'ix_certificados_aluno_id' not in indices:
        op.create_index('ix_certificados_aluno_id', _TABELA, ['aluno_id'])
    if 'ix_certificados_codigo' not in indices:
        op.create_index('ix_certificados_codigo', _TABELA, ['codigo_verificacao'])


def downgrade():
    op.drop_index('ix_certificados_codigo',   table_name=_TABELA)
    op.drop_index('ix_certificados_aluno_id', table_name=_TABELA)
    op.drop_table(_TABELA)
