from datetime import date, datetime, timedelta

from openpyxl import Workbook
from sqlalchemy.orm import Session

from .. import models
from .style import write_title, write_section, write_table, workbook_response

TASK_COLUMNS = ["task_id", "title", "old_status", "new_status", "changed_by", "changed_at"]
NOTE_COLUMNS = ["note_id", "content", "created_at"]


def generate(slug: str, target_date: date, db: Session) -> Workbook:
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    changes = (
        db.query(models.ActivityLog)
        .filter(
            models.ActivityLog.entity_type == "task",
            models.ActivityLog.field_changed == "status",
            models.ActivityLog.changed_at >= day_start,
            models.ActivityLog.changed_at < day_end,
        )
        .order_by(models.ActivityLog.changed_at)
        .all()
    )
    task_ids = {c.entity_id for c in changes}
    tasks_by_id = {}
    if task_ids:
        for t in db.query(models.Task).filter(models.Task.id.in_(task_ids)).all():
            tasks_by_id[t.id] = t

    task_rows = [
        {
            "task_id": c.entity_id,
            "title": tasks_by_id[c.entity_id].title if c.entity_id in tasks_by_id else "(deleted)",
            "old_status": c.old_value,
            "new_status": c.new_value,
            "changed_by": c.changed_by,
            "changed_at": c.changed_at.strftime("%Y-%m-%d %H:%M"),
        }
        for c in changes
    ]

    notes = (
        db.query(models.Note)
        .filter(models.Note.created_at >= day_start, models.Note.created_at < day_end)
        .order_by(models.Note.created_at)
        .all()
    )
    note_rows = [
        {"note_id": n.id, "content": n.content, "created_at": n.created_at.strftime("%Y-%m-%d %H:%M")}
        for n in notes
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Task Updates Today"
    row = write_title(ws, 1, f"Daily Report — {slug} — {target_date.isoformat()}")
    row = write_section(ws, row, f"Task Status Updates ({len(task_rows)})")
    row = write_table(ws, row, TASK_COLUMNS, task_rows)
    row = write_section(ws, row, f"Notes Created Today ({len(note_rows)})")
    write_table(ws, row, NOTE_COLUMNS, note_rows)

    return wb
