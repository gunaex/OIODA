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
    Integer,
    String,
    Text,
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


# ────────────────────────────────────────────────────────────────────────────
# R17.1 — Human Deliverables (the user-facing layer over internal standards)
# ────────────────────────────────────────────────────────────────────────────
class HumanDeliverableInstance(Base):
    """A generated instance of a Human Deliverable (HD-*).

    Generation is ON DEMAND only: a row exists only after a human confirms
    "Generate". No instances are created at project creation. A document may
    have multiple rows across versions; the head row (highest created_at) is
    the current one. Historical rows are immutable.
    """

    __tablename__ = "human_deliverable_instances"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _new_id("hd"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    human_code: Mapped[str] = mapped_column(String(40), index=True)  # HD-01 … HD-OPS-01
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[int] = mapped_column(default=1)  # 1 controlled / 2 working / 3 register
    level_name: Mapped[str] = mapped_column(String(20), default="CONTROLLED")

    applicability: Mapped[str] = mapped_column(String(20), default="CONDITIONAL")
    applicability_reason: Mapped[list | None] = mapped_column(JSON, nullable=True)

    document_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 0.1 … 1.0

    # lifecycle (NOT_GENERATED is implied by absence of a row; rows exist only
    # once generated, so lifecycle starts at DRAFT)
    lifecycle_status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    # readiness computed at precheck time (READY / READY_WITH_GAPS / NOT_READY / BLOCKED / NOT_DUE)
    readiness: Mapped[str] = mapped_column(String(20), default="NOT_READY")
    required_by: Mapped[str | None] = mapped_column(String(40), nullable=True)  # gate code

    # role model
    owner_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reviewer_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    approver_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    signatory_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fyi_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    signoff_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # generation provenance (mandatory)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)  # email
    generated_by_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    precheck_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    readiness_at_generation: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # content fingerprint + source snapshot (immutable once approved/baselined)
    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # freshness + material change
    freshness: Mapped[str] = mapped_column(String(20), default="UNKNOWN")  # CURRENT/STALE/UNKNOWN
    material_change: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    stale: Mapped[bool] = mapped_column(Boolean, default=False)

    # revision chain
    baseline_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "human_code": self.human_code,
            "name": self.name,
            "level": self.level,
            "level_name": self.level_name,
            "applicability": self.applicability,
            "applicability_reason": self.applicability_reason or [],
            "document_id": self.document_id,
            "version": self.version,
            "lifecycle_status": self.lifecycle_status,
            "readiness": self.readiness,
            "required_by": self.required_by,
            "owner_role": self.owner_role,
            "reviewer_roles": self.reviewer_roles or [],
            "approver_roles": self.approver_roles or [],
            "signatory_roles": self.signatory_roles or [],
            "fyi_roles": self.fyi_roles or [],
            "signoff_policy": self.signoff_policy or {},
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "generated_by": self.generated_by,
            "generated_by_id": self.generated_by_id,
            "precheck_id": self.precheck_id,
            "readiness_at_generation": self.readiness_at_generation or {},
            "snapshot_hash": self.snapshot_hash,
            "mapping_version": self.mapping_version,
            "template_version": self.template_version,
            "freshness": self.freshness,
            "material_change": self.material_change,
            "stale": self.stale,
            "baseline_id": self.baseline_id,
            "revision_id": self.revision_id,
            "supersedes_id": self.supersedes_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DeliverableSignoff(Base):
    """Version-specific sign-off. Applies ONLY to the exact version/content
    identified by document_id + document_version + snapshot_hash. Content
    changes never inherit a previous signature."""

    __tablename__ = "deliverable_signoffs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _new_id("sgn"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    human_code: Mapped[str] = mapped_column(String(40), index=True)
    instance_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    document_id: Mapped[str] = mapped_column(String(120), index=True)
    document_version: Mapped[str] = mapped_column(String(20))
    baseline_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    signoff_type: Mapped[str] = mapped_column(String(24))  # APPROVE/ACCEPT/ACKNOWLEDGE/REJECT
    decision: Mapped[str] = mapped_column(String(28))  # incl. ACCEPTED_WITH_EXCEPTIONS

    # R17.1.1 — evidence class + purpose. TEST evidence never qualifies a
    # production gate; INTERNAL must never impersonate customer acceptance.
    evidence_class: Mapped[str | None] = mapped_column(String(20), nullable=True)  # TEST/INTERNAL/CUSTOMER/FORMAL_EXTERNAL
    purpose: Mapped[str | None] = mapped_column(String(24), nullable=True)  # REVIEW/APPROVAL/ACKNOWLEDGEMENT/ACCEPTANCE/SIGN_OFF

    signer_user_id: Mapped[str] = mapped_column(String(120))
    signer_name: Mapped[str] = mapped_column(String(200))
    signer_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    signer_organization: Mapped[str | None] = mapped_column(String(200), nullable=True)

    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_exceptions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_snapshot_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    auth_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_event_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_dict(self) -> dict:
        return {
            "signoff_id": self.id,
            "project_id": self.project_id,
            "human_code": self.human_code,
            "instance_id": self.instance_id,
            "document_id": self.document_id,
            "document_version": self.document_version,
            "baseline_id": self.baseline_id,
            "document_hash": self.document_hash,
            "snapshot_hash": self.snapshot_hash,
            "signoff_type": self.signoff_type,
            "decision": self.decision,
            "evidence_class": self.evidence_class,
            "purpose": self.purpose,
            "signer_user_id": self.signer_user_id,
            "signer_name": self.signer_name,
            "signer_role": self.signer_role,
            "signer_organization": self.signer_organization,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "comment": self.comment,
            "known_exceptions": self.known_exceptions or [],
            "source_snapshot_id": self.source_snapshot_id,
            "auth_context": self.auth_context or {},
            "audit_event_id": self.audit_event_id,
        }


class GateResolution(Base):
    """A human decision about a governance gate that is NOT acceptance:

    - PROCEED_WITH_RISK  → the project knowingly proceeds without the gate's
      qualifying evidence (recorded so the risk is not silently lost)
    - WAIVED             → a company-policy exception/waiver
    - NOT_APPLICABLE     → the gate does not apply to this project

    None of these is sign-off/acceptance; they preserve the human decision and
    its reason as evidence.
    """

    __tablename__ = "gate_resolutions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _new_id("rsk"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    gate_id: Mapped[str] = mapped_column(String(40), index=True)
    document_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    human_code: Mapped[str | None] = mapped_column(String(40), nullable=True)

    resolution_type: Mapped[str] = mapped_column(String(24))  # PROCEED_WITH_RISK / WAIVED / NOT_APPLICABLE
    severity: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)

    actor_user_id: Mapped[str] = mapped_column(String(120))
    actor_name: Mapped[str] = mapped_column(String(200))
    actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "risk_override_id": self.id,
            "id": self.id,
            "project_id": self.project_id,
            "gate_id": self.gate_id,
            "document_id": self.document_id,
            "human_code": self.human_code,
            "resolution_type": self.resolution_type,
            "severity": self.severity,
            "reason": self.reason,
            "scope": self.scope,
            "actor_user_id": self.actor_user_id,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "comment": self.comment,
        }


class DeliverableAuditEvent(Base):
    """Deterministic audit trail for every critical deliverable action."""

    __tablename__ = "deliverable_audit_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _new_id("aud"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    object_type: Mapped[str] = mapped_column(String(40))  # HUMAN_DELIVERABLE / SIGNOFF / GATE
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    actor_user_id: Mapped[str] = mapped_column(String(120))
    actor_name: Mapped[str] = mapped_column(String(200))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "action": self.action,
            "actor_user_id": self.actor_user_id,
            "actor_name": self.actor_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "before_state": self.before_state or {},
            "after_state": self.after_state or {},
            "reason": self.reason,
            "request_id": self.request_id,
        }


class ImpactConfirmation(Base):
    """Immutable human review of one relationship in one evidence context.

    Rows are history, not owner truth. The effective decision is the newest
    row for a relationship/evidence context; the idempotency key prevents an
    identical human request from producing duplicate evidence or audit spam.
    """

    __tablename__ = "impact_confirmations"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: _new_id("icf"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    relationship_id: Mapped[str] = mapped_column(String(80), index=True)
    impact_candidate_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    relationship_class_at_review: Mapped[str] = mapped_column(String(24))
    relationship_snapshot: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(20), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[str] = mapped_column(String(200), index=True)
    actor_name: Mapped[str] = mapped_column(String(200))
    actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actor_org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_hash: Mapped[str] = mapped_column(String(64), index=True)
    relationship_version: Mapped[str] = mapped_column(String(40), default="impact_relationships/v1")
    change_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    def to_dict(self, *, current_evidence_hash: str | None = None) -> dict:
        stale = bool(current_evidence_hash and current_evidence_hash != self.evidence_hash)
        effective = "STALE" if stale else ("HUMAN_CONFIRMED" if self.decision == "CONFIRMED" else self.decision)
        return {
            "contract_version": "impact_confirmation/v1", "confirmation_id": self.id,
            "project_id": self.project_id, "relationship_id": self.relationship_id,
            "impact_candidate_id": self.impact_candidate_id,
            "relationship_class_at_review": self.relationship_class_at_review,
            "origin_relationship": self.relationship_snapshot, "decision": self.decision,
            "human_review_status": "STALE" if stale else self.decision,
            "effective_context": effective, "reason": self.reason,
            "actor_user_id": self.actor_user_id, "actor_name": self.actor_name,
            "actor_role": self.actor_role, "actor_org": self.actor_org,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "evidence_hash": self.evidence_hash, "relationship_version": self.relationship_version,
            "change_id": self.change_id, "evidence_refs": self.evidence_refs or [],
            "stale": stale,
            "authority_note": "Human confirmation is project context, not owner-service truth or customer acceptance.",
        }
