"""Phase 8 Sandbox API — sandbox targets, approval, execution routes."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from .sandbox_models import (
    SandboxTarget, SandboxAccount, SandboxPreflightResult,
    CostEstimate, SandboxApproval, SandboxApprovalState,
    CredentialLease, CredentialSource, CleanupPolicy,
    OwnershipTags, SandboxResourceAllowlist,
    SandboxExecutionState,
)
from .sandbox_preflight import SandboxPreflightEngine, _now, _compute_target_checksum

# In-memory stores (backed by optional persistence)
_sandbox_targets: dict[str, SandboxTarget] = {}
_sandbox_approvals: dict[str, SandboxApproval] = {}
_sandbox_executions: dict[str, dict[str, Any]] = {}


def register_sandbox_routes(app: FastAPI) -> None:
    """Register Phase 8 sandbox API routes."""

    # =========================================================================
    # Sandbox Target Management
    # =========================================================================

    @app.post("/api/v1/sandbox/targets")
    async def create_sandbox_target(body: dict[str, Any]):
        """Create a sandbox target with safety constraints."""
        target = SandboxTarget(
            provider=body.get("provider", "aws"),
            account=SandboxAccount(
                account_id=body.get("accountId", ""),
                provider=body.get("provider", "aws"),
                verified=False,
            ),
            region=body.get("region", ""),
            resource_allowlist=SandboxResourceAllowlist(
                services=body.get("services", ["s3"]),
            ),
            cost_estimate=CostEstimate(
                estimated_maximum_cost=body.get("estimatedMaxCost", 0.01),
                ceiling=body.get("costCeiling", 5.0),
            ),
            ttl_hours=body.get("ttlHours", 1.0),
        )
        _sandbox_targets[target.sandbox_target_id] = target
        return {"sandboxTarget": target.to_dict()}

    @app.get("/api/v1/sandbox/targets/{target_id}")
    async def get_sandbox_target(target_id: str):
        """Get a sandbox target by ID."""
        target = _sandbox_targets.get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Sandbox target not found")
        return {"sandboxTarget": target.to_dict()}

    @app.post("/api/v1/sandbox/targets/{target_id}/verify-identity")
    async def verify_sandbox_identity(target_id: str):
        """Verify actual AWS caller identity against sandbox target.

        Uses AWS STS GetCallerIdentity if boto3 is available and credentials exist.
        """
        target = _sandbox_targets.get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Sandbox target not found")

        caller_identity = None
        identity_source = "not_checked"

        try:
            import boto3
            sts = boto3.client("sts", region_name=target.region or "us-east-1")
            caller_identity = sts.get_caller_identity()
            identity_source = "aws_sts_live"
        except Exception as e:
            # No real credentials or boto3 unavailable — expected in local dev
            identity_source = f"unavailable: {str(e)[:100]}"

        if caller_identity:
            actual_account = str(caller_identity.get("Account", ""))
            expected_account = target.account.account_id

            if actual_account != expected_account:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "SANDBOX_ACCOUNT_MISMATCH",
                        "expected": expected_account,
                        "actual": actual_account,
                        "callerIdentity": {
                            "Account": caller_identity.get("Account"),
                            "Arn": caller_identity.get("Arn", "")[:50] + "...",
                            "UserId": caller_identity.get("UserId"),
                        },
                    },
                )

            target.account.caller_identity = caller_identity
            target.account.verified = True
            target.account.verified_at = _now()
            _sandbox_targets[target_id] = target

            return {
                "verified": True,
                "accountId": actual_account,
                "callerIdentity": {
                    "Account": caller_identity.get("Account"),
                    "Arn": caller_identity.get("Arn", "")[:50] + "...",
                    "UserId": caller_identity.get("UserId"),
                },
                "source": identity_source,
            }

        return {
            "verified": False,
            "accountId": target.account.account_id,
            "note": f"Could not verify identity: {identity_source}",
            "source": identity_source,
        }

    # =========================================================================
    # Sandbox Preflight
    # =========================================================================

    @app.post("/api/v1/sandbox/preflight")
    async def run_sandbox_preflight(body: dict[str, Any]):
        """Run sandbox-specific preflight checks."""
        package_id = body.get("packageId", "")
        target_id = body.get("sandboxTargetId", "")
        plan_checksum = body.get("planChecksum", "")
        package_checksum = body.get("packageChecksum", "")

        target = _sandbox_targets.get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Sandbox target not found")

        result = SandboxPreflightEngine.run(
            package_id=package_id,
            sandbox_target=target,
            plan_checksum=plan_checksum,
            package_checksum=package_checksum,
        )

        return {
            "preflight": result.to_dict(),
            "canProceed": result.all_passed,
        }

    # =========================================================================
    # Sandbox Approval (AIRLOCK)
    # =========================================================================

    @app.post("/api/v1/sandbox/approvals")
    async def create_sandbox_approval(body: dict[str, Any]):
        """Request sandbox execution approval."""
        target_id = body.get("sandboxTargetId", "")
        package_id = body.get("executionPackageId", "")
        plan_checksum = body.get("planChecksum", "")

        target = _sandbox_targets.get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Sandbox target not found")

        target_checksum = _compute_target_checksum(target)

        approval = SandboxApproval(
            sandbox_target_id=target_id,
            execution_package_id=package_id,
            bound_plan_checksum=plan_checksum,
            bound_target_checksum=target_checksum,
            state=SandboxApprovalState.PENDING,
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        approval.generate_warning(target, target.cost_estimate)

        _sandbox_approvals[approval.approval_id] = approval
        return {"approval": approval.to_dict()}

    @app.post("/api/v1/sandbox/approvals/{approval_id}/approve")
    async def approve_sandbox_execution(approval_id: str, approved_by: str = ""):
        """Approve a sandbox execution request."""
        approval = _sandbox_approvals.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        if approval.state != SandboxApprovalState.PENDING:
            raise HTTPException(status_code=400, detail=f"Approval is {approval.state.value}")

        approval.state = SandboxApprovalState.APPROVED
        approval.approved_by = approved_by
        approval.approved_at = _now()

        _sandbox_approvals[approval_id] = approval
        return {"approval": approval.to_dict()}

    @app.get("/api/v1/sandbox/approvals/{approval_id}")
    async def get_sandbox_approval(approval_id: str):
        """Get sandbox approval status."""
        approval = _sandbox_approvals.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        return {"approval": approval.to_dict()}

    # =========================================================================
    # Sandbox Execution
    # =========================================================================

    @app.post("/api/v1/sandbox/execute")
    async def execute_sandbox(body: dict[str, Any]):
        """Execute a sandbox deployment (requires approved sandbox target + approval)."""
        target_id = body.get("sandboxTargetId", "")
        approval_id = body.get("approvalId", "")
        package_id = body.get("executionPackageId", "")
        plan_checksum = body.get("planChecksum", "")
        package_checksum = body.get("packageChecksum", "")

        # 1. Validate sandbox target
        target = _sandbox_targets.get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Sandbox target not found")

        # 2. Validate approval
        approval = _sandbox_approvals.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.state != SandboxApprovalState.APPROVED:
            raise HTTPException(status_code=403, detail=f"Approval not approved: {approval.state.value}")
        if not approval.is_bound_to(plan_checksum, _compute_target_checksum(target)):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "APPROVAL_MISMATCH",
                    "message": "Approval not bound to current plan/target checksums",
                },
            )
        if approval.is_expired:
            raise HTTPException(status_code=403, detail="Approval expired")

        # 3. Sandbox preflight
        preflight = SandboxPreflightEngine.run(
            package_id=package_id,
            sandbox_target=target,
            plan_checksum=plan_checksum,
            package_checksum=package_checksum,
        )
        if not preflight.all_passed:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "SANDBOX_PREFLIGHT_FAILED",
                    "failures": preflight.failures,
                },
            )

        # 4. Production must remain blocked
        if target.production:
            raise HTTPException(status_code=403, detail="PRODUCTION_BLOCKED")

        # 5. Execute (for now, returns execution plan — real AWS execution deferred)
        execution_id = f"SANDEXEC-{uuid.uuid4().hex[:8].upper()}"
        execution = {
            "executionId": execution_id,
            "sandboxTargetId": target_id,
            "approvalId": approval_id,
            "packageId": package_id,
            "state": SandboxExecutionState.PREFLIGHT_PASSED.value,
            "target": target.to_dict(),
            "preflight": preflight.to_dict(),
            "readyForRealExecution": target.account.verified,
            "note": (
                "Sandbox execution plan ready. "
                "Real AWS execution requires: verified account identity + "
                "credentials + approved sandbox target."
            ),
        }
        _sandbox_executions[execution_id] = execution
        return {"execution": execution}

    @app.get("/api/v1/sandbox/executions/{execution_id}")
    async def get_sandbox_execution(execution_id: str):
        """Get sandbox execution status."""
        ex = _sandbox_executions.get(execution_id)
        if not ex:
            raise HTTPException(status_code=404, detail="Execution not found")
        return {"execution": ex}
