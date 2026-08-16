"""Phase 8 versioned policy profiles — make policy evolution explicit.

Phase 7 historical:
  SANDBOX = BLOCK

Phase 8 current:
  SANDBOX = ASK

Both:
  CONTROLLED_REAL = BLOCK
  PRODUCTION = BLOCK
"""

from __future__ import annotations

from enum import Enum
from .phase7_models import ExecutionFidelity


class PolicyProfile(str, Enum):
    PHASE7 = "PHASE7"
    PHASE8 = "PHASE8"


# ============================================================================
# Phase 7 historical policy
# ============================================================================

PHASE7_HISTORICAL_BLOCK = {
    ExecutionFidelity.SANDBOX,
    ExecutionFidelity.CONTROLLED_REAL,
    ExecutionFidelity.PRODUCTION,
}

PHASE7_HISTORICAL_ASK = {ExecutionFidelity.LOCAL_PRIVATE_CLOUD}

PHASE7_HISTORICAL_ALLOW = {
    ExecutionFidelity.PLAN_ONLY,
    ExecutionFidelity.SIMULATED,
    ExecutionFidelity.LOCAL_RUNTIME,
}

# ============================================================================
# Phase 8 current policy
# ============================================================================

PHASE8_CURRENT_BLOCK = {
    ExecutionFidelity.CONTROLLED_REAL,
    ExecutionFidelity.PRODUCTION,
}

PHASE8_CURRENT_ASK = {
    ExecutionFidelity.LOCAL_PRIVATE_CLOUD,
    ExecutionFidelity.SANDBOX,
}

PHASE8_CURRENT_ALLOW = {
    ExecutionFidelity.PLAN_ONLY,
    ExecutionFidelity.SIMULATED,
    ExecutionFidelity.LOCAL_RUNTIME,
}

# ============================================================================
# Invariants preserved across Phase 7 → Phase 8
# ============================================================================

INVARIANT_BLOCK_ALWAYS = {
    ExecutionFidelity.CONTROLLED_REAL,
    ExecutionFidelity.PRODUCTION,
}

INVARIANT_ALLOW_ALWAYS = {
    ExecutionFidelity.PLAN_ONLY,
    ExecutionFidelity.SIMULATED,
    ExecutionFidelity.LOCAL_RUNTIME,
}


def fidelity_policy_for_profile(
    fidelity: ExecutionFidelity, profile: PolicyProfile,
) -> str:
    """Return the policy decision (BLOCK/ASK/ALLOW) for a fidelity under a given profile."""
    if profile == PolicyProfile.PHASE7:
        if fidelity in PHASE7_HISTORICAL_BLOCK:
            return "BLOCK"
        if fidelity in PHASE7_HISTORICAL_ASK:
            return "ASK"
        if fidelity in PHASE7_HISTORICAL_ALLOW:
            return "ALLOW"
    elif profile == PolicyProfile.PHASE8:
        if fidelity in PHASE8_CURRENT_BLOCK:
            return "BLOCK"
        if fidelity in PHASE8_CURRENT_ASK:
            return "ASK"
        if fidelity in PHASE8_CURRENT_ALLOW:
            return "ALLOW"
    return "UNKNOWN"


def policy_transition_summary() -> dict:
    """Summarize policy transitions from Phase 7 to Phase 8."""
    return {
        "PHASE7_SANDBOX_POLICY": "BLOCK",
        "PHASE8_SANDBOX_POLICY": "ASK",
        "POLICY_TRANSITION_INTENTIONAL": True,
        "CONTROLLED_REAL": "BLOCK (unchanged)",
        "PRODUCTION": "BLOCK (unchanged)",
        "PLAN_ONLY": "ALLOW (unchanged)",
        "SIMULATED": "ALLOW (unchanged)",
        "LOCAL_RUNTIME": "ALLOW (unchanged)",
        "LOCAL_PRIVATE_CLOUD": "ASK (unchanged)",
        "transitionNote": (
            "SANDBOX moved from BLOCK to ASK in Phase 8 to enable "
            "controlled sandbox execution with explicit safety gates "
            "(preflight, approval, cost ceiling, credential lease). "
            "SANDBOX is never AUTO. CONTROLLED_REAL and PRODUCTION "
            "remain permanently BLOCKED."
        ),
    }
