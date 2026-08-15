"""Domain services — every product-level invariant is enforced here.

Rationale for a service layer (rather than router-level CRUD): rules
like "confirmed revisions are immutable" and "baselines never
re-resolve to latest" are the product's core value. They must be
impossible to bypass from the HTTP edge.
"""
from __future__ import annotations

from collections import Counter

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
    thread_id: str | None = None,
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
    if thread_id is not None:
        thread = get_or_404(db, m.CommentThread, thread_id, "CommentThread")
        if thread.project_id != project_id:
            raise DomainError("Thread belongs to a different project")
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
        thread_id=thread_id,
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


# ---------------------------------------------------------------------------
# Document workspace (rich UR/DR content, section semantic identity)
# ---------------------------------------------------------------------------

_DOC_BLOCK_KINDS = {"heading", "paragraph", "bullet_list", "numbered_list", "table", "code"}


def _normalise_sections(artifact_id: str, sections: list[dict]) -> list[dict]:
    """Assign a stable section id where one is missing.

    Section identity lives inside the snapshot and is preserved by the
    editor across edits of the same draft. The id only changes if a
    section is deleted and a new one is added — it is never reused.
    """
    out: list[dict] = []
    used: set[str] = set()
    counter = 0
    for sec in sections:
        sec = dict(sec)
        sid = sec.get("id") or f"docsec_{artifact_id}_{counter}"
        while sid in used:
            counter += 1
            sid = f"docsec_{artifact_id}_{counter}"
        used.add(sid)
        sec["id"] = sid
        blocks = []
        for blk in sec.get("blocks", []):
            blk = dict(blk)
            blk.setdefault("kind", "paragraph")
            blocks.append(blk)
        sec["blocks"] = blocks
        out.append(sec)
        counter += 1
    return out


def save_document(
    db: Session,
    *,
    revision_id: str,
    sections: list[dict],
    title: str | None = None,
    actor: str = "local-user",
) -> m.ArtifactRevision:
    """Persist rich document content for a DRAFT revision.

    Each section is registered as a DOCUMENT_SECTION semantic object so
    comments and traces can bind to it — never to a DOM position.
    Confirmed revisions are immutable and are rejected here.
    """
    revision = get_or_404(db, m.ArtifactRevision, revision_id, "Revision")
    require_editable(revision)
    artifact = revision.artifact
    sections = _normalise_sections(artifact.id, sections)
    for sec in sections:
        ensure_semantic_object(
            db,
            project_id=artifact.project_id,
            semantic_id=sec["id"],
            object_type=m.SemanticObjectType.DOCUMENT_SECTION,
            display_name=sec.get("heading") or "Untitled section",
            entity_ref=artifact.id,
        )
    snapshot = dict(revision.snapshot or {})
    snapshot["sections"] = sections
    revision.snapshot = snapshot
    if title is not None:
        revision.title = title
        artifact.title = title
    db.commit()
    return revision


def get_document(db: Session, revision_id: str) -> dict:
    """Return the revision plus its structured sections."""
    revision = get_or_404(db, m.ArtifactRevision, revision_id, "Revision")
    snapshot = revision.snapshot or {}
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        # Legacy P0 snapshots (e.g. {"sections": [{"id", "note"}]}) become
        # minimal paragraphs so nothing is lost on first edit.
        legacy = snapshot.get("sections") or snapshot.get("content") or []
        sections = [
            {
                "id": f"docsec_{revision.artifact_id}_{i}",
                "heading": sec.get("id") or sec.get("title") or f"Section {i + 1}",
                "blocks": [
                    {"kind": "paragraph", "text": sec.get("note") or sec.get("text") or ""}
                ],
            }
            for i, sec in enumerate(legacy)
        ] if isinstance(legacy, list) else []
    return {
        "revision_id": revision.id,
        "artifact_id": revision.artifact_id,
        "revision_number": revision.revision_number,
        "status": revision.status.value,
        "title": revision.title,
        "artifact_type": revision.artifact.type.value,
        "based_on_revision_id": revision.based_on_revision_id,
        "created_by": revision.created_by,
        "confirmed_by": revision.confirmed_by,
        "confirmed_at": revision.confirmed_at.isoformat() if revision.confirmed_at else None,
        "editable": revision.editable,
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# Review workflow (threads, summaries, activity timeline)
# ---------------------------------------------------------------------------


def create_thread(
    db: Session,
    *,
    project_id: str,
    title: str | None = None,
    actor: str = "local-user",
) -> m.CommentThread:
    get_or_404(db, m.Project, project_id, "Project")
    thread = m.CommentThread(project_id=project_id, title=title)
    db.add(thread)
    db.commit()
    return thread


def list_threads(db: Session, project_id: str) -> list[dict]:
    threads = db.execute(
        select(m.CommentThread)
        .where(m.CommentThread.project_id == project_id)
        .order_by(m.CommentThread.created_at.desc())
    ).scalars().all()
    out = []
    for t in threads:
        anns = db.execute(
            select(m.Annotation)
            .where(m.Annotation.thread_id == t.id)
            .order_by(m.Annotation.created_at)
        ).scalars().all()
        out.append({
            "id": t.id,
            "title": t.title,
            "resolved": t.resolved,
            "open_count": sum(1 for a in anns if a.status != m.AnnotationStatus.RESOLVED),
            "total": len(anns),
            "created_at": t.created_at.isoformat(),
            "annotations": [
                {
                    "id": a.id,
                    "anchor_semantic_id": a.anchor_semantic_id,
                    "type": a.type.value,
                    "status": a.status.value,
                    "content": a.content,
                    "created_by": a.created_by,
                    "created_at": a.created_at.isoformat(),
                }
                for a in anns
            ],
        })
    return out


def annotations_summary(db: Session, project_id: str) -> dict:
    anns = db.execute(
        select(m.Annotation).where(m.Annotation.project_id == project_id)
    ).scalars().all()
    by_status = Counter(a.status.value for a in anns)
    by_type = Counter(a.type.value for a in anns)
    by_anchor = Counter(a.anchor_semantic_id for a in anns)
    return {
        "total": len(anns),
        "open": sum(n for s, n in by_status.items() if s != "RESOLVED"),
        "resolved": by_status.get("RESOLVED", 0),
        "by_status": dict(by_status),
        "by_type": dict(by_type),
        "by_anchor": dict(by_anchor),
    }


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def timeline(db: Session, project_id: str, semantic_id: str | None = None) -> list[dict]:
    """Deterministic activity timeline, derived from real records.

    No separate activity table: events are reconstructed from revisions,
    confirmations, annotations, baselines and change requests.
    """
    events: list[dict] = []

    revisions = db.execute(
        select(m.ArtifactRevision)
        .join(m.Artifact, m.ArtifactRevision.artifact_id == m.Artifact.id)
        .where(m.Artifact.project_id == project_id)
    ).scalars().all()
    for r in revisions:
        events.append({
            "at": _iso(r.created_at), "kind": "revision_created",
            "actor": r.created_by, "label": f"{r.artifact.title} r{r.revision_number}",
            "revision_id": r.id, "semantic_id": None,
        })
        if r.confirmed_at:
            events.append({
                "at": _iso(r.confirmed_at), "kind": "revision_confirmed",
                "actor": r.confirmed_by, "label": f"{r.artifact.title} r{r.revision_number}",
                "revision_id": r.id, "semantic_id": None,
            })

    confirmations = db.execute(
        select(m.Confirmation)
        .where(m.Confirmation.project_id == project_id)
    ).scalars().all()
    for c in confirmations:
        events.append({
            "at": _iso(c.confirmed_at), "kind": "confirmation",
            "actor": c.confirmed_by, "label": c.comment or "confirmed",
            "revision_id": c.artifact_revision_id, "semantic_id": None,
        })

    annotations = db.execute(
        select(m.Annotation)
        .where(m.Annotation.project_id == project_id)
    ).scalars().all()
    for a in annotations:
        events.append({
            "at": _iso(a.created_at), "kind": f"annotation_{a.type.value.lower()}",
            "actor": a.created_by, "label": a.content[:120],
            "revision_id": a.artifact_revision_id, "semantic_id": a.anchor_semantic_id,
        })

    baselines = db.execute(
        select(m.Baseline).where(m.Baseline.project_id == project_id)
    ).scalars().all()
    for b in baselines:
        events.append({
            "at": _iso(b.created_at), "kind": "baseline_created",
            "actor": b.created_by, "label": b.name,
            "revision_id": None, "semantic_id": None,
        })

    crs = db.execute(
        select(m.ChangeRequest).where(m.ChangeRequest.project_id == project_id)
    ).scalars().all()
    for cr in crs:
        events.append({
            "at": _iso(cr.created_at), "kind": "change_request_created",
            "actor": cr.created_by, "label": f"{cr.code} — {cr.requested_change[:120]}",
            "revision_id": None, "semantic_id": cr.code,
        })

    if semantic_id:
        events = [
            e for e in events
            if e["semantic_id"] == semantic_id or e["revision_id"] is not None
        ]

    events.sort(key=lambda e: e["at"] or "")
    return events
