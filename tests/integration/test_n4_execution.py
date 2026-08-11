"""Phase N4 — full Plan -> AIRLOCK -> Execution acceptance, via the real
FastAPI routes and a real fakecloud + tofu apply. Requires fakecloud
running on localhost:4566 (matches the existing test_golden_scenario.py /
test_phase2b.py convention: FAIL loudly if unavailable, never silently
skip an acceptance-critical path).
"""

from __future__ import annotations

import os

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
        pytest.fail("fakecloud not running — N4 execution acceptance requires fakecloud online")


def _s3():
    return boto3.client("s3", endpoint_url="http://localhost:4566",
                         aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")


def _make_approved_plan(name: str, target_fidelity: str = "SIMULATED"):
    r = client.post("/api/v1/designs", params={"name": name})
    did = r.json()["design"]["designId"]
    nodes = [{"nodeId": "N1", "name": "Bucket", "category": "STORAGE", "provider": "AWS", "nativeService": "s3"}]
    client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes, "edges": []}})
    client.post(f"/api/v1/designs/{did}/accept")
    r = client.post(f"/api/v1/designs/{did}/implementation-plan", params={"targetFidelity": target_fidelity})
    pid = r.json()["plan"]["planId"]
    client.post(f"/api/v1/implementation-plans/{pid}/approve", params={"approved_by": "n4-test"})
    return did, pid


def _cleanup_run(run_id: str) -> None:
    client.post(f"/api/v1/execution-runs/{run_id}/cleanup")


# ═══════════════════════════════════════════════════════════════════
# N4.10 — golden execution
# ═══════════════════════════════════════════════════════════════════


def test_golden_simulated_execution_end_to_end():
    _require_fakecloud()
    _did, pid = _make_approved_plan("N4 Golden Test")

    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "golden-test-key"})
    assert r.status_code == 200
    epid = r.json()["package"]["executionPackageId"]

    r = client.post(f"/api/v1/execution-packages/{epid}/preflight")
    assert r.json()["status"] == "PREFLIGHT_PASSED"
    assert r.json()["summary"]["BLOCK"] == 0

    r = client.post(f"/api/v1/execution-packages/{epid}/execute")
    result = r.json()["result"]
    assert result["status"] == "COMPLETED"
    assert result["tasksPassed"] == 1
    assert result["tasksFailed"] == 0
    # Executor must never claim VERIFIED_SUCCESS — only COMPLETED/FAILED.
    assert result["status"] != "VERIFIED_SUCCESS"

    _cleanup_run(result["runId"])


# ═══════════════════════════════════════════════════════════════════
# Negative scenarios A, B, C, F, G, H (D/E covered by unit-level policy
# tests in test_n4_airlock.py — no fakecloud needed there)
# ═══════════════════════════════════════════════════════════════════


def test_scenario_a_stale_plan_rejected_at_execute():
    _require_fakecloud()
    did, pid = _make_approved_plan("N4 Neg A")
    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "neg-a"})
    epid = r.json()["package"]["executionPackageId"]

    # Mutate architecture after package creation, before execute (TOCTOU case)
    nodes2 = [
        {"nodeId": "N1", "category": "STORAGE", "provider": "AWS", "nativeService": "s3"},
        {"nodeId": "N2", "category": "DATABASE", "provider": "AWS", "nativeService": "rds"},
    ]
    client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes2, "edges": []}})

    r = client.post(f"/api/v1/execution-packages/{epid}/preflight")
    assert r.json()["status"] == "PREFLIGHT_FAILED"
    stale_check = next(c for c in r.json()["checks"] if c["checkId"] == "PLAN_NOT_STALE")
    assert stale_check["status"] == "BLOCK"

    r = client.post(f"/api/v1/execution-packages/{epid}/execute")
    assert r.status_code == 400  # package never reached PREFLIGHT_PASSED


def test_scenario_b_tampered_plan_digest_rejected_at_execute(monkeypatch):
    _require_fakecloud()
    monkeypatch.setenv("INFRA_AGAIN_ACCEPTANCE", "1")
    _did, pid = _make_approved_plan("N4 Neg B")
    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "neg-b"})
    epid = r.json()["package"]["executionPackageId"]
    client.post(f"/api/v1/execution-packages/{epid}/preflight")

    r = client.post(f"/api/v1/_test/implementation-plans/{pid}/force-checksum", params={"new_checksum": "TAMPERED"})
    assert r.status_code == 200

    r = client.post(f"/api/v1/execution-packages/{epid}/execute")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "EXECUTION_PLAN_CHECKSUM_MISMATCH"


def test_scenario_c_unapproved_plan_rejected():
    r = client.post("/api/v1/designs", params={"name": "N4 Neg C"})
    did = r.json()["design"]["designId"]
    nodes = [{"nodeId": "N1", "category": "STORAGE", "provider": "AWS", "nativeService": "s3"}]
    client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes, "edges": []}})
    client.post(f"/api/v1/designs/{did}/accept")
    r = client.post(f"/api/v1/designs/{did}/implementation-plan")
    pid = r.json()["plan"]["planId"]
    assert r.json()["plan"]["status"] == "REVIEW_READY"

    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "neg-c"})
    assert r.status_code == 400
    assert "EXECUTION_NOT_ALLOWED" in r.json()["detail"]


def test_scenario_f_unsupported_mandatory_task_rejected():
    r = client.post("/api/v1/designs", params={"name": "N4 Neg F"})
    did = r.json()["design"]["designId"]
    nodes = [
        {"nodeId": "N1", "category": "STORAGE", "provider": "AWS", "nativeService": "s3"},
        {"nodeId": "N2", "category": "CACHE", "provider": "AWS", "nativeService": "elasticache"},
    ]
    client.post(f"/api/v1/designs/{did}/update-flow", json={"flow": {"nodes": nodes, "edges": []}})
    client.post(f"/api/v1/designs/{did}/accept")
    r = client.post(f"/api/v1/designs/{did}/implementation-plan", params={"targetFidelity": "SIMULATED"})
    pid = r.json()["plan"]["planId"]
    client.post(f"/api/v1/implementation-plans/{pid}/approve", params={"approved_by": "neg-f"})

    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "neg-f"})
    epid = r.json()["package"]["executionPackageId"]
    # The unsupported task is filtered from the package itself...
    assert len(r.json()["package"]["tasks"]) == 1

    # ...but preflight must still see it via the plan and BLOCK.
    r = client.post(f"/api/v1/execution-packages/{epid}/preflight")
    assert r.json()["status"] == "PREFLIGHT_FAILED"
    cap_check = next(c for c in r.json()["checks"] if c["checkId"] == "CAPABILITY_SUPPORTED")
    assert cap_check["status"] == "BLOCK"


def test_scenario_g_same_idempotency_key_no_duplicate_resource():
    _require_fakecloud()
    _did, pid = _make_approved_plan("N4 Neg G")

    r1 = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                      json={"target_type": "fakecloud", "idempotency_key": "SAME-KEY-G"})
    r2 = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                      json={"target_type": "fakecloud", "idempotency_key": "SAME-KEY-G"})
    epid1 = r1.json()["package"]["executionPackageId"]
    epid2 = r2.json()["package"]["executionPackageId"]
    assert epid1 == epid2
    assert r2.json().get("note", "").startswith("idempotent")

    client.post(f"/api/v1/execution-packages/{epid1}/preflight")
    r = client.post(f"/api/v1/execution-packages/{epid1}/execute")
    run_id = r.json()["result"]["runId"]
    buckets_after_first = len(_s3().list_buckets()["Buckets"])

    # Re-execute the SAME (now COMPLETED) package must not duplicate mutation.
    r2 = client.post(f"/api/v1/execution-packages/{epid1}/execute")
    assert r2.status_code == 400
    buckets_after_second = len(_s3().list_buckets()["Buckets"])
    assert buckets_after_first == buckets_after_second

    _cleanup_run(run_id)


def test_scenario_h_foreign_resource_protected():
    _require_fakecloud()

    def _run(name: str) -> tuple[str, str]:
        _did, pid = _make_approved_plan(name)
        r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                         json={"target_type": "fakecloud", "idempotency_key": name})
        epid = r.json()["package"]["executionPackageId"]
        client.post(f"/api/v1/execution-packages/{epid}/preflight")
        r = client.post(f"/api/v1/execution-packages/{epid}/execute")
        return r.json()["result"]["runId"], epid

    run_a, _ = _run("N4 Neg H A")
    run_b, _ = _run("N4 Neg H B")

    before = {b["Name"] for b in _s3().list_buckets()["Buckets"]}
    r = client.post(f"/api/v1/execution-runs/{run_a}/cleanup")
    assert r.json()["status"] == "COMPLETED"
    after = {b["Name"] for b in _s3().list_buckets()["Buckets"]}

    assert len(after) == len(before) - 1  # only run_a's bucket removed
    _cleanup_run(run_b)


# ═══════════════════════════════════════════════════════════════════
# Executor cannot self-verify (section 9)
# ═══════════════════════════════════════════════════════════════════


def test_executor_never_reports_verified_success():
    _require_fakecloud()
    _did, pid = _make_approved_plan("N4 No Self Verify")
    r = client.post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "no-self-verify"})
    epid = r.json()["package"]["executionPackageId"]
    client.post(f"/api/v1/execution-packages/{epid}/preflight")
    r = client.post(f"/api/v1/execution-packages/{epid}/execute")
    result = r.json()["result"]
    assert result["status"] in ("COMPLETED", "FAILED")
    assert result["status"] != "VERIFIED_SUCCESS"
    _cleanup_run(result["runId"])
