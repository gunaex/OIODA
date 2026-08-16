"""Phase 7 AIRLOCK Policy Engine — fidelity-gated execution decisions."""

from __future__ import annotations

from typing import Any

from .phase7_models import (
    ExecutionFidelity, ExecutionPolicyDecision, ExecutionTask,
    ExecutionTarget, PolicyVerdict, ActionType,
)

# Phase 7 allowed fidelities
PHASE7_ALLOWED = {ExecutionFidelity.PLAN_ONLY, ExecutionFidelity.SIMULATED, ExecutionFidelity.LOCAL_RUNTIME}
PHASE7_ASK = {ExecutionFidelity.LOCAL_PRIVATE_CLOUD}
PHASE7_BLOCK = {ExecutionFidelity.CONTROLLED_REAL, ExecutionFidelity.PRODUCTION}

# Phase 8 moves SANDBOX from BLOCK to ASK (never AUTO)
PHASE8_ASK = {ExecutionFidelity.SANDBOX}

# Action-specific rules
ACTION_FIDELITY_RULES: dict[str, set[ExecutionFidelity]] = {
    "GENERATE_IAC": {ExecutionFidelity.PLAN_ONLY},
    "VALIDATE_IAC": {ExecutionFidelity.PLAN_ONLY},
    "PLAN_IAC": {ExecutionFidelity.PLAN_ONLY},
    "APPLY_LOCAL_IAC": {ExecutionFidelity.SIMULATED, ExecutionFidelity.LOCAL_RUNTIME},
    "CREATE_LOCAL_NAMESPACE": {ExecutionFidelity.LOCAL_RUNTIME},
    "DEPLOY_LOCAL_WORKLOAD": {ExecutionFidelity.LOCAL_RUNTIME},
    "OBSERVE_RESOURCE": PHASE7_ALLOWED,
    "VALIDATE_RESOURCE": PHASE7_ALLOWED,
    "DESTROY_RUN_OWNED_RESOURCE": {ExecutionFidelity.SIMULATED, ExecutionFidelity.LOCAL_RUNTIME},
}


class ExecutionPolicyEngine:
    """AIRLOCK policy: fidelity + target + action → ALLOW/ASK/BLOCK."""

    REAL_ENDPOINT_PATTERNS = [
        "amazonaws.com", "googleapis.com", "cloud.google.com",
        "s3.amazonaws.com", "s3.us-east-1.amazonaws.com",
    ]

    @staticmethod
    def evaluate(task: ExecutionTask, target: ExecutionTarget) -> ExecutionPolicyDecision:
        # 1. Production → BLOCK (Phase 7 & 8)
        if target.fidelity == ExecutionFidelity.PRODUCTION:
            return ExecutionPolicyDecision(
                verdict=PolicyVerdict.BLOCK,
                reason_code="PRODUCTION_BLOCKED",
                reason="Production execution not allowed",
                effective_fidelity=ExecutionFidelity.PLAN_ONLY,
            )

        # 2. CONTROLLED_REAL → BLOCK (Phase 7 & 8)
        if target.fidelity == ExecutionFidelity.CONTROLLED_REAL:
            return ExecutionPolicyDecision(
                verdict=PolicyVerdict.BLOCK,
                reason_code="CONTROLLED_REAL_BLOCKED",
                reason="CONTROLLED_REAL execution not allowed",
                effective_fidelity=ExecutionFidelity.PLAN_ONLY,
            )

        # 3. Real cloud endpoint → BLOCK (unless SANDBOX)
        if ExecutionPolicyEngine._is_real_endpoint(target):
            if target.fidelity == ExecutionFidelity.SANDBOX:
                # SANDBOX may access real endpoints — proceed to fidelity check
                pass
            else:
                return ExecutionPolicyDecision(
                    verdict=PolicyVerdict.BLOCK,
                    reason_code="REAL_CLOUD_EXECUTION_NOT_ALLOWED",
                    reason=f"Real cloud endpoint detected: {target.endpoint_reference}",
                    effective_fidelity=ExecutionFidelity.PLAN_ONLY,
                )

        # 4. Check fidelity against Phase 7/8 rules
        fid = target.fidelity
        if fid in PHASE7_BLOCK:
            return ExecutionPolicyDecision(
                verdict=PolicyVerdict.BLOCK,
                reason_code="FIDELITY_BLOCKED",
                reason=f"Fidelity {fid.value} not allowed",
                effective_fidelity=ExecutionFidelity.PLAN_ONLY,
            )

        if fid in PHASE7_ASK or fid in PHASE8_ASK:
            return ExecutionPolicyDecision(
                verdict=PolicyVerdict.ASK,
                reason_code="FIDELITY_REQUIRES_APPROVAL",
                reason=f"Fidelity {fid.value} requires explicit user approval",
                effective_fidelity=fid,
                constraints=["Requires user approval before execution"],
            )

        # 4. Check action is compatible with fidelity
        action = task.action_type.value if isinstance(task.action_type, ActionType) else str(task.action_type)
        allowed_actions = ACTION_FIDELITY_RULES.get(action, PHASE7_ALLOWED)
        if fid not in allowed_actions:
            return ExecutionPolicyDecision(
                verdict=PolicyVerdict.BLOCK,
                reason_code="ACTION_FIDELITY_MISMATCH",
                reason=f"Action {action} not allowed at fidelity {fid.value}",
                effective_fidelity=ExecutionFidelity.PLAN_ONLY,
            )

        # 5. Credential safety
        if ExecutionPolicyEngine._has_real_credentials():
            if target.fidelity == ExecutionFidelity.SANDBOX:
                # SANDBOX may have credentials — they must be temporary/least-privilege
                # (enforced by sandbox preflight, not policy)
                pass
            else:
                return ExecutionPolicyDecision(
                    verdict=PolicyVerdict.BLOCK,
                    reason_code="REAL_CREDENTIALS_DETECTED",
                    reason="Real cloud credentials detected in environment",
                    effective_fidelity=ExecutionFidelity.PLAN_ONLY,
                )

        # 6. All checks passed → ALLOW
        return ExecutionPolicyDecision(
            verdict=PolicyVerdict.ALLOW,
            reason_code="PHASE7_LOCAL_EXECUTION_ALLOWED",
            reason=f"Local execution allowed at fidelity {fid.value}",
            effective_fidelity=fid,
        )

    @staticmethod
    def _is_real_endpoint(target: ExecutionTarget) -> bool:
        ep = target.endpoint_reference.lower()
        for pattern in ExecutionPolicyEngine.REAL_ENDPOINT_PATTERNS:
            if pattern in ep:
                return True
        # Also check for non-local addresses
        if ep and ep not in ("localhost", "127.0.0.1", ""):
            # If it's an IP, only allow localhost/loopback
            if ep.startswith("http://") or ep.startswith("https://"):
                # Check host portion
                host = ep.split("//")[1].split("/")[0].split(":")[0]
                if host not in ("localhost", "127.0.0.1", "0.0.0.0"):
                    return True
        return False

    @staticmethod
    def _has_real_credentials() -> bool:
        import os
        return bool(os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

    @staticmethod
    def evaluate_package(tasks: list[ExecutionTask], target: ExecutionTarget) -> ExecutionPolicyDecision:
        """Evaluate all tasks; most restrictive wins."""
        verdicts = []
        for task in tasks:
            decision = ExecutionPolicyEngine.evaluate(task, target)
            verdicts.append(decision)
            if decision.verdict == PolicyVerdict.BLOCK:
                return decision

        # If any ASK, return ASK
        for d in verdicts:
            if d.verdict == PolicyVerdict.ASK:
                return d

        # All ALLOW
        return verdicts[0] if verdicts else ExecutionPolicyDecision(
            verdict=PolicyVerdict.ALLOW,
            reason_code="NO_TASKS",
            reason="No tasks to evaluate",
            effective_fidelity=target.fidelity,
        )
