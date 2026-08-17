"""R17.1 — Human Deliverable HTTP router.

User-facing endpoints over the human deliverable model. All mutations require
an authenticated ecosystem identity (actor_ctx); AI never signs or approves.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import services as svc
from ..models import Project
from ..routers.deps import actor_ctx, db_session
from . import catalog as cat
from . import human as hsvc
from .standards import BY_NAME

router = APIRouter(prefix="/api")


def _project(db: Session, project_id: str) -> Project:
    return svc.guard_project(db, project_id)


# ── Catalog (small, human-facing) ───────────────────────────────────────────
@router.get("/human-deliverable-catalog")
def human_deliverable_catalog():
    return {
        "levels": cat.LEVELS,
        "roles": cat.ROLES,
        "signoff_gates": cat.SIGN_OFF_GATES,
        "signoff_modes": cat.SIGNOFF_MODES,
        "signoff_decisions": cat.SIGNOFF_DECISIONS,
        "deliverables": [
            {
                "code": h["code"], "name": h["name"], "level": h["level"],
                "level_name": cat.LEVELS[h["level"]], "purpose": h["purpose"],
                "required_by": h["required_by"], "owner_role": h["owner_role"],
                "reviewer_roles": h["reviewer_roles"], "approver_roles": h["approver_roles"],
                "signatory_roles": h["signatory_roles"], "fyi_roles": h["fyi_roles"],
                "signoff_policy": h["signoff_policy"],
                "sections": [{"title": s["title"], "kind": s["kind"],
                              "modules": len(s["standards"])} for s in h["sections"]],
            }
            for h in cat.HUMAN_DELIVERABLES.values()
        ],
        "supporting_registers": cat.SUPPORTING_REGISTERS,
        "internal_module_count": len(BY_NAME),
    }


# ── Deliverable Center (list) ───────────────────────────────────────────────
@router.get("/projects/{project_id}/human-deliverables")
def list_human_deliverables(project_id: str, db: Session = Depends(db_session),
                            actx=Depends(actor_ctx)):
    return hsvc.list_human_deliverables(db, _project(db, project_id), actx)


@router.get("/projects/{project_id}/human-deliverables/{human_code}")
def get_human_deliverable(project_id: str, human_code: str,
                          db: Session = Depends(db_session)):
    project = _project(db, project_id)
    head = hsvc._head(db, project.id, human_code)
    precheck = hsvc.precheck(db, project, human_code)
    return {
        "project_id": project.id,
        "human_code": human_code,
        "catalog": cat.HUMAN_DELIVERABLES.get(human_code),
        "instance": head.to_dict() if head else None,
        "precheck": precheck,
        "versions": hsvc.version_history(db, project, human_code),
        "signoffs": [s for s in hsvc.signoff_register(db, project) if s["human_code"] == human_code],
    }


class PrecheckEmpty(BaseModel):
    pass


@router.post("/projects/{project_id}/human-deliverables/{human_code}/precheck")
def precheck(project_id: str, human_code: str, db: Session = Depends(db_session)):
    return hsvc.precheck(db, _project(db, project_id), human_code)


class GenerateIn(BaseModel):
    with_gaps: bool = False
    precheck_id: str | None = None


@router.post("/projects/{project_id}/human-deliverables/{human_code}/generate")
def generate(project_id: str, human_code: str, body: GenerateIn,
             db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return hsvc.generate(db, _project(db, project_id), human_code, actx,
                         with_gaps=body.with_gaps, precheck_id=body.precheck_id)


class TransitionIn(BaseModel):
    target: str
    comment: str | None = None


@router.post("/projects/{project_id}/human-deliverables/{human_code}/transition")
def transition(project_id: str, human_code: str, body: TransitionIn,
               db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return hsvc.transition(db, _project(db, project_id), human_code, body.target,
                           actx, comment=body.comment)


class SignoffIn(BaseModel):
    decision: str = "ACCEPT"
    signoff_type: str | None = None
    comment: str | None = None
    signer_role: str | None = None
    known_exceptions: list | None = None


@router.post("/projects/{project_id}/human-deliverables/{human_code}/signoff")
def signoff(project_id: str, human_code: str, body: SignoffIn,
            db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return hsvc.signoff(db, _project(db, project_id), human_code, actx, body.model_dump())


@router.get("/projects/{project_id}/human-deliverables/{human_code}/versions")
def versions(project_id: str, human_code: str, db: Session = Depends(db_session)):
    return hsvc.version_history(db, _project(db, project_id), human_code)


@router.post("/projects/{project_id}/human-deliverables/{human_code}/refresh")
def refresh_freshness(project_id: str, human_code: str, db: Session = Depends(db_session)):
    return hsvc.refresh_freshness(db, _project(db, project_id), human_code)


# ── Sign-off register / queues / audit ──────────────────────────────────────
@router.get("/projects/{project_id}/signoff-register")
def signoff_register(project_id: str, db: Session = Depends(db_session)):
    return hsvc.signoff_register(db, _project(db, project_id))


@router.get("/projects/{project_id}/my-signoffs")
def my_signoffs(project_id: str, db: Session = Depends(db_session), actx=Depends(actor_ctx)):
    return hsvc.my_signoffs(db, _project(db, project_id), actx)


@router.get("/projects/{project_id}/deliverable-audit-trail")
def audit_trail(project_id: str, db: Session = Depends(db_session)):
    return hsvc.audit_trail(db, _project(db, project_id))


# ── Exports ─────────────────────────────────────────────────────────────────
@router.get("/projects/{project_id}/exports/human/{human_code}")
def export_human(project_id: str, human_code: str, brand: str = "GEA_STANDARD",
                 db: Session = Depends(db_session)):
    project = _project(db, project_id)
    content = hsvc.build_human_workbook(db, project, human_code, brand)
    filename = f"{project.key}-{human_code}.xlsx"
    return Response(content=content,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/projects/{project_id}/exports/snapshot/{human_code}")
def export_snapshot(project_id: str, human_code: str, db: Session = Depends(db_session)):
    project = _project(db, project_id)
    content = hsvc.snapshot_export(db, project, human_code)
    return Response(content=content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{project.key}-{human_code}-snapshot.json"'})


@router.get("/projects/{project_id}/signoff-evidence")
def export_signoff_evidence(project_id: str, human_code: str | None = None,
                            db: Session = Depends(db_session)):
    project = _project(db, project_id)
    content = hsvc.signoff_evidence_export(db, project, human_code)
    return Response(content=content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{project.key}-signoff-evidence.json"'})


@router.get("/projects/{project_id}/acceptance-package")
def export_acceptance_package(project_id: str, db: Session = Depends(db_session)):
    project = _project(db, project_id)
    content = hsvc.acceptance_package(db, project)
    return Response(content=content, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{project.key}-acceptance-package.zip"'})
