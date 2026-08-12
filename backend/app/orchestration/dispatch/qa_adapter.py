"""
QA Again dispatch adapter (E8-E §42).

Classification: HARNESS. QA Again has no running local instance (E7 finding:
STUB_ONLY). Per §42, Conductor builds a QAAgainAdapter interface plus a
ContractQAStub/Harness for local acceptance — it does NOT build the QA Again
product itself, and does NOT fabricate a pass/fail judgment out of thin air:
the harness derives its result deterministically from the real
EngineeringResult it is given (structured rule, not free-text inference).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.contracts import v1
from app.orchestration.dispatch import HARNESS

STATUS = HARNESS


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_qa_request(*, run, engineering_result: dict, acceptance_criteria: dict) -> dict[str, Any]:
    qr = v1.QARequest.validate_canonical({
        "qaRequestId": f"qar-{uuid.uuid4().hex[:12]}",
        "correlationId": run.correlation_id,
        "workPackageId": run.work_package_id,
        "releaseCandidate": {
            "repo": engineering_result["repo"], "branch": engineering_result["branch"],
            "commit": engineering_result["commit"],
        },
        "acceptanceCriteria": acceptance_criteria,
        "engineeringResultReference": engineering_result["engineeringResultId"],
        "createdAt": _now_iso(),
    })
    return qr.to_canonical_dict()


def run_harness(*, run, qa_request: dict[str, Any], engineering_result: dict[str, Any]) -> dict[str, Any]:
    """Deterministic ContractQAStub: APPROVED iff engineering's own verify stage
    passed and reported zero failing tests; REJECTED otherwise. This is a structured
    rule against real upstream data, not a free-text guess (§50)."""
    pipeline = engineering_result.get("pipeline", {})
    verify_ok = (pipeline.get("verify") or {}).get("status") == "PASS"
    tests = pipeline.get("test") or {}
    tests_failed = tests.get("testsFailed", 0)

    if verify_ok and tests_failed == 0:
        gate, status = "APPROVED", "COMPLETED"
    else:
        gate, status = "REJECTED", "COMPLETED"

    canonical = v1.QAResult.validate_canonical({
        "qaResultId": f"qr-{uuid.uuid4().hex[:12]}",
        "correlationId": run.correlation_id,
        "workPackageId": run.work_package_id,
        "qaRequestId": qa_request["qaRequestId"],
        "status": status,
        "testSummary": {
            "total": tests.get("testsPassed", 0) + tests_failed,
            "passed": tests.get("testsPassed", 0), "failed": tests_failed, "skipped": 0,
        },
        "qualityGate": gate,
        "acceptanceValidation": {"businessCriteriaMet": gate == "APPROVED", "technicalCriteriaMet": verify_ok,
                                   "notes": "HARNESS: ContractQAStub derived from EngineeringResult verify/test stages."},
        "evidence": [{
            "type": "QA_TEST_RESULTS", "source": "conductor-main-qa-harness",
            "reference": f"conductor://qa-harness/{qa_request['qaRequestId']}",
            "summary": "HARNESS result: QA Again has no running local instance; this is a "
                       "disclosed ContractQAStub, not a real QA execution.",
            "timestamp": _now_iso(),
        }],
        "completedAt": _now_iso(),
    })
    return canonical.to_canonical_dict()
