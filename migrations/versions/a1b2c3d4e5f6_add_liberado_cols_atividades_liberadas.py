"""add liberado cols to atividades_liberadas

Revision ID: a1b2c3d4e5f6
Revises: f89023fdbe0c
Create Date: 2026-04-01

BUG-01 FIX: AtividadeLiberada nao tinha as colunas liberado, liberado_por,
liberado_em e extra_tentativas, causando AttributeError ao acessar atividades
no portal do aluno.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f89023fdbe0c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('atividades_liberadas', schema=None) as batch_op:
        # Verifica se as colunas ja existem antes de criar (idempotente)
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        existing = {c['name'] for c in inspector.get_columns('atividades_liberadas')}

        if 'liberado' not in existing:
            batch_op.add_column(sa.Column('liberado', sa.Integer(), nullable=False, server_default='1'))
        if 'liberado_por' not in existing:
            batch_op.add_column(sa.Column('liberado_por', sa.String(length=120), nullable=True))
        if 'liberado_em' not in existing:
            batch_op.add_column(sa.Column('liberado_em', sa.String(length=19), nullable=True))
        if 'extra_tentativas' not in existing:
            batch_op.add_column(sa.Column('extra_tentativas', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    with op.batch_alter_table('atividades_liberadas', schema=None) as batch_op:
        batch_op.drop_column('extra_tentativas')
        batch_op.drop_column('liberado_em')
        batch_op.drop_column('liberado_por')
        batch_op.drop_column('liberado')
