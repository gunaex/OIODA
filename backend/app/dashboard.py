from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models
from .database import open_project_session
from .routers.projects import MANDATORY_COLUMN_BY_CATEGORY
from .resource_utils import compute_utilization

# "Critical" priority tier referenced by the RAG spec maps to Task.priority
# == "High" (the highest of the Low/Med/High scale this app actually has).
# The spec's Amber rule explicitly carves out "overdue task ที่ไม่ critical"
# (non-critical overdue tasks), which implies overdue *critical* tasks
# belong at a higher severity than Amber even though the spec's Red bullet
# doesn't name them directly — folded into Red here rather than left
# uncovered by any tier.
CRITICAL_TASK_PRIORITY = "High"


def _phase_completion(documents: list[models.Document]) -> list[dict]:
    totals: dict[str, int] = {}
    confirmed: dict[str, int] = {}
    for d in documents:
        phase = d.phase or "Unspecified"
        totals[phase] = totals.get(phase, 0) + 1
        if d.status == "Confirmed":
            confirmed[phase] = confirmed.get(phase, 0) + 1
    return [
        {
            "phase": phase,
            "confirmed": confirmed.get(phase, 0),
            "total": total,
            "percent": round(100 * confirmed.get(phase, 0) / total) if total else 0,
        }
        for phase, total in sorted(totals.items())
    ]


def compute_phase_end_dates(gantt_items: list[models.GanttItem]) -> dict[str, date]:
    """Latest Gantt end_date per phase — the closest available proxy for a
    phase's deadline, since neither documents nor phases have a due_date of
    their own. Shared with slippage.py's document-based signal, which needs
    the exact same proxy."""
    result: dict[str, date] = {}
    for g in gantt_items:
        if not g.phase:
            continue
        result[g.phase] = max(result.get(g.phase, g.end_date), g.end_date)
    return result


def _overdue_mandatory_doc_count(
    project: models.Project | None,
    documents: list[models.Document],
    gantt_items: list[models.GanttItem],
    master_db: Session,
    today: date,
) -> int:
    """Documents have no due_date of their own — the owning phase's latest
    Gantt end_date is used as the closest available proxy for "when this
    mandatory doc was due", per the same phase/doc_code join the Phase
    Closure report already uses."""
    column_name = MANDATORY_COLUMN_BY_CATEGORY.get(project.project_category) if project else None
    if not column_name:
        return 0

    phase_due_dates = compute_phase_end_dates(gantt_items)

    templates = (
        master_db.query(models.DocumentTemplate)
        .filter(getattr(models.DocumentTemplate, column_name) == "M")
        .all()
    )
    docs_by_code = {d.doc_code: d for d in documents}

    count = 0
    for t in templates:
        phase_due = phase_due_dates.get(t.phase_name)
        if not phase_due or phase_due >= today:
            continue
        doc = docs_by_code.get(str(t.doc_code))
        if not doc or doc.status != "Confirmed":
            count += 1
    return count


def build_project_dashboard(slug: str, db: Session, master_db: Session) -> dict:
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    today = date.today()

    documents = db.query(models.Document).all()
    phase_completion = _phase_completion(documents)

    tasks = db.query(models.Task).filter(models.Task.due_date.isnot(None), models.Task.due_date < today, models.Task.status != "Done").all()
    overdue_critical_tasks = [t for t in tasks if t.priority == CRITICAL_TASK_PRIORITY]
    overdue_other_tasks = [t for t in tasks if t.priority != CRITICAL_TASK_PRIORITY]

    gantt_items = db.query(models.GanttItem).all()
    upcoming_milestones = sorted(
        (g for g in gantt_items if g.is_milestone and g.end_date >= today),
        key=lambda g: g.end_date,
    )[:5]

    overdue_mandatory_docs = _overdue_mandatory_doc_count(project, documents, gantt_items, master_db, today)

    board_items = db.query(models.BoardItem).filter(models.BoardItem.item_type.in_(["issue", "incident"])).all()
    open_items = [b for b in board_items if b.status not in ("Resolved", "Closed", "Promoted")]
    open_by_severity: dict[str, int] = {}
    for b in open_items:
        sev = b.severity or "Unspecified"
        open_by_severity[sev] = open_by_severity.get(sev, 0) + 1
    open_critical_incidents = sum(1 for b in open_items if b.item_type == "incident" and b.severity == "Critical")

    allocations_today = (
        master_db.query(models.ResourceAllocation)
        .filter(
            models.ResourceAllocation.project_slug == slug,
            models.ResourceAllocation.start_date <= today,
            models.ResourceAllocation.end_date >= today,
        )
        .all()
    )
    resource_ids = {a.resource_id for a in allocations_today}
    all_current_allocations = (
        master_db.query(models.ResourceAllocation)
        .filter(
            models.ResourceAllocation.resource_id.in_(resource_ids),
            models.ResourceAllocation.start_date <= today,
            models.ResourceAllocation.end_date >= today,
        )
        .all()
        if resource_ids
        else []
    )
    totals_by_resource: dict[int, int] = {}
    for a in all_current_allocations:
        totals_by_resource[a.resource_id] = totals_by_resource.get(a.resource_id, 0) + a.allocation_percent
    over_allocated_resource_ids = [rid for rid in resource_ids if totals_by_resource.get(rid, 0) > 100]
    resource_utilization = [
        {"resource_id": rid, "total_percent_this_project": sum(a.allocation_percent for a in allocations_today if a.resource_id == rid), "total_percent_all_projects": totals_by_resource.get(rid, 0)}
        for rid in resource_ids
    ]

    if overdue_mandatory_docs > 0 or open_critical_incidents > 0 or overdue_critical_tasks:
        rag = "red"
    elif overdue_other_tasks or over_allocated_resource_ids:
        rag = "amber"
    else:
        rag = "green"

    return {
        "slug": slug,
        "rag": rag,
        "phase_completion": phase_completion,
        "overdue_task_count": len(tasks),
        "upcoming_milestones": [
            {"id": m.id, "name": m.name, "end_date": m.end_date.isoformat(), "phase": m.phase}
            for m in upcoming_milestones
        ],
        "open_issues_by_severity": open_by_severity,
        "resource_utilization": resource_utilization,
        "overdue_mandatory_docs": overdue_mandatory_docs,
        "open_critical_incidents": open_critical_incidents,
    }


def build_global_dashboard(master_db: Session) -> dict:
    projects = master_db.query(models.Project).order_by(models.Project.name).all()
    project_summaries = []
    for p in projects:
        db = open_project_session(p.slug)
        try:
            data = build_project_dashboard(p.slug, db, master_db)
        finally:
            db.close()
        project_summaries.append(
            {
                "slug": p.slug,
                "name": p.name,
                "rag": data["rag"],
                "overdue_task_count": data["overdue_task_count"],
                "open_issue_count": sum(data["open_issues_by_severity"].values()),
            }
        )

    today = date.today()
    from_date = today - timedelta(days=today.weekday())  # this week's Monday
    to_date = from_date + timedelta(days=27)  # 4-week heatmap window

    return {
        "projects": project_summaries,
        "utilization_heatmap": compute_utilization(master_db, from_date, to_date),
    }
