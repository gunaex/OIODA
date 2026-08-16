"""p5 handoff lifecycle — last_error + conductor relay

Revision ID: 1d2e3f4a5b6c
Revises: 0c1d2e3f4a5b
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "1d2e3f4a5b6c"
down_revision = "0c1d2e3f4a5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution_handoffs", sa.Column("last_error", sa.Text, nullable=True))
    op.add_column("qa_validation_handoffs", sa.Column("last_error", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("qa_validation_handoffs", "last_error")
    op.drop_column("execution_handoffs", "last_error")
