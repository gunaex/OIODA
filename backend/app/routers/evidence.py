import hashlib
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, get_master_db
from ..evidence_utils import sniff_image, MAX_EVIDENCE_SIZE_BYTES
from ..auth import get_current_user, require_tester, require_admin
from ..quota import quota_status
from ..storage import EvidenceStorage, get_evidence_storage

logger = logging.getLogger("evidence")

router = APIRouter(
    prefix="/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
    tags=["evidence"],
    dependencies=[Depends(get_current_user)],
)


def _get_cycle_and_result(db: Session, cycle_id: int, result_id: int) -> tuple[models.TestCycle, models.CycleTestResult]:
    cycle = db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    result = (
        db.query(models.CycleTestResult)
        .filter(models.CycleTestResult.id == result_id, models.CycleTestResult.cycle_id == cycle_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return cycle, result


def _require_unlocked(cycle: models.TestCycle):
    if cycle.status == "LOCKED":
        raise HTTPException(status_code=400, detail="Cycle is LOCKED — evidence cannot be added, annotated, or archived. An admin must /reopen it first.")


def _get_evidence(db: Session, evidence_id: int, result_id: int) -> models.EvidenceItem:
    item = (
        db.query(models.EvidenceItem)
        .filter(models.EvidenceItem.id == evidence_id, models.EvidenceItem.cycle_test_result_id == result_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return item


@router.get("", response_model=list[schemas.EvidenceItemOut])
def list_evidence(slug: str, cycle_id: int, result_id: int, db: Session = Depends(get_project_db)):
    _get_cycle_and_result(db, cycle_id, result_id)
    return (
        db.query(models.EvidenceItem)
        .filter(models.EvidenceItem.cycle_test_result_id == result_id, models.EvidenceItem.status == "ACTIVE")
        .order_by(models.EvidenceItem.captured_at)
        .all()
    )


@router.post("", response_model=schemas.EvidenceItemOut)
async def upload_evidence(
    slug: str,
    cycle_id: int,
    result_id: int,
    evidence_type: str = Form("UPLOADED_IMAGE"),
    caption: str | None = Form(None),
    target_url: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    storage: EvidenceStorage = Depends(get_evidence_storage),
    user: models.User = Depends(require_tester),
):
    """Upload order is deliberate — see ADR-0002's failure-handling
    table: validate -> quota check -> idempotency check -> write to
    storage -> insert DB row, with a compensating delete if the DB
    insert fails after a successful storage write."""
    cycle, result = _get_cycle_and_result(db, cycle_id, result_id)
    _require_unlocked(cycle)

    if evidence_type not in models.EVIDENCE_TYPES:
        raise HTTPException(status_code=400, detail=f"evidence_type must be one of {models.EVIDENCE_TYPES}")

    # 1. Validate — nothing written anywhere yet, always safe to retry.
    content = await file.read()
    if len(content) > MAX_EVIDENCE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"Evidence file exceeds the {MAX_EVIDENCE_SIZE_BYTES // (1024*1024)}MB limit")
    sniffed = sniff_image(content)
    if not sniffed:
        raise HTTPException(status_code=400, detail="File is not a recognized image (PNG/JPEG/GIF/WEBP signature check failed)")
    content_type, ext = sniffed
    sha256 = hashlib.sha256(content).hexdigest()

    # 2. Quota — reject before writing any bytes if this upload would
    # exceed the project's storage_quota_bytes.
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    status_before = quota_status(project, db)
    if status_before["used_bytes"] + len(content) > status_before["quota_bytes"]:
        raise HTTPException(
            status_code=400,
            detail=f"Uploading this file would exceed the project's storage quota "
            f"({status_before['used_bytes']} + {len(content)} > {status_before['quota_bytes']} bytes)",
        )

    # 3. Idempotency — a retried upload of identical content for the same
    # result converges on the existing row instead of duplicating it.
    existing = (
        db.query(models.EvidenceItem)
        .filter(
            models.EvidenceItem.cycle_test_result_id == result_id,
            models.EvidenceItem.original_sha256 == sha256,
            models.EvidenceItem.status == "ACTIVE",
        )
        .first()
    )
    if existing:
        return existing

    # 4. Write to storage. Non-guessable key: a random UUID, not derived
    # solely from content hash (ADR-0002 requirement 5).
    object_key = f"evidence/{slug}/{result_id}/{uuid.uuid4().hex}.{ext}"
    try:
        storage.put(object_key, content, content_type)
    except Exception as exc:
        logger.error("Evidence storage write failed for key %s: %s", object_key, exc)
        raise HTTPException(status_code=502, detail="Could not store the evidence file — nothing was saved, safe to retry") from exc

    # 5. Insert DB row. If this fails, the object we just wrote would be
    # orphaned — compensate by deleting it, and say so distinctly rather
    # than returning a generic error a client might mistake for "nothing
    # happened, retry is free."
    safe_original_filename = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "evidence")[:255]
    item = models.EvidenceItem(
        cycle_id=cycle_id,
        cycle_test_result_id=result_id,
        evidence_type=evidence_type,
        object_key=object_key,
        original_filename=safe_original_filename,
        original_content_type=content_type,
        original_size_bytes=len(content),
        original_sha256=sha256,
        caption=caption,
        target_url=target_url,
        captured_by=user.email,
    )
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except Exception as exc:
        db.rollback()
        try:
            storage.delete(object_key)
        except Exception as cleanup_exc:
            # This is the one genuinely-orphaned-object case (ADR-0002) —
            # log loudly so it's found by reconciliation, don't swallow it.
            logger.error(
                "ORPHANED EVIDENCE OBJECT: key=%s could not be cleaned up after a failed DB write (%s). "
                "See docs/EVIDENCE_STORAGE_LIFECYCLE.md.",
                object_key,
                cleanup_exc,
            )
        raise HTTPException(
            status_code=500,
            detail="The evidence file could not be recorded (its storage write may or may not have been rolled back) — "
            "do not assume it exists; retry the upload.",
        ) from exc

    return item


@router.get("/{evidence_id}", response_model=schemas.EvidenceItemOut)
def get_evidence(slug: str, cycle_id: int, result_id: int, evidence_id: int, db: Session = Depends(get_project_db)):
    _get_cycle_and_result(db, cycle_id, result_id)
    return _get_evidence(db, evidence_id, result_id)


@router.get("/{evidence_id}/original")
def download_evidence_original(
    slug: str,
    cycle_id: int,
    result_id: int,
    evidence_id: int,
    db: Session = Depends(get_project_db),
    storage: EvidenceStorage = Depends(get_evidence_storage),
    _user: models.User = Depends(get_current_user),
):
    """Authorization happens here, in the backend, before anything about
    the object is revealed (ADR-0002 requirement 3). Only after that do
    we either redirect to a short-lived presigned URL (R2) or stream the
    bytes directly (filesystem) — the R2 credentials themselves never
    reach the client either way."""
    _get_cycle_and_result(db, cycle_id, result_id)
    item = _get_evidence(db, evidence_id, result_id)

    presigned = storage.presigned_get_url(item.object_key, expires_in=300)
    if presigned:
        return RedirectResponse(presigned, status_code=307)

    try:
        content = storage.get(item.object_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Original file missing from storage") from exc
    return Response(
        content=content,
        media_type=item.original_content_type,
        headers={"Content-Disposition": f'inline; filename="{item.original_filename}"'},
    )


@router.put("/{evidence_id}", response_model=schemas.EvidenceItemOut)
def update_evidence_caption(
    slug: str,
    cycle_id: int,
    result_id: int,
    evidence_id: int,
    payload: schemas.EvidenceCaptionUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_tester),
):
    cycle, _result = _get_cycle_and_result(db, cycle_id, result_id)
    _require_unlocked(cycle)
    item = _get_evidence(db, evidence_id, result_id)
    item.caption = payload.caption
    item.target_url = payload.target_url
    db.commit()
    db.refresh(item)
    return item


@router.put("/{evidence_id}/archive", response_model=schemas.EvidenceItemOut)
def archive_evidence(
    slug: str,
    cycle_id: int,
    result_id: int,
    evidence_id: int,
    db: Session = Depends(get_project_db),
    _admin: models.User = Depends(require_admin),
):
    """Archive, never delete — the stored object is untouched; this only
    hides the item from the default (ACTIVE) evidence list. See
    ADR-0002: a real purge/retention feature is deliberately out of
    scope, not an incidental side effect of this endpoint."""
    cycle, _result = _get_cycle_and_result(db, cycle_id, result_id)
    _require_unlocked(cycle)
    item = _get_evidence(db, evidence_id, result_id)
    item.status = "ARCHIVED"
    db.commit()
    db.refresh(item)
    return item


@router.get("/{evidence_id}/annotations", response_model=list[schemas.AnnotationRevisionOut])
def list_annotations(slug: str, cycle_id: int, result_id: int, evidence_id: int, db: Session = Depends(get_project_db)):
    _get_cycle_and_result(db, cycle_id, result_id)
    _get_evidence(db, evidence_id, result_id)
    return (
        db.query(models.EvidenceRevision)
        .filter(models.EvidenceRevision.evidence_id == evidence_id)
        .order_by(models.EvidenceRevision.revision_no)
        .all()
    )


@router.post("/{evidence_id}/annotations", response_model=schemas.AnnotationRevisionOut)
def create_annotation(
    slug: str,
    cycle_id: int,
    result_id: int,
    evidence_id: int,
    payload: schemas.AnnotationRevisionCreate,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(require_tester),
):
    cycle, _result = _get_cycle_and_result(db, cycle_id, result_id)
    _require_unlocked(cycle)
    item = _get_evidence(db, evidence_id, result_id)

    item.current_revision_no += 1
    revision = models.EvidenceRevision(
        evidence_id=evidence_id,
        revision_no=item.current_revision_no,
        annotation_json=payload.annotation_json,
        change_summary=payload.change_summary,
        created_by=user.email,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision
