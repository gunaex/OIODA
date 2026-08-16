"""p3 handoffs and external references

Revision ID: 6e7f8a9b0c1d
Revises: 5d6e7f8a9b0c
Create Date: 2026-01-28
"""
from alembic import op
import sqlalchemy as sa

revision = "6e7f8a9b0c1d"
down_revision = "5d6e7f8a9b0c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_handoffs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("baseline_id", sa.String(40), sa.ForeignKey("baselines.id"), nullable=True),
        sa.Column("source_revision_id", sa.String(40), nullable=True),
        sa.Column("change_request_id", sa.String(40), nullable=True),
        sa.Column("target_service", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("external_reference", sa.String(300), nullable=True),
        sa.Column("payload_snapshot", sa.JSON, nullable=True),
        sa.Column("correlation_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_execution_handoffs_project_id", "execution_handoffs", ["project_id"])
    op.create_index("ix_execution_handoffs_correlation_id", "execution_handoffs", ["correlation_id"])

    op.create_table(
        "qa_validation_handoffs",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("baseline_id", sa.String(40), sa.ForeignKey("baselines.id"), nullable=True),
        sa.Column("requirement_ids", sa.JSON, nullable=True),
        sa.Column("semantic_object_ids", sa.JSON, nullable=True),
        sa.Column("design_revision_ids", sa.JSON, nullable=True),
        sa.Column("target_release", sa.String(60), nullable=True),
        sa.Column("target_service", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("external_reference", sa.String(300), nullable=True),
        sa.Column("payload_snapshot", sa.JSON, nullable=True),
        sa.Column("correlation_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_qa_validation_handoffs_project_id", "qa_validation_handoffs", ["project_id"])
    op.create_index("ix_qa_validation_handoffs_correlation_id", "qa_validation_handoffs", ["correlation_id"])

    op.create_table(
        "external_references",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("semantic_id", sa.String(200), nullable=False),
        sa.Column("relation_type", sa.String(40), nullable=False),
        sa.Column("service", sa.String(60), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("object_type", sa.String(60), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "service", "external_id"),
    )
    op.create_index("ix_external_references_project_id", "external_references", ["project_id"])
    op.create_index("ix_external_references_semantic_id", "external_references", ["semantic_id"])


def downgrade() -> None:
    op.drop_index("ix_external_references_semantic_id", table_name="external_references")
    op.drop_index("ix_external_references_project_id", table_name="external_references")
    op.drop_table("external_references")
    op.drop_index("ix_qa_validation_handoffs_correlation_id", table_name="qa_validation_handoffs")
    op.drop_index("ix_qa_validation_handoffs_project_id", table_name="qa_validation_handoffs")
    op.drop_table("qa_validation_handoffs")
    op.drop_index("ix_execution_handoffs_correlation_id", table_name="execution_handoffs")
    op.drop_index("ix_execution_handoffs_project_id", table_name="execution_handoffs")
    op.drop_table("execution_handoffs")
