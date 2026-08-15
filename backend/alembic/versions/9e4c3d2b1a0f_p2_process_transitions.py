"""add process transitions and flow layout

Process transitions are explicit structured relationships between steps.
Flow node positions are persisted separately from the semantic flow.

Revision ID: 9e4c3d2b1a0f
Revises: 6f3a2b1c9d4e
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa


revision = '9e4c3d2b1a0f'
down_revision = '6f3a2b1c9d4e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('process_flows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('layout', sa.JSON(), nullable=True))

    op.create_table('process_transitions',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('flow_id', sa.String(length=40), nullable=False),
        sa.Column('semantic_id', sa.String(length=200), nullable=False),
        sa.Column('from_step_semantic_id', sa.String(length=200), nullable=False),
        sa.Column('to_step_semantic_id', sa.String(length=200), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=True),
        sa.Column('condition', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['flow_id'], ['process_flows.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('process_transitions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_process_transitions_flow_id'), ['flow_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('process_transitions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_process_transitions_flow_id'))
    op.drop_table('process_transitions')

    with op.batch_alter_table('process_flows', schema=None) as batch_op:
        batch_op.drop_column('layout')
