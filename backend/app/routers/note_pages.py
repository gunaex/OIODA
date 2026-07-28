"""Note System — markdown wiki pages with hashtags, wiki-links and backlinks.

Distinct from routers/notes.py, which is the one-line quick-capture note that
gets promoted to a task/issue. These are long-lived pages.

RBAC follows the existing convention: reads are open to every logged-in role
(client_viewer included), writes go through require_internal.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, note_parser, schemas
from ..auth import get_current_user, require_internal
from ..database import get_project_db

router = APIRouter(prefix="/api/{slug}", tags=["note-pages"], dependencies=[Depends(get_current_user)])

EXCERPT_CHARS = 160


def _tags_for(db: Session, note_ids: list[int]) -> dict[int, list[str]]:
    if not note_ids:
        return {}
    rows = (
        db.query(models.NoteTag.note_page_id, models.NoteTag.tag)
        .filter(models.NoteTag.note_page_id.in_(note_ids))
        .order_by(models.NoteTag.id)
        .all()
    )
    out: dict[int, list[str]] = {}
    for note_id, tag in rows:
        out.setdefault(note_id, []).append(tag)
    return out


def _excerpt(content: Optional[str]) -> Optional[str]:
    if not content:
        return None
    flat = " ".join(content.split())
    return flat[:EXCERPT_CHARS] + ("…" if len(flat) > EXCERPT_CHARS else "")


def _summaries(db: Session, notes: list[models.NotePage]) -> list[schemas.NotePageSummary]:
    tag_map = _tags_for(db, [n.id for n in notes])
    return [
        schemas.NotePageSummary(
            id=n.id,
            title=n.title,
            created_by=n.created_by,
            created_at=n.created_at,
            updated_at=n.updated_at,
            tags=tag_map.get(n.id, []),
            excerpt=_excerpt(n.content_markdown),
        )
        for n in notes
    ]


def _detail(db: Session, note: models.NotePage) -> schemas.NotePageOut:
    return schemas.NotePageOut(
        id=note.id,
        title=note.title,
        content_markdown=note.content_markdown,
        created_by=note.created_by,
        created_at=note.created_at,
        updated_at=note.updated_at,
        tags=_tags_for(db, [note.id]).get(note.id, []),
        # Resolved live rather than read back from note_links, so the response
        # can also describe the *unresolved* links (which have no row by
        # design) — that's what tells the frontend to render them as text.
        links=[schemas.NoteLinkOut(**link) for link in note_parser.resolve_links(db, note.content_markdown, note.id)],
    )


def _get_note(db: Session, note_id: int) -> models.NotePage:
    note = db.query(models.NotePage).filter(models.NotePage.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note page not found")
    return note


# ---------- Note pages CRUD ----------


@router.get("/note-pages", response_model=list[schemas.NotePageSummary])
def list_note_pages(
    slug: str,
    tag: Optional[str] = Query(None, description="filter to notes carrying this hashtag"),
    q: Optional[str] = Query(None, description="substring match on title or body"),
    db: Session = Depends(get_project_db),
):
    query = db.query(models.NotePage)
    if tag:
        note_ids = [
            row[0]
            for row in db.query(models.NoteTag.note_page_id).filter(models.NoteTag.tag == tag.strip().lstrip("#").lower()).all()
        ]
        if not note_ids:
            return []
        query = query.filter(models.NotePage.id.in_(note_ids))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(models.NotePage.title.ilike(pattern) | models.NotePage.content_markdown.ilike(pattern))
    return _summaries(db, query.order_by(models.NotePage.updated_at.desc()).all())


@router.post("/note-pages", response_model=schemas.NotePageOut)
def create_note_page(
    slug: str,
    payload: schemas.NotePageCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title is required")
    note = models.NotePage(
        title=payload.title.strip(),
        content_markdown=payload.content_markdown or "",
        created_by=payload.created_by,
    )
    db.add(note)
    db.flush()  # assigns note.id, needed before the tag/link index can be built
    note_parser.resync_note(db, note)
    db.commit()
    db.refresh(note)
    return _detail(db, note)


@router.get("/note-pages/{note_id}", response_model=schemas.NotePageOut)
def get_note_page(slug: str, note_id: int, db: Session = Depends(get_project_db)):
    return _detail(db, _get_note(db, note_id))


@router.put("/note-pages/{note_id}", response_model=schemas.NotePageOut)
def update_note_page(
    slug: str,
    note_id: int,
    payload: schemas.NotePageUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    note = _get_note(db, note_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data:
        if not (data["title"] or "").strip():
            raise HTTPException(status_code=400, detail="title cannot be empty")
        note.title = data["title"].strip()
    if "content_markdown" in data:
        note.content_markdown = data["content_markdown"] or ""
    # Resync on every save, unconditionally — cheap, and it also picks up
    # links that only *now* resolve because their target was created since.
    note_parser.resync_note(db, note)
    db.commit()
    db.refresh(note)
    return _detail(db, note)


@router.delete("/note-pages/{note_id}")
def delete_note_page(
    slug: str,
    note_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    note = _get_note(db, note_id)
    db.query(models.NoteTag).filter(models.NoteTag.note_page_id == note.id).delete(synchronize_session=False)
    # Links *into* this note are dropped too, otherwise other notes' backlink
    # panels would point at a page that no longer exists.
    db.query(models.NoteLink).filter(models.NoteLink.source_note_id == note.id).delete(synchronize_session=False)
    db.query(models.NoteLink).filter(
        models.NoteLink.target_type == "note", models.NoteLink.target_id == note.id
    ).delete(synchronize_session=False)
    db.delete(note)
    db.commit()
    return {"ok": True}


# ---------- Backlinks ----------


@router.get("/note-pages/{note_id}/backlinks", response_model=list[schemas.NotePageSummary])
def note_backlinks(slug: str, note_id: int, db: Session = Depends(get_project_db)):
    """Notes that link *to* this note."""
    _get_note(db, note_id)
    source_ids = [
        row[0]
        for row in db.query(models.NoteLink.source_note_id)
        .filter(models.NoteLink.target_type == "note", models.NoteLink.target_id == note_id)
        .all()
    ]
    if not source_ids:
        return []
    notes = (
        db.query(models.NotePage)
        .filter(models.NotePage.id.in_(source_ids))
        .order_by(models.NotePage.updated_at.desc())
        .all()
    )
    return _summaries(db, notes)


# ---------- Tags ----------


@router.get("/tags", response_model=list[schemas.TagCountOut])
def list_tags(slug: str, db: Session = Depends(get_project_db)):
    """Distinct tags in use, most-used first — feeds the `#` autocomplete and
    the Tag Board's default columns."""
    rows = (
        db.query(models.NoteTag.tag, func.count(models.NoteTag.id))
        .group_by(models.NoteTag.tag)
        .order_by(func.count(models.NoteTag.id).desc(), models.NoteTag.tag)
        .all()
    )
    return [schemas.TagCountOut(tag=tag, count=count) for tag, count in rows]


@router.put("/note-pages/{note_id}/tags/move", response_model=schemas.NotePageOut)
def move_note_tag(
    slug: str,
    note_id: int,
    payload: schemas.TagRenameRequest,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    """Tag Board drag-and-drop. Rewrites the markdown text itself (`#old` ->
    `#new`, or appends `#new` when dragged in from an untagged card) and lets
    resync_note reindex from it — so the note body and the tag index can't
    disagree about what tags the note has."""
    note = _get_note(db, note_id)
    to_tag = payload.to_tag.strip().lstrip("#").lower()
    if not to_tag:
        raise HTTPException(status_code=400, detail="to_tag is required")
    from_tag = (payload.from_tag or "").strip().lstrip("#").lower()

    content = note.content_markdown or ""
    if from_tag and from_tag != to_tag:
        content = note_parser.rewrite_tag(content, from_tag, to_tag)
    if to_tag not in note_parser.extract_hashtags(content):
        content = f"{content.rstrip()}\n\n#{to_tag}\n" if content.strip() else f"#{to_tag}\n"
    note.content_markdown = content

    note_parser.resync_note(db, note)
    db.commit()
    db.refresh(note)
    return _detail(db, note)


# ---------- Reverse lookup from any entity ----------


def _resolve_entity_or_404(db: Session, entity_type: str, entity_id: int):
    target_type = note_parser.normalize_entity_type(entity_type)
    if not target_type:
        raise HTTPException(status_code=404, detail=f"Unknown entity type '{entity_type}'")
    model = {
        "note": models.NotePage,
        "task": models.Task,
        "function": models.Function,
        "document": models.Document,
        "board_item": models.BoardItem,
    }[target_type]
    obj = db.query(model).filter(model.id == entity_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{entity_type} {entity_id} not found")
    return target_type, obj


@router.get("/{entity_type}/{entity_id}/linked-notes", response_model=list[schemas.NotePageSummary])
def linked_notes_for_entity(slug: str, entity_type: str, entity_id: int, db: Session = Depends(get_project_db)):
    """"Which notes mention this Task/Function/Document/Issue?" — the entity
    side of the backlink story."""
    target_type, _obj = _resolve_entity_or_404(db, entity_type, entity_id)
    source_ids = [
        row[0]
        for row in db.query(models.NoteLink.source_note_id)
        .filter(models.NoteLink.target_type == target_type, models.NoteLink.target_id == entity_id)
        .all()
    ]
    if not source_ids:
        return []
    notes = (
        db.query(models.NotePage)
        .filter(models.NotePage.id.in_(source_ids))
        .order_by(models.NotePage.updated_at.desc())
        .all()
    )
    return _summaries(db, notes)


# Wiki-link prefix to emit when linking *from* an entity page. board_item
# rows use their own flavour word so the inserted link reads naturally
# (`[[issue:ISS-001]]`, not `[[board_item:ISS-001]]`).
def _link_prefix_for(target_type: str, obj) -> str:
    if target_type == "board_item":
        return obj.item_type
    return target_type


@router.post("/{entity_type}/{entity_id}/link-note", response_model=schemas.NotePageOut)
def link_note_to_entity(
    slug: str,
    entity_type: str,
    entity_id: int,
    payload: schemas.LinkNoteRequest,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    """"Link to Note" button: appends `[[entity_type:CODE]]` to an existing
    note (note_id) or to a freshly created one (title). The wiki-link in the
    markdown is what creates the link — resync_note does the rest, so this
    behaves exactly as if someone had typed it by hand."""
    target_type, obj = _resolve_entity_or_404(db, entity_type, entity_id)
    code = note_parser.entity_code(obj, target_type)
    if not code:
        raise HTTPException(
            status_code=400,
            detail=f"This {entity_type} has no code yet — give it one first so notes can link to it by code.",
        )
    wikilink = f"[[{_link_prefix_for(target_type, obj)}:{code}]]"

    if payload.note_id is not None:
        note = _get_note(db, payload.note_id)
        if wikilink.lower() not in (note.content_markdown or "").lower():
            body = (note.content_markdown or "").rstrip()
            note.content_markdown = f"{body}\n\n{wikilink}\n" if body else f"{wikilink}\n"
    else:
        title = (payload.title or "").strip() or f"{note_parser.entity_label(obj, target_type)} — notes"
        note = models.NotePage(
            title=title,
            content_markdown=f"{wikilink}\n",
            created_by=payload.created_by,
        )
        db.add(note)
        db.flush()

    note_parser.resync_note(db, note)
    db.commit()
    db.refresh(note)
    return _detail(db, note)
