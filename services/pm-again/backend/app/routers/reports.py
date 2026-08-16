import json
from datetime import date as date_cls, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_project_db, get_master_db
from ..reports import daily, weekly, monthly, phase_closure
from ..reports.style import workbook_response
from fastapi import HTTPException

from ..auth import get_current_user, require_internal
from ..reports.monthly import AUDIENCES

# Baseline: must be logged in. Daily/Weekly/Monthly (internal ops detail —
# overdue tasks, etc.) get an extra require_internal below; Phase Closure
# stays open to client_viewer since it's explicitly the client-facing report
# per its own spec description.
router = APIRouter(prefix="/api/{slug}/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


def _log(db: Session, report_type: str, params: dict, generated_by: str | None):
    db.add(
        models.ReportGenerationLog(
            report_type=report_type,
            params_json=json.dumps(params, default=str),
            generated_by=generated_by,
        )
    )
    db.commit()


@router.get("/daily")
def report_daily(
    slug: str,
    date: date_cls | None = Query(None),
    generated_by: str | None = Query(None),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    target_date = date or datetime.utcnow().date()
    wb = daily.generate(slug, target_date, db, master_db)
    _log(db, "daily", {"date": target_date}, generated_by)
    return workbook_response(wb, f"{slug}-daily-{target_date.isoformat()}.xlsx")


@router.get("/weekly")
def report_weekly(
    slug: str,
    week_start: date_cls = Query(...),
    generated_by: str | None = Query(None),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    wb = weekly.generate(slug, week_start, db, master_db)
    _log(db, "weekly", {"week_start": week_start}, generated_by)
    return workbook_response(wb, f"{slug}-weekly-{week_start.isoformat()}.xlsx")


@router.get("/monthly")
def report_monthly(
    slug: str,
    month: str = Query(..., description="YYYY-MM"),
    audience: str = Query("internal", description="internal | client"),
    generated_by: str | None = Query(None),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_internal),
):
    if audience not in AUDIENCES:
        raise HTTPException(status_code=400, detail=f"audience must be one of {AUDIENCES}")
    try:
        year_str, month_str = month.split("-")
        year, month_number = int(year_str), int(month_str)
        if not 1 <= month_number <= 12:
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format, e.g. 2026-07")

    wb = monthly.generate(slug, year, month_number, db, master_db, audience)
    # The audience is logged too — which copy went out matters as much as when.
    _log(db, "monthly", {"month": month, "audience": audience}, generated_by)
    return workbook_response(wb, f"{slug}-monthly-{month}-{audience}.xlsx")


@router.get("/phase-closure")
def report_phase_closure(
    slug: str,
    phase_code: int = Query(...),
    generated_by: str | None = Query(None),
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    wb = phase_closure.generate(slug, phase_code, db, master_db)
    _log(db, "phase_closure", {"phase_code": phase_code}, generated_by)
    return workbook_response(wb, f"{slug}-phase-closure-{phase_code}.xlsx")
