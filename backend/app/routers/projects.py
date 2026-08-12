"""
Conductor Again — Projects Router
Project registry + per-project vision, requirements.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.activity import log_activity
from app.auth import get_current_user, require_roles
from app.database import get_master_db, get_project_db
from app.models import ProjectRegistry, Requirement, User, Vision
from app.schemas import (
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RequirementCreate,
    RequirementOut,
    VisionCreate,
    VisionOut,
)

router = APIRouter(prefix="/api", tags=["projects"])

# ── Project Registry (Master DB) ──────────────────────────

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    return db.query(ProjectRegistry).filter(ProjectRegistry.status != "deleted").all()


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(ProjectRegistry).filter(ProjectRegistry.slug == body.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project slug already exists")

    project = ProjectRegistry(
        slug=body.slug,
        name=body.name,
        description=body.description,
        created_by=user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Initialize per-project DB
    from app.database import get_project_engine
    get_project_engine(body.slug)

    log_activity(
        db=get_project_db(body.slug).__next__(),
        actor=user.email,
        action="project_created",
        entity_type="project",
        entity_id=project.id,
        details=f"Project '{body.name}' created",
    )

    return project


@router.patch("/projects/{slug}", response_model=ProjectOut)
def update_project(
    slug: str,
    body: ProjectUpdate,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    project = db.query(ProjectRegistry).filter(ProjectRegistry.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.status is not None:
        project.status = body.status

    db.commit()
    db.refresh(project)
    return project


# ── Vision (Per-Project DB) ───────────────────────────────

@router.get("/{slug}/vision", response_model=list[VisionOut])
def list_visions(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    return db.query(Vision).order_by(Vision.revision.desc()).all()


@router.post("/{slug}/vision", response_model=VisionOut, status_code=201)
def create_vision(
    slug: str,
    body: VisionCreate,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    latest = db.query(Vision).order_by(Vision.revision.desc()).first()
    revision = (latest.revision + 1) if latest else 1

    vision = Vision(
        revision=revision,
        content=body.content,
        created_by=user.email,
    )
    db.add(vision)
    db.commit()
    db.refresh(vision)

    log_activity(db, user.email, "vision_created", "vision", vision.id, f"Revision {revision}")
    return vision


# ── Requirements (Per-Project DB) ─────────────────────────

@router.get("/{slug}/requirements", response_model=list[RequirementOut])
def list_requirements(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    return db.query(Requirement).order_by(Requirement.code).all()


@router.post("/{slug}/requirements", response_model=RequirementOut, status_code=201)
def create_requirement(
    slug: str,
    body: RequirementCreate,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(Requirement).filter(Requirement.code == body.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Requirement code already exists")

    req = Requirement(
        code=body.code,
        title=body.title,
        description=body.description,
        created_by=user.email,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    log_activity(db, user.email, "requirement_created", "requirement", req.id, f"Code: {req.code}")
    return req
