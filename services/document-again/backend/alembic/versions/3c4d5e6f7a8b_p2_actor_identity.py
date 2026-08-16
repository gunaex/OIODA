"""add actor identity integration

Stable Account Again subject ids are recorded alongside display names on
audit-critical tables, plus an actor_identities resolution cache.

Revision ID: 3c4d5e6f7a8b
Revises: 8a1b2c3d4e5f
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa


revision = '3c4d5e6f7a8b'
down_revision = '8a1b2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ('artifact_revisions', 'annotations', 'confirmations', 'change_requests', 'baselines', 'decisions'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('actor_id', sa.String(length=200), nullable=True))

    op.create_table('actor_identities',
        sa.Column('actor_id', sa.String(length=200), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('tenant_id', sa.String(length=200), nullable=True),
        sa.Column('source', sa.String(length=40), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('actor_id')
    )


def downgrade() -> None:
    op.drop_table('actor_identities')
    for table in ('artifact_revisions', 'annotations', 'confirmations', 'change_requests', 'baselines', 'decisions'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('actor_id')
