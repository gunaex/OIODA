"""
Conductor Again — Delivery Readiness Engine (E8-F).

Explicit, deterministic policy. Do not compute readiness by accidental status
arithmetic (§49) — every branch below is enumerated and mapped to a stable
reason code (§52).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

POLICY_VERSION = "e8-readiness-policy-v1"

REASON_CODES = {
    "READY_ALL_REQUIRED_GATES_PASS",
    "READY_WITH_NON_BLOCKING_ENGINEERING_PARTIAL",
    "BLOCKED_ENGINEERING_FAILED",
    "BLOCKED_ENGINEERING_PARTIAL",
    "BLOCKED_INFRA_FAILED",
    "BLOCKED_QA_REJECTED",
    "BLOCKED_MISSING_REQUIRED_RESULT",
}


@dataclass
class ReadinessInputs:
    assignments: dict  # {"engineering": bool, "infrastructure": bool, "qa": bool}
    engineering_status: Optional[str] = None  # SUCCESS, PARTIAL, FAILED, REPAIRED
    engineering_partial_blocking: bool = False  # structured flag, not text-inferred (§50)
    infrastructure_status: Optional[str] = None  # SUCCESS, PARTIAL, FAILED
    qa_quality_gate: Optional[str] = None  # APPROVED, REJECTED, PENDING
    evidence_refs: list = field(default_factory=list)


@dataclass
class ReadinessDecision:
    decision: str  # READY_FOR_DELIVERY | NOT_READY
    reason_code: str
    reason: str


def evaluate_readiness(inputs: ReadinessInputs) -> ReadinessDecision:
    assignments = inputs.assignments or {}

    # Missing mandatory specialist result (§49)
    if assignments.get("engineering") and inputs.engineering_status is None:
        return ReadinessDecision("NOT_READY", "BLOCKED_MISSING_REQUIRED_RESULT",
                                  "Engineering is assigned but no EngineeringResult has been received.")
    if assignments.get("infrastructure") and inputs.infrastructure_status is None:
        return ReadinessDecision("NOT_READY", "BLOCKED_MISSING_REQUIRED_RESULT",
                                  "Infrastructure is assigned but no InfrastructureResult has been received.")
    if assignments.get("qa") and inputs.qa_quality_gate is None:
        return ReadinessDecision("NOT_READY", "BLOCKED_MISSING_REQUIRED_RESULT",
                                  "QA is assigned but no QAResult has been received.")

    # Engineering FAILED -> NOT_READY (§49)
    if inputs.engineering_status == "FAILED":
        return ReadinessDecision("NOT_READY", "BLOCKED_ENGINEERING_FAILED",
                                  "EngineeringResult status is FAILED.")

    # Engineering PARTIAL + blocking -> NOT_READY
    if inputs.engineering_status == "PARTIAL" and inputs.engineering_partial_blocking:
        return ReadinessDecision("NOT_READY", "BLOCKED_ENGINEERING_PARTIAL",
                                  "EngineeringResult status is PARTIAL with a blocking finding.")

    # Infrastructure FAILED -> NOT_READY
    if inputs.infrastructure_status == "FAILED":
        return ReadinessDecision("NOT_READY", "BLOCKED_INFRA_FAILED",
                                  "InfrastructureResult status is FAILED.")

    # QA REJECTED -> NOT_READY
    if inputs.qa_quality_gate == "REJECTED":
        return ReadinessDecision("NOT_READY", "BLOCKED_QA_REJECTED",
                                  "QAResult qualityGate is REJECTED.")

    # QA PENDING (assigned, present, but not yet decided) -> NOT_READY via missing-result semantics
    if inputs.qa_quality_gate == "PENDING":
        return ReadinessDecision("NOT_READY", "BLOCKED_MISSING_REQUIRED_RESULT",
                                  "QAResult qualityGate is still PENDING.")

    # Engineering PARTIAL, non-blocking + Infra SUCCESS + QA APPROVED -> READY with caveat (§49, §66)
    if inputs.engineering_status == "PARTIAL" and not inputs.engineering_partial_blocking:
        infra_ok = (not assignments.get("infrastructure")) or inputs.infrastructure_status in ("SUCCESS", "PARTIAL")
        qa_ok = (not assignments.get("qa")) or inputs.qa_quality_gate == "APPROVED"
        if infra_ok and qa_ok:
            return ReadinessDecision(
                "READY_FOR_DELIVERY", "READY_WITH_NON_BLOCKING_ENGINEERING_PARTIAL",
                "EngineeringResult is PARTIAL but non-blocking; Infrastructure and QA gates pass.",
            )

    # All required gates pass -> READY_FOR_DELIVERY
    engineering_ok = (not assignments.get("engineering")) or inputs.engineering_status in ("SUCCESS", "REPAIRED")
    infra_ok = (not assignments.get("infrastructure")) or inputs.infrastructure_status == "SUCCESS"
    qa_ok = (not assignments.get("qa")) or inputs.qa_quality_gate == "APPROVED"
    if engineering_ok and infra_ok and qa_ok:
        return ReadinessDecision("READY_FOR_DELIVERY", "READY_ALL_REQUIRED_GATES_PASS",
                                  "All assigned specialist gates report success/approval.")

    # Fallback: anything not explicitly matched is NOT_READY, never an accidental READY.
    return ReadinessDecision("NOT_READY", "BLOCKED_MISSING_REQUIRED_RESULT",
                              "Readiness policy did not match a defined READY branch.")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
