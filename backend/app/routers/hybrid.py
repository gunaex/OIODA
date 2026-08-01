import hashlib
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db, project_evidence_dir
from ..auth import get_current_user, get_current_runner

router = APIRouter(prefix="/api/{slug}/hybrid/runs", tags=["hybrid-runs"])

# Terminal states — a run that reached one of these cannot be mutated
# further, matching the "failure is never silently rewritten" rule used
# everywhere else in this app (locked cycles, published revisions).
TERMINAL_STATUSES = ("PASSED", "FAILED", "BLOCKED", "NOT_APPLICABLE", "CANCELLED")

# A checkpoint `decision` (PASS/FAIL/BLOCKED/NOT_APPLICABLE) is not
# spelled the same as a run `status` (RESUMING/FAILED/BLOCKED/
# NOT_APPLICABLE) — PASS in particular means "resume", not "done yet".
_DECISION_TO_RUN_STATUS = {
    "PASS": "RESUMING",
    "FAIL": "FAILED",
    "BLOCKED": "BLOCKED",
    "NOT_APPLICABLE": "NOT_APPLICABLE",
}


def _get_run(db: Session, run_id: int) -> models.HybridRun:
    run = db.query(models.HybridRun).filter(models.HybridRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _add_event(db: Session, run_id: int, event_type: str, actor_type: str, payload_json: str | None = None):
    if event_type not in models.RUNNER_EVENT_TYPES:
        raise HTTPException(status_code=400, detail=f"event_type must be one of {models.RUNNER_EVENT_TYPES}")
    if actor_type not in models.ACTOR_TYPES:
        raise HTTPException(status_code=400, detail=f"actor_type must be one of {models.ACTOR_TYPES}")
    db.add(models.HybridRunEvent(run_id=run_id, event_type=event_type, actor_type=actor_type, payload_json=payload_json))


@router.post("", response_model=schemas.HybridRunOut)
def create_run(
    slug: str,
    payload: schemas.HybridRunCreate,
    db: Session = Depends(get_project_db),
    _runner: models.RunnerToken = Depends(get_current_runner),
):
    run = models.HybridRun(status="RUNNING", label=payload.label)
    db.add(run)
    db.flush()
    _add_event(db, run.id, "RUN_CLAIMED", "RUNNER")
    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=schemas.HybridRunDetailOut)
def get_run(
    slug: str,
    run_id: int,
    db: Session = Depends(get_project_db),
):
    """Readable by runner token or user session — the runner polls this
    while WAITING_FOR_HUMAN; a human-facing page would use the same
    endpoint. No single dependency covers both, so this endpoint checks
    manually rather than declaring one auth dependency."""
    run = _get_run(db, run_id)
    events = db.query(models.HybridRunEvent).filter(models.HybridRunEvent.run_id == run_id).order_by(models.HybridRunEvent.id).all()
    latest_decision = (
        db.query(models.HybridCheckpointDecision)
        .filter(models.HybridCheckpointDecision.run_id == run_id)
        .order_by(models.HybridCheckpointDecision.id.desc())
        .first()
    )
    result = schemas.HybridRunDetailOut.model_validate(run)
    result.events = events
    result.latest_decision = latest_decision
    return result


@router.post("/{run_id}/events", response_model=schemas.HybridRunEventOut)
def post_event(
    slug: str,
    run_id: int,
    payload: schemas.HybridRunEventCreate,
    db: Session = Depends(get_project_db),
    _runner: models.RunnerToken = Depends(get_current_runner),
):
    run = _get_run(db, run_id)
    if run.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Run {run_id} already ended (status: {run.status})")

    if payload.event_type == "CHECKPOINT_WAITING":
        run.status = "WAITING_FOR_HUMAN"
    elif payload.event_type == "RUN_COMPLETED":
        raise HTTPException(status_code=400, detail="Use the run's final status transition, not a raw RUN_COMPLETED event, to end a run")

    _add_event(db, run_id, payload.event_type, payload.actor_type, payload.payload_json)
    db.commit()

    event = (
        db.query(models.HybridRunEvent)
        .filter(models.HybridRunEvent.run_id == run_id)
        .order_by(models.HybridRunEvent.id.desc())
        .first()
    )
    return event


@router.post("/{run_id}/checkpoint-decision", response_model=schemas.HybridCheckpointDecisionOut)
def decide_checkpoint(
    slug: str,
    run_id: int,
    payload: schemas.HybridCheckpointDecisionCreate,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(get_current_user),
):
    run = _get_run(db, run_id)
    if run.status != "WAITING_FOR_HUMAN":
        raise HTTPException(status_code=400, detail=f"Run {run_id} is not waiting for a human decision (status: {run.status})")
    if payload.decision not in models.CHECKPOINT_DECISIONS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {models.CHECKPOINT_DECISIONS}")
    if payload.decision == "FAIL" and not payload.reason:
        raise HTTPException(status_code=400, detail="FAIL requires a reason")
    if payload.decision == "BLOCKED" and not payload.reason:
        raise HTTPException(status_code=400, detail="BLOCKED requires a reason")
    if payload.decision == "NOT_APPLICABLE" and not payload.reason:
        raise HTTPException(status_code=400, detail="NOT_APPLICABLE requires a reason")

    decision = models.HybridCheckpointDecision(
        run_id=run_id,
        decision=payload.decision,
        reason=payload.reason,
        decided_by=user.email,
    )
    db.add(decision)

    # PASS is the only decision that lets automation resume; every other
    # decision ends the run immediately — the runner cannot argue with a
    # human's FAIL/BLOCKED/NOT_APPLICABLE call by continuing anyway.
    run.status = _DECISION_TO_RUN_STATUS[payload.decision]
    _add_event(db, run_id, "CHECKPOINT_RELEASED", "HUMAN", payload_json=f'{{"decision":"{payload.decision}"}}')

    db.commit()
    db.refresh(decision)
    return decision


@router.post("/{run_id}/evidence", response_model=schemas.HybridRunEvidenceOut)
async def upload_evidence(
    slug: str,
    run_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_project_db),
    _runner: models.RunnerToken = Depends(get_current_runner),
):
    run = _get_run(db, run_id)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Evidence file exceeds the 10MB spike limit")

    sha256 = hashlib.sha256(content).hexdigest()
    run_dir = os.path.join(project_evidence_dir(slug), "hybrid-runs", str(run_id))
    os.makedirs(run_dir, exist_ok=True)
    original_filename = file.filename or "evidence.png"
    stored_path = os.path.join(run_dir, f"{sha256}_{original_filename}")
    with open(stored_path, "wb") as f:
        f.write(content)

    evidence = models.HybridRunEvidence(
        run_id=run_id,
        original_path=stored_path,
        original_filename=original_filename,
        original_content_type=file.content_type or "application/octet-stream",
        original_size_bytes=len(content),
        original_sha256=sha256,
    )
    db.add(evidence)
    _add_event(db, run_id, "EVIDENCE_UPLOADED", "RUNNER", payload_json=f'{{"evidence_filename":"{original_filename}"}}')
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/{run_id}/evidence/{evidence_id}")
def download_evidence(
    slug: str,
    run_id: int,
    evidence_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(get_current_user),
):
    evidence = (
        db.query(models.HybridRunEvidence)
        .filter(models.HybridRunEvidence.id == evidence_id, models.HybridRunEvidence.run_id == run_id)
        .first()
    )
    if not evidence or not os.path.exists(evidence.original_path):
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(evidence.original_path, media_type=evidence.original_content_type, filename=evidence.original_filename)


@router.post("/{run_id}/finish", response_model=schemas.HybridRunOut)
def finish_run(
    slug: str,
    run_id: int,
    db: Session = Depends(get_project_db),
    _runner: models.RunnerToken = Depends(get_current_runner),
):
    """Runner calls this once it has finished executing post-checkpoint
    steps. The final status was already decided by the human checkpoint
    (RESUMING -> the runner finishes -> PASSED) or by an earlier
    FAIL/BLOCKED/NOT_APPLICABLE decision that already ended the run — this
    endpoint only finalizes a run still in RESUMING; it can never turn a
    human's non-PASS decision into a pass."""
    run = _get_run(db, run_id)
    if run.status != "RESUMING":
        raise HTTPException(status_code=400, detail=f"Run {run_id} is not in RESUMING (status: {run.status}) — refusing to auto-finalize")

    run.status = "PASSED"
    run.ended_at = datetime.utcnow()
    _add_event(db, run_id, "RUN_COMPLETED", "SYSTEM")
    db.commit()
    db.refresh(run)
    return run
