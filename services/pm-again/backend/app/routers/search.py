from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_project_db
from ..auth import require_internal

# Search results span tasks/notes/board-items — internal-only content — so
# the whole endpoint is blocked for client_viewer rather than trying to
# filter results per-type.
router = APIRouter(prefix="/api/{slug}/search", tags=["search"], dependencies=[Depends(require_internal)])


@router.get("", response_model=list[schemas.SearchResult])
def search(slug: str, q: str = Query(..., min_length=1), db: Session = Depends(get_project_db)):
    like = f"%{q}%"
    results: list[schemas.SearchResult] = []

    functions = (
        db.query(models.Function)
        .filter(
            (models.Function.name.like(like))
            | (models.Function.function_code.like(like))
            | (models.Function.owner.like(like))
        )
        .limit(20)
        .all()
    )
    results += [
        schemas.SearchResult(type="function", id=f.id, title=f.name, subtitle=f.function_code) for f in functions
    ]

    tasks = (
        db.query(models.Task)
        .filter(
            (models.Task.title.like(like)) | (models.Task.task_code.like(like)) | (models.Task.owner.like(like))
        )
        .limit(20)
        .all()
    )
    results += [schemas.SearchResult(type="task", id=t.id, title=t.title, subtitle=t.task_code) for t in tasks]

    documents = (
        db.query(models.Document)
        .filter(
            (models.Document.title.like(like))
            | (models.Document.doc_code.like(like))
            | (models.Document.owner.like(like))
        )
        .limit(20)
        .all()
    )
    results += [
        schemas.SearchResult(type="document", id=d.id, title=d.title, subtitle=d.doc_code) for d in documents
    ]

    notes = db.query(models.Note).filter(models.Note.content.like(like)).limit(20).all()
    results += [
        schemas.SearchResult(type="note", id=n.id, title=n.content[:80], subtitle=n.status) for n in notes
    ]

    board_items = (
        db.query(models.BoardItem)
        .filter(
            (models.BoardItem.title.like(like))
            | (models.BoardItem.item_code.like(like))
            | (models.BoardItem.owner.like(like))
        )
        .limit(20)
        .all()
    )
    results += [
        schemas.SearchResult(type=b.item_type, id=b.id, title=b.title, subtitle=b.item_code) for b in board_items
    ]

    return results
