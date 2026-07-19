from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..excel_utils import make_excel_response, make_template_response, read_import_excel
from ..auth import get_current_user, require_internal

router = APIRouter(prefix="/api/{slug}/gantt", tags=["gantt"], dependencies=[Depends(get_current_user)])

COLUMNS = [
    "name",
    "phase",
    "start_date",
    "end_date",
    "progress",
    "dependencies",
    "linked_task_id",
    "is_milestone",
    "baseline_start",
    "baseline_end",
]


@router.get("", response_model=list[schemas.GanttItemOut])
def list_gantt_items(slug: str, db: Session = Depends(get_project_db)):
    return db.query(models.GanttItem).order_by(models.GanttItem.start_date).all()


@router.post("", response_model=schemas.GanttItemOut)
def create_gantt_item(
    slug: str,
    payload: schemas.GanttItemCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = models.GanttItem(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=schemas.GanttItemOut)
def update_gantt_item(
    slug: str,
    item_id: int,
    payload: schemas.GanttItemUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.GanttItem).filter(models.GanttItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Gantt item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_gantt_item(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.GanttItem).filter(models.GanttItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Gantt item not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.get("/export")
def export_gantt(slug: str, db: Session = Depends(get_project_db)):
    items = db.query(models.GanttItem).order_by(models.GanttItem.start_date).all()
    rows = [{col: getattr(item, col) for col in COLUMNS} for item in items]
    return make_excel_response(rows, COLUMNS, f"{slug}-gantt.xlsx")


@router.get("/import-template")
def import_template():
    return make_template_response(COLUMNS, "gantt-import-template.xlsx")


@router.post("/import")
async def import_gantt(
    slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    content = await file.read()
    records = read_import_excel(content, COLUMNS)
    created = 0
    for record in records:
        if not record.get("name") or not record.get("start_date") or not record.get("end_date"):
            continue
        if record.get("is_milestone") is not None:
            record["is_milestone"] = bool(record["is_milestone"])
        if record.get("progress") is not None:
            try:
                record["progress"] = int(record["progress"])
            except (TypeError, ValueError):
                record["progress"] = 0
        if record.get("linked_task_id") is not None:
            try:
                record["linked_task_id"] = int(record["linked_task_id"])
            except (TypeError, ValueError):
                record["linked_task_id"] = None
        db.add(models.GanttItem(**record))
        created += 1
    db.commit()
    return {"imported": created}
