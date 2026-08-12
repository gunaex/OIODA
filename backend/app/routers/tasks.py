from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import code_generator, models, schemas
from ..database import get_master_db, get_project_db
from ..import_engine import ImportError_, export_response, raise_import_errors, read_rows, template_response
from ..import_schemas import TASKS as SCHEMA
from ..activity import log_changes
from ..auth import require_internal
from ..ecosystem.ecosystem_auth import require_project_tenant_match

# Entire router requires an internal role (pmo_admin/dev/qa) — client_viewer
# must not see tasks at all, per the security spec ("ห้ามเห็น internal task").
# require_project_tenant_match is a no-op unless ECOSYSTEM_MODE=true and the
# project has a tenant_id set (CROSS_TENANT_TASK_ACCESS_BLOCKED).
router = APIRouter(
    prefix="/api/{slug}/tasks",
    tags=["tasks"],
    dependencies=[Depends(require_internal), Depends(require_project_tenant_match)],
)

# Column list now lives in import_schemas — one definition for the
# template, the import validator and the export.
COLUMNS = SCHEMA.template_columns


def _unique_copy_code(db: Session, original_code: Optional[str]) -> Optional[str]:
    """original-COPY, or original-COPY2, -COPY3, ... if that's taken too —
    cloning the same task twice used to silently produce two rows sharing a
    code; the unique index means it must not, so this finds a free one."""
    if not original_code:
        return None
    candidate = f"{original_code}-COPY"
    n = 2
    while code_generator.code_exists(db, "task", candidate):
        candidate = f"{original_code}-COPY{n}"
        n += 1
    return candidate


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
def create_task(
    slug: str,
    payload: schemas.TaskCreate,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    data = payload.model_dump()
    # Running Code Generator: a blank code auto-generates (when the project
    # has a Project Code set); a code given by hand is used as typed, and
    # advances the sequence if it matches this project's own pattern.
    data["task_code"] = code_generator.resolve_code_for_create(db, master_db, slug, "task", data.get("task_code"))
    obj = models.Task(**data)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Task code '{data['task_code']}' is already used in this project.")
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
    data["task_code"] = _unique_copy_code(db, original.task_code)
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
    rows = [{col: getattr(item, col, None) for col in SCHEMA.export_columns} for item in items]
    return export_response(rows, SCHEMA.export_columns, f"{slug}-tasks.xlsx")


@router.get("/import-template")
def import_template():
    return template_response(SCHEMA, "tasks-import-template.xlsx")


@router.post("/import")
async def import_tasks(
    slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    content = await file.read()
    try:
        records, report = read_rows(content, SCHEMA)
    except ImportError_ as exc:
        raise_import_errors(exc)

    code_errors = code_generator.validate_import_codes(db, "task", records, "task_code")
    if code_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"{len(code_errors)} cell(s) could not be imported. Nothing was saved.",
                "errors": code_errors,
                "error_count": len(code_errors),
            },
        )

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
        # Blank -> auto-generate; given -> used as-is, advancing the sequence
        # if it matches this project's pattern. Uniqueness was already
        # cleared above, so nothing here needs to raise.
        record["task_code"] = code_generator.resolve_code_for_import_row(db, master_db, slug, "task", record.get("task_code"))
        db.add(models.Task(**record))
        created += 1
    db.commit()
    return {"imported": created, **report}
