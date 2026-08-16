"""p4 tenant isolation

Revision ID: 8a9b0c1d2e3f
Revises: 7f8a9b0c1d2e
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "8a9b0c1d2e3f"
down_revision = "7f8a9b0c1d2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("tenant_id", sa.String(200), nullable=True))
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_tenant_id", table_name="projects")
    op.drop_column("projects", "tenant_id")
