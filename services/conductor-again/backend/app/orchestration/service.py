"""
Conductor Again — Orchestration Service (E8-B).

The actual missing heart of Conductor: BusinessIntent intake, DeliveryRun
creation, work-package generation, specialist dispatch/result-intake
bookkeeping, and hard-failure short-circuiting (§23). This module does NOT
perform specialist work itself — dispatch adapters (E8-E) do that.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.contracts import v1
from app.contracts.validator import CanonicalContractValidator
from app.orchestration.models import (
    DeliveryRun,
    OrchestrationBusinessIntent,
    ReadinessDecision,
    SpecialistDispatch,
    SpecialistResult,
)
from app.orchestration.readiness import ReadinessInputs, evaluate_readiness
from app.orchestration.state_machine import (
    InvalidTransitionError,
    transition_business_intent,
    transition_run_stage,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class TenantMismatchError(Exception):
    pass


class IdempotencyConflictError(Exception):
    """Same idempotency key, different payload (§46)."""


class HardFailureBlocksDispatchError(Exception):
    """A hard upstream failure blocks the requested downstream dispatch (§23)."""


class OrchestrationService:
    def __init__(self, db: Session):
        self.db = db

    # ── BusinessIntent (§13) ──────────────────────────────────

    def create_business_intent(
        self, *, tenant_id: str, project_slug: Optional[str], title: str, description: str,
        priority: str, requester: str = "", tags: Optional[list[str]] = None,
        correlation_id: Optional[str] = None, created_by: str = "",
    ) -> OrchestrationBusinessIntent:
        business_intent_id = _id("bi")
        correlation_id = correlation_id or _id("corr")
        canonical = v1.BusinessIntent.validate_canonical({
            "businessIntentId": business_intent_id,
            "correlationId": correlation_id,
            "title": title,
            "description": description,
            "priority": priority,
            "requester": requester,
            "tags": tags or [],
            "createdAt": _now_iso(),
        })
        row = OrchestrationBusinessIntent(
            business_intent_id=business_intent_id,
            tenant_id=tenant_id,
            project_slug=project_slug,
            correlation_id=correlation_id,
            title=title,
            description=description,
            priority=priority,
            requester=requester,
            tags=tags or [],
            status="RECEIVED",
            canonical_payload=canonical.to_canonical_dict(),
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def transition_intent_status(self, intent: OrchestrationBusinessIntent, target: str) -> OrchestrationBusinessIntent:
        transition_business_intent(intent.status, target)  # raises InvalidTransitionError if illegal
        intent.status = target
        self.db.commit()
        self.db.refresh(intent)
        return intent

    def require_tenant(self, obj, tenant_id: str):
        """Tenant isolation enforcement (§29). Raise, never silently filter."""
        if obj.tenant_id != tenant_id:
            raise TenantMismatchError(
                f"{type(obj).__name__} belongs to tenant {obj.tenant_id!r}, not {tenant_id!r}"
            )

    # ── DeliveryWorkPackage + DeliveryRun (§15, §21) ─────────

    def create_delivery_run(
        self, *, intent: OrchestrationBusinessIntent, assignments: dict, description: str = "",
        engineering_context: Optional[dict] = None, infrastructure_context: Optional[dict] = None,
        qa_context: Optional[dict] = None,
    ) -> DeliveryRun:
        work_package_id = _id("wp")
        run_id = _id("run")
        canonical = v1.DeliveryWorkPackage.validate_canonical({
            "workPackageId": work_package_id,
            "correlationId": intent.correlation_id,
            "businessIntentId": intent.business_intent_id,
            "title": intent.title,
            "description": description or intent.description,
            "priority": intent.priority,
            "state": "PLANNED",
            "assignments": assignments,
            "engineeringContext": engineering_context,
            "infrastructureContext": infrastructure_context,
            "qaContext": qa_context,
            "createdAt": _now_iso(),
        })
        run = DeliveryRun(
            run_id=run_id,
            tenant_id=intent.tenant_id,
            business_intent_id=intent.id,
            work_package_id=work_package_id,
            correlation_id=intent.correlation_id,
            current_stage="PLAN",
            status="IN_PROGRESS",
            work_package_payload=canonical.to_canonical_dict(),
        )
        self.db.add(run)
        if intent.status == "RECEIVED":
            self.transition_intent_status(intent, "ANALYZING")
        if intent.status == "ANALYZING":
            self.transition_intent_status(intent, "PLANNED")
        self.db.commit()
        self.db.refresh(run)
        return run

    # ── Idempotency (§46) ────────────────────────────────────

    def find_existing_dispatch(self, idempotency_key: str) -> Optional[SpecialistDispatch]:
        return (
            self.db.query(SpecialistDispatch)
            .filter(SpecialistDispatch.idempotency_key == idempotency_key)
            .first()
        )

    def register_dispatch(
        self, *, run: DeliveryRun, specialist: str, contract_name: str, canonical_id: str,
        payload: dict, idempotency_key: str, adapter_status: str, causation_id: Optional[str] = None,
    ) -> SpecialistDispatch:
        existing = self.find_existing_dispatch(idempotency_key)
        if existing:
            if existing.request_payload != payload:
                raise IdempotencyConflictError(
                    f"idempotencyKey {idempotency_key!r} already used with a different payload"
                )
            return existing  # same key + same payload -> same logical result (§46)

        dispatch = SpecialistDispatch(
            run_id=run.id,
            tenant_id=run.tenant_id,
            specialist=specialist,
            contract_name=contract_name,
            canonical_id=canonical_id,
            correlation_id=run.correlation_id,
            causation_id=causation_id,
            idempotency_key=idempotency_key,
            request_payload=payload,
            adapter_status=adapter_status,
            dispatch_status="PENDING",
        )
        self.db.add(dispatch)
        self.db.commit()
        self.db.refresh(dispatch)
        return dispatch

    def advance_stage(self, run: DeliveryRun, target_stage: str):
        run.current_stage = transition_run_stage(run.current_stage, target_stage)
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_dispatch_sent(self, dispatch: SpecialistDispatch, response_payload: Optional[dict] = None):
        dispatch.dispatch_status = "SENT"
        dispatch.sent_at = datetime.now(timezone.utc)
        if response_payload is not None:
            dispatch.response_payload = response_payload
        self.db.commit()

    def mark_dispatch_failed(self, dispatch: SpecialistDispatch, error: str):
        dispatch.dispatch_status = "FAILED"
        dispatch.error = error
        self.db.commit()

    # ── Hard failure rule (§23) ──────────────────────────────

    def assert_no_downstream_after_hard_failure(self, run: DeliveryRun, next_specialist: str):
        """Raise HardFailureBlocksDispatchError if an upstream specialist hard-failed."""
        eng_result = self.latest_result(run, "ENGINEERING")
        if next_specialist in ("INFRASTRUCTURE", "QA") and eng_result and eng_result.status == "FAILED":
            raise HardFailureBlocksDispatchError(
                f"Engineering hard-failed ({eng_result.canonical_id}); {next_specialist} dispatch blocked."
            )
        if next_specialist == "QA":
            infra_result = self.latest_result(run, "INFRASTRUCTURE")
            if infra_result and infra_result.status == "FAILED":
                raise HardFailureBlocksDispatchError(
                    f"Infrastructure hard-failed ({infra_result.canonical_id}); QA dispatch blocked."
                )

    def latest_result(self, run: DeliveryRun, specialist: str) -> Optional[SpecialistResult]:
        return (
            self.db.query(SpecialistResult)
            .filter(SpecialistResult.run_id == run.id, SpecialistResult.specialist == specialist)
            .order_by(SpecialistResult.received_at.desc())
            .first()
        )

    # ── Specialist result intake (§20) ───────────────────────

    def intake_result(
        self, *, run: DeliveryRun, specialist: str, contract_name: str, payload: dict,
    ) -> SpecialistResult:
        """Validate against the canonical contract, match correlation, store."""
        model_cls = {
            "EngineeringResult": v1.EngineeringResult,
            "InfrastructureResult": v1.InfrastructureResult,
            "QAResult": v1.QAResult,
            "PMStatus": v1.PMStatus,
        }[contract_name]
        validated = model_cls.validate_canonical(payload)
        data = validated.to_canonical_dict()

        if data.get("correlationId") != run.correlation_id:
            raise ValueError(
                f"correlationId {data.get('correlationId')!r} does not match run correlation {run.correlation_id!r}"
            )
        if data.get("workPackageId") and data["workPackageId"] != run.work_package_id:
            raise ValueError(
                f"workPackageId {data.get('workPackageId')!r} does not match run work package {run.work_package_id!r}"
            )

        canonical_id_field = {
            "EngineeringResult": "engineeringResultId",
            "InfrastructureResult": "infrastructureResultId",
            "QAResult": "qaResultId",
            "PMStatus": "pmStatusId",
        }[contract_name]
        status_field = {
            "EngineeringResult": "status",
            "InfrastructureResult": "status",
            "QAResult": "qualityGate",
            "PMStatus": "projectStatus",
        }[contract_name]

        result = SpecialistResult(
            run_id=run.id,
            tenant_id=run.tenant_id,
            specialist=specialist,
            contract_name=contract_name,
            canonical_id=data[canonical_id_field],
            correlation_id=data["correlationId"],
            status=data.get(status_field, ""),
            payload=data,
            evidence_refs=[e.get("reference") for e in data.get("evidence", [])] if data.get("evidence") else [],
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    # ── Readiness (E8-F) ──────────────────────────────────────

    def compute_readiness(self, run: DeliveryRun) -> ReadinessDecision:
        assignments = (run.work_package_payload or {}).get("assignments", {})
        eng = self.latest_result(run, "ENGINEERING")
        infra = self.latest_result(run, "INFRASTRUCTURE")
        qa = self.latest_result(run, "QA")
        pm = self.latest_result(run, "PM")

        eng_blocking = bool((eng.payload.get("conductorPolicy") or {}).get("blocking")) if eng else False

        inputs = ReadinessInputs(
            assignments=assignments,
            engineering_status=eng.status if eng else None,
            engineering_partial_blocking=eng_blocking,
            infrastructure_status=infra.status if infra else None,
            qa_quality_gate=qa.status if qa else None,
            pm_project_status=pm.status if pm else None,
            evidence_refs=[
                *(eng.evidence_refs if eng else []),
                *(infra.evidence_refs if infra else []),
                *(qa.evidence_refs if qa else []),
                *(pm.evidence_refs if pm else []),
            ],
        )
        decision = evaluate_readiness(inputs)

        aggregated_evidence = {
            "pmEvidence": (pm.payload.get("evidence") if pm else []) or [],
            "engineeringEvidence": (eng.payload.get("evidence") if eng else []) or [],
            "infrastructureEvidence": (infra.payload.get("evidence") if infra else []) or [],
            "qaEvidence": (qa.payload.get("evidence") if qa else []) or [],
        }
        specialist_results = {
            k: v for k, v in {
                "pmStatus": pm.status if pm else None,
                "engineeringStatus": eng.status if eng else None,
                "infrastructureStatus": infra.status if infra else None,
                "qaQualityGate": qa.status if qa else None,
            }.items() if v is not None
        }

        decision_id = _id("drr")
        canonical = v1.DeliveryReadinessResult.validate_canonical({
            "deliveryReadinessResultId": decision_id,
            "correlationId": run.correlation_id,
            "workPackageId": run.work_package_id,
            "decision": decision.decision,
            "reason": decision.reason,
            "aggregatedEvidence": aggregated_evidence,
            "specialistResults": specialist_results,
            "decidedBy": "conductor-main",
            "decidedAt": _now_iso(),
        })

        row = ReadinessDecision(
            decision_id=decision_id,
            run_id=run.id,
            tenant_id=run.tenant_id,
            correlation_id=run.correlation_id,
            decision=decision.decision,
            reason_code=decision.reason_code,
            reason=decision.reason,
            inputs_ref={
                "pmStatusId": pm.canonical_id if pm else None,
                "engineeringResultId": eng.canonical_id if eng else None,
                "infrastructureResultId": infra.canonical_id if infra else None,
                "qaResultId": qa.canonical_id if qa else None,
            },
            evidence_refs=inputs.evidence_refs,
            canonical_payload=canonical.to_canonical_dict(),
        )
        self.db.add(row)
        run.status = decision.decision
        # Readiness is the terminal decision authority: it always resolves the run to
        # COMPLETE regardless of which upstream stages actually ran (dispatch adapters
        # advance current_stage step-by-step in the live flow; a hard-failure or
        # missing-assignment short-circuit can reach here from any earlier stage).
        run.current_stage = "COMPLETE"
        if decision.decision == "READY_FOR_DELIVERY":
            self.transition_intent_status_safe(run, "READY_FOR_REVIEW")
        self.db.commit()
        self.db.refresh(row)
        return row

    def transition_intent_status_safe(self, run: DeliveryRun, target: str):
        intent = run.business_intent
        try:
            transition_business_intent(intent.status, target)
        except InvalidTransitionError:
            return
        intent.status = target
