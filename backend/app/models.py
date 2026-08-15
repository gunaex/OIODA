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
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
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
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    IMPLEMENTED = "IMPLEMENTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("prj"))
    key: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "DA"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="project")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="project")


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

    project: Mapped[Project] = relationship(back_populates="requirements")


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

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cnf"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_revision_id: Mapped[str] = mapped_column(
        ForeignKey("artifact_revisions.id"), index=True
    )
    confirmed_by: Mapped[str] = mapped_column(String(100), default="local-user")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
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
    requested_by: Mapped[str] = mapped_column(String(100), default="local-user")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_change: Mapped[str] = mapped_column(Text)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        Enum(ChangeRequestStatus), default=ChangeRequestStatus.OPEN
    )
    target_release: Mapped[str | None] = mapped_column(String(60), nullable=True)
    schedule_impact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    commercial_impact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(String(100), default="local-user")

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
