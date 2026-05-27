"""add tabela contrato_aceites (log imutavel de aceite de contrato)

Revision ID: c4d5e6f7a8b9
Revises: b3f1a2e9c047
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3f1a2e9c047'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tabelas = inspector.get_table_names()

    if 'contrato_aceites' not in tabelas:
        op.create_table(
            'contrato_aceites',
            sa.Column('id',            sa.Integer(),     nullable=False),
            sa.Column('aluno_id',      sa.Integer(),     nullable=False),
            sa.Column('versao',        sa.String(20),    nullable=False, server_default='v1.0'),
            sa.Column('hash_contrato', sa.String(64),    nullable=False),
            sa.Column('aceito_em',     sa.String(19),    nullable=False),
            sa.Column('ip',            sa.String(45),    nullable=True),
            sa.Column('user_agent',    sa.String(500),   nullable=True),
            sa.ForeignKeyConstraint(['aluno_id'], ['alunos.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_contrato_aceite_aluno_id',  'contrato_aceites', ['aluno_id'])
        op.create_index('ix_contrato_aceite_aceito_em', 'contrato_aceites', ['aceito_em'])


def downgrade():
    op.drop_index('ix_contrato_aceite_aceito_em', table_name='contrato_aceites')
    op.drop_index('ix_contrato_aceite_aluno_id',  table_name='contrato_aceites')
    op.drop_table('contrato_aceites')
