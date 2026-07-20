import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_master_db, get_project_engine, project_db_exists, open_project_session
from ..auth import get_current_user, require_internal

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
def list_projects(db: Session = Depends(get_master_db)):
    return db.query(models.Project).order_by(models.Project.created_at.desc()).all()


@router.get("/{slug}", response_model=schemas.ProjectOut)
def get_project(slug: str, db: Session = Depends(get_master_db)):
    project = db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project_db_exists(slug):
        get_project_engine(slug)
    return project
