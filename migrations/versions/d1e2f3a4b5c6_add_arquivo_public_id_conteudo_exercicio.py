"""add arquivo_public_id to conteudos and exercicios

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    colunas_conteudos = [c['name'] for c in inspector.get_columns('conteudos')]
    if 'arquivo_public_id' not in colunas_conteudos:
        op.add_column('conteudos',
            sa.Column('arquivo_public_id', sa.String(500), nullable=True)
        )

    colunas_exercicios = [c['name'] for c in inspector.get_columns('exercicios')]
    if 'arquivo_public_id' not in colunas_exercicios:
        op.add_column('exercicios',
            sa.Column('arquivo_public_id', sa.String(500), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('exercicios') as batch_op:
        batch_op.drop_column('arquivo_public_id')

    with op.batch_alter_table('conteudos') as batch_op:
        batch_op.drop_column('arquivo_public_id')
