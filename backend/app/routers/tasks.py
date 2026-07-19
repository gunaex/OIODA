from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..excel_utils import make_excel_response, make_template_response, read_import_excel
from ..activity import log_changes
from ..auth import require_internal

# Entire router requires an internal role (pmo_admin/dev/qa) — client_viewer
# must not see tasks at all, per the security spec ("ห้ามเห็น internal task").
router = APIRouter(prefix="/api/{slug}/tasks", tags=["tasks"], dependencies=[Depends(require_internal)])

COLUMNS = [
    "task_code",
    "title",
    "description",
    "phase",
    "owner",
    "due_date",
    "status",
    "priority",
    "is_followup",
    "linked_function_id",
]


def apply_filters(q, owner: Optional[str], status: Optional[str], phase: Optional[str], is_followup: Optional[bool]):
    if owner:
        q = q.filter(models.Task.owner == owner)
    if status:
        q = q.filter(models.Task.status == status)
    if phase:
        q = q.filter(models.Task.phase == phase)
    if is_followup is not None:
        q = q.filter(models.Task.is_followup == is_followup)
    return q


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(
    slug: str,
    owner: Optional[str] = None,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    is_followup: Optional[bool] = None,
    db: Session = Depends(get_project_db),
):
    q = apply_filters(db.query(models.Task), owner, status, phase, is_followup)
    return q.order_by(models.Task.id).all()


@router.post("", response_model=schemas.TaskOut)
def create_task(slug: str, payload: schemas.TaskCreate, db: Session = Depends(get_project_db)):
    obj = models.Task(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=schemas.TaskOut)
def update_task(
    slug: str,
    item_id: int,
    payload: schemas.TaskUpdate,
    changed_by: Optional[str] = Query(None),
    db: Session = Depends(get_project_db),
):
    obj = db.query(models.Task).filter(models.Task.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    updates = payload.model_dump(exclude_unset=True)
    diffs = {k: (getattr(obj, k), v) for k, v in updates.items() if getattr(obj, k) != v}
    for key, value in updates.items():
        setattr(obj, key, value)
    log_changes(db, "task", item_id, diffs, changed_by)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_task(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    obj = db.query(models.Task).filter(models.Task.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/clone", response_model=schemas.TaskOut)
def clone_task(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    original = db.query(models.Task).filter(models.Task.id == item_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Task not found")
    data = {
        c.name: getattr(original, c.name)
        for c in models.Task.__table__.columns
        if c.name not in ("id", "task_code", "created_at")
    }
    data["task_code"] = f"{original.task_code}-COPY" if original.task_code else None
    data["title"] = f"{original.title} (Copy)"
    clone = models.Task(**data)
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/export")
def export_tasks(
    slug: str,
    owner: Optional[str] = None,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    is_followup: Optional[bool] = None,
    db: Session = Depends(get_project_db),
):
    items = apply_filters(db.query(models.Task), owner, status, phase, is_followup).order_by(models.Task.id).all()
    rows = [{col: getattr(item, col) for col in COLUMNS} for item in items]
    return make_excel_response(rows, COLUMNS, f"{slug}-tasks.xlsx")


@router.get("/import-template")
def import_template():
    return make_template_response(COLUMNS, "tasks-import-template.xlsx")


@router.post("/import")
async def import_tasks(slug: str, file: UploadFile = File(...), db: Session = Depends(get_project_db)):
    content = await file.read()
    records = read_import_excel(content, COLUMNS)
    created = 0
    for record in records:
        if not record.get("title"):
            continue
        if record.get("is_followup") is not None:
            record["is_followup"] = bool(record["is_followup"])
        if record.get("linked_function_id") is not None:
            try:
                record["linked_function_id"] = int(record["linked_function_id"])
            except (TypeError, ValueError):
                record["linked_function_id"] = None
        db.add(models.Task(**record))
        created += 1
    db.commit()
    return {"imported": created}
