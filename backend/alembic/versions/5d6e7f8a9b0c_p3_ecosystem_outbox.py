"""add ecosystem event and outbox model

Revision ID: 5d6e7f8a9b0c
Revises: 3c4d5e6f7a8b
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa


revision = '5d6e7f8a9b0c'
down_revision = '3c4d5e6f7a8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('ecosystem_events',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('event_type', sa.String(length=60), nullable=False),
        sa.Column('project_id', sa.String(length=40), nullable=False),
        sa.Column('tenant_id', sa.String(length=200), nullable=True),
        sa.Column('source_service', sa.String(length=60), nullable=False),
        sa.Column('source_object_id', sa.String(length=200), nullable=True),
        sa.Column('source_revision', sa.String(length=200), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_id', sa.String(length=200), nullable=True),
        sa.Column('payload_version', sa.String(length=20), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('correlation_id', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ecosystem_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ecosystem_events_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ecosystem_events_correlation_id'), ['correlation_id'], unique=False)

    op.create_table('outbox_events',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('event_id', sa.String(length=40), nullable=False),
        sa.Column('target_service', sa.String(length=60), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('external_reference', sa.String(length=300), nullable=True),
        sa.Column('correlation_id', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['ecosystem_events.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'target_service')
    )
    with op.batch_alter_table('outbox_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_outbox_events_event_id'), ['event_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_outbox_events_correlation_id'), ['correlation_id'], unique=False)


def downgrade() -> None:
    op.drop_table('outbox_events')
    op.drop_table('ecosystem_events')
