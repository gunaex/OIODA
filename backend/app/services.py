"""Domain services — every product-level invariant is enforced here.

Rationale for a service layer (rather than router-level CRUD): rules
like "confirmed revisions are immutable" and "baselines never
re-resolve to latest" are the product's core value. They must be
impossible to bypass from the HTTP edge.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models as m
from .models import RevisionStatus


class DomainError(Exception):
    """Rule violation the caller must see as 4xx/409."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def get_or_404(db: Session, model, id_: str, what: str):
    obj = db.get(model, id_)
    if obj is None:
        raise DomainError(f"{what} not found: {id_}", status_code=404)
    return obj


def require_editable(revision: m.ArtifactRevision) -> None:
    if revision.status != RevisionStatus.DRAFT:
        raise DomainError(
            f"Revision {revision.id} is {revision.status.value} and therefore immutable. "
            "Clone it as a new DRAFT revision to continue editing.",
        )


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


def create_project(db: Session, *, key: str, name: str, description=None, actor="local-user"):
    project = m.Project(key=key, name=name, description=description, created_by=actor)
    db.add(project)
    db.commit()
    return project


# ---------------------------------------------------------------------------
# Artifact + Revision lifecycle
# ---------------------------------------------------------------------------


def create_artifact(
    db: Session,
    *,
    project_id: str,
    type: m.ArtifactType,
    title: str,
    snapshot: dict | None = None,
    actor="local-user",
) -> m.Artifact:
    project = get_or_404(db, m.Project, project_id, "Project")
    artifact = m.Artifact(project_id=project.id, type=type, title=title, created_by=actor)
    db.add(artifact)
    db.flush()
    revision = m.ArtifactRevision(
        artifact_id=artifact.id,
        revision_number=1,
        status=RevisionStatus.DRAFT,
        snapshot=snapshot or {},
        title=title,
        created_by=actor,
    )
    db.add(revision)
    db.flush()
    artifact.current_draft_revision_id = revision.id
    db.commit()
    return artifact


def next_revision_number(db: Session, artifact_id: str) -> int:
    result = db.execute(
        select(m.ArtifactRevision.revision_number)
        .where(m.ArtifactRevision.artifact_id == artifact_id)
        .order_by(m.ArtifactRevision.revision_number.desc())
        .limit(1)
    ).scalar_one_or_none()
    return (result or 0) + 1


def create_revision(
    db: Session,
    *,
    artifact_id: str,
    snapshot: dict | None = None,
    based_on_revision_id: str | None = None,
    actor="local-user",
) -> m.ArtifactRevision:
    """Clone-as-new-revision. Confirmed history is never touched."""
    artifact = get_or_404(db, m.Artifact, artifact_id, "Artifact")
    if based_on_revision_id:
        parent = get_or_404(
            db, m.ArtifactRevision, based_on_revision_id, "Revision"
        )
        if parent.artifact_id != artifact_id:
            raise DomainError("based_on_revision belongs to a different artifact")
        base_snapshot = dict(parent.snapshot or {})
        base_title = parent.title
    else:
        latest = (
            db.execute(
                select(m.ArtifactRevision)
                .where(m.ArtifactRevision.artifact_id == artifact_id)
                .order_by(m.ArtifactRevision.revision_number.desc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        base_snapshot = dict(latest.snapshot or {}) if latest else {}
        base_title = latest.title if latest else artifact.title
        based_on_revision_id = latest.id if latest else None

    revision = m.ArtifactRevision(
        artifact_id=artifact_id,
        revision_number=next_revision_number(db, artifact_id),
        status=RevisionStatus.DRAFT,
        based_on_revision_id=based_on_revision_id,
        snapshot=snapshot if snapshot is not None else base_snapshot,
        title=base_title,
        created_by=actor,
    )
    db.add(revision)
    db.flush()
    # A new draft supersedes any previous DRAFT pointer but old drafts
    # themselves become SUPERSEDED only when a newer revision is confirmed.
    if revision.based_on and revision.based_on.status == RevisionStatus.DRAFT:
        revision.based_on.status = RevisionStatus.SUPERSEDED
    artifact.current_draft_revision_id = revision.id
    db.commit()
    return revision


def update_revision_snapshot(
    db: Session, revision_id: str, snapshot: dict, title: str | None = None
) -> m.ArtifactRevision:
    revision = get_or_404(db, m.ArtifactRevision, revision_id, "Revision")
    require_editable(revision)
    revision.snapshot = snapshot
    if title is not None:
        revision.title = title
        revision.artifact.title = title
    db.commit()
    return revision


# Allowed transitions: DRAFT→IN_REVIEW→(CONFIRMED|DRAFT), CONFIRMED→SUPERSEDED,
# and ARCHIVED from CONFIRMED/SUPERSEDED. CONFIRMED is never edited.
_ALLOWED_TRANSITIONS = {
    RevisionStatus.DRAFT: {RevisionStatus.IN_REVIEW, RevisionStatus.ARCHIVED},
    RevisionStatus.IN_REVIEW: {RevisionStatus.DRAFT, RevisionStatus.CONFIRMED, RevisionStatus.ARCHIVED},
    RevisionStatus.CONFIRMED: {RevisionStatus.SUPERSEDED, RevisionStatus.ARCHIVED},
    RevisionStatus.SUPERSEDED: {RevisionStatus.ARCHIVED},
    RevisionStatus.ARCHIVED: set(),
}


def transition_revision(db: Session, revision_id: str, to_status: RevisionStatus) -> m.ArtifactRevision:
    revision = get_or_404(db, m.ArtifactRevision, revision_id, "Revision")
    if to_status not in _ALLOWED_TRANSITIONS[revision.status]:
        raise DomainError(
            f"Illegal transition {revision.status.value} → {to_status.value}"
        )
    revision.status = to_status
    db.commit()
    return revision


def submit_for_review(db: Session, revision_id: str) -> m.ArtifactRevision:
    revision = get_or_404(db, m.ArtifactRevision, revision_id, "Revision")
    if revision.status != RevisionStatus.DRAFT:
        raise DomainError("Only DRAFT revisions can be submitted for review")
    revision.status = RevisionStatus.IN_REVIEW
    db.commit()
    return revision


def confirm_revision(
    db: Session,
    revision_id: str,
    *,
    actor="local-user",
    comment: str | None = None,
    evidence: dict | None = None,
    supersede_confirmed: bool = True,
) -> tuple[m.ArtifactRevision, m.Confirmation]:
    """Confirm = freeze. If an older CONFIRMED revision of the same artifact
    exists, it becomes SUPERSEDED (still readable, still bound in old baselines)."""
    revision = get_or_404(db, m.ArtifactRevision, revision_id, "Revision")
    if revision.status not in (RevisionStatus.IN_REVIEW, RevisionStatus.DRAFT):
        raise DomainError(
            f"Cannot confirm a revision in status {revision.status.value}"
        )
    revision.status = RevisionStatus.CONFIRMED
    revision.confirmed_at = m.utcnow()
    revision.confirmed_by = actor

    if supersede_confirmed:
        siblings = db.execute(
            select(m.ArtifactRevision).where(
                m.ArtifactRevision.artifact_id == revision.artifact_id,
                m.ArtifactRevision.id != revision.id,
                m.ArtifactRevision.status == RevisionStatus.CONFIRMED,
            )
        ).scalars().all()
        for sib in siblings:
            sib.status = RevisionStatus.SUPERSEDED

    confirmation = m.Confirmation(
        project_id=revision.artifact.project_id,
        artifact_revision_id=revision.id,
        confirmed_by=actor,
        comment=comment,
        evidence=evidence,
    )
    db.add(confirmation)
    db.commit()
    return revision, confirmation


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------


def create_baseline(
    db: Session,
    *,
    project_id: str,
    name: str,
    description: str | None = None,
    artifact_revision_ids: list[str],
    actor="local-user",
) -> m.Baseline:
    """Freeze the exact artifact→revision pairs given at creation time.

    The stored binding rows are never re-resolved afterwards — that is
    the whole point. A later v8 of a child artifact does not change a
    baseline that bound v7.
    """
    get_or_404(db, m.Project, project_id, "Project")
    if not artifact_revision_ids:
        raise DomainError("A baseline must bind at least one revision")

    seen: dict[str, m.ArtifactRevision] = {}
    for rid in artifact_revision_ids:
        rev = get_or_404(db, m.ArtifactRevision, rid, "Revision")
        if rev.status != RevisionStatus.CONFIRMED:
            raise DomainError(
                f"Revision {rid} is {rev.status.value}; only CONFIRMED revisions "
                "may be frozen into a baseline"
            )
        if rev.artifact.project_id != project_id:
            raise DomainError(f"Revision {rid} belongs to another project")
        if rev.artifact_id in seen:
            raise DomainError("Each artifact may appear at most once per baseline")
        seen[rev.artifact_id] = rev

    baseline = m.Baseline(
        project_id=project_id, name=name, description=description, created_by=actor
    )
    db.add(baseline)
    db.flush()
    for artifact_id, rev in seen.items():
        semantic_object = db.execute(
            select(m.SemanticObject).where(
                m.SemanticObject.project_id == project_id,
                m.SemanticObject.entity_ref == artifact_id,
            )
        ).scalar_one_or_none()
        db.add(
            m.BaselineBinding(
                baseline_id=baseline.id,
                artifact_id=artifact_id,
                artifact_revision_id=rev.id,
                semantic_object_id=semantic_object.semantic_id if semantic_object else None,
                semantic_object_type=(
                    semantic_object.object_type.value if semantic_object else None
                ),
            )
        )
    db.commit()
    return baseline


def resolve_baseline(db: Session, baseline_id: str) -> m.Baseline:
    baseline = get_or_404(db, m.Baseline, baseline_id, "Baseline")
    db.expire(baseline, ["bindings"])  # always read the frozen rows
    return baseline


# ---------------------------------------------------------------------------
# SemanticObject + TraceLink
# ---------------------------------------------------------------------------


def ensure_semantic_object(
    db: Session,
    *,
    project_id: str,
    semantic_id: str,
    object_type: m.SemanticObjectType,
    display_name: str,
    entity_ref: str | None = None,
) -> m.SemanticObject:
    obj = db.execute(
        select(m.SemanticObject).where(
            m.SemanticObject.project_id == project_id,
            m.SemanticObject.semantic_id == semantic_id,
        )
    ).scalar_one_or_none()
    if obj:
        if entity_ref:
            obj.entity_ref = entity_ref
        db.commit()
        return obj
    obj = m.SemanticObject(
        project_id=project_id,
        semantic_id=semantic_id,
        object_type=object_type,
        display_name=display_name,
        entity_ref=entity_ref,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        obj = db.execute(
            select(m.SemanticObject).where(
                m.SemanticObject.project_id == project_id,
                m.SemanticObject.semantic_id == semantic_id,
            )
        ).scalar_one()
    return obj


def create_trace_link(
    db: Session,
    *,
    project_id: str,
    source_semantic_id: str,
    target_semantic_id: str,
    relation_type: m.TraceRelationType,
    revision_context: str | None = None,
    actor="local-user",
) -> m.TraceLink:
    for sid in (source_semantic_id, target_semantic_id):
        exists = db.execute(
            select(m.SemanticObject.id).where(
                m.SemanticObject.project_id == project_id,
                m.SemanticObject.semantic_id == sid,
            )
        ).scalar_one_or_none()
        if not exists:
            raise DomainError(
                f"Unknown semantic object '{sid}'. Traces may only connect "
                "registered semantic objects — never pixel positions or titles.",
                status_code=422,
            )
    link = m.TraceLink(
        project_id=project_id,
        source_semantic_id=source_semantic_id,
        target_semantic_id=target_semantic_id,
        relation_type=relation_type,
        revision_context=revision_context,
        created_by=actor,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError("Trace link already exists")
    return link


def impact_of(db: Session, project_id: str, semantic_id: str) -> dict:
    """1-hop upstream/downstream impact using trace links only."""
    outgoing = db.execute(
        select(m.TraceLink).where(
            m.TraceLink.project_id == project_id,
            m.TraceLink.source_semantic_id == semantic_id,
        )
    ).scalars().all()
    incoming = db.execute(
        select(m.TraceLink).where(
            m.TraceLink.project_id == project_id,
            m.TraceLink.target_semantic_id == semantic_id,
        )
    ).scalars().all()
    return {
        "semantic_id": semantic_id,
        "downstream": [
            {"semantic_id": l.target_semantic_id, "relation": l.relation_type.value}
            for l in outgoing
        ],
        "upstream": [
            {"semantic_id": l.source_semantic_id, "relation": l.relation_type.value}
            for l in incoming
        ],
    }


# ---------------------------------------------------------------------------
# Annotation
# ---------------------------------------------------------------------------


def create_annotation(
    db: Session,
    *,
    project_id: str,
    anchor_object_type: str,
    anchor_semantic_id: str,
    content: str,
    type: m.AnnotationType = m.AnnotationType.COMMENT,
    artifact_revision_id: str | None = None,
    canvas_x: float | None = None,
    canvas_y: float | None = None,
    drawing_payload: dict | None = None,
    actor="local-user",
) -> m.Annotation:
    anchored = db.execute(
        select(m.SemanticObject.id).where(
            m.SemanticObject.project_id == project_id,
            m.SemanticObject.semantic_id == anchor_semantic_id,
        )
    ).scalar_one_or_none()
    if not anchored:
        raise DomainError(
            f"Cannot anchor annotation to unknown semantic object '{anchor_semantic_id}'. "
            "Coordinates are optional placement data, never the anchor.",
            status_code=422,
        )
    annotation = m.Annotation(
        project_id=project_id,
        artifact_revision_id=artifact_revision_id,
        anchor_object_type=anchor_object_type,
        anchor_semantic_id=anchor_semantic_id,
        canvas_x=canvas_x,
        canvas_y=canvas_y,
        type=type,
        content=content,
        drawing_payload=drawing_payload,
        created_by=actor,
    )
    db.add(annotation)
    db.commit()
    return annotation


def set_annotation_status(
    db: Session, annotation_id: str, status: m.AnnotationStatus
) -> m.Annotation:
    annotation = get_or_404(db, m.Annotation, annotation_id, "Annotation")
    valid = {s.value for s in m.AnnotationStatus}
    if status.value not in valid:
        raise DomainError("Invalid annotation status")
    annotation.status = status
    db.commit()
    return annotation


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


def next_requirement_code(db: Session, project_id: str) -> str:
    count = (
        db.execute(
            select(m.Requirement.id).where(m.Requirement.project_id == project_id)
        )
        .scalars()
        .all()
    )
    return f"REQ-{len(count) + 1:04d}"


def create_requirement(
    db: Session,
    *,
    project_id: str,
    title: str,
    description=None,
    source_type=None,
    source_reference=None,
    priority=None,
    actor="local-user",
) -> m.Requirement:
    code = next_requirement_code(db, project_id)
    requirement = m.Requirement(
        project_id=project_id,
        code=code,
        title=title,
        description=description,
        source_type=source_type,
        source_reference=source_reference,
        priority=priority,
        created_by=actor,
    )
    db.add(requirement)
    db.flush()
    ensure_semantic_object(
        db,
        project_id=project_id,
        semantic_id=code,
        object_type=m.SemanticObjectType.REQUIREMENT,
        display_name=title,
        entity_ref=requirement.id,
    )
    db.commit()
    return requirement


# ---------------------------------------------------------------------------
# ChangeRequest
# ---------------------------------------------------------------------------


def next_cr_code(db: Session, project_id: str) -> str:
    count = (
        db.execute(
            select(m.ChangeRequest.id).where(m.ChangeRequest.project_id == project_id)
        )
        .scalars()
        .all()
    )
    return f"CR-{len(count) + 1:04d}"


def create_change_request(
    db: Session,
    *,
    project_id: str,
    requested_change: str,
    affected_semantic_ids: list[str],
    reason=None,
    requested_by="local-user",
    target_release=None,
    schedule_impact=None,
    commercial_impact=None,
    actor="local-user",
) -> m.ChangeRequest:
    for sid in affected_semantic_ids:
        exists = db.execute(
            select(m.SemanticObject.id).where(
                m.SemanticObject.project_id == project_id,
                m.SemanticObject.semantic_id == sid,
            )
        ).scalar_one_or_none()
        if not exists:
            raise DomainError(
                f"Change request references unknown semantic object '{sid}'",
                status_code=422,
            )
    cr = m.ChangeRequest(
        project_id=project_id,
        code=next_cr_code(db, project_id),
        requested_by=requested_by,
        reason=reason,
        requested_change=requested_change,
        target_release=target_release,
        schedule_impact=schedule_impact,
        commercial_impact=commercial_impact,
        created_by=actor,
    )
    db.add(cr)
    db.flush()
    for sid in affected_semantic_ids:
        db.add(m.ChangeRequestLink(change_request_id=cr.id, semantic_id=sid))
    db.commit()
    return cr


def implement_change_request(
    db: Session,
    change_request_id: str,
    *,
    artifact_revision_map: dict[str, str] | None = None,
    actor="local-user",
) -> dict:
    """Mark a CR IMPLEMENTED by pointing it at the new revision(s) it spawned.

    The CR itself never mutates old confirmed baselines — it only
    references the freshly created draft/confirmed revisions.
    """
    cr = get_or_404(db, m.ChangeRequest, change_request_id, "ChangeRequest")
    if cr.status == m.ChangeRequestStatus.IMPLEMENTED:
        raise DomainError("Change request already implemented")
    spawned: list[dict] = []
    for artifact_id, snapshot in (artifact_revision_map or {}).items():
        rev = create_revision(
            db, artifact_id=artifact_id, snapshot=snapshot, actor=actor
        )
        ensure_semantic_object(
            db,
            project_id=cr.project_id,
            semantic_id=f"rev_{rev.id}",
            object_type=m.SemanticObjectType.DOCUMENT_SECTION,
            display_name=f"{cr.code} revision {rev.revision_number}",
            entity_ref=rev.id,
        )
        db.add(
            m.TraceLink(
                project_id=cr.project_id,
                source_semantic_id=cr.code,
                target_semantic_id=f"rev_{rev.id}",
                relation_type=m.TraceRelationType.GENERATED_FROM,
                created_by=actor,
            )
        )
        spawned.append({"artifact_id": artifact_id, "revision_id": rev.id, "revision_number": rev.revision_number})
    cr.status = m.ChangeRequestStatus.IMPLEMENTED
    db.commit()
    return {"change_request": cr, "spawned_revisions": spawned}


# ---------------------------------------------------------------------------
# Database design (structured model; diagram is a view over it)
# ---------------------------------------------------------------------------


def create_schema(
    db: Session, *, project_id: str, name: str, semantic_id: str, description=None, actor="local-user"
) -> m.DatabaseSchema:
    schema = m.DatabaseSchema(
        project_id=project_id, name=name, semantic_id=semantic_id, description=description,
        created_by=actor,
    )
    db.add(schema)
    db.flush()
    ensure_semantic_object(
        db,
        project_id=project_id,
        semantic_id=semantic_id,
        object_type=m.SemanticObjectType.DB_SCHEMA,
        display_name=name,
        entity_ref=schema.id,
    )
    db.commit()
    return schema


def create_table(
    db: Session, *, schema_id: str, name: str, semantic_id: str | None = None, description=None
) -> m.DatabaseTable:
    schema = get_or_404(db, m.DatabaseSchema, schema_id, "Schema")
    semantic_id = semantic_id or f"tbl_{name}"
    table = m.DatabaseTable(
        schema_id=schema_id, semantic_id=semantic_id, name=name, description=description
    )
    db.add(table)
    db.flush()
    ensure_semantic_object(
        db,
        project_id=schema.project_id,
        semantic_id=semantic_id,
        object_type=m.SemanticObjectType.DB_TABLE,
        display_name=name,
        entity_ref=table.id,
    )
    db.commit()
    return table


def create_field(
    db: Session,
    *,
    table_id: str,
    name: str,
    data_type: str,
    semantic_id: str | None = None,
    length=None,
    nullable=False,
    default=None,
    primary_key=False,
    foreign_key=False,
    reference=None,
    description=None,
    remark=None,
) -> m.DatabaseField:
    table = get_or_404(db, m.DatabaseTable, table_id, "Table")
    semantic_id = semantic_id or f"fld_{table.name}_{name}"
    position = (
        db.execute(
            select(m.DatabaseField.id).where(m.DatabaseField.table_id == table_id)
        )
        .scalars()
        .all()
    )
    field = m.DatabaseField(
        table_id=table_id,
        semantic_id=semantic_id,
        name=name,
        data_type=data_type,
        length=length,
        nullable=nullable,
        default=default,
        primary_key=primary_key,
        foreign_key=foreign_key,
        reference=reference,
        description=description,
        remark=remark,
        position=len(position),
    )
    db.add(field)
    db.flush()
    ensure_semantic_object(
        db,
        project_id=table.schema.project_id,
        semantic_id=semantic_id,
        object_type=m.SemanticObjectType.DB_FIELD,
        display_name=f"{table.name}.{name}",
        entity_ref=field.id,
    )
    db.commit()
    return field


def create_relation(
    db: Session,
    *,
    schema_id: str,
    from_field_semantic_id: str,
    to_field_semantic_id: str,
    relation_type="MANY_TO_ONE",
) -> m.DatabaseRelation:
    for sid in (from_field_semantic_id, to_field_semantic_id):
        exists = db.execute(
            select(m.DatabaseField.id).where(m.DatabaseField.semantic_id == sid)
        ).scalar_one_or_none()
        if not exists:
            raise DomainError(f"Unknown field semantic id '{sid}'", status_code=422)
    rel = m.DatabaseRelation(
        schema_id=schema_id,
        semantic_id=f"rel_{from_field_semantic_id}__{to_field_semantic_id}",
        from_field_semantic_id=from_field_semantic_id,
        to_field_semantic_id=to_field_semantic_id,
        relation_type=relation_type,
    )
    db.add(rel)
    db.flush()
    schema = get_or_404(db, m.DatabaseSchema, schema_id, "Schema")
    ensure_semantic_object(
        db,
        project_id=schema.project_id,
        semantic_id=rel.semantic_id,
        object_type=m.SemanticObjectType.DB_RELATION,
        display_name=f"{from_field_semantic_id} → {to_field_semantic_id}",
        entity_ref=rel.id,
    )
    db.commit()
    return rel


def data_dictionary(db: Session, schema_id: str) -> list[dict]:
    """A pure view over the structured model — no separate truth stored."""
    schema = get_or_404(db, m.DatabaseSchema, schema_id, "Schema")
    result = []
    for table in schema.tables:
        for f in table.fields:
            result.append(
                {
                    "table": table.name,
                    "table_semantic_id": table.semantic_id,
                    "field": f.name,
                    "field_semantic_id": f.semantic_id,
                    "data_type": f.data_type,
                    "length": f.length,
                    "nullable": f.nullable,
                    "default": f.default,
                    "primary_key": f.primary_key,
                    "foreign_key": f.foreign_key,
                    "reference": f.reference,
                    "description": f.description,
                    "remark": f.remark,
                }
            )
    return result
