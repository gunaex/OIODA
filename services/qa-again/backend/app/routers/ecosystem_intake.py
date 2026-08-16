"""QA-E4/E5: Conductor Main -> QA Again ecosystem intake + QAResult delivery.

Single service-authenticated boundary a Conductor-issued QARequest crosses
into QA Again's own domain, and the canonical QAResult crosses back out.
Mirrors PM Again's app/routers/ecosystem_intake.py in shape and philosophy.
"""

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..contracts.v1 import QARequest as CanonicalQARequest
from ..contracts.validator import CanonicalContractValidator, ContractValidationError
from ..database import get_master_db, open_project_session
from ..ecosystem import account_again_client
from ..ecosystem.ecosystem_auth import ECOSYSTEM_MODE
from ..ecosystem.mapping_service import TenantMismatch, intake_qa_request
from ..ecosystem.service_auth import require_conductor_service_identity
from .. import ecosystem_intake as ecosystem_intake_service
from ..ecosystem_intake import IdempotencyConflictError, NotMappedError
from ..qa_result_service import QAResultNotAvailableError, build_qa_result

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])

CONDUCTOR_MAIN_URL = os.environ.get("CONDUCTOR_MAIN_URL", "http://localhost:8010/api")


@router.post("/qa-requests")
def intake_qa_request_endpoint(
    request: Request,
    payload: dict,
    master_db: Session = Depends(get_master_db),
    claims: dict = Depends(require_conductor_service_identity),
):
    # Canonical validation first — a payload that doesn't conform is
    # rejected before it ever touches QA Again's own domain.
    try:
        CanonicalContractValidator.validate("QARequest", payload)
    except ContractValidationError as exc:
        raise HTTPException(status_code=422, detail=f"QARequest does not conform to canonical schema: {exc.errors}")

    try:
        qar = CanonicalQARequest.model_validate(payload)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    idempotency_key = request.headers.get("Idempotency-Key") or f"CONDUCTOR_MAIN:QA_REQUEST:{qar.qaRequestId}"
    # Prefer the caller's per-request tenant context over the service
    # token's own (often-null, shared-across-tenants) registered tenant —
    # same convention as PM Again's DeliveryWorkPackage intake.
    tenant_id = request.headers.get("X-Tenant-Id") or claims.get("tenantId")

    try:
        external_request, project, created = intake_qa_request(
            master_db, qar, idempotency_key=idempotency_key, tenant_id=tenant_id
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": "idempotency_conflict", "message": str(exc), "idempotencyKey": exc.idempotency_key},
        )
    except TenantMismatch as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "externalQARequestId": external_request.id,
        "correlationId": external_request.correlation_id,
        "qaProjectSlug": project.slug if project else None,
        "testCycleId": external_request.test_cycle_id,
        "status": external_request.status,
        "created": created,
    }


def _find_external_request_or_404(master_db: Session, qa_request_id: str) -> models.ExternalQARequest:
    external_request = (
        master_db.query(models.ExternalQARequest)
        .filter(models.ExternalQARequest.qa_request_id == qa_request_id)
        .order_by(models.ExternalQARequest.created_at.desc())
        .first()
    )
    if not external_request:
        raise HTTPException(status_code=404, detail=f"No ExternalQARequest found for qaRequestId {qa_request_id!r}")
    return external_request


def _enforce_request_tenant(external_request: models.ExternalQARequest, request: Request, claims: dict) -> None:
    """CROSS_TENANT_QAREQUEST_BLOCKED / CROSS_TENANT_QARESULT_BLOCKED —
    CONDUCTOR_MAIN is a shared, cross-tenant service identity by design
    (QA-E6), so the service token alone is never enough to authorize
    access to a specific tenant's QARequest/QAResult: the caller's
    per-request tenant context must also match what this ExternalQARequest
    was actually intaken under. An ExternalQARequest intaken with no
    tenant (tenant_id is None) stays exempt, matching the same convention
    used for untenanted projects elsewhere. 404, not 403, to avoid leaking
    cross-tenant existence."""
    if not external_request.tenant_id:
        return
    caller_tenant = request.headers.get("X-Tenant-Id") or claims.get("tenantId")
    if caller_tenant != external_request.tenant_id:
        raise HTTPException(status_code=404, detail=f"No ExternalQARequest found for qaRequestId {external_request.qa_request_id!r}")


@router.post("/qa-requests/{qa_request_id}/rerun")
def rerun_qa_request(
    qa_request_id: str,
    request: Request,
    master_db: Session = Depends(get_master_db),
    claims: dict = Depends(require_conductor_service_identity),
):
    """QA-E9.9 — explicit re-run, distinct from idempotent replay of
    POST /qa-requests: this always records a new QAExecutionAttempt
    (QA-E2's ecosystem_intake.explicit_rerun), never a new TestCycle or a
    second ExternalQARequest. Requires the request to already be mapped
    to a cycle (QA-E4)."""
    external_request = _find_external_request_or_404(master_db, qa_request_id)
    _enforce_request_tenant(external_request, request, claims)
    triggered_by = f"ecosystem:{claims.get('systemId', 'CONDUCTOR_MAIN')}"
    try:
        attempt = ecosystem_intake_service.explicit_rerun(master_db, external_request, triggered_by=triggered_by)
    except NotMappedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return {
        "externalQARequestId": external_request.id,
        "qaProjectSlug": external_request.qa_project_slug,
        "testCycleId": external_request.test_cycle_id,
        "attemptId": attempt.id,
        "attemptNo": attempt.attempt_no,
        "trigger": attempt.trigger,
    }


@router.get("/qa-requests/{qa_request_id}/qa-result")
def qa_result_by_qa_request_id(
    qa_request_id: str,
    request: Request,
    master_db: Session = Depends(get_master_db),
    claims: dict = Depends(require_conductor_service_identity),
):
    """Service-authenticated canonical QAResult lookup keyed by
    qaRequestId — the identifier Conductor actually holds, distinct from
    the human-facing /api/{slug}/cycles/{cycle_id}/qa-result endpoint."""
    external_request = (
        master_db.query(models.ExternalQARequest)
        .filter(models.ExternalQARequest.qa_request_id == qa_request_id)
        .order_by(models.ExternalQARequest.created_at.desc())
        .first()
    )
    if not external_request or not external_request.qa_project_slug or not external_request.test_cycle_id:
        raise HTTPException(status_code=404, detail="No QA Again cycle mapped for this qaRequestId yet")
    _enforce_request_tenant(external_request, request, claims)

    project_db = open_project_session(external_request.qa_project_slug)
    try:
        try:
            qa_result = build_qa_result(
                project_db, master_db, slug=external_request.qa_project_slug, cycle_id=external_request.test_cycle_id
            )
        except QAResultNotAvailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    finally:
        project_db.close()

    return qa_result.to_canonical_dict()


def _conductor_reachable() -> bool:
    try:
        resp = httpx.get(f"{CONDUCTOR_MAIN_URL}/health", timeout=3.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


@router.get("/connection-status")
def connection_status(_user: models.User = Depends(get_current_user)):
    """Real, API-backed connection diagnostics for the operator UI —
    QA_ECOSYSTEM_UI_NOT_MOCK_BACKED. Never claims a connection that wasn't
    actually probed."""
    return {
        "ecosystemMode": ECOSYSTEM_MODE,
        "accountAgain": {"reachable": account_again_client.health()},
        "conductorMain": {"reachable": _conductor_reachable()},
    }
