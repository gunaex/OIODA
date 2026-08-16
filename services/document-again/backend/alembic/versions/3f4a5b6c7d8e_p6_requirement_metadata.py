"""p6 requirement metadata

Revision ID: 3f4a5b6c7d8e
Revises: 2e3f4a5b6c7d
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "3f4a5b6c7d8e"
down_revision = "2e3f4a5b6c7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("requirements", sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("requirements", "metadata")
