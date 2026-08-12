"""Account Again — Audit service."""

import json
from typing import Optional
from sqlalchemy.orm import Session

from account_again.models.audit import AuditRecord, FORBIDDEN_AUDIT_FIELDS
from account_again.models.tenant import _new_id, _now


def _sanitize_metadata(meta: Optional[dict]) -> Optional[str]:
    """Remove forbidden fields from audit metadata before storage."""
    if not meta:
        return None
    clean = {k: v for k, v in meta.items() if k not in FORBIDDEN_AUDIT_FIELDS}
    return json.dumps(clean) if clean else None


def write_audit(
    db: Session,
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    result: str,
    tenant_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AuditRecord:
    record = AuditRecord(
        audit_id=_new_id(),
        actor_type=actor_type,
        actor_id=actor_id,
        tenant_id=tenant_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        correlation_id=correlation_id,
        metadata_json=_sanitize_metadata(metadata),
    )
    db.add(record)
    db.flush()
    return record
