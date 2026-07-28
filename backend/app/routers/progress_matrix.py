"""Progress Matrix (予定実績表) endpoints.

RBAC follows the Gantt's convention, which this view is the sibling of: any
logged-in role can read the matrix (client_viewer included — it's a
progress-reporting view), only internal roles can set plan dates.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import activity, business_day, models, progress_matrix, schemas
from ..auth import get_current_user, require_internal
from ..database import get_master_db, get_project_db
from ..workflow_definitions import PROGRESS_ENTITY_TYPES, PROGRESS_TRIGGER_STATUS

router = APIRouter(prefix="/api/{slug}", tags=["progress-matrix"], dependencies=[Depends(get_current_user)])

# The board flavours are accepted as entity_type values too, so the UI's
# "Issue / Incident / Backlog" filter chips map straight onto the API.
BOARD_FLAVOURS = {"issue", "incident", "backlog"}


def _parse_entity_types(raw: Optional[list[str]]) -> tuple[list[str], set[str]]:
    """Returns (entity types to query, board flavours to keep). Defaults to
    everything the trigger table knows about."""
    if not raw:
        return list(PROGRESS_ENTITY_TYPES), set()
    requested = {v.strip().lower() for part in raw for v in part.split(",") if v.strip()}
    flavours = requested & BOARD_FLAVOURS
    types = [t for t in PROGRESS_ENTITY_TYPES if t in requested]
    if flavours and "board_item" not in types:
        types.append("board_item")
    unknown = requested - set(PROGRESS_ENTITY_TYPES) - BOARD_FLAVOURS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity_type(s): {', '.join(sorted(unknown))}. "
            f"Allowed: {', '.join(PROGRESS_ENTITY_TYPES)}, {', '.join(sorted(BOARD_FLAVOURS))}",
        )
    if not types:
        raise HTTPException(status_code=400, detail="No valid entity_type requested")
    return types, flavours


@router.get("/progress-matrix")
def get_progress_matrix(
    slug: str,
    entity_type: Optional[list[str]] = Query(None, description="task|function|board_item|issue|incident|backlog; repeatable or comma-separated"),
    phase: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    types, flavours = _parse_entity_types(entity_type)
    return progress_matrix.build_progress_matrix(
        slug=slug,
        db=db,
        master_db=master_db,
        entity_types=types,
        phase=phase,
        owner=owner,
        date_from=date_from,
        date_to=date_to,
        board_flavours=flavours or None,
    )


@router.get("/progress-matrix/calendar")
def get_calendar(
    slug: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    master_db: Session = Depends(get_master_db),
):
    """One row per day in the window: weekday letter, whether it's a business
    day, and the holiday name if there is one.

    Served from the backend rather than computed in the browser so the matrix
    greys out exactly the same days the Thai Business-day Engine skips when it
    counts a delay — the shading and the arithmetic cannot disagree.
    """
    if date_to < date_from:
        raise HTTPException(status_code=400, detail="'to' cannot be before 'from'")
    if (date_to - date_from).days > 400:
        raise HTTPException(status_code=400, detail="Range too wide — 400 days maximum")

    holidays = {
        h.holiday_date: h
        for h in master_db.query(models.ThaiHoliday)
        .filter(models.ThaiHoliday.holiday_date >= date_from, models.ThaiHoliday.holiday_date <= date_to)
        .all()
    }

    days = []
    cursor = date_from
    while cursor <= date_to:
        holiday = holidays.get(cursor)
        days.append(
            {
                "date": cursor.isoformat(),
                "day": cursor.day,
                "month": cursor.strftime("%b %Y"),
                "weekday": "MTWTFSS"[cursor.weekday()],
                "is_weekend": cursor.weekday() >= 5,
                "is_holiday": holiday is not None,
                "holiday_name": (holiday.name_en or holiday.name_th) if holiday else None,
                "is_business_day": business_day.is_business_day(cursor, master_db),
            }
        )
        cursor += timedelta(days=1)
    return {"from": date_from.isoformat(), "to": date_to.isoformat(), "today": date.today().isoformat(), "days": days}


@router.get("/progress-matrix/legend")
def get_legend(slug: str):
    """The symbol table, served from the backend so the on-screen legend and
    the rendering rules can't drift apart."""
    return {
        "symbols": [
            {"symbol": "PS", "meaning": "Plan Start"},
            {"symbol": "PR", "meaning": "Plan Result (planned finish)"},
            {"symbol": "RS", "meaning": "Result Start (actually started)"},
            {"symbol": "R", "meaning": "Result (actually finished)"},
            {"symbol": "PSR", "meaning": "Plan Start + Plan Result on the same day"},
            {"symbol": "RSR", "meaning": "Result Start + Result on the same day"},
            {"symbol": "PS/RS", "meaning": "A plan marker and an actual marker sharing one day"},
        ],
        "markers": [
            {
                "style": "solid",
                "meaning": "Actual date derived from a status change in the activity log",
            },
            {
                "style": "dashed",
                "meaning": "Actual date entered by hand — not derived from the activity log",
            },
            {
                "style": "conflict",
                "meaning": "A hand-entered date disagrees with what the log recorded",
            },
        ],
        "trigger_status": PROGRESS_TRIGGER_STATUS,
    }


@router.put("/plan-dates", response_model=schemas.PlanDatesOut)
def set_plan_dates(
    slug: str,
    payload: schemas.PlanDatesRequest,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    if payload.baseline_start and payload.baseline_end and payload.baseline_end < payload.baseline_start:
        raise HTTPException(status_code=400, detail="baseline_end cannot be before baseline_start")
    if payload.baseline_start is None and payload.baseline_end is None:
        raise HTTPException(status_code=400, detail="Provide baseline_start and/or baseline_end")

    item = progress_matrix.upsert_plan_dates(
        db, payload.entity_type, payload.entity_id, payload.baseline_start, payload.baseline_end
    )
    if item is None:
        raise HTTPException(status_code=404, detail=f"{payload.entity_type} {payload.entity_id} not found")
    return schemas.PlanDatesOut(
        gantt_item_id=item.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        baseline_start=item.baseline_start,
        baseline_end=item.baseline_end,
    )


# ---------- manual actual (RS/R) overrides ----------
#
# The audit entry these write uses field_changed="actual_date_override", NOT
# "status". That matters: compute_actual_dates only ever reads rows where
# field_changed == "status", so an override can never be laundered into
# looking like a real status change and come back out as a derived date. The
# two layers stay separable forever.
OVERRIDE_LOG_FIELD = "actual_date_override"


def _log_override_change(db: Session, entity_type: str, entity_id: int, old: str, new: str, by: Optional[str]):
    activity.log_change(db, entity_type, entity_id, OVERRIDE_LOG_FIELD, old, new, by)
    db.commit()


def _describe(row) -> str:
    if row is None:
        return "none"
    start = row.actual_start_override.isoformat() if row.actual_start_override else "-"
    end = row.actual_end_override.isoformat() if row.actual_end_override else "-"
    return f"start={start} end={end}"


@router.get("/actual-overrides/{entity_type}/{entity_id}")
def get_actual_override(
    slug: str,
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_project_db),
):
    """All three layers for one entity, so the editor can show what the log
    derived alongside whatever was typed in."""
    if entity_type not in PROGRESS_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {PROGRESS_ENTITY_TYPES}")
    detail = progress_matrix.compute_actual_dates(db, entity_type, entity_id)
    return {
        key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in detail.items()
    }


@router.put("/actual-overrides", response_model=schemas.ActualOverrideOut)
def set_actual_override(
    slug: str,
    payload: schemas.ActualOverrideRequest,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    if (
        payload.actual_start_override
        and payload.actual_end_override
        and payload.actual_end_override < payload.actual_start_override
    ):
        raise HTTPException(status_code=400, detail="actual_end cannot be before actual_start")
    if payload.actual_start_override is None and payload.actual_end_override is None:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one date, or DELETE the override to fall back to the activity log.",
        )

    existing = (
        db.query(models.ProgressActualOverride)
        .filter(
            models.ProgressActualOverride.entity_type == payload.entity_type,
            models.ProgressActualOverride.entity_id == payload.entity_id,
        )
        .first()
    )
    before = _describe(existing)

    row = progress_matrix.upsert_actual_override(
        db,
        payload.entity_type,
        payload.entity_id,
        payload.actual_start_override,
        payload.actual_end_override,
        payload.reason,
        payload.created_by,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"{payload.entity_type} {payload.entity_id} not found")

    _log_override_change(db, payload.entity_type, payload.entity_id, before, _describe(row), payload.created_by)
    return row


@router.delete("/actual-overrides/{entity_type}/{entity_id}")
def clear_actual_override(
    slug: str,
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    if entity_type not in PROGRESS_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {PROGRESS_ENTITY_TYPES}")
    existing = (
        db.query(models.ProgressActualOverride)
        .filter(
            models.ProgressActualOverride.entity_type == entity_type,
            models.ProgressActualOverride.entity_id == entity_id,
        )
        .first()
    )
    before = _describe(existing)
    if not progress_matrix.delete_actual_override(db, entity_type, entity_id):
        raise HTTPException(status_code=404, detail="No override set for this item")
    _log_override_change(db, entity_type, entity_id, before, "none", None)
    return {"ok": True}


@router.get("/plan-dates/{entity_type}/{entity_id}", response_model=schemas.PlanDatesOut | None)
def get_plan_dates(
    slug: str,
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_project_db),
):
    """Lets the "Set Plan Dates" control open pre-filled with whatever is
    already on record."""
    if entity_type not in PROGRESS_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {PROGRESS_ENTITY_TYPES}")
    item = (
        db.query(models.GanttItem)
        .filter(
            models.GanttItem.linked_entity_type == entity_type,
            models.GanttItem.linked_entity_id == entity_id,
        )
        .order_by(models.GanttItem.id)
        .first()
    )
    if item is None:
        return None
    return schemas.PlanDatesOut(
        gantt_item_id=item.id,
        entity_type=entity_type,
        entity_id=entity_id,
        baseline_start=item.baseline_start,
        baseline_end=item.baseline_end,
    )
