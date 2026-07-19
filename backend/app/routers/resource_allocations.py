from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_master_db
from ..auth import get_current_user, require_internal

# Lives under /api/{slug}/... like every other project-scoped router, but
# the underlying table is in master.db (not the per-project SQLite file) —
# resources are cross-project by design, see the spec. project_slug is a
# plain filter column here, not a cross-DB FK.
router = APIRouter(
    prefix="/api/{slug}/resource-allocations",
    tags=["resource-allocations"],
    dependencies=[Depends(get_current_user)],
)


def _get_project_or_404(slug: str, db: Session) -> models.Project:
    project = db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[schemas.ResourceAllocationOut])
def list_allocations(slug: str, db: Session = Depends(get_master_db)):
    _get_project_or_404(slug, db)
    return (
        db.query(models.ResourceAllocation)
        .filter(models.ResourceAllocation.project_slug == slug)
        .order_by(models.ResourceAllocation.start_date)
        .all()
    )


@router.post("", response_model=schemas.ResourceAllocationOut)
def create_allocation(
    slug: str,
    payload: schemas.ResourceAllocationCreate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    _get_project_or_404(slug, db)
    resource = db.query(models.Resource).filter(models.Resource.id == payload.resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    obj = models.ResourceAllocation(**payload.model_dump(), project_slug=slug)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{allocation_id}", response_model=schemas.ResourceAllocationOut)
def update_allocation(
    slug: str,
    allocation_id: int,
    payload: schemas.ResourceAllocationUpdate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    obj = (
        db.query(models.ResourceAllocation)
        .filter(models.ResourceAllocation.id == allocation_id, models.ResourceAllocation.project_slug == slug)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Allocation not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{allocation_id}")
def delete_allocation(
    slug: str,
    allocation_id: int,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    obj = (
        db.query(models.ResourceAllocation)
        .filter(models.ResourceAllocation.id == allocation_id, models.ResourceAllocation.project_slug == slug)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Allocation not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
