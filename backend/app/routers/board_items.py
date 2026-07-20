import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, get_master_db
from ..excel_utils import make_excel_response
from ..auth import require_internal
from ..business_day import add_business_days
from ..workflow_definitions import BOARD_ITEM_TRANSITIONS

router = APIRouter(prefix="/api/{slug}/board-items", tags=["board-items"], dependencies=[Depends(require_internal)])

ITEM_CODE_PREFIX = {"issue": "ISS", "incident": "INC", "backlog": "BLG"}
DEFAULT_STATUS = {"issue": "Open", "incident": "Open", "backlog": "Backlog"}
# Business-day SLA (Thai Business-day Engine) — weekends and thai_holidays
# are skipped. Per that spec's migration note: existing sla_due_date values
# on items created before this change are NOT backfilled/recalculated, only
# newly created/re-severity'd items use this.
SLA_DAYS = {"Critical": 1, "High": 3, "Medium": 7, "Low": 14}

EXPORT_COLUMNS = [
    "item_code",
    "title",
    "description",
    "severity",
    "status",
    "phase",
    "owner",
    "sla_due_date",
    "linked_task_id",
    "promoted_from_id",
]


def generate_item_code(db: Session, item_type: str) -> str:
    prefix = ITEM_CODE_PREFIX[item_type]
    existing = db.query(models.BoardItem.item_code).filter(models.BoardItem.item_type == item_type).all()
    max_n = 0
    for (code,) in existing:
        if not code:
            continue
        m = re.match(rf"^{prefix}-(\d+)$", code)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{prefix}-{max_n + 1:03d}"


def compute_sla_due_date(severity: Optional[str], from_dt: datetime, master_db: Session) -> Optional[date]:
    days = SLA_DAYS.get(severity)
    if days is None:
        return None
    return add_business_days(from_dt.date(), days, master_db)


@router.get("", response_model=list[schemas.BoardItemOut])
def list_board_items(
    slug: str,
    type: str = Query(...),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    owner: Optional[str] = None,
    db: Session = Depends(get_project_db),
):
    q = db.query(models.BoardItem).filter(models.BoardItem.item_type == type)
    if severity:
        q = q.filter(models.BoardItem.severity == severity)
    if status:
        q = q.filter(models.BoardItem.status == status)
    if phase:
        q = q.filter(models.BoardItem.phase == phase)
    if owner:
        q = q.filter(models.BoardItem.owner == owner)
    return q.order_by(models.BoardItem.id).all()


@router.post("", response_model=schemas.BoardItemOut)
def create_board_item(
    slug: str,
    payload: schemas.BoardItemCreate,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    data = payload.model_dump()
    item_type = data["item_type"]
    obj = models.BoardItem(
        **data,
        item_code=generate_item_code(db, item_type),
        status=DEFAULT_STATUS[item_type],
        sla_due_date=compute_sla_due_date(data.get("severity"), datetime.utcnow(), master_db),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=schemas.BoardItemOut)
def update_board_item(
    slug: str,
    item_id: int,
    payload: schemas.BoardItemUpdate,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    obj = db.query(models.BoardItem).filter(models.BoardItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Board item not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(obj, key, value)
    if "severity" in updates:
        obj.sla_due_date = compute_sla_due_date(obj.severity, obj.created_at, master_db)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_board_item(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    obj = db.query(models.BoardItem).filter(models.BoardItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Board item not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/export")
def export_board_items(slug: str, type: str = Query(...), db: Session = Depends(get_project_db)):
    items = db.query(models.BoardItem).filter(models.BoardItem.item_type == type).order_by(models.BoardItem.id).all()
    rows = [{col: getattr(item, col) for col in EXPORT_COLUMNS} for item in items]
    return make_excel_response(rows, EXPORT_COLUMNS, f"{slug}-{type}.xlsx")


@router.post("/{item_id}/promote", response_model=schemas.BoardItemOut)
def promote_board_item(
    slug: str,
    item_id: int,
    payload: schemas.PromoteRequest,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    obj = db.query(models.BoardItem).filter(models.BoardItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Board item not found")

    allowed = BOARD_ITEM_TRANSITIONS.get(obj.item_type, [])
    if payload.target_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot promote a '{obj.item_type}' item to '{payload.target_type}' (allowed: {sorted(allowed) or 'none'})",
        )

    if payload.target_type == "task":
        task = models.Task(title=obj.title, status="Todo", priority="Med", phase=obj.phase, owner=obj.owner)
        db.add(task)
        db.flush()
        obj.linked_task_id = task.id
        db.commit()
        db.refresh(obj)
        return obj

    # backlog -> issue, or issue -> incident: create the next-stage item and
    # mark this one as superseded, keeping the trail via promoted_from_id.
    new_item = models.BoardItem(
        item_type=payload.target_type,
        item_code=generate_item_code(db, payload.target_type),
        title=obj.title,
        description=obj.description,
        severity=obj.severity,
        status=DEFAULT_STATUS[payload.target_type],
        phase=obj.phase,
        owner=obj.owner,
        promoted_from_id=obj.id,
        sla_due_date=compute_sla_due_date(obj.severity, datetime.utcnow(), master_db),
    )
    obj.status = "Promoted"
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item
