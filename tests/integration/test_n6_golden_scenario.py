"""Phase N6 — ONE golden end-to-end scenario, through the real API, real
fakecloud, real tofu apply/destroy. Requires fakecloud running on
localhost:4566 (same convention as test_n4_execution.py / test_n5_evidence.py:
FAIL loudly if unavailable).

Scenario: minimal AWS file-storage architecture (ALB + Lambda + S3 +
CloudWatch — no database, no compliance signal) generated via AGAINPILOT's
real deterministic generate+refine flow, then carried through N1-N5 to
VERIFIED_SUCCESS.
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
        pytest.fail("fakecloud not running — N6 golden scenario requires fakecloud online")


def _refine(instruction: str, nodes: list[dict], edges: list[dict], detected: dict) -> tuple[list[dict], list[dict]]:
    r = client.post("/api/v1/againpilot/refine", json={
        "instruction": instruction, "nodes": nodes, "edges": edges, "provider": "AWS",
        "forceMode": "DETERMINISTIC_FALLBACK", "detectedRequirements": detected,
    })
    p = r.json()["proposal"]
    return p["nodes"], p["edges"]


def _build_golden_architecture() -> tuple[list[dict], list[dict]]:
    """Real requirement -> real AGAINPILOT generation -> real refine down to
    the smallest set of currently-SIMULATED-executable service categories
    (no manual node construction)."""
    brief = ("Build a simple internal file storage service on AWS. Users upload files through a "
             "lightweight serverless API behind a load balancer, files are stored in object storage, "
             "and basic operational monitoring is in place. Single region, low traffic, no compliance "
             "or high-availability requirements.")
    r = client.post("/api/v1/againpilot/generate", json={
        "brief": brief, "providerPreference": "AWS", "platformPreference": "NATIVE_VM",
        "forceMode": "DETERMINISTIC_FALLBACK",
    })
    body = r.json()
    assert body["resultMode"] == "DETERMINISTIC_FALLBACK"
    nodes, edges = body["proposal"]["nodes"], body["proposal"]["edges"]
    detected = body["proposal"].get("detectedRequirements", {})

    for instr in ["Remove Route 53", "Remove CloudFront", "Remove WAF", "Remove ElastiCache",
                  "Remove KMS", "Remove Secrets Manager", "Remove Amazon RDS"]:
        nodes, edges = _refine(instr, nodes, edges, detected)
    nodes, edges = _refine("Use Lambda instead of ECS Fargate", nodes, edges, detected)
    return nodes, edges


def test_golden_end_to_end_requirement_to_verified_success():
    _require_fakecloud()

    # ── Requirement -> AGAINPILOT generation + refine (real flow) ──
    nodes, edges = _build_golden_architecture()
    categories = {n["category"] for n in nodes}
    assert "DATABASE" not in categories  # keeps the scenario within currently-executable roles

    # ── Provider Intelligence resolution ──
    r = client.post("/api/v1/provider-intelligence/architecture-summary", json={"nodes": nodes})
    summary = r.json()
    assert summary["unknownServiceCount"] == 0
    non_user_nodes = [n for n in nodes if n["category"] not in ("USER", "EXTERNAL")]
    assert summary["executableCount"] == len(non_user_nodes)

    # ── Completeness (real validator) ──
    from infra_again.intelligence.againpilot import validate_architecture_completeness, DetectedRequirement
    detected = DetectedRequirement(provider="AWS", platform="NATIVE_VM", expected_load="",
                                    availability=[], compliance=[], security=[], data_sensitivity=[])
    completeness = validate_architecture_completeness(nodes, edges, detected)
    assert completeness.overall.value == "PASS"
    assert completeness.missing_roles == []

    # ── Acceptance ──
    r = client.post("/api/v1/designs", params={"name": "N6 Golden Scenario Test"})
    design_id = r.json()["design"]["designId"]
    r = client.post(f"/api/v1/designs/{design_id}/update-flow", json={"flow": {"nodes": nodes, "edges": edges}})
    assert r.json()["contentChanged"] is True
    r = client.post(f"/api/v1/designs/{design_id}/accept")
    assert r.json()["design"]["status"] == "BASELINE_FROZEN"
    design_revision = r.json()["design"]["revision"]

    # ── Feasibility ──
    r = client.get(f"/api/v1/designs/{design_id}/feasibility", params={"fidelity": "SIMULATED"})
    feas = r.json()["feasibility"]
    assert feas["overallExecutability"] == "EXECUTABLE"
    assert feas["simulatedReady"] is True
    assert feas["blockingIssues"] == []

    # ── Implementation Plan ──
    r = client.post(f"/api/v1/designs/{design_id}/implementation-plan", params={"targetFidelity": "SIMULATED"})
    plan = r.json()["plan"]
    plan_id = plan["planId"]
    assert plan["generationMethod"] == "ARCHITECTURE_AWARE"
    assert plan["planDigest"]
    assert plan["architectureRevision"] == design_revision
    assert plan["feasibilityDigest"]
    assert plan["blockers"] == []
    all_tasks = [t for w in plan["workPackages"] for t in w["tasks"]]
    assert all(t["executionClassification"] == "EXECUTABLE" for t in all_tasks)
    # Node-to-task traceability
    assert all(t["sourceNodeIds"] for t in all_tasks)

    # ── Approval ──
    r = client.post(f"/api/v1/implementation-plans/{plan_id}/approve", params={"approved_by": "n6-golden"})
    assert r.json()["plan"]["status"] == "APPROVED_FOR_EXECUTION"
    approved_digest = r.json()["plan"]["approvedPlanDigest"]
    assert approved_digest == plan["planDigest"]
    r = client.get(f"/api/v1/implementation-plans/{plan_id}/status")
    assert r.json()["stale"] is False

    # ── ExecutionPackage + AIRLOCK ──
    r = client.post(f"/api/v1/implementation-plans/{plan_id}/execution-packages",
                     json={"target_type": "fakecloud", "idempotency_key": "n6-golden-scenario"})
    pkg = r.json()["package"]
    execution_package_id = pkg["executionPackageId"]
    assert pkg["planId"] == plan_id
    assert pkg["planChecksum"] == plan["planDigest"]
    assert pkg["designId"] == design_id
    assert pkg["designRevision"] == design_revision

    r = client.post(f"/api/v1/execution-packages/{execution_package_id}/preflight")
    preflight = r.json()
    assert preflight["status"] == "PREFLIGHT_PASSED"
    assert preflight["summary"]["BLOCK"] == 0 and preflight["summary"]["FAIL"] == 0

    # ── Execute -> Observe -> Validate -> Verify -> Evidence ──
    r = client.post(f"/api/v1/execution-packages/{execution_package_id}/execute")
    result = r.json()["result"]
    run_id = result["runId"]

    assert result["executorResult"] == "COMPLETED"
    assert result["observationResult"] == "OBSERVED"
    assert result["validationResult"] == "VALIDATED"
    assert result["verifierResult"] == "VERIFIED_SUCCESS"
    # No blocking drift (MISSING/CHANGED/UNKNOWN) — EXTRA is allowed (sibling
    # same-run resources are non-blocking by design).
    blocking = [d for d in result["driftFindings"] if d["classification"] in ("MISSING", "CHANGED", "UNKNOWN")]
    assert blocking == []

    evidence_package_id = result["evidencePackageId"]
    ep = result["evidencePackage"]
    assert ep["evidencePackageId"] == evidence_package_id
    assert ep["planId"] == plan_id
    assert ep["planDigest"] == plan["planDigest"]
    assert ep["designId"] == design_id
    assert ep["designRevision"] == design_revision
    assert ep["executionPackageId"] == execution_package_id
    assert ep["runId"] == run_id
    assert ep["verifierResult"] == "VERIFIED_SUCCESS"

    # ── Cleanup — exact ownership, independently verified ──
    cleanup = client.post(f"/api/v1/execution-runs/{run_id}/cleanup").json()
    assert cleanup["status"] == "COMPLETED"
    assert cleanup["failed"] == []

    common = dict(endpoint_url="http://localhost:4566", aws_access_key_id="test",
                  aws_secret_access_key="test", region_name="us-east-1")
    s3, elbv2, lam, logs = (boto3.client(s, **common) for s in ("s3", "elbv2", "lambda", "logs"))
    for name, remaining in (
        ("buckets", [b["Name"] for b in s3.list_buckets()["Buckets"] if b["Name"].startswith("infra-again-")]),
        ("loadBalancers", [l["LoadBalancerName"] for l in elbv2.describe_load_balancers()["LoadBalancers"] if l["LoadBalancerName"].startswith("ia-")]),
        ("functions", [f["FunctionName"] for f in lam.list_functions()["Functions"] if "infra-again" in f["FunctionName"].lower()]),
        ("logGroups", [g["logGroupName"] for g in logs.describe_log_groups()["logGroups"] if "infra-again" in g["logGroupName"].lower()]),
    ):
        assert remaining == [], f"leftover {name} after cleanup: {remaining}"
