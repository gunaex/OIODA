"""p4 audit events

Revision ID: 9b0c1d2e3f4a
Revises: 8a9b0c1d2e3f
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "9b0c1d2e3f4a"
down_revision = "8a9b0c1d2e3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("tenant_id", sa.String(200), nullable=True),
        sa.Column("project_id", sa.String(40), nullable=True),
        sa.Column("actor_id", sa.String(200), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("object_type", sa.String(60), nullable=True),
        sa.Column("object_id", sa.String(200), nullable=True),
        sa.Column("revision_context", sa.String(200), nullable=True),
        sa.Column("baseline_id", sa.String(40), nullable=True),
        sa.Column("correlation_id", sa.String(200), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for col in ("tenant_id", "project_id", "actor_id", "action", "object_id", "baseline_id", "correlation_id"):
        op.create_index(f"ix_audit_events_{col}", "audit_events", [col])


def downgrade() -> None:
    for col in ("tenant_id", "project_id", "actor_id", "action", "object_id", "baseline_id", "correlation_id"):
        op.drop_index(f"ix_audit_events_{col}", table_name="audit_events")
    op.drop_table("audit_events")
