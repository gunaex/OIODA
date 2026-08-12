"""External work reference intake: correlation, idempotency, and mapping
between an ecosystem source object (e.g. Conductor's DeliveryWorkPackage)
and whatever PM Again created locally in response to it."""

import hashlib
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


def _payload_hash(payload: dict) -> str:
    # Canonical JSON (sorted keys) so semantically-identical payloads with
    # different key ordering hash the same.
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyConflict(Exception):
    def __init__(self, existing: "models.ExternalWorkReference"):
        self.existing = existing
        super().__init__(
            f"idempotency_key {existing.idempotency_key!r} was already used with a different payload"
        )


def record_external_work(
    db: Session,
    *,
    source_system: str,
    source_object_type: str,
    source_object_id: str,
    correlation_id: str,
    idempotency_key: str,
    payload: dict,
    tenant_id: str | None = None,
) -> tuple["models.ExternalWorkReference", bool]:
    """Returns (reference, created). Same idempotency_key + same payload ->
    the existing row is returned unchanged (created=False) — no duplicate
    work. Same idempotency_key + a different payload -> IdempotencyConflict,
    which the caller should turn into an explicit 409."""

    incoming_hash = _payload_hash(payload)

    existing = (
        db.query(models.ExternalWorkReference)
        .filter(models.ExternalWorkReference.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        if existing.payload_hash != incoming_hash:
            raise IdempotencyConflict(existing)
        return existing, False

    reference = models.ExternalWorkReference(
        tenant_id=tenant_id,
        source_system=source_system,
        source_object_type=source_object_type,
        source_object_id=source_object_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        payload_hash=incoming_hash,
        status="RECEIVED",
    )
    db.add(reference)
    db.commit()
    db.refresh(reference)
    return reference, True


def attach_local_mapping(
    db: Session,
    reference: "models.ExternalWorkReference",
    *,
    project_id: int | None = None,
    local_object_type: str | None = None,
    local_object_id: str | None = None,
    status: str | None = None,
) -> "models.ExternalWorkReference":
    if project_id is not None:
        reference.project_id = project_id
    if local_object_type is not None:
        reference.local_object_type = local_object_type
    if local_object_id is not None:
        reference.local_object_id = local_object_id
    if status is not None:
        reference.status = status
    reference.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(reference)
    return reference


def add_evidence(
    db: Session,
    reference: "models.ExternalWorkReference",
    *,
    type: str | None = None,
    source: str | None = None,
    reference_value: str | None = None,
    summary: str | None = None,
) -> "models.EvidenceReference":
    evidence = models.EvidenceReference(
        external_work_reference_id=reference.id,
        type=type,
        source=source,
        reference=reference_value,
        summary=summary,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def raise_conflict_http(exc: IdempotencyConflict) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "error": "idempotency_conflict",
            "message": str(exc),
            "existing_reference_id": exc.existing.id,
        },
    )
