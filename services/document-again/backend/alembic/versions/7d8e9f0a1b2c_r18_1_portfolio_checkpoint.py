"""R18.1 portfolio review checkpoint.

Revision ID: 7d8e9f0a1b2c
Revises: 6c7d8e9f0a1b
"""
from alembic import op
import sqlalchemy as sa
revision="7d8e9f0a1b2c"; down_revision="6c7d8e9f0a1b"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("portfolio_review_checkpoints",
        sa.Column("id",sa.String(40),primary_key=True), sa.Column("user_id",sa.String(200),nullable=False,index=True),
        sa.Column("scope_key",sa.String(80),nullable=False), sa.Column("project_cutoffs",sa.JSON(),nullable=False),
        sa.Column("project_evidence_cursors",sa.JSON(),nullable=False), sa.Column("included_project_ids",sa.JSON(),nullable=False),
        sa.Column("portfolio_cursor",sa.String(64),nullable=False), sa.Column("acknowledged_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("user_id","scope_key",name="uq_portfolio_review_checkpoint_user_scope"))

def downgrade(): op.drop_table("portfolio_review_checkpoints")
