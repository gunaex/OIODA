from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..auth import require_internal

# Not explicitly addressed by the security spec — defaulting to "internal
# working tool" (same treatment as tasks/notes) since that's the safer
# default. Revisit if client-facing diagrams become a real use case.
router = APIRouter(prefix="/api/{slug}/whiteboards", tags=["whiteboards"], dependencies=[Depends(require_internal)])


@router.get("", response_model=list[schemas.WhiteboardOut])
def list_whiteboards(
    slug: str,
    linked_entity_type: Optional[str] = Query(None),
    linked_entity_id: Optional[int] = Query(None),
    db: Session = Depends(get_project_db),
):
    q = db.query(models.Whiteboard)
    if linked_entity_type:
        q = q.filter(models.Whiteboard.linked_entity_type == linked_entity_type)
    if linked_entity_id is not None:
        q = q.filter(models.Whiteboard.linked_entity_id == linked_entity_id)
    return q.order_by(models.Whiteboard.updated_at.desc()).all()


@router.post("", response_model=schemas.WhiteboardOut)
def create_whiteboard(slug: str, payload: schemas.WhiteboardCreate, db: Session = Depends(get_project_db)):
    data = payload.model_dump()
    if not data.get("xml_content"):
        data["xml_content"] = schemas.BLANK_DIAGRAM_XML
    obj = models.Whiteboard(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{item_id}", response_model=schemas.WhiteboardOut)
def get_whiteboard(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    obj = db.query(models.Whiteboard).filter(models.Whiteboard.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    return obj


@router.put("/{item_id}", response_model=schemas.WhiteboardOut)
def update_whiteboard(slug: str, item_id: int, payload: schemas.WhiteboardUpdate, db: Session = Depends(get_project_db)):
    obj = db.query(models.Whiteboard).filter(models.Whiteboard.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_whiteboard(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    obj = db.query(models.Whiteboard).filter(models.Whiteboard.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Whiteboard not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
