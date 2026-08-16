from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..auth import require_internal

router = APIRouter(prefix="/api/{slug}/comments", tags=["comments"], dependencies=[Depends(require_internal)])


@router.get("", response_model=list[schemas.CommentOut])
def list_comments(
    slug: str,
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    db: Session = Depends(get_project_db),
):
    return (
        db.query(models.Comment)
        .filter(models.Comment.entity_type == entity_type, models.Comment.entity_id == entity_id)
        .order_by(models.Comment.created_at)
        .all()
    )


@router.post("", response_model=schemas.CommentOut)
def create_comment(slug: str, payload: schemas.CommentCreate, db: Session = Depends(get_project_db)):
    obj = models.Comment(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_comment(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    obj = db.query(models.Comment).filter(models.Comment.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}
