from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models
from .dashboard import compute_phase_end_dates
from .routers.projects import MANDATORY_COLUMN_BY_CATEGORY

GAP_THRESHOLD = 20  # percentage points — elapsed_pct - progress
DOC_RATIO_THRESHOLD = 1.0  # docs remaining per day left
MIN_HISTORY_SAMPLES = 3  # per spec: don't predict from too little data


def _gantt_gap(g: models.GanttItem, today: date) -> float | None:
    """elapsed_pct - progress, per the spec's formula (uses start_date, not
    baseline_start — baseline_end is the only baseline field the formula
    actually calls for). None if the item can't be assessed (still not
    started, or a zero-length baseline window)."""
    if not g.baseline_end or g.start_date >= g.baseline_end:
        return None
    if today < g.start_date:
        return None
    elapsed_pct = (today - g.start_date).days / (g.baseline_end - g.start_date).days * 100
    return elapsed_pct - (g.progress or 0)


def compute_task_slippage(db: Session) -> list[dict]:
    """Gantt-based signal (spec 1.1). Milestones are excluded — zero-length
    by nature, "elapsed time vs progress" doesn't apply to them."""
    today = date.today()
    gantt_items = (
        db.query(models.GanttItem)
        .filter(models.GanttItem.is_milestone == False, models.GanttItem.progress < 100)  # noqa: E712
        .all()
    )

    avg_delay_by_phase = _historical_avg_delay_by_phase(db)

    results = []
    for g in gantt_items:
        gap = _gantt_gap(g, today)

        # Already past its own baseline deadline and still not done — worse
        # than merely "at risk", same escalation the doc-signal uses for
        # "overdue". Not spelled out under 1.1 in the spec text, but the
        # flag enum (on_track/at_risk/overdue) and the RAG spec's own
        # doc-signal precedent both imply it belongs here.
        if g.baseline_end and today > g.baseline_end:
            flag = "overdue"
        elif gap is None or gap <= GAP_THRESHOLD:
            continue
        else:
            flag = "at_risk"

        expected_completion = None
        if g.phase and g.baseline_end:
            avg_delay = avg_delay_by_phase.get(g.phase)
            if avg_delay is not None:
                expected_completion = g.baseline_end + timedelta(days=round(avg_delay))

        results.append(
            {
                "id": g.id,
                "name": g.name,
                "phase": g.phase,
                "flag": flag,
                "gap_score": round(gap, 1) if gap is not None else None,
                "progress": g.progress,
                "baseline_end": g.baseline_end.isoformat() if g.baseline_end else None,
                "expected_completion": expected_completion.isoformat() if expected_completion else None,
            }
        )

    results.sort(key=lambda r: r["gap_score"] if r["gap_score"] is not None else 0, reverse=True)
    return results


def _historical_avg_delay_by_phase(db: Session) -> dict[str, float]:
    """Spec 1.3: average(actual_end - baseline_end) per phase, over
    completed Gantt items (progress == 100 stands in for "done" — GanttItem
    has no separate status column). Only returned for phases with at least
    MIN_HISTORY_SAMPLES data points; thin data isn't predictive."""
    done_items = (
        db.query(models.GanttItem)
        .filter(models.GanttItem.progress == 100, models.GanttItem.baseline_end.isnot(None))
        .all()
    )
    delays_by_phase: dict[str, list[int]] = {}
    for g in done_items:
        if not g.phase:
            continue
        delays_by_phase.setdefault(g.phase, []).append((g.end_date - g.baseline_end).days)

    return {
        phase: sum(delays) / len(delays)
        for phase, delays in delays_by_phase.items()
        if len(delays) >= MIN_HISTORY_SAMPLES
    }


def compute_phase_slippage(project: models.Project | None, db: Session, master_db: Session) -> list[dict]:
    """Document-based signal (spec 1.2) — reuses the same mandatory-doc /
    phase-deadline join as the RAG logic and Phase Closure report."""
    today = date.today()
    column_name = MANDATORY_COLUMN_BY_CATEGORY.get(project.project_category) if project else None
    if not column_name:
        return []

    documents = db.query(models.Document).all()
    docs_by_code = {d.doc_code: d for d in documents}
    gantt_items = db.query(models.GanttItem).all()
    phase_due_dates = compute_phase_end_dates(gantt_items)

    templates = (
        master_db.query(models.DocumentTemplate)
        .filter(getattr(models.DocumentTemplate, column_name) == "M")
        .all()
    )
    remaining_by_phase: dict[str, int] = {}
    for t in templates:
        if not t.phase_name:
            continue
        doc = docs_by_code.get(str(t.doc_code))
        if not doc or doc.status != "Confirmed":
            remaining_by_phase[t.phase_name] = remaining_by_phase.get(t.phase_name, 0) + 1

    results = []
    for phase, docs_remaining in remaining_by_phase.items():
        phase_due = phase_due_dates.get(phase)
        if not phase_due:
            continue  # can't assess without a phase deadline
        days_left = (phase_due - today).days

        if days_left <= 0 and docs_remaining > 0:
            flag = "overdue"
        elif days_left > 0 and (docs_remaining / days_left) > DOC_RATIO_THRESHOLD:
            flag = "at_risk"
        else:
            continue

        results.append(
            {
                "phase": phase,
                "flag": flag,
                "docs_remaining": docs_remaining,
                "days_left_in_phase": days_left,
                "ratio": round(docs_remaining / days_left, 2) if days_left > 0 else None,
            }
        )

    results.sort(key=lambda r: (r["flag"] != "overdue", -(r["docs_remaining"])))
    return results


def compute_slippage_summary(project: models.Project | None, db: Session, master_db: Session) -> dict:
    return {
        "tasks": compute_task_slippage(db),
        "phases": compute_phase_slippage(project, db, master_db),
    }
