"""Canonical domain model for Document Again.

Two ID families (see docs/ARCHITECTURE.md):

1. Opaque entity IDs (``prj_…``, ``art_…``, ``rev_…``) — internal
   primary keys, stable, never reused.
2. Canonical semantic IDs (``REQ-0042``, ``tbl_x``, ``fld_x_y``,
   ``flow_x``, ``api_x``) — the identity used by traces, annotations
   and baselines. They survive document/layout changes.

The revision snapshot + baseline binding tables are the heart of the
product: a confirmed revision is immutable and a baseline freezes the
exact artifact→revision pairs that existed at confirmation time.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    import uuid

    return f"{prefix}_{uuid.uuid4().hex[:20]}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ArtifactType(str, enum.Enum):
    REQUIREMENT_REGISTER = "REQUIREMENT_REGISTER"
    UR = "UR"
    DR = "DR"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    ER_DIAGRAM = "ER_DIAGRAM"
    DATA_DICTIONARY = "DATA_DICTIONARY"
    PROCESS_FLOW = "PROCESS_FLOW"
    ARCHITECTURE = "ARCHITECTURE"
    API_DESIGN = "API_DESIGN"
    WHITEBOARD = "WHITEBOARD"
    NOTE = "NOTE"
    CHANGE_REQUEST = "CHANGE_REQUEST"
    DECISION = "DECISION"


class RevisionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    CONFIRMED = "CONFIRMED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class SemanticObjectType(str, enum.Enum):
    REQUIREMENT = "REQUIREMENT"
    DOCUMENT_SECTION = "DOCUMENT_SECTION"
    DB_SCHEMA = "DB_SCHEMA"
    DB_TABLE = "DB_TABLE"
    DB_FIELD = "DB_FIELD"
    DB_RELATION = "DB_RELATION"
    PROCESS_FLOW = "PROCESS_FLOW"
    PROCESS_STEP = "PROCESS_STEP"
    API_ENDPOINT = "API_ENDPOINT"
    ARCHITECTURE_NODE = "ARCHITECTURE_NODE"
    SCREEN = "SCREEN"
    DECISION = "DECISION"
    ASSUMPTION = "ASSUMPTION"
    CLARIFICATION = "CLARIFICATION"


class TraceRelationType(str, enum.Enum):
    DERIVED_FROM = "DERIVED_FROM"
    IMPLEMENTS = "IMPLEMENTS"
    DESIGNED_BY = "DESIGNED_BY"
    VALIDATED_BY = "VALIDATED_BY"
    AFFECTS = "AFFECTS"
    REFERENCES = "REFERENCES"
    SUPERSEDES = "SUPERSEDES"
    GENERATED_FROM = "GENERATED_FROM"
    CONFIRMED_BY = "CONFIRMED_BY"


class AnnotationType(str, enum.Enum):
    COMMENT = "COMMENT"
    QUESTION = "QUESTION"
    CLARIFICATION = "CLARIFICATION"
    DECISION = "DECISION"
    ASSUMPTION = "ASSUMPTION"
    ISSUE = "ISSUE"
    CHANGE_REQUEST = "CHANGE_REQUEST"


class AnnotationStatus(str, enum.Enum):
    OPEN = "OPEN"
    REPLIED = "REPLIED"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"


class RequirementStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    CONFIRMED = "CONFIRMED"
    SUPERSEDED = "SUPERSEDED"


class ChangeRequestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    IMPACT_ANALYZED = "IMPACT_ANALYZED"
    UNDER_HUMAN_REVIEW = "UNDER_HUMAN_REVIEW"
    INTERNAL_REVIEW_COMPLETE = "INTERNAL_REVIEW_COMPLETE"
    ACCEPTED = "ACCEPTED"
    IMPLEMENTATION_PLANNED = "IMPLEMENTATION_PLANNED"
    IMPLEMENTED = "IMPLEMENTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    CLOSED = "CLOSED"


class ImpactReviewState(str, enum.Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    REVIEWED = "REVIEWED"


class SuggestionStatus(str, enum.Enum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    AI_REVIEWED = "AI_REVIEWED"
    PROPOSED_UPDATE = "PROPOSED_UPDATE"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
    NEEDS_FOLLOW_UP = "NEEDS_FOLLOW_UP"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("prj"))
    key: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "DA"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    project_meta: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)
    # R16 project lifecycle authority (Document Again owns the lifecycle state).
    lifecycle_state: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE|ARCHIVED|DELETE_REQUESTED|DELETED
    cloned_from_project_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cloned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cloned_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clone_policy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="project")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="project")


class Suggestion(Base):
    """A grounded, auditable OIDA concern/question. AI observes and suggests;
    the human always decides. A suggestion never mutates confirmed truth on its
    own — accepting it only drafts a project-memory record (clarification /
    assumption) that flows through the normal review/impact workflow."""

    __tablename__ = "suggestions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("sug"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True)  # requirement|design|pm|qa|infra|commercial
    related_object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    type: Mapped[str | None] = mapped_column(String(40), nullable=True)  # CLARIFICATION_REQUIRED|MISSING_INFORMATION|...
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # HIGH|MEDIUM|LOW
    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus), default=SuggestionStatus.OPEN
    )
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # Customer / owner answer and its interpretation (never auto-applied).
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_source: Mapped[str | None] = mapped_column(String(40), nullable=True)  # CUSTOMER|PROJECT_OWNER|ARCHITECT|PM|QA|INFRA|OTHER
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    interpretation_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # HIGH|MEDIUM|LOW
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_update: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)  # ACCEPTED|REJECTED
    consultation: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # provider runs + aggregation snapshot
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Consultation(Base):
    """R15 Multi-Agent Council consultation record. Stores the context snapshot
    used for the independent runs (reproducibility + stale detection), the
    provider run cards, the deterministic aggregation, and human review. It is
    a consultation record — it never writes to any authority service."""

    __tablename__ = "consultations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("con"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    task_type: Mapped[str] = mapped_column(String(60), default="GENERAL_REVIEW")
    role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    runs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    aggregation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    human_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Artifact + Revision (generic document/design container)
# ---------------------------------------------------------------------------


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("art"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[ArtifactType] = mapped_column(Enum(ArtifactType))
    title: Mapped[str] = mapped_column(String(300))
    current_draft_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_revisions.id", use_alter=True, name="fk_artifact_current_draft"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

    project: Mapped[Project] = relationship(back_populates="artifacts")
    revisions: Mapped[list["ArtifactRevision"]] = relationship(
        back_populates="artifact",
        foreign_keys="ArtifactRevision.artifact_id",
        order_by="ArtifactRevision.revision_number",
    )


class ArtifactRevision(Base):
    """The unit of confirmation. Snapshots are frozen once confirmed."""

    __tablename__ = "artifact_revisions"
    __table_args__ = (UniqueConstraint("artifact_id", "revision_number"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rev"))
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[RevisionStatus] = mapped_column(
        Enum(RevisionStatus), default=RevisionStatus.DRAFT
    )
    based_on_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_revisions.id"), nullable=True
    )
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # frozen content payload
    title: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # stable Account Again subject id

    artifact: Mapped[Artifact] = relationship(
        back_populates="revisions", foreign_keys=[artifact_id]
    )
    based_on: Mapped["ArtifactRevision | None"] = relationship(
        remote_side=[id], foreign_keys=[based_on_revision_id]
    )

    @property
    def editable(self) -> bool:
        return self.status == RevisionStatus.DRAFT


# ---------------------------------------------------------------------------
# Baseline — frozen artifact→revision bindings
# ---------------------------------------------------------------------------


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("bsl"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_release: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    bindings: Mapped[list["BaselineBinding"]] = relationship(
        back_populates="baseline", cascade="all, delete-orphan"
    )


class BaselineBinding(Base):
    """One frozen artifact→revision pair inside a baseline. Never re-resolved."""

    __tablename__ = "baseline_bindings"
    __table_args__ = (UniqueConstraint("baseline_id", "artifact_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("bbl"))
    baseline_id: Mapped[str] = mapped_column(ForeignKey("baselines.id"), index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"))
    artifact_revision_id: Mapped[str] = mapped_column(ForeignKey("artifact_revisions.id"))
    semantic_object_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    semantic_object_type: Mapped[str | None] = mapped_column(String(60), nullable=True)

    baseline: Mapped[Baseline] = relationship(back_populates="bindings")


# ---------------------------------------------------------------------------
# Requirement — canonical, independent of generated documents
# ---------------------------------------------------------------------------


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("req"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))  # canonical REQ-0042
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus), default=RequirementStatus.DRAFT
    )
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

    project: Mapped[Project] = relationship(back_populates="requirements")
    revisions: Mapped[list["RequirementRevision"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="RequirementRevision.revision_number",
    )


class RequirementRevision(Base):
    """Immutable versioned history of a requirement. Confirmed revisions are
    never edited in place — a new DRAFT revision is created instead."""

    __tablename__ = "requirement_revisions"
    __table_args__ = (UniqueConstraint("requirement_id", "revision_number"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rqrev"))
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[RequirementStatus] = mapped_column(
        Enum(RequirementStatus), default=RequirementStatus.DRAFT
    )
    based_on_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    requirement: Mapped[Requirement] = relationship(back_populates="revisions")


class RequirementChange(Base):
    """A controlled edit lifecycle: draft → impact → regenerate → review →
    confirm → baseline. Historical truth and audit data live here."""

    __tablename__ = "requirement_changes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("chg"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id"), index=True)
    from_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")  # DRAFT | IMPACT_READY | REGENERATED | REVIEWED | CONFIRMED | CANCELLED
    impact_json: Mapped[dict | None] = mapped_column("impact", JSON, nullable=True)
    generated_revision_ids: Mapped[list] = mapped_column(JSON, default=list)
    baseline_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# SemanticObject + TraceLink — stable identity layer
# ---------------------------------------------------------------------------


class SemanticObject(Base):
    __tablename__ = "semantic_objects"
    __table_args__ = (UniqueConstraint("project_id", "semantic_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("sem"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))  # e.g. REQ-0042, tbl_x
    object_type: Mapped[SemanticObjectType] = mapped_column(Enum(SemanticObjectType))
    display_name: Mapped[str] = mapped_column(String(300))
    entity_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)  # opaque row id
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")


class TraceLink(Base):
    __tablename__ = "trace_links"
    __table_args__ = (
        UniqueConstraint("project_id", "source_semantic_id", "target_semantic_id", "relation_type"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("trc"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_semantic_id: Mapped[str] = mapped_column(String(200), index=True)
    target_semantic_id: Mapped[str] = mapped_column(String(200), index=True)
    relation_type: Mapped[TraceRelationType] = mapped_column(Enum(TraceRelationType))
    revision_context: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Annotation + CommentThread
# ---------------------------------------------------------------------------


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ann"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("artifact_revisions.id"), nullable=True, index=True
    )
    anchor_object_type: Mapped[str] = mapped_column(String(60))  # DOCUMENT_SECTION, DB_TABLE…
    anchor_semantic_id: Mapped[str] = mapped_column(String(200), index=True)
    canvas_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    canvas_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    type: Mapped[AnnotationType] = mapped_column(Enum(AnnotationType), default=AnnotationType.COMMENT)
    content: Mapped[str] = mapped_column(Text)
    drawing_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[AnnotationStatus] = mapped_column(
        Enum(AnnotationStatus), default=AnnotationStatus.OPEN
    )
    thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("comment_threads.id"), nullable=True, index=True
    )
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    thread: Mapped["CommentThread | None"] = relationship(back_populates="annotations")


class CommentThread(Base):
    __tablename__ = "comment_threads"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("thr"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    annotations: Mapped[list[Annotation]] = relationship(back_populates="thread")


# ---------------------------------------------------------------------------
# Review / Confirmation
# ---------------------------------------------------------------------------


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rvw"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_revision_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_revisions.id"), index=True
    )
    reviewer: Mapped[str] = mapped_column(String(100), default="local-user")
    verdict: Mapped[str] = mapped_column(String(20))  # APPROVE / CHANGES_REQUESTED
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Confirmation(Base):
    __tablename__ = "confirmations"
    __table_args__ = (UniqueConstraint("artifact_revision_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cnf"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_revision_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_revisions.id"), index=True
    )
    confirmed_by: Mapped[str] = mapped_column(String(100), default="local-user")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)


# ---------------------------------------------------------------------------
# ChangeRequest
# ---------------------------------------------------------------------------


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cr"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # CR-0001
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(100), default="local-user")
    requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_change: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        Enum(ChangeRequestStatus), default=ChangeRequestStatus.DRAFT
    )
    target_release: Mapped[str | None] = mapped_column(String(60), nullable=True)
    schedule_impact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    commercial_impact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    links: Mapped[list["ChangeRequestLink"]] = relationship(
        back_populates="change_request", cascade="all, delete-orphan"
    )


class ChangeRequestLink(Base):
    __tablename__ = "change_request_links"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("crl"))
    change_request_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), index=True)  # affected object
    link_type: Mapped[str] = mapped_column(String(40), default="AFFECTS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    change_request: Mapped[ChangeRequest] = relationship(back_populates="links")


class ChangeRequestImpact(Base):
    """Commercial/scope impact of a Change Request — kept separate from the CR
    row so the impact model can evolve without migrating confirmed CR history.
    Effort/timeline/commercial values are only ever what a human entered or an
    approved estimator supplied; unknowns stay explicit, never zero."""

    __tablename__ = "change_request_impacts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cri"))
    change_request_id: Mapped[str] = mapped_column(ForeignKey("change_requests.id"), index=True)
    classification: Mapped[str | None] = mapped_column(String(40), nullable=True)  # CLARIFICATION | CORRECTION | REQUIREMENT_CHANGE | SCOPE_EXPANSION | CHANGE_REQUEST
    function_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {added:[], modified:[], removed:[], unaffected:[]}
    effort_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {status, total_md, by_role:[{role, effort, unit, basis, confidence}], history:[]}
    timeline_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {status, extension_days, proposed_completion, confidence, activities:[]}
    technical_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {affected:[], unaffected:[], unknown:[]}
    qa_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {new_scenarios:[], regression:[], evidence:"PRESERVED", effort_status}
    infra_impact: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {new:[], modified:[], unchanged:[], note}
    commercial_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # NO_ADDITIONAL_COST | ADDITIONAL_COST_REQUIRED | ESTIMATION_REQUIRED | PROPOSED | CUSTOMER_REVIEW | APPROVED | REJECTED
    pricing_basis: Mapped[str | None] = mapped_column(String(300), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # HIGH | MEDIUM | LOW | UNKNOWN
    customer_approval: Mapped[str | None] = mapped_column(String(20), nullable=True)  # APPROVED | REJECTED | PENDING
    approval_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {approved_by, approved_at, reference, note, amount}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ImpactAnalysis(Base):
    """A point-in-time snapshot of an impact analysis, so a future user can
    answer "why did OIDA say this was the impact at that time?".

    ``result_json`` holds the full enriched analysis (known/potential/unknown,
    confidence, coverage, per-item reasons and paths, human review decisions).
    ``trace_fingerprint`` is a hash of the trace graph + baseline used, so a
    later re-read can mark the snapshot STALE without trusting memory."""

    __tablename__ = "impact_analyses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ian"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # change_request | requirement_change
    target_id: Mapped[str] = mapped_column(String(40), index=True)
    baseline_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    baseline_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # HIGH|MEDIUM|LOW|UNKNOWN
    coverage_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # FULL|PARTIAL|NOT_MEASURABLE
    trace_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)
    stale_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    review_state: Mapped[ImpactReviewState] = mapped_column(
        Enum(ImpactReviewState), default=ImpactReviewState.NOT_REVIEWED
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# ---------------------------------------------------------------------------
# Database design model (structured; diagram is a view over this)
# ---------------------------------------------------------------------------


class DatabaseSchema(Base):
    __tablename__ = "database_schemas"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("dbs"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), unique=True)  # schema key
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)  # ERD node positions only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

    tables: Mapped[list["DatabaseTable"]] = relationship(
        back_populates="schema", cascade="all, delete-orphan"
    )


class DatabaseTable(Base):
    __tablename__ = "database_tables"
    __table_args__ = (UniqueConstraint("schema_id", "semantic_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("tbl"))
    schema_id: Mapped[str] = mapped_column(ForeignKey("database_schemas.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))  # tbl_approval_history
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    schema: Mapped[DatabaseSchema] = relationship(back_populates="tables")
    fields: Mapped[list["DatabaseField"]] = relationship(
        back_populates="table", cascade="all, delete-orphan", order_by="DatabaseField.position"
    )


class DatabaseField(Base):
    __tablename__ = "database_fields"
    __table_args__ = (
        UniqueConstraint("table_id", "semantic_id"),
        Index("ix_db_fields_table", "table_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("fld"))
    table_id: Mapped[str] = mapped_column(ForeignKey("database_tables.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))  # fld_<table>_<field>
    name: Mapped[str] = mapped_column(String(200))
    data_type: Mapped[str] = mapped_column(String(100))
    length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nullable: Mapped[bool] = mapped_column(Boolean, default=False)
    default: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    foreign_key: Mapped[bool] = mapped_column(Boolean, default=False)
    reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    table: Mapped[DatabaseTable] = relationship(back_populates="fields")


class DatabaseRelation(Base):
    __tablename__ = "database_relations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rel"))
    schema_id: Mapped[str] = mapped_column(ForeignKey("database_schemas.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))
    from_field_semantic_id: Mapped[str] = mapped_column(String(200))
    to_field_semantic_id: Mapped[str] = mapped_column(String(200))
    relation_type: Mapped[str] = mapped_column(String(30), default="MANY_TO_ONE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Process flow / API design (lightweight structured models for P0)
# ---------------------------------------------------------------------------


class ProcessFlow(Base):
    __tablename__ = "process_flows"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("flw"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)  # flow node positions only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    steps: Mapped[list["ProcessStep"]] = relationship(
        back_populates="flow", cascade="all, delete-orphan", order_by="ProcessStep.position"
    )


class ProcessStep(Base):
    __tablename__ = "process_steps"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("stp"))
    flow_id: Mapped[str] = mapped_column(ForeignKey("process_flows.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    step_type: Mapped[str] = mapped_column(String(40), default="TASK")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    flow: Mapped[ProcessFlow] = relationship(back_populates="steps")


class ProcessTransition(Base):
    """Explicit structured transition between two process steps."""

    __tablename__ = "process_transitions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("trs"))
    flow_id: Mapped[str] = mapped_column(ForeignKey("process_flows.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))
    from_step_semantic_id: Mapped[str] = mapped_column(String(200))
    to_step_semantic_id: Mapped[str] = mapped_column(String(200))
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class APIEndpoint(Base):
    __tablename__ = "api_endpoints"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("api"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), unique=True)  # api_order_approve
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    authentication: Mapped[str] = mapped_column(String(40), default="NONE")
    request_spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    parameters: Mapped[list["ApiParameter"]] = relationship(back_populates="endpoint", cascade="all, delete-orphan")
    request_fields: Mapped[list["ApiRequestField"]] = relationship(back_populates="endpoint", cascade="all, delete-orphan")
    response_fields: Mapped[list["ApiResponseField"]] = relationship(back_populates="endpoint", cascade="all, delete-orphan")
    error_responses: Mapped[list["ApiErrorResponse"]] = relationship(back_populates="endpoint", cascade="all, delete-orphan")


class ApiParameter(Base):
    __tablename__ = "api_parameters"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("prm"))
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("api_endpoints.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(20), default="query")  # query|path|header|body
    data_type: Mapped[str] = mapped_column(String(100), default="string")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    endpoint: Mapped[APIEndpoint] = relationship(back_populates="parameters")


class ApiRequestField(Base):
    __tablename__ = "api_request_fields"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rqf"))
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("api_endpoints.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    data_type: Mapped[str] = mapped_column(String(100), default="string")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    endpoint: Mapped[APIEndpoint] = relationship(back_populates="request_fields")


class ApiResponseField(Base):
    __tablename__ = "api_response_fields"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rsf"))
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("api_endpoints.id"), index=True)
    status_code: Mapped[str] = mapped_column(String(5), default="200")
    name: Mapped[str] = mapped_column(String(200))
    data_type: Mapped[str] = mapped_column(String(100), default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    endpoint: Mapped[APIEndpoint] = relationship(back_populates="response_fields")


class ApiErrorResponse(Base):
    __tablename__ = "api_error_responses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("apierr"))
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("api_endpoints.id"), index=True)
    status_code: Mapped[str] = mapped_column(String(5))
    message: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    endpoint: Mapped[APIEndpoint] = relationship(back_populates="error_responses")


# ---------------------------------------------------------------------------
# Architecture design workspace (structured; diagram is a view)
# ---------------------------------------------------------------------------


class ArchitectureDiagram(Base):
    __tablename__ = "architecture_diagrams"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("arch"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    nodes: Mapped[list["ArchitectureNode"]] = relationship(back_populates="diagram", cascade="all, delete-orphan")
    edges: Mapped[list["ArchitectureEdge"]] = relationship(back_populates="diagram", cascade="all, delete-orphan")


class ArchitectureNode(Base):
    __tablename__ = "architecture_nodes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("anod"))
    diagram_id: Mapped[str] = mapped_column(ForeignKey("architecture_diagrams.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    node_type: Mapped[str] = mapped_column(String(40), default="SERVICE")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technology: Mapped[str | None] = mapped_column(String(200), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    diagram: Mapped[ArchitectureDiagram] = relationship(back_populates="nodes")


class ArchitectureEdge(Base):
    __tablename__ = "architecture_edges"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("aedge"))
    diagram_id: Mapped[str] = mapped_column(ForeignKey("architecture_diagrams.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200))
    from_node_semantic_id: Mapped[str] = mapped_column(String(200))
    to_node_semantic_id: Mapped[str] = mapped_column(String(200))
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    diagram: Mapped[ArchitectureDiagram] = relationship(back_populates="edges")


# ---------------------------------------------------------------------------
# Decision / Assumption / Clarification / Release
# ---------------------------------------------------------------------------


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("dec"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), unique=True)  # DEC-0007
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String(100), default="local-user")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supersedes_semantic_id: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Assumption(Base):
    __tablename__ = "assumptions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("asm"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), unique=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")


class Clarification(Base):
    __tablename__ = "clarifications"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("clr"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    asked_by: Mapped[str] = mapped_column(String(100), default="local-user")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("rel_"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[str] = mapped_column(String(60))
    baseline_id: Mapped[str | None] = mapped_column(ForeignKey("baselines.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActorIdentity(Base):
    """Resolved actor (Account Again subject) seen by Document Again.

    Records the stable identity + display name + tenant for audit; it is
    a cache of the Account Again identity, never a replacement for it.
    """

    __tablename__ = "actor_identities"

    actor_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    tenant_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="LOCAL")  # ACCOUNT_AGAIN | LOCAL
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EcosystemEvent(Base):
    """Append-only ecosystem event record (provenance, never mutated)."""

    __tablename__ = "ecosystem_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("evt"))
    event_type: Mapped[str] = mapped_column(String(60))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_service: Mapped[str] = mapped_column(String(60), default="document-again")
    source_object_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_revision: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload_version: Mapped[str] = mapped_column(String(20), default="1.0")
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    """Durable delivery state for an ecosystem event (DB-backed outbox).

    Delivery is idempotent: (event_id, target_service) is unique, so the
    same event is never enqueued twice for the same downstream service.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("event_id", "target_service"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("obx"))
    event_id: Mapped[str] = mapped_column(ForeignKey("ecosystem_events.id"), index=True)
    target_service: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|SENT|ACKNOWLEDGED|FAILED
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExecutionHandoff(Base):
    """First-class handoff of a confirmed design baseline to PM Again.

    Document Again remains the design authority; PM Again is the execution
    authority. Only immutable references (baseline/revision/semantic ids)
    are sent — never a mutable copy of execution state.
    """

    __tablename__ = "execution_handoffs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("pmh"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[str | None] = mapped_column(ForeignKey("baselines.id"), nullable=True)
    source_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    change_request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_service: Mapped[str] = mapped_column(String(60), default="pm-again")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT|READY|SENT|ACKNOWLEDGED|FAILED|CANCELLED
    external_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class QAValidationHandoff(Base):
    """First-class validation handoff of exact baseline context to QA Again.

    QA Again remains the verification authority; Document Again stores only
    references to QA test cases / runs / results.
    """

    __tablename__ = "qa_validation_handoffs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("qah"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[str | None] = mapped_column(ForeignKey("baselines.id"), nullable=True)
    requirement_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # list[str]
    semantic_object_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    design_revision_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    target_release: Mapped[str | None] = mapped_column(String(60), nullable=True)
    target_service: Mapped[str] = mapped_column(String(60), default="qa-again")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    external_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalReference(Base):
    """A revision-correct external reference into another AGAIN service.

    Links an internal semantic object to an external object (PM task, QA
    test case, …) without overloading semantic ids with foreign ids.
    """

    __tablename__ = "external_references"
    __table_args__ = (UniqueConstraint("project_id", "service", "external_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ext"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), index=True)  # internal semantic object
    relation_type: Mapped[str] = mapped_column(String(40), default="TRACKED_BY")
    service: Mapped[str] = mapped_column(String(60))
    external_id: Mapped[str] = mapped_column(String(200))
    object_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChangeSet(Base):
    """A named, reviewable batch of change intents for impact analysis v2."""

    __tablename__ = "change_sets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cs"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ChangeItem(Base):
    """One intended change to one semantic object inside a ChangeSet."""

    __tablename__ = "change_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ci"))
    change_set_id: Mapped[str] = mapped_column(ForeignKey("change_sets.id"), index=True)
    semantic_id: Mapped[str] = mapped_column(String(200), index=True)
    change_type: Mapped[str] = mapped_column(String(20), default="MODIFIED")  # MODIFIED|ADDED|REMOVED|RENAMED
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    """Immutable audit event for important actions. Never editable; not the
    same thing as user-facing comments/annotations (those remain editable
    workspace objects)."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("aud"))
    tenant_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    object_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    revision_context: Mapped[str | None] = mapped_column(String(200), nullable=True)
    baseline_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
