from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_master_db
from ..auth import get_current_user, require_internal
from ..resource_utils import compute_utilization

# Baseline: any authenticated role can read the resource pool (needed for
# dashboards); writes are internal-only (pmo_admin/dev/qa), same split as
# functions/gantt.
router = APIRouter(prefix="/api/resources", tags=["resources"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[schemas.ResourceOut])
def list_resources(db: Session = Depends(get_master_db)):
    return db.query(models.Resource).order_by(models.Resource.name).all()


@router.post("", response_model=schemas.ResourceOut)
def create_resource(
    payload: schemas.ResourceCreate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    obj = models.Resource(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# Registered before /{resource_id} so a literal "utilization" path segment
# can never be swallowed by the dynamic int route.
@router.get("/utilization")
def resource_utilization(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_master_db),
):
    return compute_utilization(db, from_, to)


@router.put("/{resource_id}", response_model=schemas.ResourceOut)
def update_resource(
    resource_id: int,
    payload: schemas.ResourceUpdate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Resource not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{resource_id}")
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Resource).filter(models.Resource.id == resource_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Resource not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
