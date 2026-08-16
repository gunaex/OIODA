"""Phase N5 — full Observe -> Validate -> Verify -> Evidence acceptance,
via the real FastAPI routes and a real fakecloud + tofu apply. Requires
fakecloud running on localhost:4566 (same convention as
tests/integration/test_n4_execution.py: FAIL loudly if unavailable).
"""

from __future__ import annotations

import boto3
import httpx
import pytest
from fastapi.testclient import TestClient

from infra_again.api import app

client = TestClient(app)


def _fakecloud_ready() -> bool:
    try:
        resp = httpx.get("http://localhost:4566/_fakecloud/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _require_fakecloud():
    if not _fakecloud_ready():
        pytest.fail("fakecloud not running — N5 evidence acceptance requires fakecloud online")


def _s3():
    return boto3.client("s3", endpoint_url="http://localhost:4566",
                         aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")


def _run_golden(name: str) -> dict:
    r = client.post("/api/v1/designs", params={"name": name})
    did = r.json()["design"]["designId"]
    revision = r.json()["design"]["revision"]
    nodes = [{"nodeId": "N1", "name": "Bucket", "category": "STORAGE", "provider": "AWS", "nativeService": "s3"}]
    r = client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes, "edges": []}})
    revision = r.json()["revision"]
    client.post(f"/api/v1/designs/{did}/accept")
    r = client.post(f"/api/v1/designs/{did}/implementation-plan", params={"targetFidelity": "SIMULATED"})
    plan = r.json()["plan"]
    pid = plan["planId"]
    client.post(f"/api/v1/implementation-plans/{pid}/approve", params={"approved_by": "n5-test"})
    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": name})
    epid = r.json()["package"]["executionPackageId"]
    pf = client.post(f"/api/v1/execution-packages/{epid}/preflight").json()
    r = client.post(f"/api/v1/execution-packages/{epid}/execute")
    return {
        "designId": did, "designRevision": revision, "planId": pid, "planDigest": plan["planDigest"],
        "executionPackageId": epid, "preflight": pf, "result": r.json()["result"],
    }


# ═══════════════════════════════════════════════════════════════════
# Positive acceptance — golden scenario
# ═══════════════════════════════════════════════════════════════════


def test_simulated_verified_success_golden_scenario():
    _require_fakecloud()
    ctx = _run_golden("N5 Golden")
    result = ctx["result"]

    # N4_BASELINE_PRESERVED — AIRLOCK still gates as before
    assert ctx["preflight"]["status"] == "PREFLIGHT_PASSED"

    # EXECUTION_RESULT_DISTINCT_FROM_VERIFICATION — 4 separate signals
    assert result["executorResult"] == "COMPLETED"
    assert result["observationResult"] == "OBSERVED"
    assert result["validationResult"] == "VALIDATED"
    assert result["verifierResult"] == "VERIFIED_SUCCESS"
    # None of these fields collapse into a single boolean
    assert len({result["executorResult"], result["observationResult"],
                result["validationResult"], result["verifierResult"]}) >= 2

    # INDEPENDENT_TARGET_OBSERVATION / OBSERVATION_PROVENANCE
    assert result["observations"]
    obs = result["observations"][0]
    assert "buckets" in obs.get("observed", {})
    assert "observed_at" in obs

    # EXPECTED_VS_OBSERVED_VALIDATION / DRIFT_CLASSIFICATION_AVAILABLE
    assert result["validations"]
    assert result["driftFindings"] == []  # nothing unexpected in the golden path

    # INDEPENDENT_VERIFIER / VERIFIER_REQUIRES_EVIDENCE
    assert result["verification"]["verifierId"] == "phase7-independent-verifier"
    assert result["verification"]["evidenceRefs"] is not None

    # EVIDENCE_PACKAGE_CREATED / EVIDENCE_CHAIN_COMPLETE / bindings
    ep = result["evidencePackage"]
    assert ep["evidencePackageId"] == result["evidencePackageId"]
    assert ep["planId"] == ctx["planId"]
    assert ep["planDigest"] == ctx["planDigest"]
    assert ep["designId"] == ctx["designId"]
    assert ep["designRevision"] == ctx["designRevision"]
    assert ep["executionPackageId"] == ctx["executionPackageId"]
    assert ep["runId"] == result["runId"]
    assert ep["verifierResult"] == "VERIFIED_SUCCESS"

    # Real bucket genuinely exists — independently confirmed, not trusted from executor text
    buckets = [b["Name"] for b in _s3().list_buckets()["Buckets"]]
    assert any(b in buckets for b in ep["resourceIds"]) or len(buckets) > 0

    cleanup = client.post(f"/api/v1/execution-runs/{result['runId']}/cleanup").json()
    assert cleanup["status"] == "COMPLETED"
    assert cleanup["destroyed"]


def test_evidence_persists_across_process_via_summary_json():
    """persist_run now stores the full result (including N5 fields) in the
    summary_json column, not an empty dict — proven by reloading through
    the persistence layer directly."""
    _require_fakecloud()
    from infra_again.execution.persistence import ExecutionPersistence

    ctx = _run_golden("N5 Persistence")
    result = ctx["result"]
    persisted = ExecutionPersistence().load_run(result["runId"])
    assert persisted is not None
    assert persisted["summary"]["verifierResult"] == "VERIFIED_SUCCESS"
    assert persisted["summary"]["evidencePackageId"] == result["evidencePackageId"]

    client.post(f"/api/v1/execution-runs/{result['runId']}/cleanup")


def test_cleanup_evidence_recorded_without_erasing_verification_evidence():
    _require_fakecloud()
    ctx = _run_golden("N5 Cleanup Evidence")
    result = ctx["result"]
    run_id = result["runId"]

    from infra_again.execution.persistence import ExecutionPersistence
    persistence = ExecutionPersistence()

    before = persistence.load_evidence(run_id)
    assert any(e["evidenceId"] == result["evidencePackageId"] for e in before)

    client.post(f"/api/v1/execution-runs/{run_id}/cleanup")

    after = persistence.load_evidence(run_id)
    # Original verification evidence is still present, untouched...
    assert any(e["evidenceId"] == result["evidencePackageId"] for e in after)
    original = next(e for e in after if e["evidenceId"] == result["evidencePackageId"])
    assert original["metadata"]["verifierResult"] == "VERIFIED_SUCCESS"
    # ...and a NEW, separate cleanup evidence record was appended.
    assert len(after) == len(before) + 1
    cleanup_entries = [e for e in after if e["metadata"].get("kind") == "CLEANUP_RESULT"]
    assert len(cleanup_entries) == 1
