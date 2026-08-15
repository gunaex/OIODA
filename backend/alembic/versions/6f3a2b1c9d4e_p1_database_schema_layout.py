"""add erd layout column to database_schemas

ERD node positions are persisted separately from the semantic schema:
moving a node never changes table/field identity.

Revision ID: 6f3a2b1c9d4e
Revises: 1286f0e54ef1
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa


revision = '6f3a2b1c9d4e'
down_revision = '1286f0e54ef1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('database_schemas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('layout', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('database_schemas', schema=None) as batch_op:
        batch_op.drop_column('layout')
