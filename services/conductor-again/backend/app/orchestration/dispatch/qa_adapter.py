"""
QA Again dispatch adapter (QA-E5).

Classification: REAL_RUNTIME. QA Again now runs a real canonical QARequest
intake endpoint and produces a real canonical QAResult from its own test
execution state (contracts/vendored/v1/schemas/QAResult.json,
backend/app/qa_result_service.py in the QA Again repo).

Still never fabricates: fetch_result returns None (not a synthetic
QAResult) whenever QA Again has no result for a qaRequestId yet —
execution still in progress, or the request never mapped to a TestCycle —
or QA Again is unreachable. This is the same "QA as NOT_USED rather than
fabricating" principle the old harness always stated, just backed by a
real client and a genuinely asynchronous result now (real QA execution
does not complete within the dispatch call itself, unlike the old
harness).

The former HARNESS/ContractQAStub classification is preserved below as
run_harness() for explicit local/offline fallback when QA Again is not
running (E7 disclosed limitation) — it is not used by the default
REAL_RUNTIME dispatch()/fetch_result() path above.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.contracts import v1
from app.integration.qa_again_client import QAAgainClient
from app.orchestration.dispatch import REAL_RUNTIME

STATUS = REAL_RUNTIME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def health() -> bool:
    return QAAgainClient.health()


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


def dispatch(*, run, qa_request: dict[str, Any]) -> dict[str, Any]:
    """Sends the canonical QARequest to QA Again's real intake endpoint.
    Raises QAAgainUnavailableError on transport failure — caller decides
    fallback policy (QA_UNAVAILABLE_NO_FAKE_APPROVAL: this never returns a
    synthetic dispatch acknowledgement)."""
    idempotency_key = f"qa-{run.run_id}"
    return QAAgainClient.dispatch_qa_request(
        qa_request=qa_request, idempotency_key=idempotency_key, tenant_id=run.tenant_id,
    )


def fetch_result(*, run, qa_request_id: str) -> Optional[dict[str, Any]]:
    """Fetches the real canonical QAResult for this qaRequestId. Returns
    None — never a fabricated result — if QA Again has no result yet or
    can't be reached."""
    return QAAgainClient.get_qa_result(qa_request_id)


# ── Legacy HARNESS fallback (pre-QA-E5) — not used by the REAL_RUNTIME
# dispatch()/fetch_result() path above. Kept for explicit local/offline
# acceptance runs when QA Again is not running. ──


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
            "summary": "HARNESS result: explicit local/offline fallback, not a real QA Again execution.",
            "timestamp": _now_iso(),
        }],
        "completedAt": _now_iso(),
    })
    return canonical.to_canonical_dict()
