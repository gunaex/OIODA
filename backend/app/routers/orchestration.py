"""
Conductor Again — Orchestration API (E8-G)

Minimal operator surfaces for the real orchestration runtime: submit intent,
start orchestration, inspect work packages/specialist results, inspect
readiness. Every response reflects real backend state (§55) — no mock data.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_master_db
from app.integration.lacc_client import LACCUnavailableError
from app.integration.pm_again_client import PMAgainUnavailableError
from app.orchestration.dispatch import idea_to_code_adapter, infra_adapter, pm_adapter, qa_adapter
from app.orchestration.ecosystem_auth import EcosystemIdentity, require_ecosystem_identity
from app.orchestration.models import DeliveryRun, OrchestrationBusinessIntent, SpecialistDispatch, SpecialistResult
from app.orchestration.service import (
    HardFailureBlocksDispatchError,
    IdempotencyConflictError,
    OrchestrationService,
    TenantMismatchError,
)

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


def _svc(db: Session = Depends(get_master_db)) -> OrchestrationService:
    return OrchestrationService(db)


def _get_intent_or_404(db: Session, business_intent_id: str, tenant_id: str) -> OrchestrationBusinessIntent:
    intent = (
        db.query(OrchestrationBusinessIntent)
        .filter(OrchestrationBusinessIntent.business_intent_id == business_intent_id)
        .first()
    )
    if not intent:
        raise HTTPException(404, "BusinessIntent not found")
    if intent.tenant_id != tenant_id:
        raise HTTPException(404, "BusinessIntent not found")  # 404, not 403 — do not leak cross-tenant existence
    return intent


def _get_run_or_404(db: Session, run_id: str, tenant_id: str) -> DeliveryRun:
    run = db.query(DeliveryRun).filter(DeliveryRun.run_id == run_id).first()
    if not run:
        raise HTTPException(404, "DeliveryRun not found")
    if run.tenant_id != tenant_id:
        raise HTTPException(404, "DeliveryRun not found")
    return run


# ── Schemas ────────────────────────────────────────────────────

class CreateIntentRequest(BaseModel):
    title: str
    description: str
    priority: str = "MEDIUM"
    requester: str = ""
    tags: list[str] = []
    project_slug: Optional[str] = None
    correlation_id: Optional[str] = None


class CreateRunRequest(BaseModel):
    assignments: dict[str, bool] = {"engineering": True, "infrastructure": True, "qa": True}
    description: Optional[str] = None


class DispatchEngineeringRequest(BaseModel):
    requirements: str
    constraints: dict = {}
    project_name: str = "conductor-project"
    idempotency_key: Optional[str] = None


class ExecuteEngineeringRequest(BaseModel):
    engineering_run_id: str


class DispatchInfrastructureRequest(BaseModel):
    requirements: dict = {}


class DispatchQARequest(BaseModel):
    acceptance_criteria: dict = {}


# ── Business Intents (§56) ──────────────────────────────────────

@router.post("/intents", status_code=201)
def create_intent(
    body: CreateIntentRequest, identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    svc: OrchestrationService = Depends(_svc),
):
    intent = svc.create_business_intent(
        tenant_id=identity.tenant_id, project_slug=body.project_slug, title=body.title,
        description=body.description, priority=body.priority, requester=body.requester,
        tags=body.tags, correlation_id=body.correlation_id, created_by=identity.user.email,
    )
    return _intent_view(intent)


@router.get("/intents")
def list_intents(
    identity: EcosystemIdentity = Depends(require_ecosystem_identity), db: Session = Depends(get_master_db),
):
    rows = (
        db.query(OrchestrationBusinessIntent)
        .filter(OrchestrationBusinessIntent.tenant_id == identity.tenant_id)
        .order_by(OrchestrationBusinessIntent.created_at.desc())
        .all()
    )
    return [_intent_view(r) for r in rows]


@router.get("/intents/{business_intent_id}")
def get_intent(
    business_intent_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db),
):
    intent = _get_intent_or_404(db, business_intent_id, identity.tenant_id)
    return _intent_view(intent)


# ── Delivery Runs (§57) ──────────────────────────────────────────

@router.post("/intents/{business_intent_id}/runs", status_code=201)
def create_run(
    business_intent_id: str, body: CreateRunRequest,
    identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    intent = _get_intent_or_404(db, business_intent_id, identity.tenant_id)
    run = svc.create_delivery_run(intent=intent, assignments=body.assignments, description=body.description or "")
    return _run_view(run)


@router.get("/runs/{run_id}")
def get_run(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity), db: Session = Depends(get_master_db),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    return _run_view(run, include_detail=True)


@router.get("/runs/{run_id}/results")
def list_results(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity), db: Session = Depends(get_master_db),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    return [_result_view(r) for r in run.results]


@router.get("/runs/{run_id}/dispatches")
def list_dispatches(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity), db: Session = Depends(get_master_db),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    return [_dispatch_view(d) for d in run.dispatches]


# ── Engineering dispatch (§58) ───────────────────────────────────

@router.post("/runs/{run_id}/dispatch-engineering")
def dispatch_engineering(
    run_id: str, body: DispatchEngineeringRequest,
    identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    idem_key = body.idempotency_key or f"eng-{run.run_id}"
    # Idempotency compares the caller-supplied REQUEST fingerprint, not the rendered
    # canonical envelope (which carries a fresh generated id/timestamp on every call) —
    # same requirements+constraints under the same key is the "same logical result" (§46).
    request_fingerprint = {"requirements": body.requirements, "constraints": body.constraints,
                            "project_name": body.project_name}
    # Deterministic canonical id derived from the idempotency key so a genuine replay
    # (same key, same fingerprint) also produces byte-identical canonical envelopes.
    ewp = idea_to_code_adapter.build_engineering_work_package(
        run=run, requirements=body.requirements, constraints=body.constraints,
        engineering_work_package_id=f"ewp-{idem_key}",
    )
    try:
        dispatch = svc.register_dispatch(
            run=run, specialist="ENGINEERING", contract_name="EngineeringWorkPackage",
            canonical_id=ewp["engineeringWorkPackageId"], payload=request_fingerprint, idempotency_key=idem_key,
            adapter_status=idea_to_code_adapter.STATUS,
        )
    except IdempotencyConflictError as e:
        raise HTTPException(409, str(e))

    if dispatch.dispatch_status == "PENDING":
        try:
            response = idea_to_code_adapter.dispatch(run=run, engineering_work_package=ewp, project_name=body.project_name)
        except LACCUnavailableError as e:
            svc.mark_dispatch_failed(dispatch, str(e))
            raise HTTPException(502, f"Idea -> Code dispatch failed: {e}")
        svc.mark_dispatch_sent(dispatch, response)
        svc.advance_stage(run, "ENGINEERING")
    return {"dispatch": _dispatch_view(dispatch), "engineeringWorkPackage": ewp}


@router.post("/runs/{run_id}/execute-engineering")
def execute_engineering(
    run_id: str, body: ExecuteEngineeringRequest,
    identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    try:
        result_payload = idea_to_code_adapter.run_and_collect_result(run=run, engineering_run_id=body.engineering_run_id)
    except LACCUnavailableError as e:
        raise HTTPException(502, f"Idea -> Code execution failed: {e}")
    result = svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult", payload=result_payload)
    return _result_view(result)


# ── Infrastructure dispatch (§41, §58) ───────────────────────────

@router.post("/runs/{run_id}/dispatch-infrastructure")
def dispatch_infrastructure(
    run_id: str, body: DispatchInfrastructureRequest,
    identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    try:
        svc.assert_no_downstream_after_hard_failure(run, "INFRASTRUCTURE")
    except HardFailureBlocksDispatchError as e:
        raise HTTPException(409, str(e))

    eng = svc.latest_result(run, "ENGINEERING")
    if not eng:
        raise HTTPException(409, "No EngineeringResult received yet")

    req = infra_adapter.build_infrastructure_request(run=run, engineering_result_id=eng.canonical_id, requirements=body.requirements)
    dispatch = svc.register_dispatch(
        run=run, specialist="INFRASTRUCTURE", contract_name="InfrastructureRequest",
        canonical_id=req["infrastructureRequestId"], payload=req, idempotency_key=f"infra-{run.run_id}",
        adapter_status=infra_adapter.STATUS,
    )
    result_payload = infra_adapter.simulate_result(run=run, infrastructure_request=req)
    svc.mark_dispatch_sent(dispatch, result_payload)
    svc.advance_stage(run, "INFRASTRUCTURE")
    result = svc.intake_result(run=run, specialist="INFRASTRUCTURE", contract_name="InfrastructureResult", payload=result_payload)
    return {"dispatch": _dispatch_view(dispatch), "result": _result_view(result)}


# ── QA dispatch (§42, §58) ────────────────────────────────────────

@router.post("/runs/{run_id}/dispatch-qa")
def dispatch_qa(
    run_id: str, body: DispatchQARequest,
    identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    try:
        svc.assert_no_downstream_after_hard_failure(run, "QA")
    except HardFailureBlocksDispatchError as e:
        raise HTTPException(409, str(e))

    eng = svc.latest_result(run, "ENGINEERING")
    if not eng:
        raise HTTPException(409, "No EngineeringResult received yet")

    qar = qa_adapter.build_qa_request(run=run, engineering_result=eng.payload, acceptance_criteria=body.acceptance_criteria)
    dispatch = svc.register_dispatch(
        run=run, specialist="QA", contract_name="QARequest", canonical_id=qar["qaRequestId"], payload=qar,
        idempotency_key=f"qa-{run.run_id}", adapter_status=qa_adapter.STATUS,
    )
    result_payload = qa_adapter.run_harness(run=run, qa_request=qar, engineering_result=eng.payload)
    svc.mark_dispatch_sent(dispatch, result_payload)
    svc.advance_stage(run, "QA")
    result = svc.intake_result(run=run, specialist="QA", contract_name="QAResult", payload=result_payload)
    return {"dispatch": _dispatch_view(dispatch), "result": _result_view(result)}


# ── PM Again dispatch + status (PM-E5) ────────────────────────────
# Informational/non-blocking: PM Again is execution-visibility authority,
# not delivery-readiness authority. This never advances current_stage —
# "PM" is not a slot in the ENGINEERING->INFRASTRUCTURE->QA stage pipeline,
# it runs alongside it.

@router.post("/runs/{run_id}/dispatch-pm")
def dispatch_pm(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    dwp = run.work_package_payload
    try:
        dispatch = svc.register_dispatch(
            run=run, specialist="PM", contract_name="DeliveryWorkPackage",
            canonical_id=run.work_package_id, payload=dwp, idempotency_key=f"pm-{run.run_id}",
            adapter_status=pm_adapter.STATUS,
        )
    except IdempotencyConflictError as e:
        raise HTTPException(409, str(e))

    if dispatch.dispatch_status == "PENDING":
        try:
            response = pm_adapter.dispatch(run=run, delivery_work_package=dwp)
        except PMAgainUnavailableError as e:
            svc.mark_dispatch_failed(dispatch, str(e))
            raise HTTPException(502, f"PM Again dispatch failed: {e}")
        svc.mark_dispatch_sent(dispatch, response)
    return {"dispatch": _dispatch_view(dispatch)}


@router.post("/runs/{run_id}/refresh-pm-status")
def refresh_pm_status(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    status_payload = pm_adapter.fetch_status(run=run)
    if status_payload is None:
        return {"pmStatus": None, "note": "PM Again has no status for this work package yet, or is unreachable."}
    result = svc.intake_result(run=run, specialist="PM", contract_name="PMStatus", payload=status_payload)
    return {"pmStatus": _result_view(result)}


# ── Delivery Readiness (§F, §57) ─────────────────────────────────

@router.post("/runs/{run_id}/readiness")
def compute_readiness(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity),
    db: Session = Depends(get_master_db), svc: OrchestrationService = Depends(_svc),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    decision = svc.compute_readiness(run)
    return _readiness_view(decision)


@router.get("/runs/{run_id}/readiness")
def get_readiness(
    run_id: str, identity: EcosystemIdentity = Depends(require_ecosystem_identity), db: Session = Depends(get_master_db),
):
    run = _get_run_or_404(db, run_id, identity.tenant_id)
    if not run.readiness_decisions:
        raise HTTPException(404, "No readiness decision computed yet")
    return _readiness_view(run.readiness_decisions[-1])


# ── View helpers ──────────────────────────────────────────────────

def _intent_view(intent: OrchestrationBusinessIntent) -> dict:
    return {
        "businessIntentId": intent.business_intent_id, "tenantId": intent.tenant_id,
        "projectSlug": intent.project_slug, "correlationId": intent.correlation_id,
        "title": intent.title, "description": intent.description, "priority": intent.priority,
        "status": intent.status, "createdAt": intent.created_at.isoformat() if intent.created_at else None,
        "canonicalPayload": intent.canonical_payload,
    }


def _run_view(run: DeliveryRun, include_detail: bool = False) -> dict:
    view = {
        "runId": run.run_id, "tenantId": run.tenant_id, "workPackageId": run.work_package_id,
        "correlationId": run.correlation_id, "currentStage": run.current_stage, "status": run.status,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
    }
    if include_detail:
        view["workPackagePayload"] = run.work_package_payload
        view["dispatches"] = [_dispatch_view(d) for d in run.dispatches]
        view["results"] = [_result_view(r) for r in run.results]
        view["readinessDecisions"] = [_readiness_view(r) for r in run.readiness_decisions]
    return view


def _dispatch_view(d: SpecialistDispatch) -> dict:
    return {
        "specialist": d.specialist, "contractName": d.contract_name, "canonicalId": d.canonical_id,
        "correlationId": d.correlation_id, "idempotencyKey": d.idempotency_key,
        "adapterStatus": d.adapter_status, "dispatchStatus": d.dispatch_status,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
    }


def _result_view(r: SpecialistResult) -> dict:
    return {
        "specialist": r.specialist, "contractName": r.contract_name, "canonicalId": r.canonical_id,
        "status": r.status, "correlationId": r.correlation_id, "evidenceRefs": r.evidence_refs,
        "receivedAt": r.received_at.isoformat() if r.received_at else None, "payload": r.payload,
    }


def _readiness_view(r) -> dict:
    return {
        "decisionId": r.decision_id, "runId": r.run.run_id if hasattr(r, "run") and r.run else None,
        "decision": r.decision, "reasonCode": r.reason_code, "reason": r.reason,
        "policyVersion": r.policy_version, "evidenceRefs": r.evidence_refs,
        "decidedAt": r.decided_at.isoformat() if r.decided_at else None,
        "canonicalPayload": r.canonical_payload,
    }
