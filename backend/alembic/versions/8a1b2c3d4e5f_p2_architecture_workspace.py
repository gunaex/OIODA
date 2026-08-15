"""add architecture design workspace

Revision ID: 8a1b2c3d4e5f
Revises: 2b5d4e3c1a9b
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa


revision = '8a1b2c3d4e5f'
down_revision = '2b5d4e3c1a9b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('architecture_diagrams',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('project_id', sa.String(length=40), nullable=False),
        sa.Column('semantic_id', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('layout', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('semantic_id')
    )
    with op.batch_alter_table('architecture_diagrams', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_architecture_diagrams_project_id'), ['project_id'], unique=False)

    op.create_table('architecture_nodes',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('diagram_id', sa.String(length=40), nullable=False),
        sa.Column('semantic_id', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('node_type', sa.String(length=40), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('technology', sa.String(length=200), nullable=True),
        sa.Column('environment', sa.String(length=100), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['diagram_id'], ['architecture_diagrams.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('diagram_id', 'semantic_id')
    )
    with op.batch_alter_table('architecture_nodes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_architecture_nodes_diagram_id'), ['diagram_id'], unique=False)

    op.create_table('architecture_edges',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('diagram_id', sa.String(length=40), nullable=False),
        sa.Column('semantic_id', sa.String(length=200), nullable=False),
        sa.Column('from_node_semantic_id', sa.String(length=200), nullable=False),
        sa.Column('to_node_semantic_id', sa.String(length=200), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['diagram_id'], ['architecture_diagrams.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('architecture_edges', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_architecture_edges_diagram_id'), ['diagram_id'], unique=False)


def downgrade() -> None:
    op.drop_table('architecture_edges')
    op.drop_table('architecture_nodes')
    op.drop_table('architecture_diagrams')
