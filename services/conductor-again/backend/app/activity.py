"""
Conductor Again — Activity Logging
Audit trail for every meaningful action.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ActivityLog


def log_activity(
    db: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_type: str = "human",
    details: str = "",
):
    entry = ActivityLog(
        actor=actor,
        actor_type=actor_type,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
