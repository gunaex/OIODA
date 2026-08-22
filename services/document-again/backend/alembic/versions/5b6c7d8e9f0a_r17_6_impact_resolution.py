"""R17.6 impact resolution projection and immutable history.

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
"""
from alembic import op
import sqlalchemy as sa

revision = "5b6c7d8e9f0a"
down_revision = "4a5b6c7d8e9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("impact_resolutions",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("change_id", sa.String(80), nullable=True, index=True),
        sa.Column("impact_candidate_id", sa.String(80), nullable=True, index=True),
        sa.Column("confirmation_id", sa.String(40), sa.ForeignKey("impact_confirmations.id"), nullable=False, unique=True, index=True),
        sa.Column("latest_action_route_id", sa.String(40), sa.ForeignKey("impact_action_routes.id"), nullable=True),
        sa.Column("owner_result_ref", sa.JSON(), nullable=True),
        sa.Column("resolution_state", sa.String(32), nullable=False, index=True),
        sa.Column("resolution_reason", sa.Text(), nullable=False),
        sa.Column("evaluation_rule_id", sa.String(80), nullable=False),
        sa.Column("evaluation_rule_version", sa.String(20), nullable=False),
        sa.Column("pre_action_truth_ref", sa.JSON(), nullable=True),
        sa.Column("post_action_truth_ref", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False, index=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("impact_resolution_events",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("resolution_id", sa.String(40), sa.ForeignKey("impact_resolutions.id"), nullable=False, index=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("event_type", sa.String(60), nullable=False, index=True),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.String(200), nullable=False),
        sa.Column("transition_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True))


def downgrade() -> None:
    op.drop_table("impact_resolution_events")
    op.drop_table("impact_resolutions")
