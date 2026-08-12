"""
Infrastructure Again dispatch adapter (E8-E §41).

Classification: FROZEN_RUNTIME_REFERENCE, not LIVE_ADAPTER. INFRA-AGAIN is
frozen (again-ecosystem-v1 / infra-again-v1 tags) — this adapter builds a
genuinely canonical InfrastructureRequest but does NOT invoke INFRA-AGAIN's
live API, because doing so would trigger real (even if fake-cloud) provision
side effects against a frozen baseline this task explicitly forbids touching.
Per E8 §41, a contract-realistic adapter/harness is acceptable here as long
as the classification is disclosed honestly — it is, in both this docstring
and the adapter_status field every dispatch record carries.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.contracts import v1
from app.orchestration.dispatch import FROZEN_RUNTIME

STATUS = FROZEN_RUNTIME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_infrastructure_request(*, run, engineering_result_id: str, requirements: dict) -> dict[str, Any]:
    ir = v1.InfrastructureRequest.validate_canonical({
        "infrastructureRequestId": f"ir-{uuid.uuid4().hex[:12]}",
        "correlationId": run.correlation_id,
        "workPackageId": run.work_package_id,
        "engineeringResultId": engineering_result_id,
        "requirements": requirements,
        "createdAt": _now_iso(),
    })
    return ir.to_canonical_dict()


def simulate_result(*, run, infrastructure_request: dict[str, Any]) -> dict[str, Any]:
    """FROZEN_RUNTIME_REFERENCE: deterministic, disclosed-as-simulated result. Never
    presented as a real provisioning outcome — evidence reference says so explicitly."""
    canonical = v1.InfrastructureResult.validate_canonical({
        "infrastructureResultId": f"ifr-{uuid.uuid4().hex[:12]}",
        "correlationId": run.correlation_id,
        "workPackageId": run.work_package_id,
        "infrastructureRequestId": infrastructure_request["infrastructureRequestId"],
        "status": "SUCCESS",
        "provider": "ON_PREM",
        "platform": "NATIVE_VM",
        "endpoints": [],
        "pipeline": {
            "provision": {"status": "SIMULATED", "tool": "OPENTOFU"},
            "validate": {"status": "SIMULATED", "healthCheckPassed": True},
        },
        "evidence": [{
            "type": "VALIDATION_RESULTS", "source": "conductor-main-frozen-runtime-reference",
            "reference": f"conductor://frozen-reference/infra/{infrastructure_request['infrastructureRequestId']}",
            "summary": "FROZEN_RUNTIME_REFERENCE: INFRA-AGAIN is frozen per ecosystem baseline; this "
                       "is a disclosed simulated result, not a real provisioning outcome.",
            "timestamp": _now_iso(),
        }],
        "completedAt": _now_iso(),
    })
    return canonical.to_canonical_dict()
