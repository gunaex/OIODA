"""p3 impact v2 change sets

Revision ID: 7f8a9b0c1d2e
Revises: 6e7f8a9b0c1d
Create Date: 2026-01-28
"""
from alembic import op
import sqlalchemy as sa

revision = "7f8a9b0c1d2e"
down_revision = "6e7f8a9b0c1d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_sets",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("actor_id", sa.String(200), nullable=True),
    )
    op.create_index("ix_change_sets_project_id", "change_sets", ["project_id"])

    op.create_table(
        "change_items",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("change_set_id", sa.String(40), sa.ForeignKey("change_sets.id"), nullable=False),
        sa.Column("semantic_id", sa.String(200), nullable=False),
        sa.Column("change_type", sa.String(20), nullable=False),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_change_items_change_set_id", "change_items", ["change_set_id"])
    op.create_index("ix_change_items_semantic_id", "change_items", ["semantic_id"])


def downgrade() -> None:
    op.drop_index("ix_change_items_semantic_id", table_name="change_items")
    op.drop_index("ix_change_items_change_set_id", table_name="change_items")
    op.drop_table("change_items")
    op.drop_index("ix_change_sets_project_id", table_name="change_sets")
    op.drop_table("change_sets")
