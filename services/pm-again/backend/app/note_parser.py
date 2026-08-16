"""Hashtag + wiki-link parsing for note pages.

Everything here is *derived* data: `note_tags` and `note_links` are wiped and
rebuilt from `note_pages.content_markdown` on every save (resync, not diff),
so the index can never drift from the text. Parsing runs once per save — not
per keystroke.

Resolution is best-effort by design: a `[[link]]` that points at a title or
code that doesn't exist is silently skipped (no row, no error). The frontend
renders those as plain text.
"""

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models

# Thai (฀-๿) is included alongside ASCII word chars so Thai-language
# tags work. A '#' immediately followed by a space (markdown heading) can't
# match, since the class requires at least one tag character.
HASHTAG_RE = re.compile(r"#([0-9A-Za-z_\-฀-๿]+)")

# Non-greedy, and '[' / ']' excluded from the body so nested/streaky brackets
# can't swallow neighbouring links.
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

# Wiki-link prefix -> note_links.target_type. issue/incident/backlog are the
# three board_item flavours; all three resolve against board_items.item_code.
LINK_PREFIXES = {
    "note": "note",
    "task": "task",
    "function": "function",
    "document": "document",
    "doc": "document",
    "issue": "board_item",
    "incident": "board_item",
    "backlog": "board_item",
    "board_item": "board_item",
}

# Entity types accepted by the reverse-lookup endpoints. Same set as
# note_links.target_type, plus the aliases above so callers can use the word
# they see in the UI ("issue") rather than the storage name ("board_item").
ENTITY_TYPE_ALIASES = dict(LINK_PREFIXES)

TARGET_TYPES = ("note", "task", "function", "document", "board_item")


def normalize_entity_type(entity_type: str) -> str | None:
    return ENTITY_TYPE_ALIASES.get((entity_type or "").strip().lower())


# ---------- extraction ----------


def extract_hashtags(content: str | None) -> list[str]:
    """Normalized (lowercase, no leading '#'), de-duplicated, first-seen order."""
    if not content:
        return []
    seen = []
    for raw in HASHTAG_RE.findall(content):
        tag = raw.lower()
        if tag not in seen:
            seen.append(tag)
    return seen


def extract_wikilinks(content: str | None) -> list[str]:
    """Raw inner text of each `[[...]]`, de-duplicated, first-seen order."""
    if not content:
        return []
    seen = []
    for raw in WIKILINK_RE.findall(content):
        body = raw.strip()
        if body and body not in seen:
            seen.append(body)
    return seen


# ---------- resolution ----------


def _resolve_entity(db: Session, target_type: str, code: str):
    """Returns the matching row, or None. Code matching is case-insensitive
    so `[[task:t-001]]` finds TASK code 'T-001'."""
    code = code.strip()
    if not code:
        return None
    # func.lower(...) == rather than ilike(): ilike would treat '%' and '_'
    # inside a code (e.g. "REQ_01") as wildcards and match the wrong row.
    lowered = code.lower()
    if target_type == "note":
        return (
            db.query(models.NotePage)
            .filter(func.lower(models.NotePage.title) == lowered)
            .order_by(models.NotePage.id)
            .first()
        )
    if target_type == "task":
        model, column = models.Task, models.Task.task_code
    elif target_type == "function":
        model, column = models.Function, models.Function.function_code
    elif target_type == "document":
        model, column = models.Document, models.Document.doc_code
    elif target_type == "board_item":
        model, column = models.BoardItem, models.BoardItem.item_code
    else:
        return None
    return db.query(model).filter(func.lower(column) == lowered).order_by(model.id).first()


def entity_code(obj, target_type: str) -> str | None:
    return {
        "note": lambda: obj.title,
        "task": lambda: obj.task_code,
        "function": lambda: obj.function_code,
        "document": lambda: obj.doc_code,
        "board_item": lambda: obj.item_code,
    }[target_type]()


def entity_label(obj, target_type: str) -> str:
    if target_type == "note":
        return obj.title
    if target_type == "task":
        return obj.title
    if target_type == "function":
        return obj.name
    if target_type == "document":
        return obj.title
    return obj.title  # board_item


def resolve_wikilink(db: Session, body: str, exclude_note_id: int | None = None) -> dict:
    """Resolves one `[[...]]` body. Always returns a dict — `resolved` False
    means "render as plain text", never an error.

    Two accepted forms:
      `[[Note Title]]`      -> match note_pages.title (case-insensitive)
      `[[task:CODE]]`       -> match that entity's code column
    """
    prefix, _, rest = body.partition(":")
    target_type = LINK_PREFIXES.get(prefix.strip().lower()) if rest else None
    if target_type:
        code = rest
    else:
        # No (recognized) prefix -> plain note-title link.
        target_type, code = "note", body

    obj = _resolve_entity(db, target_type, code)
    if obj is None or (target_type == "note" and exclude_note_id is not None and obj.id == exclude_note_id):
        return {"raw": body, "resolved": False, "target_type": target_type, "target_id": None, "label": body}
    return {
        "raw": body,
        "resolved": True,
        "target_type": target_type,
        "target_id": obj.id,
        "label": entity_label(obj, target_type),
    }


def resolve_links(db: Session, content: str | None, exclude_note_id: int | None = None) -> list[dict]:
    """Read-only: resolves every wiki-link in `content` without touching the
    DB index. Used by the note-detail response so the frontend knows which
    `[[...]]` to render as a link and where each one points."""
    return [resolve_wikilink(db, body, exclude_note_id) for body in extract_wikilinks(content)]


# ---------- resync (called on every save) ----------


def resync_note(db: Session, note: models.NotePage) -> None:
    """Wipes and rebuilds this note's tag/link index from its markdown.
    Flushes but does not commit — the caller owns the transaction."""
    db.query(models.NoteTag).filter(models.NoteTag.note_page_id == note.id).delete(synchronize_session=False)
    db.query(models.NoteLink).filter(models.NoteLink.source_note_id == note.id).delete(synchronize_session=False)

    for tag in extract_hashtags(note.content_markdown):
        db.add(models.NoteTag(note_page_id=note.id, tag=tag))

    # A note linking to itself would make the backlinks panel list the note
    # you're already reading, so self-links are dropped.
    seen: set[tuple[str, int]] = set()
    for link in resolve_links(db, note.content_markdown, exclude_note_id=note.id):
        if not link["resolved"]:
            continue
        key = (link["target_type"], link["target_id"])
        if key in seen:
            continue
        seen.add(key)
        db.add(models.NoteLink(source_note_id=note.id, target_type=key[0], target_id=key[1]))

    db.flush()


def rewrite_tag(content: str | None, old_tag: str, new_tag: str) -> str:
    """Text-level `#oldtag` -> `#newtag` rewrite used by the Tag Board's
    drag-and-drop. The markdown stays the source of truth — resync_note then
    reindexes from the rewritten text, exactly as a manual edit would."""
    if not content:
        return content or ""
    pattern = re.compile(
        r"#(" + re.escape(old_tag) + r")(?![0-9A-Za-z_\-฀-๿])",
        re.IGNORECASE,
    )
    return pattern.sub(f"#{new_tag}", content)
