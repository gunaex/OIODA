from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import code_generator, models, schemas
from ..database import get_project_db, get_master_db
from ..import_engine import ImportError_, export_response, raise_import_errors, read_rows, template_response
from ..import_schemas import FUNCTIONS as SCHEMA
from ..activity import log_changes
from ..auth import get_current_user, require_internal

router = APIRouter(prefix="/api/{slug}/functions", tags=["functions"], dependencies=[Depends(get_current_user)])

# Column definitions live in import_schemas so template/import/export can't
# drift. The estimate-only extension columns are still split out here, since
# a "simple" project shouldn't be shown pricing fields it never uses.
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
    """Which columns a project of this type gets, filtered through the schema
    so an export-only field (pd_total) can never leak into the template even
    though the estimate column list historically mentioned it."""
    columns = ESTIMATE_COLUMNS if project_type == "estimate" else SIMPLE_COLUMNS
    return [c for c in columns if c in SCHEMA.importable]


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


def _unique_copy_code(db: Session, original_code: Optional[str]) -> Optional[str]:
    """Same reasoning as tasks._unique_copy_code — cloning the same function
    twice must not produce two rows sharing a code now that the code column
    is unique."""
    if not original_code:
        return None
    candidate = f"{original_code}-COPY"
    n = 2
    while code_generator.code_exists(db, "function", candidate):
        candidate = f"{original_code}-COPY{n}"
        n += 1
    return candidate


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
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    data = apply_pd_total(payload.model_dump())
    data["function_code"] = code_generator.resolve_code_for_create(
        db, master_db, slug, "function", data.get("function_code")
    )
    obj = models.Function(**data)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Function code '{data['function_code']}' is already used in this project."
        )
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
    data["function_code"] = _unique_copy_code(db, original.function_code)
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
    # pd_total is export-only: shown here for reference, refused on import.
    export_columns = columns + [c for c in SCHEMA.export_only if c not in columns]
    rows = [{col: getattr(item, col, None) for col in export_columns} for item in items]
    return export_response(rows, export_columns, f"{slug}-functions.xlsx")


@router.get("/import-template")
def import_template(
    slug: str,
    type: Optional[str] = Query(None),
    master_db: Session = Depends(get_master_db),
):
    resolved_type = resolve_project_type(slug, type, master_db)
    columns = columns_for_type(resolved_type)
    return template_response(SCHEMA, f"functions-import-template-{resolved_type}.xlsx", columns)


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
    try:
        records, report = read_rows(content, SCHEMA, columns)
    except ImportError_ as exc:
        raise_import_errors(exc)

    code_errors = code_generator.validate_import_codes(db, "function", records, "function_code")
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
        if not record.get("name"):
            continue
        record["function_code"] = code_generator.resolve_code_for_import_row(
            db, master_db, slug, "function", record.get("function_code")
        )
        db.add(models.Function(**apply_pd_total(record)))
        created += 1
    db.commit()
    return {"imported": created, **report}
