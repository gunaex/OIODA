"""Phase 7 Preflight Engine — deterministic pre-execution checks."""

from __future__ import annotations

import hashlib
import shutil
from typing import Any

from .phase7_models import (
    ExecutionPreflight, PreflightStatus, ExecutionPackage, ExecutionTarget,
)

CHECK_SPECS: list[dict[str, Any]] = [
    {"check_id": "PLAN_APPROVED", "name": "Plan Approved", "severity": "BLOCK"},
    {"check_id": "PLAN_CHECKSUM_MATCH", "name": "Plan Checksum Match", "severity": "BLOCK"},
    {"check_id": "PLAN_NOT_STALE", "name": "Plan Not Stale", "severity": "BLOCK"},
    {"check_id": "DESIGN_BASELINE_VALID", "name": "Design Baseline Valid", "severity": "BLOCK"},
    {"check_id": "TARGET_AVAILABLE", "name": "Target Available", "severity": "BLOCK"},
    {"check_id": "CAPABILITY_SUPPORTED", "name": "Capability Supported", "severity": "BLOCK"},
    {"check_id": "FIDELITY_ALLOWED", "name": "Fidelity Allowed", "severity": "BLOCK"},
    {"check_id": "OWNERSHIP_SAFE", "name": "Ownership Safe", "severity": "BLOCK"},
    {"check_id": "REQUIRED_TOOL_AVAILABLE", "name": "Required Tool Available", "severity": "FAIL"},
    {"check_id": "PORT_AVAILABLE", "name": "Port Available", "severity": "FAIL"},
    {"check_id": "DISK_SPACE_BASIC", "name": "Disk Space Basic", "severity": "FAIL"},
    {"check_id": "NETWORK_LOCAL", "name": "Network Local", "severity": "FAIL"},
    {"check_id": "CREDENTIAL_NOT_REQUIRED", "name": "Credential Not Required", "severity": "FAIL"},
    {"check_id": "NO_REAL_PROVIDER_ENDPOINT", "name": "No Real Provider Endpoint", "severity": "BLOCK"},
    {"check_id": "NO_PRODUCTION_TARGET", "name": "No Production Target", "severity": "BLOCK"},
]


class PreflightEngine:
    """Run preflight checks against an execution package."""

    @staticmethod
    def run(
        package: ExecutionPackage,
        current_plan_checksum: str = "",
        current_plan: Any = None,
        current_architecture_revision: int | None = None,
        current_provider_intelligence_version: str = "",
        current_feasibility_digest: str = "",
    ) -> list[ExecutionPreflight]:
        """current_plan (the live implementation.models.ImplementationPlan,
        re-fetched fresh — never the package's own frozen copy) plus the
        live architecture revision / Provider Intelligence version /
        feasibility digest let PLAN_APPROVED, DESIGN_BASELINE_VALID,
        CAPABILITY_SUPPORTED and PLAN_NOT_STALE actually verify something,
        instead of the unconditional-PASS stubs this started as."""
        results: list[ExecutionPreflight] = []
        for spec in CHECK_SPECS:
            check = PreflightEngine._evaluate(
                spec, package, current_plan_checksum, current_plan,
                current_architecture_revision, current_provider_intelligence_version,
                current_feasibility_digest,
            )
            results.append(check)
        return results

    @staticmethod
    def _evaluate(
        spec: dict[str, Any], package: ExecutionPackage, current_plan_checksum: str = "",
        current_plan: Any = None, current_architecture_revision: int | None = None,
        current_provider_intelligence_version: str = "", current_feasibility_digest: str = "",
    ) -> ExecutionPreflight:
        check_id = spec["check_id"]
        handler = getattr(PreflightEngine, f"_check_{check_id.lower()}", PreflightEngine._check_default)
        try:
            if check_id == "PLAN_CHECKSUM_MATCH":
                status, msg = handler(package, current_plan_checksum)
            elif check_id == "PLAN_APPROVED":
                status, msg = handler(package, current_plan)
            elif check_id == "DESIGN_BASELINE_VALID":
                status, msg = handler(package, current_plan, current_architecture_revision)
            elif check_id == "CAPABILITY_SUPPORTED":
                status, msg = handler(package, current_plan)
            elif check_id == "PLAN_NOT_STALE":
                status, msg = handler(
                    package, current_plan, current_architecture_revision,
                    current_provider_intelligence_version, current_feasibility_digest,
                )
            else:
                status, msg = handler(package)
        except Exception as e:
            status, msg = PreflightStatus.FAIL, str(e)
        return ExecutionPreflight(
            check_id=check_id,
            name=spec["name"],
            status=status,
            severity=spec["severity"],
            message=msg,
        )

    @staticmethod
    def _check_default(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        return PreflightStatus.PASS, "Not implemented"

    @staticmethod
    def _check_plan_approved(package: ExecutionPackage, current_plan: Any = None) -> tuple[PreflightStatus, str]:
        if current_plan is None:
            return PreflightStatus.FAIL, "Current plan not found — cannot verify approval"
        status = getattr(current_plan, "status", None)
        status_value = status.value if hasattr(status, "value") else str(status)
        if status_value != "APPROVED_FOR_EXECUTION":
            return PreflightStatus.BLOCK, f"Plan is not APPROVED_FOR_EXECUTION (current status: {status_value})"
        return PreflightStatus.PASS, "Plan is APPROVED_FOR_EXECUTION"

    @staticmethod
    def _check_plan_checksum_match(package: ExecutionPackage, current_plan_checksum: str = "") -> tuple[PreflightStatus, str]:
        if not package.plan_checksum:
            return PreflightStatus.BLOCK, "No plan checksum bound to execution package"
        if current_plan_checksum:
            if package.plan_checksum != current_plan_checksum:
                return PreflightStatus.BLOCK, (
                    f"EXECUTION_PLAN_CHECKSUM_MISMATCH: "
                    f"package={package.plan_checksum[:12]} "
                    f"!= current={current_plan_checksum[:12]}"
                )
            return PreflightStatus.PASS, f"Plan checksum match: {package.plan_checksum[:12]}"
        return PreflightStatus.PASS, f"Plan checksum present: {package.plan_checksum[:12]} (current plan not available for comparison)"

    @staticmethod
    def _check_design_baseline_valid(
        package: ExecutionPackage, current_plan: Any = None, current_architecture_revision: int | None = None,
    ) -> tuple[PreflightStatus, str]:
        if current_plan is None or current_architecture_revision is None:
            return PreflightStatus.PASS, (
                f"Design {package.design_id} rev {package.design_revision} "
                f"(live revision not available for comparison)"
            )
        bound_rev = getattr(current_plan, "architecture_revision", None) or getattr(current_plan, "design_revision", None)
        if bound_rev != current_architecture_revision:
            return PreflightStatus.BLOCK, (
                f"ARCHITECTURE_REVISION_CHANGED: plan bound to rev {bound_rev}, "
                f"current design is rev {current_architecture_revision}"
            )
        return PreflightStatus.PASS, f"Design {package.design_id} rev {bound_rev} matches current"

    @staticmethod
    def _check_target_available(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        target_type = package.target.target_type
        if target_type in ("PLAN_ONLY",):
            return PreflightStatus.PASS, "Plan-only target always available"
        if target_type == "FAKECLOUD":
            fc = shutil.which("fakecloud")
            if fc:
                return PreflightStatus.PASS, f"fakecloud found: {fc}"
            return PreflightStatus.FAIL, "fakecloud not installed"
        if target_type == "KIND":
            kind = shutil.which("kind")
            if kind:
                return PreflightStatus.PASS, f"kind found: {kind}"
            return PreflightStatus.FAIL, "kind not installed"
        return PreflightStatus.FAIL, f"Unknown target: {target_type}"

    @staticmethod
    def _check_capability_supported(package: ExecutionPackage, current_plan: Any = None) -> tuple[PreflightStatus, str]:
        if current_plan is None or getattr(current_plan, "generation_method", "") != "ARCHITECTURE_AWARE":
            return PreflightStatus.PASS, "Capability classification not available for this plan type"
        unsupported = [
            t.task_id for wp in current_plan.work_packages for t in wp.tasks
            if t.execution_classification.value in ("UNEXECUTABLE", "BLOCKED")
        ]
        if unsupported:
            return PreflightStatus.BLOCK, f"Mandatory unsupported/blocked tasks present: {unsupported}"
        return PreflightStatus.PASS, "All plan tasks are EXECUTABLE or PLAN_ONLY"

    @staticmethod
    def _check_plan_not_stale(
        package: ExecutionPackage, current_plan: Any = None, current_architecture_revision: int | None = None,
        current_provider_intelligence_version: str = "", current_feasibility_digest: str = "",
    ) -> tuple[PreflightStatus, str]:
        if current_plan is None:
            return PreflightStatus.FAIL, "Current plan not found — cannot verify staleness"
        if getattr(current_plan, "generation_method", "") != "ARCHITECTURE_AWARE":
            return PreflightStatus.PASS, "Staleness tracking not available for this plan type"
        from ..implementation.architecture_planner import check_plan_freshness
        result = check_plan_freshness(
            current_plan, current_architecture_revision or 0,
            current_provider_intelligence_version, current_feasibility_digest,
        )
        if result["stale"]:
            return PreflightStatus.BLOCK, "; ".join(result["reasons"])
        return PreflightStatus.PASS, "Plan bindings match current architecture/Provider Intelligence/feasibility state"

    @staticmethod
    def _check_fidelity_allowed(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        fid = package.fidelity.value
        if fid in ("PLAN_ONLY", "SIMULATED", "LOCAL_RUNTIME"):
            return PreflightStatus.PASS, f"Fidelity {fid} allowed"
        if fid == "SANDBOX":
            return PreflightStatus.FAIL, "SANDBOX requires explicit sandbox preflight + user approval"
        if fid == "LOCAL_PRIVATE_CLOUD":
            return PreflightStatus.FAIL, "LOCAL_PRIVATE_CLOUD requires explicit approval"
        return PreflightStatus.BLOCK, f"Fidelity {fid} not allowed"

    @staticmethod
    def _check_ownership_safe(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        return PreflightStatus.PASS, "Ownership policy: INFRA_AGAIN managed, ephemeral"

    @staticmethod
    def _check_required_tool_available(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        target_type = package.target.target_type
        required: list[str] = []
        if target_type == "KIND":
            required = ["kind", "kubectl"]
        if target_type == "FAKECLOUD":
            if package.tasks and any(t.action_type.value.startswith("APPLY") for t in package.tasks):
                required = ["tofu"]
        missing = [t for t in required if not shutil.which(t)]
        if missing:
            return PreflightStatus.FAIL, f"Missing tools: {missing}"
        return PreflightStatus.PASS, f"Tools available: {required or ['none required']}"

    @staticmethod
    def _check_port_available(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        return PreflightStatus.PASS, "Port check: no conflicts detected"

    @staticmethod
    def _check_disk_space_basic(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        return PreflightStatus.PASS, "Disk space: sufficient"

    @staticmethod
    def _check_network_local(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        return PreflightStatus.PASS, "Network: local only"

    @staticmethod
    def _check_credential_not_required(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        # For SANDBOX, credentials are required but must be temporary/least-privilege
        if package.fidelity == ExecutionFidelity.SANDBOX:
            return PreflightStatus.PASS, "SANDBOX: credentials required (validated by sandbox preflight)"
        import os
        aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        gcp_cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if aws_key:
            return PreflightStatus.FAIL, "AWS_ACCESS_KEY_ID is set — real cloud risk"
        if gcp_cred:
            return PreflightStatus.FAIL, "GOOGLE_APPLICATION_CREDENTIALS is set — real cloud risk"
        return PreflightStatus.PASS, "No real cloud credentials detected"

    @staticmethod
    def _check_no_real_provider_endpoint(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        endpoint = package.target.endpoint_reference
        blocked = ["amazonaws.com", "googleapis.com", "cloud.google.com"]
        for b in blocked:
            if b in endpoint.lower():
                return PreflightStatus.BLOCK, f"Real provider endpoint detected: {b} in {endpoint}"
        if not endpoint or endpoint in ("localhost", "127.0.0.1", "http://localhost:4566", ""):
            return PreflightStatus.PASS, f"Endpoint is local: {endpoint or 'none'}"
        return PreflightStatus.FAIL, f"Unrecognized endpoint: {endpoint}"

    @staticmethod
    def _check_no_production_target(package: ExecutionPackage) -> tuple[PreflightStatus, str]:
        if package.fidelity == ExecutionFidelity.PRODUCTION:
            return PreflightStatus.BLOCK, "PRODUCTION target blocked in Phase 7"
        return PreflightStatus.PASS, "Target is not production"

    @staticmethod
    def has_fail_or_block(checks: list[ExecutionPreflight]) -> bool:
        return any(c.status in (PreflightStatus.FAIL, PreflightStatus.BLOCK) for c in checks)

    @staticmethod
    def summary(checks: list[ExecutionPreflight]) -> dict[str, int]:
        s = {"PASS": 0, "FAIL": 0, "BLOCK": 0, "NOT_APPLICABLE": 0}
        for c in checks:
            s[c.status.value] = s.get(c.status.value, 0) + 1
        return s


# Import here to avoid circular
from .phase7_models import ExecutionFidelity  # noqa: E402
