"""One activity query, shared by all three reports.

Every workflow module writes field-level changes to `activity_log`, so
"everything that happened" is one query plus a lookup back to each entity for
its code and title — not a separate query per module. Adding a module later
means adding it to ENTITY_SOURCES here and it appears in all three reports at
once.
"""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .. import models

# entity_type in activity_log -> (model, code attribute, title attribute,
# label shown in reports). The label is what a reader sees, so it is the
# business word rather than the table name.
ENTITY_SOURCES = {
    "task": (models.Task, "task_code", "title", "Task"),
    "function": (models.Function, "function_code", "name", "Function"),
    "document": (models.Document, "doc_code", "title", "Document"),
    "board_item": (models.BoardItem, "item_code", "title", "Board Item"),
    "change_request": (models.ChangeRequest, "cr_code", "title", "Change Request"),
}

# Fields whose changes are noise in a status-focused report.
STATUS_FIELD = "status"


def day_bounds(target: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target, datetime.min.time())
    return start, start + timedelta(days=1)


def range_bounds(start: date, end_exclusive: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, datetime.min.time()),
        datetime.combine(end_exclusive, datetime.min.time()),
    )


def fetch(db: Session, start_dt: datetime, end_dt: datetime, entity_types: Optional[list[str]] = None) -> list[dict]:
    """Every logged change in the window, enriched with the entity's code and
    title. Rows whose entity has since been deleted are kept — the change did
    happen, and dropping it would make the report disagree with the log."""
    query = db.query(models.ActivityLog).filter(
        models.ActivityLog.changed_at >= start_dt,
        models.ActivityLog.changed_at < end_dt,
    )
    if entity_types:
        query = query.filter(models.ActivityLog.entity_type.in_(entity_types))
    entries = query.order_by(models.ActivityLog.changed_at, models.ActivityLog.id).all()
    if not entries:
        return []

    # One lookup per entity type present, not one per row.
    ids_by_type: dict[str, set] = {}
    for e in entries:
        ids_by_type.setdefault(e.entity_type, set()).add(e.entity_id)

    resolved: dict[tuple, tuple] = {}
    for entity_type, ids in ids_by_type.items():
        source = ENTITY_SOURCES.get(entity_type)
        if not source:
            continue
        model, code_attr, title_attr, _label = source
        for obj in db.query(model).filter(model.id.in_(ids)).all():
            resolved[(entity_type, obj.id)] = (
                getattr(obj, code_attr, None),
                getattr(obj, title_attr, None),
                getattr(obj, "owner", None),
            )

    rows = []
    for e in entries:
        label = ENTITY_SOURCES.get(e.entity_type, (None, None, None, e.entity_type))[3]
        code, title, owner = resolved.get((e.entity_type, e.entity_id), (None, None, None))
        rows.append(
            {
                "changed_at": e.changed_at,
                "time": e.changed_at.strftime("%H:%M") if e.changed_at else "",
                "datetime": e.changed_at.strftime("%Y-%m-%d %H:%M") if e.changed_at else "",
                "date": e.changed_at.date() if e.changed_at else None,
                "module": label,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "entity_code": code or f"#{e.entity_id}",
                "entity_title": title or "(deleted)",
                "owner": owner,
                "field": e.field_changed,
                "from": e.old_value,
                "to": e.new_value,
                "by": e.changed_by,
            }
        )
    return rows


def status_changes(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["field"] == STATUS_FIELD]


def count_by(rows: list[dict], key: str) -> dict:
    out: dict = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


def count_by_pair(rows: list[dict], row_key: str, col_key: str) -> dict:
    out: dict = {}
    for r in rows:
        out.setdefault(r[row_key], {})
        out[r[row_key]][r[col_key]] = out[r[row_key]].get(r[col_key], 0) + 1
    return out


GENERIC_ROLE = "Team member"


def role_map(master_db: Session) -> dict:
    """name -> role, from the company resource pool."""
    return {
        r.name: (r.role or GENERIC_ROLE)
        for r in master_db.query(models.Resource).all()
        if r.name
    }


def to_role(name: Optional[str], roles: dict) -> Optional[str]:
    """Person's name -> the role they were acting in.

    Anything not found in the resource pool becomes the generic label rather
    than falling through as the raw name — the failure mode of a lookup miss
    must not be "leak the name to the client".
    """
    if not name:
        return None
    return roles.get(name, GENERIC_ROLE)


def anonymize(rows: list[dict], roles: dict) -> list[dict]:
    """Client-facing copy of the feed with people replaced by roles."""
    out = []
    for r in rows:
        copy = dict(r)
        copy["by"] = to_role(r.get("by"), roles)
        copy["owner"] = to_role(r.get("owner"), roles)
        out.append(copy)
    return out
