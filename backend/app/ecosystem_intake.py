"""QA-E2: correlation / idempotency / external QARequest mapping.

An ExternalQARequest row is QA Again's own integration bookkeeping for a
Conductor Main QARequest — it does not duplicate Conductor's orchestration
state (QA-E1 §16, §36). Two distinct concerns live here:

- Idempotent intake: the same (idempotencyKey, payload) replayed must not
  create a second QA campaign; the same idempotencyKey with a *different*
  payload is a conflict, not a silent overwrite (§18).
- Explicit re-run: a deliberate re-execution against an already-mapped
  TestCycle. This always creates a new QAExecutionAttempt row, so a replay
  (zero new attempts) and a re-run (exactly one new attempt) stay
  distinguishable in the audit trail (§19).
"""

import hashlib
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from . import models
from .database import open_project_session


class IdempotencyConflictError(Exception):
    """Same idempotencyKey used with a materially different payload."""

    def __init__(self, idempotency_key: str):
        self.idempotency_key = idempotency_key
        super().__init__(f"idempotencyKey {idempotency_key!r} already used with a different payload")


class NotMappedError(Exception):
    """Re-run requested before the ExternalQARequest was mapped to a cycle."""


def fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def register_external_qa_request(
    db: Session,
    *,
    idempotency_key: str,
    qa_request_id: str,
    correlation_id: str,
    source_system: str,
    payload: dict[str, Any],
    tenant_id: Optional[str] = None,
    delivery_run_id: Optional[str] = None,
    business_intent_id: Optional[str] = None,
    engineering_result_ref: Optional[str] = None,
    infrastructure_result_ref: Optional[str] = None,
) -> tuple[models.ExternalQARequest, bool]:
    """Idempotent intake of a canonical QARequest.

    Returns (row, created). `created=False` means this was a replay of an
    already-seen (idempotencyKey, payload) pair — the existing row is
    returned unchanged, no new QA campaign is started.

    Raises IdempotencyConflictError if idempotency_key was already used
    with a different payload (caller should surface this as HTTP 409).
    """
    fp = fingerprint(payload)
    existing = (
        db.query(models.ExternalQARequest)
        .filter(models.ExternalQARequest.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        if existing.payload_fingerprint != fp:
            raise IdempotencyConflictError(idempotency_key)
        return existing, False

    row = models.ExternalQARequest(
        tenant_id=tenant_id,
        source_system=source_system,
        qa_request_id=qa_request_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        delivery_run_id=delivery_run_id,
        business_intent_id=business_intent_id,
        engineering_result_ref=engineering_result_ref,
        infrastructure_result_ref=infrastructure_result_ref,
        payload_fingerprint=fp,
        payload_json=json.dumps(payload, sort_keys=True),
        status="RECEIVED",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def map_to_cycle(
    db: Session,
    external_request: models.ExternalQARequest,
    *,
    qa_project_slug: str,
    cycle_id: int,
    triggered_by: Optional[str] = None,
) -> models.QAExecutionAttempt:
    """Maps an ExternalQARequest to a TestCycle, recording attempt #1.

    Idempotent: mapping the same ExternalQARequest twice returns the
    existing attempt #1 rather than creating a second one — mirrors intake
    idempotency at the mapping step.
    """
    project_db = open_project_session(qa_project_slug)
    try:
        existing_attempt = (
            project_db.query(models.QAExecutionAttempt)
            .filter(
                models.QAExecutionAttempt.external_qa_request_idempotency_key == external_request.idempotency_key,
                models.QAExecutionAttempt.attempt_no == 1,
            )
            .first()
        )
        if existing_attempt:
            return existing_attempt

        attempt = models.QAExecutionAttempt(
            cycle_id=cycle_id,
            external_qa_request_idempotency_key=external_request.idempotency_key,
            attempt_no=1,
            trigger="INITIAL",
            triggered_by=triggered_by,
        )
        project_db.add(attempt)
        project_db.commit()
        project_db.refresh(attempt)
    finally:
        project_db.close()

    external_request.qa_project_slug = qa_project_slug
    external_request.test_cycle_id = cycle_id
    external_request.status = "MAPPED"
    db.add(external_request)
    db.commit()

    return attempt


def explicit_rerun(
    db: Session,
    external_request: models.ExternalQARequest,
    *,
    triggered_by: Optional[str] = None,
) -> models.QAExecutionAttempt:
    """Records an explicit re-run: always a new QAExecutionAttempt row,
    distinct from idempotent replay of the same QARequest (which creates
    zero new attempts). Requires the request to already be mapped."""
    if not external_request.qa_project_slug or not external_request.test_cycle_id:
        raise NotMappedError("ExternalQARequest must be mapped to a TestCycle before it can be re-run")

    project_db = open_project_session(external_request.qa_project_slug)
    try:
        last_attempt_no = (
            project_db.query(models.QAExecutionAttempt.attempt_no)
            .filter(models.QAExecutionAttempt.cycle_id == external_request.test_cycle_id)
            .order_by(models.QAExecutionAttempt.attempt_no.desc())
            .limit(1)
            .scalar()
        ) or 0

        attempt = models.QAExecutionAttempt(
            cycle_id=external_request.test_cycle_id,
            external_qa_request_idempotency_key=external_request.idempotency_key,
            attempt_no=last_attempt_no + 1,
            trigger="EXPLICIT_RERUN",
            triggered_by=triggered_by,
        )
        project_db.add(attempt)
        project_db.commit()
        project_db.refresh(attempt)
        return attempt
    finally:
        project_db.close()
