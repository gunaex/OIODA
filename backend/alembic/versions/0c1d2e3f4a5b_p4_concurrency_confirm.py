"""p4 concurrency — unique confirmation per revision

Revision ID: 0c1d2e3f4a5b
Revises: 9b0c1d2e3f4a
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0c1d2e3f4a5b"
down_revision = "9b0c1d2e3f4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite cannot ALTER a table to add a constraint; use batch mode
    # (copy-and-move) which Alembic supports for SQLite.
    with op.batch_alter_table("confirmations") as batch_op:
        batch_op.create_unique_constraint("uq_confirmations_revision", ["artifact_revision_id"])


def downgrade() -> None:
    with op.batch_alter_table("confirmations") as batch_op:
        batch_op.drop_constraint("uq_confirmations_revision", type_="unique")
