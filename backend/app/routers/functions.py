from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, get_master_db
from ..excel_utils import make_excel_response, make_template_response, read_import_excel
from ..activity import log_changes
from ..auth import get_current_user, require_internal

router = APIRouter(prefix="/api/{slug}/functions", tags=["functions"], dependencies=[Depends(get_current_user)])

CORE_COLUMNS = ["function_code", "name", "description", "type", "phase", "owner", "status"]

EXTENSION_COLUMNS = [
    "module",
    "priority",
    "scope_class",
    "complexity",
    "pd_ba",
    "pd_ux",
    "pd_fe",
    "pd_be",
    "pd_int_data",
    "pd_qa",
    "pd_devops",
    "pd_total",
    "performance_class",
    "target_option_a",
    "target_option_b",
    "target_option_c",
    "performance_note",
    "price_thb",
    "commercial_note",
]

# Simple projects still get `module` for grouping, but none of the
# estimate/pricing fields.
SIMPLE_COLUMNS = CORE_COLUMNS + ["module"]
ESTIMATE_COLUMNS = CORE_COLUMNS + EXTENSION_COLUMNS

PD_FIELDS = ["pd_ba", "pd_ux", "pd_fe", "pd_be", "pd_int_data", "pd_qa", "pd_devops"]


def columns_for_type(project_type: str) -> list[str]:
    return ESTIMATE_COLUMNS if project_type == "estimate" else SIMPLE_COLUMNS


def resolve_project_type(slug: str, override: Optional[str], master_db: Session) -> str:
    if override in ("simple", "estimate"):
        return override
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    return (project.project_type if project else None) or "simple"


def apply_pd_total(data: dict) -> dict:
    """Recompute pd_total from the pd_* breakdown; any client-supplied
    value for pd_total is ignored. Leaves pd_total as None if every
    breakdown field is unset (e.g. a "simple" project's function)."""
    values = [data.get(f) for f in PD_FIELDS]
    if all(v is None for v in values):
        data["pd_total"] = None
    else:
        data["pd_total"] = sum(v or 0 for v in values)
    return data


def apply_filters(q, phase: Optional[str], status: Optional[str], func_type: Optional[str]):
    # Named `func_type` (not `type`) because `type` is already used on the
    # export/import-template/import endpoints below to mean "simple vs
    # estimate template" — different concern, same router, must not collide.
    if phase:
        q = q.filter(models.Function.phase == phase)
    if status:
        q = q.filter(models.Function.status == status)
    if func_type:
        q = q.filter(models.Function.type == func_type)
    return q


@router.get("", response_model=list[schemas.FunctionOut])
def list_functions(
    slug: str,
    phase: Optional[str] = None,
    status: Optional[str] = None,
    func_type: Optional[str] = None,
    db: Session = Depends(get_project_db),
):
    q = apply_filters(db.query(models.Function), phase, status, func_type)
    return q.order_by(models.Function.id).all()


@router.post("", response_model=schemas.FunctionOut)
def create_function(
    slug: str,
    payload: schemas.FunctionCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    data = apply_pd_total(payload.model_dump())
    obj = models.Function(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=schemas.FunctionOut)
def update_function(
    slug: str,
    item_id: int,
    payload: schemas.FunctionUpdate,
    changed_by: Optional[str] = Query(None),
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Function).filter(models.Function.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Function not found")
    updates = payload.model_dump(exclude_unset=True)
    diffs = {k: (getattr(obj, k), v) for k, v in updates.items() if getattr(obj, k) != v}
    for key, value in updates.items():
        setattr(obj, key, value)
    if set(updates) & set(PD_FIELDS):
        current = {f: getattr(obj, f) for f in PD_FIELDS}
        obj.pd_total = apply_pd_total(current)["pd_total"]
    log_changes(db, "function", item_id, diffs, changed_by)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_function(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Function).filter(models.Function.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Function not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/clone", response_model=schemas.FunctionOut)
def clone_function(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    original = db.query(models.Function).filter(models.Function.id == item_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Function not found")
    data = {
        c.name: getattr(original, c.name)
        for c in models.Function.__table__.columns
        if c.name not in ("id", "function_code", "created_at", "updated_at")
    }
    data["function_code"] = f"{original.function_code}-COPY" if original.function_code else None
    data["name"] = f"{original.name} (Copy)"
    clone = models.Function(**data)
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


@router.get("/export")
def export_functions(
    slug: str,
    type: Optional[str] = Query(None),
    phase: Optional[str] = None,
    status: Optional[str] = None,
    func_type: Optional[str] = None,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    resolved_type = resolve_project_type(slug, type, master_db)
    columns = columns_for_type(resolved_type)
    items = apply_filters(db.query(models.Function), phase, status, func_type).order_by(models.Function.id).all()
    rows = [{col: getattr(item, col) for col in columns} for item in items]
    return make_excel_response(rows, columns, f"{slug}-functions.xlsx")


@router.get("/import-template")
def import_template(
    slug: str,
    type: Optional[str] = Query(None),
    master_db: Session = Depends(get_master_db),
):
    resolved_type = resolve_project_type(slug, type, master_db)
    columns = columns_for_type(resolved_type)
    return make_template_response(columns, f"functions-import-template-{resolved_type}.xlsx")


@router.post("/import")
async def import_functions(
    slug: str,
    type: Optional[str] = Query(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    resolved_type = resolve_project_type(slug, type, master_db)
    columns = columns_for_type(resolved_type)
    content = await file.read()
    records = read_import_excel(content, columns)
    created = 0
    for record in records:
        if not record.get("name"):
            continue
        db.add(models.Function(**apply_pd_total(record)))
        created += 1
    db.commit()
    return {"imported": created}
