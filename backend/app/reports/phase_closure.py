from openpyxl import Workbook
from sqlalchemy.orm import Session

from .. import models
from .style import write_title, write_section, write_table
from ..routers.projects import MANDATORY_COLUMN_BY_CATEGORY

CHECKLIST_COLUMNS = ["doc_code", "doc_name", "mandatory_level", "status", "confirmed_date", "signed_by"]
SIGNOFF_COLUMNS = ["doc_code", "doc_title", "signed_by", "signed_role", "status", "signed_at", "comment"]


def generate(slug: str, phase_code: int, db: Session, master_db: Session) -> Workbook:
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    column_name = MANDATORY_COLUMN_BY_CATEGORY.get(project.project_category) if project else None

    templates = (
        master_db.query(models.DocumentTemplate)
        .filter(models.DocumentTemplate.phase_code == phase_code)
        .order_by(models.DocumentTemplate.doc_code)
        .all()
    )
    phase_name = templates[0].phase_name if templates else None

    documents = db.query(models.Document).filter(models.Document.phase == phase_name).all() if phase_name else []
    docs_by_code = {d.doc_code: d for d in documents}

    checklist_rows = []
    signoff_rows = []
    for t in templates:
        doc = docs_by_code.get(str(t.doc_code))
        mandatory_level = getattr(t, column_name) if column_name else None
        latest_approved = None
        if doc:
            latest_approved = (
                db.query(models.DocumentSignoff)
                .filter(models.DocumentSignoff.document_id == doc.id, models.DocumentSignoff.status == "Approved")
                .order_by(models.DocumentSignoff.signed_at.desc())
                .first()
            )
            all_signoffs = (
                db.query(models.DocumentSignoff)
                .filter(models.DocumentSignoff.document_id == doc.id)
                .order_by(models.DocumentSignoff.signed_at)
                .all()
            )
            for s in all_signoffs:
                signoff_rows.append(
                    {
                        "doc_code": t.doc_code,
                        "doc_title": doc.title,
                        "signed_by": s.signed_by,
                        "signed_role": s.signed_role,
                        "status": s.status,
                        "signed_at": s.signed_at.strftime("%Y-%m-%d %H:%M"),
                        "comment": s.comment,
                    }
                )

        checklist_rows.append(
            {
                "doc_code": t.doc_code,
                "doc_name": t.doc_name,
                "mandatory_level": mandatory_level,
                "status": doc.status if doc else "Not Started",
                "confirmed_date": latest_approved.signed_at.strftime("%Y-%m-%d") if latest_approved else None,
                "signed_by": latest_approved.signed_by if latest_approved else None,
            }
        )

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Document Checklist"
    row = write_title(ws1, 1, f"Phase Closure Report — {slug} — Phase {phase_code} ({phase_name or 'unknown'})")
    if not column_name:
        row = write_section(ws1, row, "Note: project has no project_category set — mandatory/optional level unavailable")
    write_table(ws1, row, CHECKLIST_COLUMNS, checklist_rows)

    ws2 = wb.create_sheet("Signoff Detail")
    row2 = write_title(ws2, 1, "Sign-off History for This Phase")
    write_table(ws2, row2, SIGNOFF_COLUMNS, signoff_rows)

    return wb
