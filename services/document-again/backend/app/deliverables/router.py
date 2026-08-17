"""R17 — Deliverable framework HTTP router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import services as svc
from ..models import Project
from ..routers.deps import actor, actor_ctx, db_session
from . import service as dsvc
from . import xlsx as dxlsx
from .layouts import BRAND_PROFILES, layout_registry
from .standards import all_standards, standards_by_domain
from .taxonomy import (
    APPLICABILITY_STATES,
    CATEGORIES,
    LIFECYCLE_STATES,
    LIFECYCLE_TRANSITIONS,
    PROJECT_ATTRIBUTES,
    PROJECT_TYPES,
    WORKSTREAMS,
)

router = APIRouter(prefix="/api")


def _project(db: Session, project_id: str) -> Project:
    return svc.guard_project(db, project_id)


# ── Registries / taxonomies ────────────────────────────────────────────────
@router.get("/deliverable-taxonomy")
def deliverable_taxonomy():
    return {
        "project_types": PROJECT_TYPES,
        "workstreams": WORKSTREAMS,
        "categories": CATEGORIES,
        "applicability_states": APPLICABILITY_STATES,
        "lifecycle_states": LIFECYCLE_STATES,
        "lifecycle_transitions": LIFECYCLE_TRANSITIONS,
        "project_attributes": PROJECT_ATTRIBUTES,
    }


@router.get("/deliverable-standards")
def deliverable_standards(domain: str | None = None):
    by_domain = standards_by_domain()
    if domain:
        return by_domain.get(domain.upper(), [])
    return {
        "count": len(all_standards()),
        "by_domain": {d: len(v) for d, v in by_domain.items()},
        "standards": all_standards(),
    }


@router.get("/deliverable-layouts")
def deliverable_layouts():
    return layout_registry()


@router.get("/brand-profiles")
def brand_profiles():
    return list(BRAND_PROFILES.keys())


# ── Project profile ────────────────────────────────────────────────────────
class ProfileIn(BaseModel):
    primary_type: str | None = None
    workstreams: list[str] | None = None
    attributes: dict | None = None
    ai_recommendation: dict | None = None
    confirmed: bool = False


@router.get("/projects/{project_id}/deliverable-profile")
def get_profile(project_id: str, db: Session = Depends(db_session)):
    return dsvc.get_profile(db, _project(db, project_id))


@router.put("/projects/{project_id}/deliverable-profile")
def put_profile(project_id: str, body: ProfileIn, db: Session = Depends(db_session),
                actx=Depends(actor_ctx)):
    return dsvc.set_profile(
        db, _project(db, project_id),
        {
            "primary_type": body.primary_type,
            "workstreams": body.workstreams or [],
            "attributes": body.attributes or {},
            "ai_recommendation": body.ai_recommendation,
        },
        actor=actx.name, confirmed=body.confirmed,
    )


# ── Matrix / gaps ───────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/deliverable-matrix")
def get_matrix(project_id: str, db: Session = Depends(db_session)):
    return dsvc.get_matrix(db, _project(db, project_id))


@router.post("/projects/{project_id}/deliverable-matrix/generate")
def generate_matrix(project_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return dsvc.generate_matrix(db, _project(db, project_id), actor=actx.name, persist=True)


@router.get("/projects/{project_id}/deliverable-gaps")
def get_gaps(project_id: str, db: Session = Depends(db_session)):
    return dsvc.detect_gaps(db, _project(db, project_id))


# ── Instances ───────────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/deliverables/{standard_code}")
def get_instance(project_id: str, standard_code: str, db: Session = Depends(db_session)):
    inst = dsvc.get_instance(db, project_id, standard_code)
    if not inst:
        return {"project_id": project_id, "standard_code": standard_code, "instance": None}
    return {"project_id": project_id, "standard_code": standard_code, "instance": inst.to_dict()}


class TransitionIn(BaseModel):
    target: str
    version: str | None = None
    owner: str | None = None
    human: bool = False


@router.post("/projects/{project_id}/deliverables/{standard_code}/transition")
def transition(project_id: str, standard_code: str, body: TransitionIn,
               db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return dsvc.transition_instance(
        db, project_id, standard_code, body.target,
        actor=actx.name, human=body.human, version=body.version, owner=body.owner,
    )


class ApplicabilityIn(BaseModel):
    applicability: str


@router.post("/projects/{project_id}/deliverables/{standard_code}/applicability")
def override_applicability(project_id: str, standard_code: str, body: ApplicabilityIn,
                           db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return dsvc.override_applicability(
        db, project_id, standard_code, body.applicability, actor=actx.name,
    )


# ── Export ──────────────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/exports/{mode}")
def export_workbook(project_id: str, mode: str, brand: str = "GEA_STANDARD",
                    db: Session = Depends(db_session)):
    project = _project(db, project_id)
    try:
        content = dxlsx.build_workbook(db, project, mode.upper(), brand)
    except ValueError:
        return Response(content='{"detail":"unknown workbook mode"}', status_code=404,
                        media_type="application/json")
    filename = f"{project.key}-{mode.upper()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
