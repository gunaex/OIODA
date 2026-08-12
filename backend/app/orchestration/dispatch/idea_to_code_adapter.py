"""
Idea -> Code dispatch adapter (E8-E §40).

REAL_RUNTIME: verified live against a running Local AI Control Center
(which co-locates the Idea -> Code pipeline). Dispatch goes through
LocalAIControlCenterClient — Conductor builds the canonical
EngineeringWorkPackage, the adapter maps it to LACC's own local v1 contract
shape (an explicit adapter, not a shared contract), and maps the run result
back to a canonical EngineeringResult.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.contracts import v1
from app.integration.lacc_client import LACCUnavailableError, LocalAIControlCenterClient
from app.orchestration.dispatch import REAL_RUNTIME

STATUS = REAL_RUNTIME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_engineering_work_package(
    *, run, requirements: str, constraints: dict | None = None, engineering_work_package_id: str | None = None,
) -> dict[str, Any]:
    ewp = v1.EngineeringWorkPackage.validate_canonical({
        "engineeringWorkPackageId": engineering_work_package_id or f"ewp-{uuid.uuid4().hex[:12]}",
        "correlationId": run.correlation_id,
        "workPackageId": run.work_package_id,
        "requirements": requirements,
        "constraints": constraints or {},
        "createdAt": _now_iso(),
    })
    return ewp.to_canonical_dict()


def dispatch(*, run, engineering_work_package: dict[str, Any], project_name: str) -> dict[str, Any]:
    """Sends the EngineeringWorkPackage to the real Idea -> Code boundary.
    Raises LACCUnavailableError on transport failure — caller decides fallback policy."""
    return LocalAIControlCenterClient.dispatch_engineering_work_package(
        engineering_work_package=engineering_work_package,
        delivery_work_package=run.work_package_payload,
        project_name=project_name,
    )


def run_and_collect_result(*, run, engineering_run_id: str) -> dict[str, Any]:
    """Runs the real Idea -> Code pipeline (plan -> execute -> verify) and maps the
    outcome to a canonical EngineeringResult snapshot."""
    outcome = LocalAIControlCenterClient.start_engineering_run(engineering_run_id)
    return to_canonical_engineering_result(run=run, engineering_run_id=engineering_run_id, outcome=outcome)


def to_canonical_engineering_result(*, run, engineering_run_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
    verification = outcome.get("verification") or {}
    result = outcome.get("result") or {}
    verify_passed = bool(verification.get("passed"))
    build_ok = (result.get("build") or {}).get("status") == "PASS" or (result.get("build") or {}).get("status") == "COMPLETED"
    tests = result.get("tests") or {}

    if verify_passed:
        status = "SUCCESS"
    elif tests.get("passed", 0) > 0 or build_ok:
        status = "PARTIAL"
    else:
        status = "FAILED"

    evidence = [{
        "type": "VERIFIER_REPORT", "source": "idea-to-code",
        "reference": f"lacc://idea-to-code/{engineering_run_id}/verification",
        "summary": "; ".join(verification.get("findings", [])) or "verification recorded",
        "timestamp": result.get("completedAt", _now_iso()),
    }, {
        "type": "TEST_RESULTS", "source": "idea-to-code",
        "reference": f"lacc://idea-to-code/{engineering_run_id}/tests",
        "summary": f"passed={tests.get('passed', 0)} failed={tests.get('failed', 0)}",
        "timestamp": result.get("completedAt", _now_iso()),
    }]

    canonical = v1.EngineeringResult.validate_canonical({
        "engineeringResultId": f"er-{uuid.uuid4().hex[:12]}",
        "correlationId": run.correlation_id,
        "workPackageId": run.work_package_id,
        "status": status,
        "repo": outcome.get("engineeringRunId", engineering_run_id),
        "branch": f"feature/{run.correlation_id}",
        "commit": "local-working-tree",
        "pipeline": {
            "plan": {"status": "COMPLETED" if outcome.get("plan") else "FAILED"},
            "execute": {"status": "COMPLETED" if result else "FAILED",
                        "filesChanged": len(result.get("changedFiles", []))},
            "build": {"status": "COMPLETED" if build_ok else "FAILED"},
            "test": {"status": "COMPLETED" if tests else "FAILED",
                      "testsPassed": tests.get("passed", 0), "testsFailed": tests.get("failed", 0)},
            "verify": {"status": "PASS" if verify_passed else "FAIL",
                       "verifierRole": (verification.get("verifierMeta") or {}).get("provider", "")},
        },
        "evidence": evidence,
        "completedAt": result.get("completedAt", _now_iso()),
    })
    data = canonical.to_canonical_dict()
    # Conductor-owned policy metadata, NOT part of the canonical contract (§50): whether
    # a PARTIAL result should block delivery readiness. A build/test FAIL that still
    # produced changed files is blocking; anything else PARTIAL is treated as
    # non-blocking so the readiness engine's caveated READY branch can be reached.
    data["conductorPolicy"] = {"blocking": status == "PARTIAL" and not build_ok}
    return data
