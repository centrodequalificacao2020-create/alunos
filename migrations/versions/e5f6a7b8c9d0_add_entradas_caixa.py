"""add tabela entradas_caixa (entradas manuais de caixa)

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tabelas = inspector.get_table_names()

    if 'entradas_caixa' not in tabelas:
        op.create_table(
            'entradas_caixa',
            sa.Column('id',                  sa.Integer(),     nullable=False),
            sa.Column('descricao',           sa.String(200),   nullable=False),
            sa.Column('valor',               sa.Float(),       nullable=False, server_default='0'),
            sa.Column('data',                sa.String(10),    nullable=False),
            sa.Column('forma',               sa.String(40),    nullable=True),
            sa.Column('categoria',           sa.String(60),    nullable=True),
            sa.Column('observacao',          sa.Text(),        nullable=True),
            sa.Column('criado_em',           sa.String(19),    nullable=True),
            sa.Column('criado_por',          sa.String(80),    nullable=True),
            sa.Column('cancelado',           sa.Integer(),     nullable=False, server_default='0'),
            sa.Column('cancelado_em',        sa.String(19),    nullable=True),
            sa.Column('cancelado_por',       sa.String(80),    nullable=True),
            sa.Column('motivo_cancelamento', sa.String(200),   nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_entradas_caixa_data',      'entradas_caixa', ['data'])
        op.create_index('ix_entradas_caixa_cancelado', 'entradas_caixa', ['cancelado'])


def downgrade():
    op.drop_index('ix_entradas_caixa_cancelado', table_name='entradas_caixa')
    op.drop_index('ix_entradas_caixa_data',      table_name='entradas_caixa')
    op.drop_table('entradas_caixa')
