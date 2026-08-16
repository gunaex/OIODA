from sqlalchemy.orm import Session

from . import models


def log_change(db: Session, entity_type: str, entity_id: int, field: str, old_value, new_value, changed_by: str | None = None):
    """Records one field-level change. Called from update handlers whenever
    a field actually changes value (not on every PUT — only on real diffs)."""
    if old_value == new_value:
        return
    db.add(
        models.ActivityLog(
            entity_type=entity_type,
            entity_id=entity_id,
            field_changed=field,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            changed_by=changed_by,
        )
    )


def log_changes(db: Session, entity_type: str, entity_id: int, changes: dict[str, tuple], changed_by: str | None = None):
    """`changes` maps field name -> (old_value, new_value)."""
    for field, (old_value, new_value) in changes.items():
        log_change(db, entity_type, entity_id, field, old_value, new_value, changed_by)
