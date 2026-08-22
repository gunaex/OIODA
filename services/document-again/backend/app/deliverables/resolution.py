"""R17.6 deterministic change-to-resolution evaluation."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..project_truth import build_project_truth
from ..services import record_audit
from .models import (ImpactActionRoute, ImpactConfirmation, ImpactResolution,
                     ImpactResolutionEvent)

CONTRACT = "impact_resolution/v1"
REGISTRY_VERSION = "impact_resolution_rules/v1"
RULE_VERSION = "1"
STATES = ("OPEN", "ACTION_PLANNED", "ACTION_IN_PROGRESS", "WAITING_ON_OWNER",
          "RECHECK_REQUIRED", "RESOLVED", "RESOLVED_WITH_EXCEPTION",
          "NO_LONGER_APPLICABLE", "BLOCKED", "UNKNOWN")
RULES = {
    "ROUTE_PM_DELIVERY_HANDOFF": {
        "rule_id": "PM-DELIVERY-HANDOFF-COMPLETION", "rule_version": RULE_VERSION,
        "required_truth": "PM source OK and matching handoff/work package explicitly COMPLETE or RESOLVED",
    },
    "ROUTE_QA_VALIDATION_HANDOFF": {
        "rule_id": "QA-VALIDATION-EVIDENCE-COMPLETE", "rule_version": RULE_VERSION,
        "required_truth": "QA source OK; validation evidence COMPLETE; no remaining, failed, blocked tests or blocking defects",
    },
}


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def registry() -> dict:
    return {"contract_version": REGISTRY_VERSION, "rules": RULES, "states": STATES,
            "ai_resolution_authority": "NONE", "customer_acceptance_side_effect": False}


def _truth_ref(truth: dict, domain: str) -> dict:
    source = truth.get("sources", {}).get(domain, {})
    facts = truth.get(domain) or {}
    return {"contract_version": truth.get("contract_version"), "generated_at": truth.get("generated_at"),
            "domain": domain.upper(), "source_status": source.get("source_status", "UNKNOWN"),
            "source_revision": source.get("source_revision"), "snapshot_hash": _hash(facts),
            "normalized_facts": facts, "downstream_call_count": truth.get("downstream_call_count", 0)}


def _completed_pm(truth: dict, entity_id: str | None) -> bool:
    pm = truth.get("pm") or {}
    rows = pm.get("delivery_handoffs") or pm.get("work_packages") or pm.get("items") or []
    return any(str(row.get("id") or row.get("external_reference")) == str(entity_id)
               and str(row.get("status", "")).upper() in {"COMPLETE", "COMPLETED", "RESOLVED", "DONE"}
               for row in rows if isinstance(row, dict))


def _completed_qa(truth: dict) -> bool:
    qa = truth.get("qa") or {}
    return (str(qa.get("evidence_status", "")).upper() in {"COMPLETE", "COMPLETED", "AVAILABLE"}
            and all(int(qa.get(key) or 0) == 0 for key in
                    ("remaining_test_count", "failed_test_count", "blocked_test_count", "blocking_defect_count")))


def _state(confirmation, route, truth: dict, current_evidence_hash: str):
    action = route.action_type if route else None
    rule = RULES.get(action, {"rule_id": "CONFIRMED-IMPACT-LIFECYCLE", "rule_version": RULE_VERSION})
    if confirmation.evidence_hash != current_evidence_hash:
        return "RECHECK_REQUIRED", "Resolution evidence changed; deterministic re-evaluation is required.", rule
    if confirmation.decision == "REJECTED":
        return "NO_LONGER_APPLICABLE", "The relationship is no longer applicable in the current confirmed context.", rule
    if confirmation.decision != "CONFIRMED":
        return "OPEN", "The impact has not been confirmed as resolved or inapplicable.", rule
    if not route:
        return "ACTION_PLANNED", "A supported human action is available but has not executed.", rule
    if route.status in {"EXECUTING", "REQUESTED"}:
        return "ACTION_IN_PROGRESS", "The owner mutation is still in progress.", rule
    if route.status == "UNKNOWN_RESULT":
        return "RECHECK_REQUIRED", "The owner result remains uncertain after reconciliation.", rule
    if route.status == "OWNER_UNAVAILABLE":
        return "BLOCKED", "The required owner service is unavailable.", rule
    if route.status != "SUCCEEDED":
        return "OPEN", f"The owner action ended as {route.status}; the impact remains open.", rule
    domain = "pm" if action == "ROUTE_PM_DELIVERY_HANDOFF" else "qa"
    source_status = truth.get("sources", {}).get(domain, {}).get("source_status", "UNKNOWN")
    if source_status not in {"OK", "EMPTY"}:
        return "UNKNOWN", f"{domain.upper()} truth is {source_status}; resolution cannot be determined.", rule
    resolved = (_completed_pm(truth, (route.result_ref or {}).get("entity_id")) if domain == "pm"
                else _completed_qa(truth))
    if resolved:
        return "RESOLVED", f"Authoritative {domain.upper()} truth satisfies {rule['rule_id']}.", rule
    return "WAITING_ON_OWNER", f"The action succeeded, but authoritative {domain.upper()} completion evidence is not present.", rule


def evaluate(db: Session, project, confirmation: ImpactConfirmation, *, current_evidence_hash: str,
             authorization: str | None, actor_id: str, truth: dict | None = None) -> dict:
    started = time.monotonic()
    route = db.execute(select(ImpactActionRoute).where(
        ImpactActionRoute.confirmation_id == confirmation.id).order_by(ImpactActionRoute.requested_at.desc())).scalars().first()
    fresh_truth = truth if truth is not None else build_project_truth(project, authorization)
    state, reason, rule = _state(confirmation, route, fresh_truth, current_evidence_hash)
    domain = "pm" if route and route.action_type == "ROUTE_PM_DELIVERY_HANDOFF" else "qa" if route else "document"
    post_ref = _truth_ref(fresh_truth, domain) if domain != "document" else {
        "contract_version": "reviewer_evidence/v1", "snapshot_hash": current_evidence_hash, "domain": "DOCUMENT"}
    evidence = list(dict.fromkeys([confirmation.id, confirmation.relationship_id, current_evidence_hash,
                                  *(([route.id] if route else [])), post_ref.get("snapshot_hash")]))
    row = db.execute(select(ImpactResolution).where(ImpactResolution.confirmation_id == confirmation.id)).scalar_one_or_none()
    previous = row.resolution_state if row else None
    now = datetime.now(timezone.utc)
    if not row:
        row = ImpactResolution(project_id=project.id, change_id=confirmation.change_id,
            impact_candidate_id=confirmation.impact_candidate_id, confirmation_id=confirmation.id,
            resolution_state=state, resolution_reason=reason, evaluation_rule_id=rule["rule_id"],
            evaluation_rule_version=rule["rule_version"], evidence_hash=current_evidence_hash,
            post_action_truth_ref=post_ref, evidence_refs=evidence)
        db.add(row); db.flush()
    else:
        row.latest_action_route_id = route.id if route else None; row.owner_result_ref = route.result_ref if route else None
        row.resolution_state = state; row.resolution_reason = reason
        row.evaluation_rule_id = rule["rule_id"]; row.evaluation_rule_version = rule["rule_version"]
        row.post_action_truth_ref = post_ref; row.evidence_refs = evidence; row.evidence_hash = current_evidence_hash
        row.evaluated_at = now
        if previous != state: row.state_entered_at = now
    row.latest_action_route_id = route.id if route else None
    row.owner_result_ref = route.result_ref if route else None
    if route and not row.pre_action_truth_ref:
        row.pre_action_truth_ref = {"snapshot_hash": route.evidence_hash,
                                    "precondition_snapshot_hash": _hash(route.precondition_snapshot)}
    if previous != state:
        transition_hash = _hash({"resolution": row.id, "from": previous, "to": state,
                                 "evidence": evidence, "rule": rule})
        event_type = "IMPACT_RESOLUTION_REOPENED" if previous == "RESOLVED" else (
            "IMPACT_RESOLVED" if state == "RESOLVED" else "IMPACT_RESOLUTION_STATE_CHANGED")
        db.add(ImpactResolutionEvent(resolution_id=row.id, project_id=project.id, event_type=event_type,
            from_state=previous, to_state=state, reason=reason, evidence_refs=evidence,
            actor_user_id=actor_id, transition_hash=transition_hash))
        record_audit(db, action=event_type, project_id=project.id, actor_id=actor_id,
            object_type="ImpactResolution", object_id=row.id, revision_context=current_evidence_hash,
            metadata={"from_state": previous, "to_state": state, "rule_id": rule["rule_id"],
                      "customer_acceptance": False, "ai_authority": False})
    db.commit()
    return to_dict(db, row, round((time.monotonic() - started) * 1000, 2))


def to_dict(db: Session, row: ImpactResolution, latency_ms: float | None = None) -> dict:
    events = db.execute(select(ImpactResolutionEvent).where(ImpactResolutionEvent.resolution_id == row.id)
                        .order_by(ImpactResolutionEvent.created_at)).scalars().all()
    out = {"contract_version": CONTRACT, "resolution_id": row.id, "project_id": row.project_id,
        "change_id": row.change_id, "impact_candidate_id": row.impact_candidate_id,
        "confirmation_id": row.confirmation_id, "latest_action_route_id": row.latest_action_route_id,
        "owner_result_ref": row.owner_result_ref, "resolution_state": row.resolution_state,
        "resolution_reason": row.resolution_reason, "evaluation_rule_id": row.evaluation_rule_id,
        "evaluation_rule_version": row.evaluation_rule_version, "pre_action_truth_ref": row.pre_action_truth_ref,
        "post_action_truth_ref": row.post_action_truth_ref, "evidence_refs": row.evidence_refs,
        "evaluated_at": row.evaluated_at.isoformat(), "state_entered_at": row.state_entered_at.isoformat(),
        "history": [{"event_type": e.event_type, "from_state": e.from_state, "state": e.to_state,
                     "reason": e.reason, "evidence": e.evidence_refs, "actor": e.actor_user_id,
                     "timestamp": e.created_at.isoformat()} for e in events],
        "customer_acceptance": False, "ai_authority": False}
    if latency_ms is not None: out["evaluation_latency_ms"] = latency_ms
    return out


def history(db: Session, project_id: str) -> dict:
    rows = db.execute(select(ImpactResolution).where(ImpactResolution.project_id == project_id)
                      .order_by(ImpactResolution.evaluated_at.desc())).scalars().all()
    resolutions = [to_dict(db, row) for row in rows]
    groups = {"new": {"OPEN", "ACTION_PLANNED"}, "in_progress": {"ACTION_IN_PROGRESS"},
              "waiting": {"WAITING_ON_OWNER"}, "blocked": {"BLOCKED"},
              "resolved": {"RESOLVED", "RESOLVED_WITH_EXCEPTION", "NO_LONGER_APPLICABLE"},
              "unverified": {"UNKNOWN", "RECHECK_REQUIRED"}}
    counts = {name: sum(item["resolution_state"] in states for item in resolutions)
              for name, states in groups.items()}
    active = [item for item in resolutions if item["resolution_state"] not in groups["resolved"]]
    return {"contract_version": CONTRACT, "resolutions": resolutions,
            "project_attention_projection": {"contract_version": "project_attention/v1",
                "counts": counts, "active_resolution_ids": [item["resolution_id"] for item in active],
                "recently_resolved_ids": [item["resolution_id"] for item in resolutions
                                          if item["resolution_state"] in groups["resolved"]],
                "resolved_are_current_blockers": False}}
