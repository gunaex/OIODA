import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, get_master_db, PROJECTS_DIR
from ..import_engine import ImportError_, export_response, raise_import_errors, read_rows, template_response
from ..import_schemas import DOCUMENTS as SCHEMA
from ..activity import log_changes
from .projects import MANDATORY_COLUMN_BY_CATEGORY
from ..auth import get_current_user, require_internal, require_signoff_role
from ..workflow_definitions import DOCUMENT_TRANSITIONS, is_transition_allowed

router = APIRouter(prefix="/api/{slug}/documents", tags=["documents"], dependencies=[Depends(get_current_user)])


def _restrict_to_confirmed_for_client_viewer(q, user: models.User):
    """client_viewer may read documents, but only ones that are Confirmed —
    per the security spec, everything else (Draft/InReview/Rejected) is
    internal working state they must not see."""
    if user.role == "client_viewer":
        q = q.filter(models.Document.status == "Confirmed")
    return q

# From import_schemas. The last_signed_* columns are joined from the sign-off
# history rather than being fields on the document, so they are export-only.
EXPORT_COLUMNS = SCHEMA.export_columns


def _latest_signoff(db: Session, document_id: int):
    return (
        db.query(models.DocumentSignoff)
        .filter(models.DocumentSignoff.document_id == document_id)
        .order_by(models.DocumentSignoff.signed_at.desc())
        .first()
    )


@router.get("", response_model=list[schemas.DocumentOut])
def list_documents(
    slug: str,
    phase: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.Document)
    if phase:
        q = q.filter(models.Document.phase == phase)
    if status:
        q = q.filter(models.Document.status == status)
    q = _restrict_to_confirmed_for_client_viewer(q, user)
    return q.order_by(models.Document.id).all()


@router.get("/export")
def export_documents(
    slug: str,
    phase: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.Document)
    if phase:
        q = q.filter(models.Document.phase == phase)
    if status:
        q = q.filter(models.Document.status == status)
    q = _restrict_to_confirmed_for_client_viewer(q, user)
    items = q.order_by(models.Document.id).all()
    rows = []
    for item in items:
        latest = _latest_signoff(db, item.id)
        rows.append(
            {
                "doc_code": item.doc_code,
                "title": item.title,
                "phase": item.phase,
                "doc_type": item.doc_type,
                "status": item.status,
                "version": item.version,
                "owner": item.owner,
                "last_signed_by": latest.signed_by if latest else None,
                "last_signed_at": latest.signed_at if latest else None,
                "last_signoff_status": latest.status if latest else None,
            }
        )
    return export_response(rows, EXPORT_COLUMNS, f"{slug}-documents.xlsx")


@router.get("/import-template")
def documents_import_template(slug: str):
    return template_response(SCHEMA, "documents-import-template.xlsx")


@router.post("/import")
async def import_documents(
    slug: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    """Documents were export-only until now.

    `status` is deliberately not importable: a document becomes Confirmed by
    going through sign-off, and letting a spreadsheet write that value would
    walk straight past the approval the status exists to evidence. Every
    imported document starts at Draft and goes through the workflow.
    """
    content = await file.read()
    try:
        records, report = read_rows(content, SCHEMA)
    except ImportError_ as exc:
        raise_import_errors(exc)

    created = 0
    for record in records:
        db.add(models.Document(**record, status="Draft", version=1))
        created += 1
    db.commit()
    return {
        "imported": created,
        "note": "Imported documents start at Draft — status is set by the sign-off workflow, not by import.",
        **report,
    }


@router.get("/suggested", response_model=list[schemas.DocumentTemplateOut])
def suggested_optional_documents(
    slug: str,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    """Optional ('O') document_templates rows for this project's category
    that haven't already been added to its documents list — surfaced in the
    UI as suggestions the user can add on demand."""
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    if not project or not project.project_category:
        return []

    column_name = MANDATORY_COLUMN_BY_CATEGORY.get(project.project_category)
    if not column_name:
        return []

    already_added = {
        doc_code for (doc_code,) in db.query(models.Document.doc_code).all() if doc_code is not None
    }

    templates = (
        master_db.query(models.DocumentTemplate)
        .filter(getattr(models.DocumentTemplate, column_name) == "O")
        .order_by(models.DocumentTemplate.doc_code)
        .all()
    )
    return [t for t in templates if str(t.doc_code) not in already_added]


@router.post("/from-template/{doc_code}", response_model=schemas.DocumentOut)
def add_document_from_template(
    slug: str,
    doc_code: int,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    template = master_db.query(models.DocumentTemplate).filter(models.DocumentTemplate.doc_code == doc_code).first()
    if not template:
        raise HTTPException(status_code=404, detail="Document template not found")

    obj = models.Document(
        doc_code=str(template.doc_code),
        title=template.doc_name,
        phase=template.phase_name,
        doc_type=template.doc_set_name,
        status="Draft",
        version=1,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# NOTE: this dynamic route must stay below every fixed-string GET route
# above (e.g. /export) — Starlette matches path patterns in registration
# order, and an untyped `{item_id}` placeholder matches "export" as a
# string before FastAPI gets a chance to coerce it to int (which then 422s).
@router.get("/{item_id}", response_model=schemas.DocumentOut)
def get_document(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(get_current_user),
):
    obj = db.query(models.Document).filter(models.Document.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Document not found")
    if user.role == "client_viewer" and obj.status != "Confirmed":
        # 404, not 403 — a client_viewer shouldn't be able to tell a
        # not-yet-confirmed document even exists.
        raise HTTPException(status_code=404, detail="Document not found")
    return obj


@router.post("", response_model=schemas.DocumentOut)
def create_document(
    slug: str,
    payload: schemas.DocumentCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = models.Document(**payload.model_dump(), status="Draft", version=1)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=schemas.DocumentOut)
def update_document(
    slug: str,
    item_id: int,
    payload: schemas.DocumentUpdate,
    changed_by: str | None = None,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Document).filter(models.Document.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Document not found")
    updates = payload.model_dump(exclude_unset=True)
    diffs = {k: (getattr(obj, k), v) for k, v in updates.items() if getattr(obj, k) != v}
    for key, value in updates.items():
        setattr(obj, key, value)
    log_changes(db, "document", item_id, diffs, changed_by)
    if obj.status == "Confirmed":
        # Editing a confirmed document invalidates its approval — it must be
        # re-reviewed and re-signed off before it can be Confirmed again.
        obj.version += 1
        obj.status = "Draft"
    elif obj.status == "Rejected":
        # A rejected document has no approval to invalidate, so no version
        # bump — but it must go back to Draft or it can never re-enter
        # submit-review (which only accepts Draft), leaving it stuck.
        obj.status = "Draft"
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_document(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Document).filter(models.Document.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Document not found")
    db.query(models.DocumentSignoff).filter(models.DocumentSignoff.document_id == item_id).delete()
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/submit-review", response_model=schemas.DocumentOut)
def submit_review(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Document).filter(models.Document.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Document not found")
    if not is_transition_allowed(DOCUMENT_TRANSITIONS, obj.status, "InReview"):
        raise HTTPException(status_code=400, detail=f"Cannot submit for review from status '{obj.status}' (must be Draft)")
    obj.status = "InReview"
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{item_id}/signoff", response_model=schemas.DocumentOut)
def signoff_document(
    slug: str,
    item_id: int,
    payload: schemas.DocumentSignoffCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_signoff_role),
):
    obj = db.query(models.Document).filter(models.Document.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Document not found")
    target_status = "Confirmed" if payload.status == "Approved" else "Rejected"
    if not is_transition_allowed(DOCUMENT_TRANSITIONS, obj.status, target_status):
        raise HTTPException(status_code=400, detail=f"Cannot sign off from status '{obj.status}' (must be InReview)")

    record = models.DocumentSignoff(
        document_id=item_id,
        signed_by=payload.signed_by,
        signed_role=payload.signed_role,
        status=payload.status,
        comment=payload.comment,
        signed_at=datetime.utcnow(),
    )
    db.add(record)

    # This is the only path that can move a document to Confirmed — enforced
    # here, not just in the UI, per the spec's acceptance criteria.
    obj.status = target_status

    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{item_id}/signoffs", response_model=list[schemas.DocumentSignoffOut])
def list_signoffs(
    slug: str,
    item_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    return (
        db.query(models.DocumentSignoff)
        .filter(models.DocumentSignoff.document_id == item_id)
        .order_by(models.DocumentSignoff.signed_at.desc())
        .all()
    )


@router.post("/upload/{item_id}", response_model=schemas.DocumentOut)
async def upload_document_file(
    slug: str,
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    obj = db.query(models.Document).filter(models.Document.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Document not found")

    doc_dir = os.path.join(PROJECTS_DIR, slug, "documents")
    os.makedirs(doc_dir, exist_ok=True)
    safe_name = f"{item_id}_{file.filename}"
    dest_path = os.path.join(doc_dir, safe_name)
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    obj.file_path = os.path.join(slug, "documents", safe_name).replace("\\", "/")
    db.commit()
    db.refresh(obj)
    return obj
