"""
Conductor Again — Orchestration state machine (E8-B §13, §22).

Deterministic BusinessIntent status transitions and DeliveryRun stage flow.
Kept intentionally simple for the E8 MVP dependency model (§22): sequential
stages with an explicit hard-failure short-circuit (§23).
"""

BUSINESS_INTENT_STATES = [
    "RECEIVED", "ANALYZING", "PLANNED", "IN_EXECUTION",
    "BLOCKED", "READY_FOR_REVIEW", "COMPLETED", "FAILED",
]

BUSINESS_INTENT_TRANSITIONS = {
    "RECEIVED": {"ANALYZING", "FAILED"},
    "ANALYZING": {"PLANNED", "BLOCKED", "FAILED"},
    "PLANNED": {"IN_EXECUTION", "BLOCKED", "FAILED"},
    "IN_EXECUTION": {"READY_FOR_REVIEW", "BLOCKED", "FAILED"},
    "BLOCKED": {"IN_EXECUTION", "FAILED"},
    "READY_FOR_REVIEW": {"COMPLETED", "IN_EXECUTION", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}

RUN_STAGES = ["INTENT", "PLAN", "ENGINEERING", "INFRASTRUCTURE", "QA", "DELIVERY_READINESS", "COMPLETE"]

RUN_STAGE_TRANSITIONS = {
    "INTENT": {"PLAN"},
    "PLAN": {"ENGINEERING"},
    "ENGINEERING": {"INFRASTRUCTURE", "DELIVERY_READINESS"},  # hard failure skips to readiness (§23)
    "INFRASTRUCTURE": {"QA", "DELIVERY_READINESS"},
    "QA": {"DELIVERY_READINESS"},
    "DELIVERY_READINESS": {"COMPLETE"},
    "COMPLETE": set(),
}


class InvalidTransitionError(Exception):
    pass


def transition_business_intent(current: str, target: str) -> str:
    if target not in BUSINESS_INTENT_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(f"BusinessIntent cannot go {current} -> {target}")
    return target


def transition_run_stage(current: str, target: str) -> str:
    if target not in RUN_STAGE_TRANSITIONS.get(current, set()):
        raise InvalidTransitionError(f"DeliveryRun cannot go {current} -> {target}")
    return target
