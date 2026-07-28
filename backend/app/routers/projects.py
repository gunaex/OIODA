import os
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import (
    get_master_db,
    get_project_engine,
    project_db_exists,
    project_db_path,
    open_project_session,
    dispose_project_engine,
)
from ..auth import get_current_user, require_internal, require_roles, verify_password

router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(get_current_user)])

# A project slug matching one of these would permanently collide with a
# fixed-literal-prefix router (/api/resources/..., /api/dashboard/global) —
# reserved so slugify() always routes around them instead.
RESERVED_SLUGS = {"resources", "dashboard", "auth", "projects", "health", "holidays", "business-days", "workflows"}

MANDATORY_COLUMN_BY_CATEGORY = {
    "critical": "mandatory_critical",
    "non_critical": "mandatory_non_critical",
    "ma": "mandatory_ma",
    "rollout": "mandatory_rollout",
}


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "project"


def populate_mandatory_documents(slug: str, category: str, master_db: Session):
    """Insert one Draft document per document_templates row whose
    mandatory_{category} column is 'M', into the newly-created project's
    own documents table."""
    column_name = MANDATORY_COLUMN_BY_CATEGORY.get(category)
    if not column_name:
        return

    templates = (
        master_db.query(models.DocumentTemplate)
        .filter(getattr(models.DocumentTemplate, column_name) == "M")
        .order_by(models.DocumentTemplate.doc_code)
        .all()
    )
    if not templates:
        return

    project_db = open_project_session(slug)
    try:
        for t in templates:
            project_db.add(
                models.Document(
                    doc_code=str(t.doc_code),
                    title=t.doc_name,
                    phase=t.phase_name,
                    doc_type=t.doc_set_name,
                    status="Draft",
                    version=1,
                )
            )
        project_db.commit()
    finally:
        project_db.close()


@router.post("", response_model=schemas.ProjectOut)
def create_project(
    payload: schemas.ProjectCreate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    base_slug = slugify(payload.name)
    slug = base_slug
    suffix = 1
    while slug in RESERVED_SLUGS or db.query(models.Project).filter(models.Project.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    project = models.Project(
        name=payload.name,
        slug=slug,
        project_type=payload.project_type,
        project_category=payload.project_category,
        project_code=payload.project_code,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # Provision an empty per-project SQLite DB with all tables created.
    get_project_engine(slug)

    if payload.project_category:
        populate_mandatory_documents(slug, payload.project_category, db)

    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(
    include_archived: bool = Query(False),
    db: Session = Depends(get_master_db),
):
    q = db.query(models.Project)
    if not include_archived:
        q = q.filter(models.Project.archived == False)  # noqa: E712
    return q.order_by(models.Project.created_at.desc()).all()


@router.get("/{slug}", response_model=schemas.ProjectOut)
def get_project(slug: str, db: Session = Depends(get_master_db)):
    project = db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project_db_exists(slug):
        get_project_engine(slug)
    return project


@router.put("/{slug}/settings", response_model=schemas.ProjectOut)
def update_project_settings(
    slug: str,
    payload: schemas.ProjectUpdate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    """Project Settings. Today this is just the running-code prefix — a
    project created before the Running Code Generator existed, or one that
    skipped setting it, gets it here rather than needing to be recreated."""
    project = db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project


# Archive/delete are the most consequential actions in the app (hiding or
# permanently destroying a whole project's data) — restricted to pmo_admin
# specifically (not the broader require_internal), and both require the
# requesting user to re-enter their own current password, same check as
# changing your password (see auth.py's change_password), as a deliberate
# extra confirmation step before something this hard to reverse.
@router.put("/{slug}/archive", response_model=schemas.ProjectOut)
def archive_project(
    slug: str,
    payload: schemas.ProjectArchiveRequest,
    db: Session = Depends(get_master_db),
    user: models.User = Depends(require_roles("pmo_admin")),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    project = db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.archived = payload.archived
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{slug}")
def delete_project(
    slug: str,
    payload: schemas.ProjectDeleteRequest,
    db: Session = Depends(get_master_db),
    user: models.User = Depends(require_roles("pmo_admin")),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    project = db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # resource_allocations.project_slug is a plain string, not a real FK
    # (see the comment on that model) — clean these up explicitly or
    # they'd silently dangle, pointing at a project that no longer exists.
    db.query(models.ResourceAllocation).filter(models.ResourceAllocation.project_slug == slug).delete()
    db.delete(project)
    db.commit()

    dispose_project_engine(slug)
    db_path = project_db_path(slug)
    if os.path.exists(db_path):
        os.remove(db_path)

    return {"ok": True}
