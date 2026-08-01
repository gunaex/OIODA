from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..activity import log_change
from ..auth import get_current_user, require_tester, require_admin

router = APIRouter(prefix="/api/{slug}/cycles", tags=["cycles"], dependencies=[Depends(get_current_user)])


def _result_counts(db: Session, cycle_id: int) -> schemas.ResultCounts:
    rows = (
        db.query(models.CycleTestResult.status, models.CycleTestResult.id)
        .filter(models.CycleTestResult.cycle_id == cycle_id)
        .all()
    )
    counts = schemas.ResultCounts()
    for status, _id in rows:
        setattr(counts, status, getattr(counts, status) + 1)
    return counts


def _to_out(db: Session, cycle: models.TestCycle) -> schemas.TestCycleOut:
    out = schemas.TestCycleOut.model_validate(cycle)
    out.result_counts = _result_counts(db, cycle.id)
    return out


@router.get("", response_model=list[schemas.TestCycleOut])
def list_cycles(slug: str, db: Session = Depends(get_project_db)):
    cycles = db.query(models.TestCycle).order_by(models.TestCycle.created_at.desc()).all()
    return [_to_out(db, c) for c in cycles]


@router.post("", response_model=schemas.TestCycleOut)
def create_cycle(
    slug: str,
    payload: schemas.TestCycleCreate,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(require_tester),
):
    revision = db.query(models.ScriptRevision).filter(models.ScriptRevision.id == payload.script_revision_id).first()
    if not revision:
        raise HTTPException(status_code=404, detail="Script revision not found")
    if revision.suite_id != payload.suite_id:
        raise HTTPException(status_code=400, detail="script_revision_id does not belong to suite_id")
    if revision.status != "PUBLISHED":
        raise HTTPException(status_code=400, detail=f"A cycle must reference a PUBLISHED revision (current status: {revision.status})")

    cases = db.query(models.TestCase).filter(models.TestCase.revision_id == revision.id).all()
    if not cases:
        raise HTTPException(status_code=400, detail="Cannot create a cycle from a revision with no test cases")

    cycle = models.TestCycle(
        suite_id=payload.suite_id,
        script_revision_id=payload.script_revision_id,
        cycle_code=payload.cycle_code,
        name=payload.name,
        environment=payload.environment,
        release_version=payload.release_version,
        target_base_url=payload.target_base_url,
        status="READY",
        require_evidence_for_pass=payload.require_evidence_for_pass,
        created_by=user.email,
    )
    db.add(cycle)
    db.flush()  # assigns cycle.id before creating result rows

    # Snapshot: one NOT_RUN result per case in *this exact* revision.
    # Never re-derived later — a subsequent publish of a newer revision
    # must never change this cycle (rebuild prompt §12).
    for case in cases:
        db.add(models.CycleTestResult(cycle_id=cycle.id, test_case_id=case.id, status="NOT_RUN"))

    db.commit()
    db.refresh(cycle)
    return _to_out(db, cycle)


@router.get("/{cycle_id}", response_model=schemas.TestCycleOut)
def get_cycle(slug: str, cycle_id: int, db: Session = Depends(get_project_db)):
    cycle = db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return _to_out(db, cycle)


@router.put("/{cycle_id}", response_model=schemas.TestCycleOut)
def update_cycle(
    slug: str,
    cycle_id: int,
    payload: schemas.TestCycleUpdate,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(require_tester),
):
    cycle = db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status == "LOCKED":
        raise HTTPException(status_code=400, detail="Cycle is LOCKED — use /reopen (admin) before editing")

    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        if updates["status"] == "LOCKED":
            raise HTTPException(status_code=400, detail="Use POST /cycles/{id}/lock to lock a cycle")
        if updates["status"] not in models.CYCLE_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {models.CYCLE_STATUSES}")

    for key, value in updates.items():
        setattr(cycle, key, value)
    db.commit()
    db.refresh(cycle)
    return _to_out(db, cycle)


@router.post("/{cycle_id}/lock", response_model=schemas.TestCycleOut)
def lock_cycle(
    slug: str,
    cycle_id: int,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(require_admin),
):
    cycle = db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status == "LOCKED":
        raise HTTPException(status_code=400, detail="Cycle is already locked")

    cycle.status = "LOCKED"
    cycle.locked_at = datetime.utcnow()
    cycle.locked_by = user.email
    if not cycle.finished_at:
        cycle.finished_at = cycle.locked_at
    db.commit()
    db.refresh(cycle)
    return _to_out(db, cycle)


@router.post("/{cycle_id}/reopen", response_model=schemas.TestCycleOut)
def reopen_cycle(
    slug: str,
    cycle_id: int,
    payload: schemas.CycleReopenRequest,
    db: Session = Depends(get_project_db),
    user: models.User = Depends(require_admin),
):
    """Administrative reopen — requires a reason and is audit-logged
    (rebuild prompt §11: "any administrative reopen must require reason
    and append an audit record")."""
    cycle = db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.status != "LOCKED":
        raise HTTPException(status_code=400, detail="Only a LOCKED cycle can be reopened")
    if not payload.reason.strip():
        raise HTTPException(status_code=400, detail="A reason is required to reopen a locked cycle")

    log_change(db, "cycle", cycle_id, "status", "LOCKED", f"IN_PROGRESS (reopened: {payload.reason})", user.email)
    cycle.status = "IN_PROGRESS"
    cycle.locked_at = None
    cycle.locked_by = None
    cycle.finished_at = None
    db.commit()
    db.refresh(cycle)
    return _to_out(db, cycle)
