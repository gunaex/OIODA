"""R17.5 controlled, human-triggered owner action routing.

Wave 1 uses the existing Document -> Conductor -> PM/QA handoff boundary.
Owner services persist their own truth; these rows are orchestration evidence.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import services as svc
from ..project_truth import build_project_truth, normalize_bindings
from ..services import DomainError, record_audit
from .models import ImpactActionEvent, ImpactActionRoute, ImpactConfirmation

CONTRACT = "action_route/v1"
REGISTRY_VERSION = "impact_action_registry/v1"
TERMINAL = {"SUCCEEDED", "FAILED", "CONFLICT", "UNAUTHORIZED", "FORBIDDEN", "OWNER_UNAVAILABLE", "STALE", "UNKNOWN_RESULT"}
REGISTRY = {
    "ROUTE_PM_DELIVERY_HANDOFF": {
        "owner": "PM_AGAIN", "execution_mode": "CONTROLLED_OWNER_WRITE", "risk_class": "LOW",
        "required_permission": "existing project mutation authorization",
        "required_fields": [], "idempotency": "OIDA route key + Conductor handoff ID + PM native key",
        "label": "Create PM Delivery Handoff",
    },
    "ROUTE_QA_VALIDATION_HANDOFF": {
        "owner": "QA_AGAIN", "execution_mode": "CONTROLLED_OWNER_WRITE", "risk_class": "LOW",
        "required_permission": "existing project mutation authorization",
        "required_fields": ["qa_scope_id when multiple bound scopes exist"],
        "idempotency": "OIDA route key + Conductor handoff ID + QA native key",
        "label": "Create QA Validation Handoff",
    },
}
PROHIBITED = {"CUSTOMER_ACCEPTANCE", "SIGN_OFF", "APPROVE_WAIVER", "DEPLOY_INFRA", "ROLLBACK",
              "DELETE_PROJECT", "RUN_TESTS", "BULK_PM_UPDATE", "AUTO_REGENERATE", "CREATE_CR"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def registry() -> dict:
    return {"contract_version": REGISTRY_VERSION, "actions": REGISTRY,
            "prohibited": sorted(PROHIBITED), "arbitrary_actions": False}


def _confirmation(db: Session, project_id: str, confirmation_id: str,
                  current_evidence_hash: str) -> ImpactConfirmation:
    row = db.get(ImpactConfirmation, confirmation_id)
    if not row or row.project_id != project_id:
        raise DomainError("Confirmed impact context was not found", status_code=404)
    if row.decision != "CONFIRMED":
        raise DomainError("A current CONFIRMED relationship is required", status_code=409)
    if row.evidence_hash != current_evidence_hash:
        raise DomainError("Confirmation is STALE; review the relationship again", status_code=409)
    return row


def preview(db: Session, project, *, action_type: str, confirmation_id: str,
            current_evidence_hash: str, parameters: dict | None = None) -> dict:
    started = time.monotonic()
    if action_type not in REGISTRY:
        category = "PROHIBITED" if action_type in PROHIBITED else "NOT_SUPPORTED"
        return {"contract_version": CONTRACT, "status": "NOT_AVAILABLE", "failure_category": category,
                "human_trigger_required": True, "executable": False}
    confirmation = _confirmation(db, project.id, confirmation_id, current_evidence_hash)
    params = parameters or {}
    bindings = normalize_bindings(project)
    spec = REGISTRY[action_type]
    status, missing, target = "READY", [], None
    if action_type == "ROUTE_PM_DELIVERY_HANDOFF":
        binding = bindings["pm"]
        target = binding.get("external_project_id")
        if binding.get("binding_status") != "BOUND" or not target:
            status = "NOT_AVAILABLE"
    else:
        available = [q for q in bindings["qa"] if q.get("binding_status") == "BOUND" and q.get("external_project_id")]
        selected = params.get("qa_scope_id")
        if len(available) > 1 and not selected:
            status, missing = "REQUIRES_INPUT", ["qa_scope_id"]
        elif selected and not any(selected in {q.get("scope_id"), q.get("external_project_id")} for q in available):
            status, missing = "REQUIRES_INPUT", ["valid qa_scope_id"]
        elif not available:
            status = "NOT_AVAILABLE"
        else:
            target = selected or available[0].get("external_project_id")
    preview_core = {"project_id": project.id, "confirmation_id": confirmation.id,
                    "action_type": action_type, "target_service": spec["owner"],
                    "target_entity_id": target, "parameters": params,
                    "evidence_hash": current_evidence_hash}
    return {"contract_version": CONTRACT, "action_route_id": f"PREVIEW-{_hash(preview_core)[:16]}",
            **preview_core, "status": status, "required_input": missing,
            "label": spec["label"], "execution_mode": spec["execution_mode"],
            "risk_class": spec["risk_class"], "human_trigger_required": True,
            "executable": status == "READY", "what_will_change":
                ("PM Again will persist an idempotent delivery work-package reference via Conductor Main."
                 if action_type == "ROUTE_PM_DELIVERY_HANDOFF" else
                 "QA Again will persist an idempotent QA-request reference via Conductor Main."),
            "what_will_not_change": "No customer acceptance, sign-off, Infra state, or local shadow owner record will be created.",
            "evidence_refs": [confirmation.id, confirmation.relationship_id, current_evidence_hash],
            "precondition_snapshot": {"confirmation_decision": confirmation.decision,
                                      "confirmation_evidence_hash": confirmation.evidence_hash,
                                      "bindings": bindings},
            "preview_latency_ms": round((time.monotonic() - started) * 1000, 2)}


def _event(db: Session, route: ImpactActionRoute, event: str, actor_id: str, **detail) -> None:
    db.add(ImpactActionEvent(action_route_id=route.id, event_type=event,
                             actor_user_id=actor_id, detail=detail))


class OwnerRouter:
    """Mockable adapter over the already-supported owner handoff APIs."""
    def execute(self, db: Session, project, action_type: str, parameters: dict, actor) -> tuple[dict, float, float]:
        mutation_started = time.monotonic()
        if action_type == "ROUTE_PM_DELIVERY_HANDOFF":
            created = svc.create_execution_handoff(
                db, project_id=project.id, baseline_id=parameters.get("baseline_id"),
                source_revision_id=parameters.get("source_revision_id"), status="READY",
                actor=actor.name, actor_id=actor.id)
            kind = "execution"
        else:
            created = svc.create_qa_validation_handoff(
                db, project_id=project.id, baseline_id=parameters.get("baseline_id"),
                requirement_ids=parameters.get("requirement_ids") or [],
                semantic_object_ids=parameters.get("semantic_object_ids") or [],
                design_revision_ids=parameters.get("design_revision_ids") or [],
                target_release=parameters.get("target_release"), status="READY",
                actor=actor.name, actor_id=actor.id)
            kind = "qa"
        try:
            delivered = svc.deliver_handoff_to_conductor(db, created["id"], kind)
        except Exception as exc:
            # A timeout may occur after Conductor/owner persistence. Reconcile
            # the local owner acknowledgement once; never blindly resend.
            rows = (svc.list_execution_handoffs(db, project.id) if kind == "execution"
                    else svc.list_qa_handoffs(db, project.id))
            observed = next((row for row in rows if row["id"] == created["id"]), None)
            if observed and observed.get("status") == "ACKNOWLEDGED" and observed.get("external_reference"):
                delivered = observed
            else:
                setattr(exc, "reconciliation_attempted", True)
                raise
        mutation_ms = (time.monotonic() - mutation_started) * 1000
        reconcile_started = time.monotonic()
        rows = (svc.list_execution_handoffs(db, project.id) if kind == "execution"
                else svc.list_qa_handoffs(db, project.id))
        verified = next((row for row in rows if row["id"] == created["id"]), None)
        reconcile_ms = (time.monotonic() - reconcile_started) * 1000
        if not verified or verified.get("status") != "ACKNOWLEDGED" or not verified.get("external_reference"):
            raise DomainError("Owner result could not be reconciled after dispatch", status_code=502)
        return {"service": REGISTRY[action_type]["owner"], "entity_id": verified["external_reference"],
                "handoff_id": verified["id"], "status": verified["status"],
                "created_at": verified.get("created_at")}, mutation_ms, reconcile_ms


def _failure(exc: Exception) -> str:
    text = str(exc).lower()
    code = getattr(exc, "status_code", None)
    if code == 401: return "UNAUTHORIZED"
    if code == 403: return "FORBIDDEN"
    if code == 409: return "CONFLICT"
    if "timeout" in text: return "UNKNOWN_RESULT"
    if code in {502, 503} or "unreachable" in text or "unavailable" in text: return "OWNER_UNAVAILABLE"
    if code == 422: return "VALIDATION_FAILED"
    return "OWNER_ERROR"


def execute(db: Session, project, *, action_type: str, confirmation_id: str,
            current_evidence_hash: str, parameters: dict | None, actor,
            authorization: str | None = None, owner_router: OwnerRouter | None = None) -> dict:
    started = time.monotonic()
    check = preview(db, project, action_type=action_type, confirmation_id=confirmation_id,
                    current_evidence_hash=current_evidence_hash, parameters=parameters)
    if check["status"] != "READY":
        raise DomainError(f"Action is {check['status']}", status_code=409 if check["status"] == "REQUIRES_INPUT" else 422)
    confirmation = db.get(ImpactConfirmation, confirmation_id)
    idem = _hash({"project": project.id, "confirmation": confirmation_id, "action": action_type,
                  "parameters": parameters or {}, "evidence": current_evidence_hash})
    existing = db.execute(select(ImpactActionRoute).where(ImpactActionRoute.idempotency_key == idem)).scalar_one_or_none()
    if existing:
        return route_dict(db, existing) | {"idempotent_replay": True}
    route = ImpactActionRoute(
        project_id=project.id, impact_candidate_id=confirmation.impact_candidate_id,
        confirmation_id=confirmation_id, action_type=action_type,
        target_service=check["target_service"], target_entity_id=check["target_entity_id"],
        requested_by=actor.id, parameters=parameters or {}, precondition_snapshot=check["precondition_snapshot"],
        evidence_hash=current_evidence_hash, idempotency_key=idem, status="EXECUTING")
    try:
        db.add(route); db.flush(); _event(db, route, "ACTION_REQUESTED", actor.id, human_trigger=True)
        _event(db, route, "ACTION_EXECUTION_STARTED", actor.id); db.commit()
    except IntegrityError:
        db.rollback()
        route = db.execute(select(ImpactActionRoute).where(ImpactActionRoute.idempotency_key == idem)).scalar_one()
        return route_dict(db, route) | {"idempotent_replay": True}
    try:
        result_ref, mutation_ms, reconciliation_ms = (owner_router or OwnerRouter()).execute(
            db, project, action_type, parameters or {}, actor)
        route.status, route.result_ref = "SUCCEEDED", result_ref
        _event(db, route, "ACTION_SUCCEEDED", actor.id, result_ref=result_ref)
        _event(db, route, "ACTION_RECONCILED", actor.id, owner_status=result_ref["status"])
        truth_started = time.monotonic()
        truth = build_project_truth(project, authorization)
        truth_ms = (time.monotonic() - truth_started) * 1000
        route.result_ref = {**result_ref, "truth_contract": truth["contract_version"],
                            "truth_source_status": truth.get("sources", {}).get(
                                "pm" if action_type == "ROUTE_PM_DELIVERY_HANDOFF" else "qa", {}).get("source_status")}
        db.commit()
        record_audit(db, action="ACTION_SUCCEEDED", project_id=project.id, actor_id=actor.id,
                     object_type="ImpactActionRoute", object_id=route.id,
                     revision_context=current_evidence_hash,
                     metadata={"action_type": action_type, "target_service": route.target_service,
                               "confirmation_id": confirmation_id, "result_ref": route.result_ref,
                               "human_executed": True, "customer_acceptance": False})
        from . import resolution as resolution_svc
        resolution = resolution_svc.evaluate(db, project, confirmation,
            current_evidence_hash=current_evidence_hash, authorization=authorization,
            actor_id=actor.id, truth=truth)
        return route_dict(db, route) | {"idempotent_replay": False, "impact_resolution": resolution,
            "performance": {"total_ms": round((time.monotonic()-started)*1000, 2),
                            "owner_mutation_ms": round(mutation_ms, 2),
                            "reconciliation_ms": round(reconciliation_ms, 2),
                            "truth_refresh_ms": round(truth_ms, 2)}}
    except Exception as exc:
        category = _failure(exc)
        route.status, route.failure_category, route.failure_detail = category, category, str(exc)[:600]
        _event(db, route, "ACTION_FAILED", actor.id, failure_category=category)
        db.commit()
        record_audit(db, action="ACTION_FAILED", project_id=project.id, actor_id=actor.id,
                     object_type="ImpactActionRoute", object_id=route.id,
                     revision_context=current_evidence_hash,
                     metadata={"action_type": action_type, "target_service": route.target_service,
                               "failure_category": category, "human_executed": True,
                               "customer_acceptance": False})
        return route_dict(db, route) | {"idempotent_replay": False,
                                       "reconciliation_attempted": bool(getattr(exc, "reconciliation_attempted", True)),
                                       "retry_policy": "RECONCILE_BEFORE_MANUAL_RETRY"}


def route_dict(db: Session, route: ImpactActionRoute) -> dict:
    events = db.execute(select(ImpactActionEvent).where(ImpactActionEvent.action_route_id == route.id)
                        .order_by(ImpactActionEvent.created_at)).scalars().all()
    return {"contract_version": CONTRACT, "action_route_id": route.id, "project_id": route.project_id,
            "impact_candidate_id": route.impact_candidate_id, "confirmation_id": route.confirmation_id,
            "action_type": route.action_type, "target_service": route.target_service,
            "target_entity_id": route.target_entity_id, "requested_by": route.requested_by,
            "requested_at": route.requested_at.isoformat(), "parameters": route.parameters,
            "precondition_snapshot": route.precondition_snapshot, "idempotency_key": route.idempotency_key,
            "status": route.status, "result_ref": route.result_ref, "failure_category": route.failure_category,
            "failure_detail": route.failure_detail,
            "events": [{"event_type": e.event_type, "actor_user_id": e.actor_user_id,
                        "created_at": e.created_at.isoformat(), "detail": e.detail} for e in events],
            "human_triggered": True, "autonomous": False}


def history(db: Session, project_id: str) -> dict:
    rows = db.execute(select(ImpactActionRoute).where(ImpactActionRoute.project_id == project_id)
                      .order_by(ImpactActionRoute.requested_at.desc())).scalars().all()
    return {"contract_version": CONTRACT, "routes": [route_dict(db, row) for row in rows]}
