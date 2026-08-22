"""R18.2 per-user project review checkpoint.

Revision ID: 6c7d8e9f0a1b
Revises: 5b6c7d8e9f0a
"""
from alembic import op
import sqlalchemy as sa

revision = "6c7d8e9f0a1b"
down_revision = "5b6c7d8e9f0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("project_review_checkpoints",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(200), nullable=False, index=True),
        sa.Column("reviewed_through", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("reviewed_evidence_cursors", sa.JSON(), nullable=False),
        sa.Column("briefing_cursor", sa.String(64), nullable=False),
        sa.Column("review_source", sa.String(40), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_review_checkpoint_user"))


def downgrade() -> None:
    op.drop_table("project_review_checkpoints")
