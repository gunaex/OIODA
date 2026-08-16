from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..auth import get_current_user, require_internal

# Read stays open to any authenticated role (same as gantt.py) — Present
# mode is meant to show annotated pins to client_viewer too. Writes are
# gated the same way gantt.py gates task edits.
router = APIRouter(
    prefix="/api/{slug}/gantt-annotations",
    tags=["gantt-annotations"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[schemas.GanttAnnotationOut])
def list_gantt_annotations(slug: str, db: Session = Depends(get_project_db)):
    return db.query(models.GanttAnnotation).order_by(models.GanttAnnotation.gantt_date).all()


@router.post("", response_model=schemas.GanttAnnotationOut)
def create_gantt_annotation(
    slug: str,
    payload: schemas.GanttAnnotationCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = models.GanttAnnotation(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=schemas.GanttAnnotationOut)
def update_gantt_annotation(
    slug: str,
    item_id: int,
    payload: schemas.GanttAnnotationUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.GanttAnnotation).filter(models.GanttAnnotation.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Annotation not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_gantt_annotation(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.GanttAnnotation).filter(models.GanttAnnotation.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Annotation not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
