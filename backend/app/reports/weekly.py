from datetime import date, datetime, timedelta

from openpyxl import Workbook
from sqlalchemy.orm import Session

from .. import models
from .style import write_title, write_section, write_table

DETAIL_COLUMNS = ["entity_type", "entity_id", "old_status", "new_status", "changed_by", "changed_at"]
SUMMARY_COLUMNS = [
    "phase",
    "functions_total",
    "functions_done",
    "functions_pct",
    "tasks_total",
    "tasks_done",
    "tasks_pct",
    "documents_total",
    "documents_confirmed",
    "documents_pct",
]

FUNCTION_DONE_STATUSES = ("Confirmed", "Done")
TASK_DONE_STATUSES = ("Done",)
DOCUMENT_DONE_STATUSES = ("Confirmed",)


def _pct(done: int, total: int) -> str:
    if total == 0:
        return "-"
    return f"{round(done / total * 100)}%"


def generate(slug: str, week_start: date, db: Session) -> Workbook:
    week_end = week_start + timedelta(days=7)
    start_dt = datetime.combine(week_start, datetime.min.time())
    end_dt = datetime.combine(week_end, datetime.min.time())

    changes = (
        db.query(models.ActivityLog)
        .filter(
            models.ActivityLog.field_changed == "status",
            models.ActivityLog.entity_type.in_(["task", "function", "document"]),
            models.ActivityLog.changed_at >= start_dt,
            models.ActivityLog.changed_at < end_dt,
        )
        .order_by(models.ActivityLog.changed_at)
        .all()
    )
    detail_rows = [
        {
            "entity_type": c.entity_type,
            "entity_id": c.entity_id,
            "old_status": c.old_value,
            "new_status": c.new_value,
            "changed_by": c.changed_by,
            "changed_at": c.changed_at.strftime("%Y-%m-%d %H:%M"),
        }
        for c in changes
    ]

    functions = db.query(models.Function).all()
    tasks = db.query(models.Task).all()
    documents = db.query(models.Document).all()

    phases = sorted(
        {f.phase for f in functions if f.phase}
        | {t.phase for t in tasks if t.phase}
        | {d.phase for d in documents if d.phase},
        key=models.phase_sort_key,
    )

    summary_rows = []
    for phase in phases:
        f_in_phase = [f for f in functions if f.phase == phase]
        t_in_phase = [t for t in tasks if t.phase == phase]
        d_in_phase = [d for d in documents if d.phase == phase]
        f_done = sum(1 for f in f_in_phase if f.status in FUNCTION_DONE_STATUSES)
        t_done = sum(1 for t in t_in_phase if t.status in TASK_DONE_STATUSES)
        d_done = sum(1 for d in d_in_phase if d.status in DOCUMENT_DONE_STATUSES)
        summary_rows.append(
            {
                "phase": phase,
                "functions_total": len(f_in_phase),
                "functions_done": f_done,
                "functions_pct": _pct(f_done, len(f_in_phase)),
                "tasks_total": len(t_in_phase),
                "tasks_done": t_done,
                "tasks_pct": _pct(t_done, len(t_in_phase)),
                "documents_total": len(d_in_phase),
                "documents_confirmed": d_done,
                "documents_pct": _pct(d_done, len(d_in_phase)),
            }
        )

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Progress Summary"
    row = write_title(ws1, 1, f"Weekly Report — {slug} — {week_start.isoformat()} to {(week_end - timedelta(days=1)).isoformat()}")
    row = write_section(ws1, row, "% Completion by Phase")
    write_table(ws1, row, SUMMARY_COLUMNS, summary_rows)

    ws2 = wb.create_sheet("Detail Log")
    row2 = write_title(ws2, 1, "Status Changes This Week")
    write_table(ws2, row2, DETAIL_COLUMNS, detail_rows)

    return wb
