"""Account Again — Idempotency service."""

from typing import Optional, Any
from sqlalchemy.orm import Session

from account_again.models.idempotency import IdempotencyRecord


def check_idempotent(db: Session, key: str) -> Optional[dict]:
    """Check if an idempotency key has already been processed."""
    record = db.query(IdempotencyRecord).filter(IdempotencyRecord.key == key).first()
    if record:
        return {"status": record.status, "result": record.result}
    return None


def record_idempotent(db: Session, key: str, result: Any = None) -> IdempotencyRecord:
    """Record a completed idempotent operation."""
    import json
    record = IdempotencyRecord(
        key=key,
        status="COMPLETED",
        result=json.dumps(result) if result is not None else None,
    )
    db.add(record)
    db.flush()
    return record
