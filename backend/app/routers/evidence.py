import hashlib
import os
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, project_evidence_dir
from ..evidence_utils import sniff_image, MAX_EVIDENCE_SIZE_BYTES
from ..auth import get_current_user, require_tester, require_admin

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
    user: models.User = Depends(require_tester),
):
    cycle, result = _get_cycle_and_result(db, cycle_id, result_id)
    _require_unlocked(cycle)

    if evidence_type not in models.EVIDENCE_TYPES:
        raise HTTPException(status_code=400, detail=f"evidence_type must be one of {models.EVIDENCE_TYPES}")

    content = await file.read()
    if len(content) > MAX_EVIDENCE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"Evidence file exceeds the {MAX_EVIDENCE_SIZE_BYTES // (1024*1024)}MB limit")

    sniffed = sniff_image(content)
    if not sniffed:
        raise HTTPException(status_code=400, detail="File is not a recognized image (PNG/JPEG/GIF/WEBP signature check failed)")
    content_type, ext = sniffed

    sha256 = hashlib.sha256(content).hexdigest()
    result_dir = os.path.join(project_evidence_dir(slug), str(result_id))
    os.makedirs(result_dir, exist_ok=True)
    # Stored filename is never the client-supplied name — sha256-derived,
    # so a malicious/garbage filename can't reach the filesystem path.
    stored_path = os.path.join(result_dir, f"{sha256}.{ext}")
    if not os.path.exists(stored_path):
        with open(stored_path, "wb") as f:
            f.write(content)

    safe_original_filename = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "evidence")[:255]

    item = models.EvidenceItem(
        cycle_id=cycle_id,
        cycle_test_result_id=result_id,
        evidence_type=evidence_type,
        original_path=stored_path,
        original_filename=safe_original_filename,
        original_content_type=content_type,
        original_size_bytes=len(content),
        original_sha256=sha256,
        caption=caption,
        target_url=target_url,
        captured_by=user.email,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{evidence_id}", response_model=schemas.EvidenceItemOut)
def get_evidence(slug: str, cycle_id: int, result_id: int, evidence_id: int, db: Session = Depends(get_project_db)):
    _get_cycle_and_result(db, cycle_id, result_id)
    return _get_evidence(db, evidence_id, result_id)


@router.get("/{evidence_id}/original")
def download_evidence_original(
    slug: str, cycle_id: int, result_id: int, evidence_id: int, db: Session = Depends(get_project_db)
):
    _get_cycle_and_result(db, cycle_id, result_id)
    item = _get_evidence(db, evidence_id, result_id)
    if not os.path.exists(item.original_path):
        raise HTTPException(status_code=404, detail="Original file missing from storage")
    return FileResponse(item.original_path, media_type=item.original_content_type, filename=item.original_filename)


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
    """Archive, never delete — the original file stays on disk untouched;
    this only hides it from the default (ACTIVE) evidence list."""
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
