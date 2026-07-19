from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from .board_items import generate_item_code, DEFAULT_STATUS
from ..auth import require_internal

router = APIRouter(prefix="/api/{slug}/notes", tags=["notes"], dependencies=[Depends(require_internal)])


@router.get("", response_model=list[schemas.NoteOut])
def list_notes(slug: str, status: str | None = None, db: Session = Depends(get_project_db)):
    q = db.query(models.Note)
    if status:
        q = q.filter(models.Note.status == status)
    return q.order_by(models.Note.created_at.desc()).all()


@router.post("", response_model=schemas.NoteOut)
def create_note(slug: str, payload: schemas.NoteCreate, db: Session = Depends(get_project_db)):
    obj = models.Note(content=payload.content, status="Open")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}")
def delete_note(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    obj = db.query(models.Note).filter(models.Note.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/promote-task", response_model=schemas.NoteOut)
def promote_to_task(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    note = db.query(models.Note).filter(models.Note.id == item_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.status != "Open":
        raise HTTPException(status_code=400, detail=f"Cannot promote a note with status '{note.status}' (must be Open)")

    task = models.Task(title=note.content, status="Todo", priority="Med")
    db.add(task)
    db.flush()  # assigns task.id without committing yet

    note.status = "PromotedToTask"
    note.linked_task_id = task.id

    db.commit()
    db.refresh(note)
    return note


@router.post("/{item_id}/promote-issue", response_model=schemas.NoteOut)
def promote_to_issue(slug: str, item_id: int, db: Session = Depends(get_project_db)):
    note = db.query(models.Note).filter(models.Note.id == item_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.status != "Open":
        raise HTTPException(status_code=400, detail=f"Cannot promote a note with status '{note.status}' (must be Open)")

    issue = models.BoardItem(
        item_type="issue",
        item_code=generate_item_code(db, "issue"),
        title=note.content,
        status=DEFAULT_STATUS["issue"],
        linked_note_id=note.id,
        sla_due_date=None,  # no severity yet — set when the issue is triaged
    )
    db.add(issue)
    db.flush()  # assigns issue.id without committing yet

    note.status = "PromotedToIssue"
    note.linked_issue_id = issue.id

    db.commit()
    db.refresh(note)
    return note
