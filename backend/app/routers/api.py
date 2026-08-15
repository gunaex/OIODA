"""Thin HTTP routers. All rules live in app.services."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import services as svc
from .deps import actor, db_session

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Serialization helpers (explicit, no ORM leaking)
# ---------------------------------------------------------------------------


def project_out(p: m.Project) -> dict:
    return {
        "id": p.id, "key": p.key, "name": p.name, "description": p.description,
        "created_at": p.created_at.isoformat(), "created_by": p.created_by,
    }


def artifact_out(a: m.Artifact) -> dict:
    return {
        "id": a.id, "project_id": a.project_id, "type": a.type.value, "title": a.title,
        "current_draft_revision_id": a.current_draft_revision_id,
        "created_at": a.created_at.isoformat(), "created_by": a.created_by,
    }


def revision_out(r: m.ArtifactRevision, with_snapshot: bool = True) -> dict:
    out = {
        "id": r.id, "artifact_id": r.artifact_id, "revision_number": r.revision_number,
        "status": r.status.value, "based_on_revision_id": r.based_on_revision_id,
        "title": r.title, "created_at": r.created_at.isoformat(), "created_by": r.created_by,
        "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
        "confirmed_by": r.confirmed_by,
    }
    if with_snapshot:
        out["snapshot"] = r.snapshot
    return out


def baseline_out(b: m.Baseline) -> dict:
    return {
        "id": b.id, "project_id": b.project_id, "name": b.name,
        "description": b.description, "created_at": b.created_at.isoformat(),
        "created_by": b.created_by,
        "bindings": [
            {
                "artifact_id": bb.artifact_id,
                "artifact_revision_id": bb.artifact_revision_id,
                "semantic_object_id": bb.semantic_object_id,
                "semantic_object_type": bb.semantic_object_type,
            }
            for bb in b.bindings
        ],
    }


def requirement_out(r: m.Requirement) -> dict:
    return {
        "id": r.id, "project_id": r.project_id, "code": r.code, "title": r.title,
        "description": r.description, "source_type": r.source_type,
        "source_reference": r.source_reference, "status": r.status.value,
        "priority": r.priority, "created_at": r.created_at.isoformat(),
        "created_by": r.created_by,
    }


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectIn(BaseModel):
    key: str
    name: str
    description: str | None = None


@router.get("/projects")
def list_projects(db: Session = Depends(db_session)):
    return [project_out(p) for p in db.execute(select(m.Project)).scalars()]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return project_out(svc.create_project(db, **body.model_dump(), actor=actor))


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(db_session)):
    return project_out(svc.get_or_404(db, m.Project, project_id, "Project"))


# ---------------------------------------------------------------------------
# Artifacts + revisions
# ---------------------------------------------------------------------------


class ArtifactIn(BaseModel):
    project_id: str
    type: m.ArtifactType
    title: str
    snapshot: dict | None = None


@router.get("/projects/{project_id}/artifacts")
def list_artifacts(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Artifact).where(m.Artifact.project_id == project_id)
    ).scalars()
    return [artifact_out(a) for a in rows]


@router.post("/artifacts", status_code=201)
def create_artifact(body: ArtifactIn, db: Session = Depends(db_session), actor=Depends(actor)):
    a = svc.create_artifact(db, **body.model_dump(), actor=actor)
    return {**artifact_out(a), "revisions": [revision_out(r) for r in a.revisions]}


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, db: Session = Depends(db_session)):
    a = svc.get_or_404(db, m.Artifact, artifact_id, "Artifact")
    return {**artifact_out(a), "revisions": [revision_out(r, with_snapshot=False) for r in a.revisions]}


class RevisionIn(BaseModel):
    snapshot: dict | None = None
    based_on_revision_id: str | None = None
    title: str | None = None


@router.post("/artifacts/{artifact_id}/revisions", status_code=201)
def create_revision(
    artifact_id: str, body: RevisionIn, db: Session = Depends(db_session), actor=Depends(actor)
):
    rev = svc.create_revision(
        db,
        artifact_id=artifact_id,
        snapshot=body.snapshot,
        based_on_revision_id=body.based_on_revision_id,
        actor=actor,
    )
    return revision_out(rev)


@router.get("/revisions/{revision_id}")
def get_revision(revision_id: str, db: Session = Depends(db_session)):
    return revision_out(svc.get_or_404(db, m.ArtifactRevision, revision_id, "Revision"))


class SnapshotIn(BaseModel):
    snapshot: dict
    title: str | None = None


@router.put("/revisions/{revision_id}/snapshot")
def update_snapshot(revision_id: str, body: SnapshotIn, db: Session = Depends(db_session)):
    return revision_out(
        svc.update_revision_snapshot(db, revision_id, body.snapshot, body.title)
    )


@router.post("/revisions/{revision_id}/submit-for-review")
def submit_for_review(revision_id: str, db: Session = Depends(db_session)):
    return revision_out(svc.submit_for_review(db, revision_id))


@router.post("/revisions/{revision_id}/return-to-draft")
def return_to_draft(revision_id: str, db: Session = Depends(db_session)):
    return revision_out(svc.transition_revision(db, revision_id, m.RevisionStatus.DRAFT))


class ConfirmIn(BaseModel):
    comment: str | None = None
    evidence: dict | None = None


@router.post("/revisions/{revision_id}/confirm")
def confirm(
    revision_id: str, body: ConfirmIn | None = None, db: Session = Depends(db_session),
    actor=Depends(actor),
):
    body = body or ConfirmIn()
    rev, confirmation = svc.confirm_revision(
        db, revision_id, actor=actor, comment=body.comment, evidence=body.evidence
    )
    return {
        "revision": revision_out(rev),
        "confirmation": {
            "id": confirmation.id, "confirmed_by": confirmation.confirmed_by,
            "confirmed_at": confirmation.confirmed_at.isoformat(),
            "comment": confirmation.comment, "evidence": confirmation.evidence,
        },
    }


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


class BaselineIn(BaseModel):
    project_id: str
    name: str
    description: str | None = None
    artifact_revision_ids: list[str]


@router.get("/projects/{project_id}/baselines")
def list_baselines(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Baseline).where(m.Baseline.project_id == project_id)
    ).scalars()
    return [baseline_out(b) for b in rows]


@router.post("/baselines", status_code=201)
def create_baseline(body: BaselineIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return baseline_out(svc.create_baseline(db, **body.model_dump(), actor=actor))


@router.get("/baselines/{baseline_id}")
def get_baseline(baseline_id: str, db: Session = Depends(db_session)):
    return baseline_out(svc.resolve_baseline(db, baseline_id))


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


class RequirementIn(BaseModel):
    project_id: str
    title: str
    description: str | None = None
    source_type: str | None = None
    source_reference: str | None = None
    priority: str | None = None


@router.get("/projects/{project_id}/requirements")
def list_requirements(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Requirement)
        .where(m.Requirement.project_id == project_id)
        .order_by(m.Requirement.code)
    ).scalars()
    return [requirement_out(r) for r in rows]


@router.post("/requirements", status_code=201)
def create_requirement(body: RequirementIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return requirement_out(svc.create_requirement(db, **body.model_dump(), actor=actor))


@router.get("/requirements/{requirement_id}")
def get_requirement(requirement_id: str, db: Session = Depends(db_session)):
    return requirement_out(svc.get_or_404(db, m.Requirement, requirement_id, "Requirement"))


# ---------------------------------------------------------------------------
# Semantic objects + traces
# ---------------------------------------------------------------------------


class SemanticObjectIn(BaseModel):
    project_id: str
    semantic_id: str
    object_type: m.SemanticObjectType
    display_name: str
    entity_ref: str | None = None


@router.get("/projects/{project_id}/semantic-objects")
def list_semantic_objects(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.SemanticObject).where(m.SemanticObject.project_id == project_id)
    ).scalars()
    return [
        {
            "id": o.id, "semantic_id": o.semantic_id, "object_type": o.object_type.value,
            "display_name": o.display_name, "entity_ref": o.entity_ref,
        }
        for o in rows
    ]


@router.post("/semantic-objects", status_code=201)
def ensure_semantic(body: SemanticObjectIn, db: Session = Depends(db_session)):
    o = svc.ensure_semantic_object(
        db,
        project_id=body.project_id,
        semantic_id=body.semantic_id,
        object_type=body.object_type,
        display_name=body.display_name,
        entity_ref=body.entity_ref,
    )
    return {
        "id": o.id, "semantic_id": o.semantic_id, "object_type": o.object_type.value,
        "display_name": o.display_name, "entity_ref": o.entity_ref,
    }


class TraceIn(BaseModel):
    project_id: str
    source_semantic_id: str
    target_semantic_id: str
    relation_type: m.TraceRelationType
    revision_context: str | None = None


@router.get("/projects/{project_id}/traces")
def list_traces(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.TraceLink).where(m.TraceLink.project_id == project_id)
    ).scalars()
    return [
        {
            "id": t.id, "source": t.source_semantic_id, "target": t.target_semantic_id,
            "relation": t.relation_type.value, "revision_context": t.revision_context,
        }
        for t in rows
    ]


@router.post("/traces", status_code=201)
def create_trace(body: TraceIn, db: Session = Depends(db_session), actor=Depends(actor)):
    t = svc.create_trace_link(db, **body.model_dump(), actor=actor)
    return {"id": t.id, "source": t.source_semantic_id, "target": t.target_semantic_id,
            "relation": t.relation_type.value}


@router.get("/projects/{project_id}/impact/{semantic_id}")
def impact(project_id: str, semantic_id: str, db: Session = Depends(db_session)):
    return svc.impact_of(db, project_id, semantic_id)


@router.get("/projects/{project_id}/trace-graph")
def trace_graph(project_id: str, db: Session = Depends(db_session)):
    return svc.trace_graph(db, project_id)


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


class AnnotationIn(BaseModel):
    project_id: str
    anchor_object_type: str
    anchor_semantic_id: str
    content: str
    type: m.AnnotationType = m.AnnotationType.COMMENT
    artifact_revision_id: str | None = None
    canvas_x: float | None = None
    canvas_y: float | None = None
    drawing_payload: dict | None = None
    thread_id: str | None = None


def annotation_out(a: m.Annotation) -> dict:
    return {
        "id": a.id, "project_id": a.project_id, "artifact_revision_id": a.artifact_revision_id,
        "anchor_object_type": a.anchor_object_type, "anchor_semantic_id": a.anchor_semantic_id,
        "canvas_x": a.canvas_x, "canvas_y": a.canvas_y, "type": a.type.value,
        "content": a.content, "status": a.status.value, "created_by": a.created_by,
        "created_at": a.created_at.isoformat(),
    }


@router.get("/projects/{project_id}/annotations")
def list_annotations(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Annotation).where(m.Annotation.project_id == project_id)
    ).scalars()
    return [annotation_out(a) for a in rows]


@router.post("/annotations", status_code=201)
def create_annotation(body: AnnotationIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return annotation_out(svc.create_annotation(db, **body.model_dump(), actor=actor))


@router.post("/annotations/{annotation_id}/status/{status}")
def set_status(annotation_id: str, status: m.AnnotationStatus, db: Session = Depends(db_session)):
    return annotation_out(svc.set_annotation_status(db, annotation_id, status))


# ---------------------------------------------------------------------------
# Review workflow (threads, summary, timeline)
# ---------------------------------------------------------------------------


class ThreadIn(BaseModel):
    project_id: str
    title: str | None = None


@router.get("/projects/{project_id}/threads")
def list_threads(project_id: str, db: Session = Depends(db_session)):
    return svc.list_threads(db, project_id)


@router.post("/threads", status_code=201)
def create_thread(body: ThreadIn, db: Session = Depends(db_session), actor=Depends(actor)):
    t = svc.create_thread(db, project_id=body.project_id, title=body.title, actor=actor)
    return {"id": t.id, "title": t.title, "resolved": t.resolved}


@router.get("/projects/{project_id}/annotations-summary")
def annotations_summary(project_id: str, db: Session = Depends(db_session)):
    return svc.annotations_summary(db, project_id)


@router.get("/projects/{project_id}/timeline")
def timeline(project_id: str, semantic_id: str | None = None, db: Session = Depends(db_session)):
    return svc.timeline(db, project_id, semantic_id=semantic_id)


@router.get("/revisions/{revision_id}/annotations")
def revision_annotations(revision_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.Annotation).where(m.Annotation.artifact_revision_id == revision_id)
    ).scalars()
    return [annotation_out(a) for a in rows]


# ---------------------------------------------------------------------------
# Change requests
# ---------------------------------------------------------------------------


class CRIn(BaseModel):
    project_id: str
    requested_change: str
    affected_semantic_ids: list[str]
    reason: str | None = None
    requested_by: str | None = None
    target_release: str | None = None
    schedule_impact: str | None = None
    commercial_impact: str | None = None


def cr_out(cr: m.ChangeRequest) -> dict:
    return {
        "id": cr.id, "code": cr.code, "project_id": cr.project_id,
        "requested_change": cr.requested_change, "reason": cr.reason,
        "status": cr.status.value, "target_release": cr.target_release,
        "schedule_impact": cr.schedule_impact, "commercial_impact": cr.commercial_impact,
        "affected_semantic_ids": [l.semantic_id for l in cr.links],
        "created_at": cr.created_at.isoformat(), "created_by": cr.created_by,
    }


@router.get("/projects/{project_id}/change-requests")
def list_crs(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.ChangeRequest).where(m.ChangeRequest.project_id == project_id)
    ).scalars()
    return [cr_out(c) for c in rows]


@router.post("/change-requests", status_code=201)
def create_cr(body: CRIn, db: Session = Depends(db_session), actor=Depends(actor)):
    return cr_out(svc.create_change_request(db, **body.model_dump(), actor=actor))


class CRImplementIn(BaseModel):
    artifact_revision_map: dict[str, dict] | None = None


@router.post("/change-requests/{change_request_id}/implement")
def implement_cr(
    change_request_id: str, body: CRImplementIn | None, db: Session = Depends(db_session),
    actor=Depends(actor),
):
    result = svc.implement_change_request(
        db, change_request_id, artifact_revision_map=(body or CRImplementIn()).artifact_revision_map,
        actor=actor,
    )
    return {"change_request": cr_out(result["change_request"]),
            "spawned_revisions": result["spawned_revisions"]}


# ---------------------------------------------------------------------------
# Database design
# ---------------------------------------------------------------------------


class SchemaIn(BaseModel):
    project_id: str
    name: str
    semantic_id: str
    description: str | None = None


class TableIn(BaseModel):
    schema_id: str
    name: str
    semantic_id: str | None = None
    description: str | None = None


class FieldIn(BaseModel):
    table_id: str
    name: str
    data_type: str
    semantic_id: str | None = None
    length: int | None = None
    nullable: bool = False
    default: str | None = None
    primary_key: bool = False
    foreign_key: bool = False
    reference: str | None = None
    description: str | None = None
    remark: str | None = None


class RelationIn(BaseModel):
    schema_id: str
    from_field_semantic_id: str
    to_field_semantic_id: str
    relation_type: str = "MANY_TO_ONE"


@router.get("/projects/{project_id}/db-schemas")
def list_schemas(project_id: str, db: Session = Depends(db_session)):
    rows = db.execute(
        select(m.DatabaseSchema).where(m.DatabaseSchema.project_id == project_id)
    ).scalars()
    out = []
    for s in rows:
        out.append({
            "id": s.id, "semantic_id": s.semantic_id, "name": s.name,
            "description": s.description,
            "layout": s.layout or {},
            "tables": [
                {
                    "id": t.id, "semantic_id": t.semantic_id, "name": t.name,
                    "description": t.description,
                    "fields": [
                        {
                            "id": f.id, "semantic_id": f.semantic_id, "name": f.name,
                            "data_type": f.data_type, "length": f.length,
                            "nullable": f.nullable, "default": f.default,
                            "primary_key": f.primary_key, "foreign_key": f.foreign_key,
                            "reference": f.reference, "description": f.description,
                            "remark": f.remark,
                        }
                        for f in t.fields
                    ],
                }
                for t in s.tables
            ],
            "relations": [
                {
                    "id": r.id, "semantic_id": r.semantic_id,
                    "from": r.from_field_semantic_id, "to": r.to_field_semantic_id,
                    "relation_type": r.relation_type,
                }
                for r in db.execute(
                    select(m.DatabaseRelation).where(m.DatabaseRelation.schema_id == s.id)
                ).scalars()
            ],
        })
    return out


@router.post("/db-schemas", status_code=201)
def create_schema(body: SchemaIn, db: Session = Depends(db_session), actor=Depends(actor)):
    s = svc.create_schema(db, **body.model_dump(), actor=actor)
    return {"id": s.id, "semantic_id": s.semantic_id, "name": s.name}


@router.post("/db-tables", status_code=201)
def create_table(body: TableIn, db: Session = Depends(db_session)):
    t = svc.create_table(db, **body.model_dump())
    return {"id": t.id, "semantic_id": t.semantic_id, "name": t.name}


@router.post("/db-fields", status_code=201)
def create_field(body: FieldIn, db: Session = Depends(db_session)):
    f = svc.create_field(db, **body.model_dump())
    return {"id": f.id, "semantic_id": f.semantic_id, "name": f.name}


@router.post("/db-relations", status_code=201)
def create_relation(body: RelationIn, db: Session = Depends(db_session)):
    r = svc.create_relation(db, **body.model_dump())
    return {"id": r.id, "semantic_id": r.semantic_id}


# --- DB designer CRUD ---


class TablePatch(BaseModel):
    name: str


class FieldPatch(BaseModel):
    name: str | None = None
    data_type: str | None = None
    length: int | None = None
    nullable: bool | None = None
    default: str | None = None
    primary_key: bool | None = None
    foreign_key: bool | None = None
    reference: str | None = None
    description: str | None = None
    remark: str | None = None


class LayoutIn(BaseModel):
    layout: dict


def field_out(f: m.DatabaseField) -> dict:
    return {
        "id": f.id, "semantic_id": f.semantic_id, "name": f.name,
        "data_type": f.data_type, "length": f.length, "nullable": f.nullable,
        "default": f.default, "primary_key": f.primary_key, "foreign_key": f.foreign_key,
        "reference": f.reference, "description": f.description, "remark": f.remark,
    }


@router.patch("/db-tables/{table_id}")
def rename_table(table_id: str, body: TablePatch, db: Session = Depends(db_session)):
    t = svc.rename_table(db, table_id, body.name)
    return {"id": t.id, "semantic_id": t.semantic_id, "name": t.name}


@router.delete("/db-tables/{table_id}", status_code=204)
def delete_table(table_id: str, db: Session = Depends(db_session)):
    svc.delete_table(db, table_id)


@router.patch("/db-fields/{field_id}")
def update_field(field_id: str, body: FieldPatch, db: Session = Depends(db_session)):
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    f = svc.update_field(db, field_id, **changes)
    return field_out(f)


@router.delete("/db-fields/{field_id}", status_code=204)
def delete_field(field_id: str, db: Session = Depends(db_session)):
    svc.delete_field(db, field_id)


@router.delete("/db-relations/{relation_id}", status_code=204)
def delete_relation(relation_id: str, db: Session = Depends(db_session)):
    svc.delete_relation(db, relation_id)


@router.get("/db-schemas/{schema_id}/erd-layout")
def get_erd_layout(schema_id: str, db: Session = Depends(db_session)):
    return svc.get_erd_layout(db, schema_id)


@router.put("/db-schemas/{schema_id}/erd-layout")
def save_erd_layout(schema_id: str, body: LayoutIn, db: Session = Depends(db_session)):
    svc.save_erd_layout(db, schema_id, body.layout)
    return {"ok": True}


@router.get("/db-schemas/{schema_id}/design-snapshot")
def design_snapshot(schema_id: str, db: Session = Depends(db_session)):
    return svc.db_design_snapshot(db, schema_id)


@router.get("/db-schemas/{schema_id}/data-dictionary")
def data_dictionary(schema_id: str, db: Session = Depends(db_session)):
    return svc.data_dictionary(db, schema_id)


# ---------------------------------------------------------------------------
# Document workspace (rich UR/DR content)
# ---------------------------------------------------------------------------


@router.get("/revisions/{revision_id}/document")
def get_document(revision_id: str, db: Session = Depends(db_session)):
    return svc.get_document(db, revision_id)


class DocumentIn(BaseModel):
    sections: list[dict]
    title: str | None = None


@router.put("/revisions/{revision_id}/document")
def save_document(
    revision_id: str, body: DocumentIn, db: Session = Depends(db_session),
    actor=Depends(actor),
):
    revision = svc.save_document(
        db, revision_id=revision_id, sections=body.sections, title=body.title, actor=actor
    )
    return svc.get_document(db, revision.id)


# ---------------------------------------------------------------------------
# Revision compare + semantic diff
# ---------------------------------------------------------------------------


@router.get("/revisions/{a_id}/diff/{b_id}")
def revision_diff(a_id: str, b_id: str, db: Session = Depends(db_session)):
    return svc.revision_diff(db, a_id, b_id)


class SemanticDiffIn(BaseModel):
    a: dict
    b: dict


@router.post("/diff/semantic")
def semantic_diff(body: SemanticDiffIn, db: Session = Depends(db_session)):
    return svc.semantic_diff(body.a, body.b)


class SnapshotDbIn(BaseModel):
    schema_id: str


@router.post("/revisions/{revision_id}/snapshot-database")
def snapshot_database(
    revision_id: str, body: SnapshotDbIn, db: Session = Depends(db_session),
):
    svc.snapshot_database_into_revision(db, revision_id, body.schema_id)
    return {"ok": True}
