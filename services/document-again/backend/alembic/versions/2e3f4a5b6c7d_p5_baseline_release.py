"""p5 release integration — baseline target release

Revision ID: 2e3f4a5b6c7d
Revises: 1d2e3f4a5b6c
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "2e3f4a5b6c7d"
down_revision = "1d2e3f4a5b6c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("baselines", sa.Column("target_release", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("baselines", "target_release")
