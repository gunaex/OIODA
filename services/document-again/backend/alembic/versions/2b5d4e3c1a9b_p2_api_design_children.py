"""add structured api design children and endpoint metadata

Revision ID: 2b5d4e3c1a9b
Revises: 9e4c3d2b1a0f
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa


revision = '2b5d4e3c1a9b'
down_revision = '9e4c3d2b1a0f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('api_endpoints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('authentication', sa.String(length=40), nullable=False, server_default='NONE'))

    op.create_table('api_parameters',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('endpoint_id', sa.String(length=40), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('location', sa.String(length=20), nullable=False),
        sa.Column('data_type', sa.String(length=100), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['endpoint_id'], ['api_endpoints.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_parameters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_parameters_endpoint_id'), ['endpoint_id'], unique=False)

    op.create_table('api_request_fields',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('endpoint_id', sa.String(length=40), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('data_type', sa.String(length=100), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['endpoint_id'], ['api_endpoints.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_request_fields', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_request_fields_endpoint_id'), ['endpoint_id'], unique=False)

    op.create_table('api_response_fields',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('endpoint_id', sa.String(length=40), nullable=False),
        sa.Column('status_code', sa.String(length=5), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('data_type', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['endpoint_id'], ['api_endpoints.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_response_fields', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_response_fields_endpoint_id'), ['endpoint_id'], unique=False)

    op.create_table('api_error_responses',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('endpoint_id', sa.String(length=40), nullable=False),
        sa.Column('status_code', sa.String(length=5), nullable=False),
        sa.Column('message', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['endpoint_id'], ['api_endpoints.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('api_error_responses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_error_responses_endpoint_id'), ['endpoint_id'], unique=False)


def downgrade() -> None:
    op.drop_table('api_error_responses')
    op.drop_table('api_response_fields')
    op.drop_table('api_request_fields')
    op.drop_table('api_parameters')
    with op.batch_alter_table('api_endpoints', schema=None) as batch_op:
        batch_op.drop_column('authentication')
        batch_op.drop_column('description')
