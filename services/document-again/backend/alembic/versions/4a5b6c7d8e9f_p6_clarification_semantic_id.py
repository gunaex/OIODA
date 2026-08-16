"""p6 clarification semantic id

Revision ID: 4a5b6c7d8e9f
Revises: 3f4a5b6c7d8e
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "4a5b6c7d8e9f"
down_revision = "3f4a5b6c7d8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("clarifications") as batch_op:
        batch_op.add_column(sa.Column("semantic_id", sa.String(200), nullable=True))
        batch_op.create_unique_constraint("uq_clarifications_semantic_id", ["semantic_id"])


def downgrade() -> None:
    with op.batch_alter_table("clarifications") as batch_op:
        batch_op.drop_constraint("uq_clarifications_semantic_id", type_="unique")
        batch_op.drop_column("semantic_id")
