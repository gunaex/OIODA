"""
Conductor Main — Document Again handoff relay (P5-A).

Acceptance point for Document Again design handoffs (DOCUMENT_AGAIN service
identity only). Conductor maps the design handoff into the canonical
DeliveryWorkPackage (PM) or QARequest (QA) vocabulary and dispatches it —
Conductor, not Document Again, owns the execution/verification mapping.

Idempotent: repeated delivery of the same handoff_id returns the same
acknowledgement and never dispatches a duplicate package/request.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_master_db
from app.integration import pm_again_client, qa_again_client
from app.integration.service_auth import require_document_again_service_identity
from app.models import DocumentHandoff

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])

SUPPORTED_CONTRACT = {"name": "document-again-handoff", "version": 1}
HANDOFF_TYPES = {"EXECUTION", "QA_VALIDATION"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _map_execution(h: dict, handoff_id: str, correlation_id: str, project_id: str | None, baseline_id: str | None) -> dict:
    return {
        "workPackageId": handoff_id,
        "correlationId": correlation_id,
        "businessIntentId": project_id or "document-again",
        "title": h.get("title") or f"Design baseline {baseline_id or handoff_id}",
        "priority": "HIGH",
        "state": "DRAFT",
        "assignments": {},
        "engineeringContext": {"requirements": h.get("requirement_ids") or []},
        "createdAt": _now_iso(),
    }


def _map_qa(h: dict, handoff_id: str, correlation_id: str, project_id: str | None, baseline_id: str | None) -> dict:
    return {
        "qaRequestId": handoff_id,
        "correlationId": correlation_id,
        "workPackageId": handoff_id,
        "releaseCandidate": {
            "baselineId": baseline_id,
            "artifactRevisionIds": h.get("artifact_revision_ids") or [],
            "targetRelease": h.get("target_release"),
            "projectId": project_id,
        },
        "acceptanceCriteria": {
            "requirementIds": h.get("requirement_ids") or [],
            "semanticObjectIds": h.get("semantic_object_ids") or [],
            "designRevisionIds": h.get("design_revision_ids") or [],
        },
        "knownIssues": [],
        "recommendedRegressionAreas": [],
        "createdAt": _now_iso(),
    }


def _ack(record: DocumentHandoff, *, duplicate: bool = False) -> dict:
    return {
        "contract": SUPPORTED_CONTRACT,
        "handoff_id": record.handoff_id,
        "handoff_type": record.handoff_type,
        "status": record.status,
        "correlationId": record.correlation_id,
        "externalReferenceId": record.external_reference or None,
        "duplicate": duplicate,
        "acknowledgedAt": record.acknowledged_at.isoformat() if record.acknowledged_at else None,
    }


@router.post("/document-handoffs")
def accept_document_handoff(
    request: Request,
    payload: dict,
    master_db: Session = Depends(get_master_db),
    claims: dict = Depends(require_document_again_service_identity),
):
    contract = payload.get("contract")
    if not isinstance(contract, dict) or contract.get("name") != SUPPORTED_CONTRACT["name"] or contract.get("version") != SUPPORTED_CONTRACT["version"]:
        raise HTTPException(status_code=422, detail="Unsupported or missing document-again-handoff contract")

    handoff_type = payload.get("handoff_type")
    if handoff_type not in HANDOFF_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown handoff_type {handoff_type!r}")

    handoff_id = payload.get("handoff_id")
    if not handoff_id:
        raise HTTPException(status_code=422, detail="handoff_id is required")

    correlation_id = payload.get("correlation_id") or handoff_id
    # Tenant context: Document Again's own validated tenant (per-request),
    # consistent with Conductor's own X-Tenant-Id convention for downstream
    # dispatch. The DOCUMENT_AGAIN token is verified before this point.
    tenant_id = payload.get("tenant_id") or claims.get("tenantId")
    project_id = payload.get("project_id")
    baseline_id = payload.get("baseline_id")

    existing = master_db.query(DocumentHandoff).filter(DocumentHandoff.handoff_id == handoff_id).first()
    if existing:
        if existing.status == "FAILED":
            pass  # fall through to retry dispatch below
        else:
            return _ack(existing, duplicate=True)

    if existing is None:
        existing = DocumentHandoff(
            handoff_id=handoff_id, handoff_type=handoff_type, tenant_id=tenant_id,
            project_id=project_id, baseline_id=baseline_id, correlation_id=correlation_id,
            status="QUEUED", payload_snapshot=payload,
        )
        master_db.add(existing)
        master_db.commit()
        master_db.refresh(existing)

    idempotency_key = f"DOCUMENT_AGAIN:{handoff_id}"
    try:
        if handoff_type == "EXECUTION":
            dwp = _map_execution(payload, handoff_id, correlation_id, project_id, baseline_id)
            ref = pm_again_client.PMAgainClient.dispatch_delivery_work_package(
                delivery_work_package=dwp, idempotency_key=idempotency_key, tenant_id=tenant_id,
            )
            external_ref = ref.get("externalWorkReferenceId") or ref.get("correlationId") or ""
        else:
            qa = _map_qa(payload, handoff_id, correlation_id, project_id, baseline_id)
            ref = qa_again_client.QAAgainClient.dispatch_qa_request(
                qa_request=qa, idempotency_key=idempotency_key, tenant_id=tenant_id,
            )
            external_ref = ref.get("externalReferenceId") or ref.get("correlationId") or ""
    except (pm_again_client.PMAgainUnavailableError, qa_again_client.QAAgainUnavailableError) as exc:
        existing.status = "FAILED"
        existing.last_error = str(exc)[:500]
        master_db.commit()
        raise HTTPException(status_code=502, detail=f"Downstream dispatch failed: {exc}") from exc

    existing.status = "ACKNOWLEDGED"
    existing.external_reference = external_ref
    existing.dispatched_at = datetime.now(timezone.utc)
    existing.acknowledged_at = datetime.now(timezone.utc)
    existing.last_error = ""
    master_db.commit()
    master_db.refresh(existing)
    return _ack(existing)
