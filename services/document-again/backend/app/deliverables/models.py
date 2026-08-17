"""R17 — Deliverable Instance model.

A deliverable instance is a PROJECT-scoped occurrence of a reusable standard.
The standard definition (code + version) is pinned at instance creation and
does not mutate when the registry is later bumped.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    import uuid

    return f"{prefix}_{uuid.uuid4().hex[:20]}"


class DeliverableInstance(Base):
    __tablename__ = "deliverable_instances"
    __table_args__ = (UniqueConstraint("project_id", "standard_code"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _new_id("dli"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    standard_code: Mapped[str] = mapped_column(String(40), index=True)
    standard_version: Mapped[str] = mapped_column(String(20), default="1.0")

    # human-facing document id, e.g. TCM-MIG-RUN-001 (generated from project key)
    document_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # applicability resolution (default / rule / ai / override / final)
    applicability: Mapped[str] = mapped_column(String(20), default="CONDITIONAL")
    applicability_reason: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    applicability_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # lifecycle (MISSING/DRAFT/INTERNAL_REVIEW/CUSTOMER_REVIEW/APPROVED/BASELINED/SUPERSEDED/ARCHIVED)
    lifecycle_status: Mapped[str] = mapped_column(String(20), default="MISSING")
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    approvers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # revision / baseline
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 0.1 … 1.0
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    baseline_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # provenance
    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_authorities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "standard_code": self.standard_code,
            "standard_version": self.standard_version,
            "document_id": self.document_id,
            "applicability": self.applicability,
            "applicability_reason": self.applicability_reason or [],
            "ai_recommendation": self.ai_recommendation,
            "applicability_override": self.applicability_override,
            "override_by": self.override_by,
            "lifecycle_status": self.lifecycle_status,
            "owner": self.owner,
            "reviewers": self.reviewers or [],
            "approvers": self.approvers or [],
            "version": self.version,
            "revision_id": self.revision_id,
            "baseline_id": self.baseline_id,
            "source_authorities": self.source_authorities or [],
            "stale": self.stale,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
