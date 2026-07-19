from datetime import date

from openpyxl import Workbook
from sqlalchemy.orm import Session

from .. import models
from .style import write_title, write_section, write_table
from ..routers.projects import MANDATORY_COLUMN_BY_CATEGORY

SUMMARY_COLUMNS = ["metric", "value"]
PHASE_COLUMNS = [
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
OVERDUE_COLUMNS = ["task_id", "title", "owner", "due_date", "status"]
MANDATORY_PENDING_COLUMNS = ["doc_code", "doc_name", "phase_name", "current_status"]

FUNCTION_DONE_STATUSES = ("Confirmed", "Done")
TASK_DONE_STATUSES = ("Done",)
DOCUMENT_DONE_STATUSES = ("Confirmed",)


def _pct(done: int, total: int) -> str:
    if total == 0:
        return "-"
    return f"{round(done / total * 100)}%"


def generate(slug: str, month: str, db: Session, master_db: Session) -> Workbook:
    functions = db.query(models.Function).all()
    tasks = db.query(models.Task).all()
    documents = db.query(models.Document).all()

    f_done = sum(1 for f in functions if f.status in FUNCTION_DONE_STATUSES)
    t_done = sum(1 for t in tasks if t.status in TASK_DONE_STATUSES)
    d_done = sum(1 for d in documents if d.status in DOCUMENT_DONE_STATUSES)

    summary_rows = [
        {"metric": "Functions Total", "value": len(functions)},
        {"metric": "Functions Done/Confirmed", "value": f_done},
        {"metric": "Functions % Complete", "value": _pct(f_done, len(functions))},
        {"metric": "Tasks Total", "value": len(tasks)},
        {"metric": "Tasks Done", "value": t_done},
        {"metric": "Tasks % Complete", "value": _pct(t_done, len(tasks))},
        {"metric": "Documents Total", "value": len(documents)},
        {"metric": "Documents Confirmed", "value": d_done},
        {"metric": "Documents % Confirmed", "value": _pct(d_done, len(documents))},
    ]

    phases = sorted(
        {f.phase for f in functions if f.phase}
        | {t.phase for t in tasks if t.phase}
        | {d.phase for d in documents if d.phase}
    )
    phase_rows = []
    for phase in phases:
        f_in_phase = [f for f in functions if f.phase == phase]
        t_in_phase = [t for t in tasks if t.phase == phase]
        d_in_phase = [d for d in documents if d.phase == phase]
        pf_done = sum(1 for f in f_in_phase if f.status in FUNCTION_DONE_STATUSES)
        pt_done = sum(1 for t in t_in_phase if t.status in TASK_DONE_STATUSES)
        pd_done = sum(1 for d in d_in_phase if d.status in DOCUMENT_DONE_STATUSES)
        phase_rows.append(
            {
                "phase": phase,
                "functions_total": len(f_in_phase),
                "functions_done": pf_done,
                "functions_pct": _pct(pf_done, len(f_in_phase)),
                "tasks_total": len(t_in_phase),
                "tasks_done": pt_done,
                "tasks_pct": _pct(pt_done, len(t_in_phase)),
                "documents_total": len(d_in_phase),
                "documents_confirmed": pd_done,
                "documents_pct": _pct(pd_done, len(d_in_phase)),
            }
        )

    today = date.today()
    overdue_rows = [
        {
            "task_id": t.id,
            "title": t.title,
            "owner": t.owner,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "status": t.status,
        }
        for t in tasks
        if t.due_date and t.due_date < today and t.status != "Done"
    ]

    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    mandatory_pending_rows = []
    if project and project.project_category:
        column_name = MANDATORY_COLUMN_BY_CATEGORY.get(project.project_category)
        if column_name:
            templates = (
                master_db.query(models.DocumentTemplate)
                .filter(getattr(models.DocumentTemplate, column_name) == "M")
                .all()
            )
            docs_by_code = {d.doc_code: d for d in documents}
            for t in templates:
                doc = docs_by_code.get(str(t.doc_code))
                current_status = doc.status if doc else "Not Started"
                if current_status != "Confirmed":
                    mandatory_pending_rows.append(
                        {
                            "doc_code": t.doc_code,
                            "doc_name": t.doc_name,
                            "phase_name": t.phase_name,
                            "current_status": current_status,
                        }
                    )

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Executive Summary"
    row = write_title(ws1, 1, f"Monthly Report — {slug} — {month}")
    write_table(ws1, row, SUMMARY_COLUMNS, summary_rows)

    ws2 = wb.create_sheet("Phase Breakdown")
    row2 = write_title(ws2, 1, "Phase Breakdown (current snapshot)")
    write_table(ws2, row2, PHASE_COLUMNS, phase_rows)

    ws3 = wb.create_sheet("Risk-Overdue")
    row3 = write_title(ws3, 1, "Risk & Overdue")
    row3 = write_section(ws3, row3, f"Overdue Tasks ({len(overdue_rows)})")
    row3 = write_table(ws3, row3, OVERDUE_COLUMNS, overdue_rows)
    row3 = write_section(ws3, row3, f"Mandatory Documents Not Yet Confirmed ({len(mandatory_pending_rows)})")
    write_table(ws3, row3, MANDATORY_PENDING_COLUMNS, mandatory_pending_rows)

    return wb
