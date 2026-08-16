from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..auth import require_internal

router = APIRouter(prefix="/api/{slug}/activity", tags=["activity"], dependencies=[Depends(require_internal)])


@router.get("", response_model=list[schemas.ActivityLogOut])
def list_activity(
    slug: str,
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    db: Session = Depends(get_project_db),
):
    q = db.query(models.ActivityLog)
    if entity_type:
        q = q.filter(models.ActivityLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(models.ActivityLog.entity_id == entity_id)
    return q.order_by(models.ActivityLog.changed_at.desc()).limit(200).all()
