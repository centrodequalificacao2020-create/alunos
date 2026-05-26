"""add contrato_assinado e contrato_assinado_em em alunos

Revision ID: b3f1a2e9c047
Revises: a1b2c3d4e5f6
Create Date: 2026-05-26

Adiciona dois campos na tabela alunos para controle do aceite
do contrato no primeiro acesso ao portal do aluno:
  - contrato_assinado      (BOOLEAN, NOT NULL, default 0)
  - contrato_assinado_em   (VARCHAR(19), nullable)
"""
from alembic import op
import sqlalchemy as sa

revision = 'b3f1a2e9c047'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing = {c['name'] for c in inspector.get_columns('alunos')}

    with op.batch_alter_table('alunos', schema=None) as batch_op:
        if 'contrato_assinado' not in existing:
            batch_op.add_column(
                sa.Column(
                    'contrato_assinado',
                    sa.Boolean(),
                    nullable=False,
                    server_default='0',
                )
            )
        if 'contrato_assinado_em' not in existing:
            batch_op.add_column(
                sa.Column(
                    'contrato_assinado_em',
                    sa.String(length=19),
                    nullable=True,
                )
            )


def downgrade():
    with op.batch_alter_table('alunos', schema=None) as batch_op:
        batch_op.drop_column('contrato_assinado_em')
        batch_op.drop_column('contrato_assinado')
