"""AGAINPILOT API contract + fallback-safety tests — API_INTEGRATION.

Exercises the actual registered FastAPI routes via TestClient against the
real app (infra_again.api.app), the same pattern used by the existing
TestControlAPI tests in tests/integration/test_phase3.py. These are HTTP
request/response contract tests, not browser tests — they prove the backend
behaves correctly; they do not prove the React panel renders correctly (that
would require BROWSER_E2E, see the review report for what could not be run
in this environment).

Real-AI failure/success paths are monkeypatched at the module-function level
(_generate_real_ai / _generate_real_refine) rather than depending on a live
Ollama model, so this suite is deterministic and fast (~1s) regardless of
whether Ollama happens to be running. The one thing that DOES need a live
model — proving the actual qwen2.5:7b output currently fails completeness on
the golden brief — is documented separately with a captured transcript
rather than asserted here, since it is nondeterministic and slow.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from infra_again.api import app
import infra_again.intelligence.againpilot as againpilot_module
from infra_again.intelligence.againpilot import get_againpilot, generate_architecture, AgainPilotRequest, ProviderPreference

client = TestClient(app)

GOLDEN_BODY = {
    "brief": "Build a patient portal on AWS for 10,000 users/day. Use private database "
              "access, containerized workloads, high availability and PDPA-aligned security.",
    "providerPreference": "AWS", "platformPreference": "KUBERNETES", "generationDepth": "DETAILED",
}


@pytest.fixture(autouse=True)
def _restore_router_state():
    router = get_againpilot()
    original_ollama = router._ollama
    yield
    router._ollama = original_ollama


def test_status_endpoint_shape():
    resp = client.get("/api/v1/againpilot/status")
    assert resp.status_code == 200
    body = resp.json()
    assert set(["mode", "provider", "model", "available"]).issubset(body.keys())


def test_generate_deterministic_when_real_ai_never_available():
    router = get_againpilot()
    router._ollama = False
    resp = client.post("/api/v1/againpilot/generate", json=GOLDEN_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("needsFallbackConsent") is None
    assert body["resultMode"] == "DETERMINISTIC_FALLBACK"
    assert body["proposal"]["nodes"]
    assert body["completeness"]["overall"] in ("PASS", "WARN")
    assert body["quality"]["overall"] in ("PASS", "WARN")


def test_generate_real_ai_failure_returns_consent_prompt_not_silent_fallback(monkeypatch):
    """The central fallback-safety property: when real AI is available but
    fails, the response must ask for consent — it must NOT contain a
    proposal, and must NOT silently be a deterministic result."""
    router = get_againpilot()
    router._ollama = True

    def fake_fail(*a, **kw):
        return None, {
            "mode": "REAL_LLM", "provider": "LOCAL_LLM", "model": "qwen2.5:7b",
            "stage1Ms": 100, "stage2Ms": 200, "correctionMs": 0, "result": "QUALITY_FAIL",
            "qualityResult": "FAIL", "completenessResult": "FAIL", "missingRoles": ["OBSERVABILITY"],
            "briefHash": "abc123", "generationTimestamp": "2026-01-01T00:00:00Z",
        }
    monkeypatch.setattr(againpilot_module, "_generate_real_ai", fake_fail)

    resp = client.post("/api/v1/againpilot/generate", json=GOLDEN_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["needsFallbackConsent"] is True
    assert "proposal" not in body
    assert body["resultMode"] == "QUALITY_FAIL"
    assert body["provenance"]["completenessResult"] == "FAIL"


def test_generate_force_deterministic_never_calls_real_ai(monkeypatch):
    """Clicking 'Use Deterministic Fallback' must not attempt real AI again."""
    router = get_againpilot()
    router._ollama = True

    def must_not_be_called(*a, **kw):
        raise AssertionError("_generate_real_ai must not be called when forceMode=DETERMINISTIC_FALLBACK")
    monkeypatch.setattr(againpilot_module, "_generate_real_ai", must_not_be_called)

    resp = client.post("/api/v1/againpilot/generate", json={**GOLDEN_BODY, "forceMode": "DETERMINISTIC_FALLBACK"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["resultMode"] == "DETERMINISTIC_FALLBACK"
    assert body["provenance"]["userConsented"] is True
    assert body["proposal"]["nodes"]


def test_generate_real_ai_success_reports_completeness_and_provenance(monkeypatch):
    router = get_againpilot()
    router._ollama = True

    good_proposal = generate_architecture(AgainPilotRequest(
        brief=GOLDEN_BODY["brief"], provider_preference=ProviderPreference.AWS,
    ))

    def fake_success(*a, **kw):
        return good_proposal, {
            "mode": "REAL_LLM", "provider": "LOCAL_LLM", "model": "qwen2.5:7b",
            "stage1Ms": 500, "stage2Ms": 900, "correctionMs": 0, "result": "REAL_LLM",
            "qualityResult": "PASS", "completenessResult": "PASS",
            "firstPassGenerator": "REAL_LLM", "correctionGenerator": None,
            "briefHash": "abc123", "generationTimestamp": "2026-01-01T00:00:00Z",
        }
    monkeypatch.setattr(againpilot_module, "_generate_real_ai", fake_success)

    resp = client.post("/api/v1/againpilot/generate", json=GOLDEN_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["resultMode"] == "REAL_LLM"
    prov = body["provenance"]
    for field in ("generationRequestedMode", "generationResultMode", "generationProvider", "generationModel",
                  "firstPassGenerator", "correctionGenerator", "stage1LatencyMs", "stage2LatencyMs",
                  "correctionLatencyMs", "briefHash", "generationTimestamp"):
        assert field in prov, f"missing canonical provenance field: {field}"
    assert body["completeness"]["overall"] == "PASS"


def test_refine_real_ai_failure_returns_consent_prompt(monkeypatch):
    router = get_againpilot()
    router._ollama = True

    def fake_fail(*a, **kw):
        return None, {"mode": "REAL_LLM", "provider": "LOCAL_LLM", "model": "qwen2.5:7b",
                       "result": "REFINE_TIMEOUT", "stage1Ms": 0, "stage2Ms": 0, "correctionMs": 0,
                       "briefHash": "x", "generationTimestamp": "2026-01-01T00:00:00Z"}
    monkeypatch.setattr(againpilot_module, "_generate_real_refine", fake_fail)

    resp = client.post("/api/v1/againpilot/refine", json={
        "instruction": "Use ECS Fargate for the application tier and ensure the database has no public route.",
        "nodes": [], "edges": [], "provider": "AWS",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["needsFallbackConsent"] is True
    assert "proposal" not in body


def test_refine_deterministic_private_db_instruction_actually_applies(monkeypatch):
    """Regression test for a bug found during this review: the deterministic
    refine path matched a 'no public route' / 'private database' instruction
    but its handler body was a bare `pass` — the instruction was silently
    discarded and the returned architecture never changed. It also recorded
    REPLACE_SERVICE / subnet-separation changes in the delta without ever
    applying them to the returned nodes. Both are fixed; this proves it."""
    router = get_againpilot()
    router._ollama = False  # force the deterministic path deterministically

    nodes = [
        {"nodeId": "N-DB", "name": "Database", "category": "DATABASE", "provider": "AWS",
         "nativeService": "rds", "platform": "NATIVE_VM", "securityZone": "public",
         "dataClassification": "internal", "owner": "", "source": "AI_GENERATED",
         "verificationState": "UNVERIFIED", "properties": {}, "serviceVerification": "SUPPORTED"},
    ]
    resp = client.post("/api/v1/againpilot/refine", json={
        "instruction": "Ensure the database has no public route.",
        "nodes": nodes, "edges": [], "provider": "AWS",
    })
    assert resp.status_code == 200
    body = resp.json()
    refined_db = next(n for n in body["proposal"]["nodes"] if n["nodeId"] == "N-DB")
    assert refined_db["securityZone"] == "private", "instruction was matched but not applied"
    changed = body["delta"]["changedNodes"]
    assert any(c.get("nodeId") == "N-DB" and c.get("field") == "securityZone" for c in changed)


def test_frozen_design_cannot_be_silently_regenerated():
    """Regression test for a bug found during this review: /generate and the
    legacy /ai-generate endpoints had no design-status guard at all, so an
    ACCEPTED/BASELINE_FROZEN design could be silently overwritten. update-flow
    already guarded this; /generate and /ai-generate did not."""
    create = client.post("/api/v1/designs", params={"name": "frozen-guard-test"})
    assert create.status_code == 200
    design_id = create.json()["design"]["designId"]

    accept = client.post(f"/api/v1/designs/{design_id}/accept")
    assert accept.status_code == 200
    assert accept.json()["design"]["status"] == "BASELINE_FROZEN"

    regen = client.post(f"/api/v1/designs/{design_id}/generate")
    assert regen.status_code == 400

    ai_regen = client.post(f"/api/v1/designs/{design_id}/ai-generate", json={"brief": {}})
    assert ai_regen.status_code == 400


def test_design_ids_are_not_a_predictable_counter():
    """Regression test for a design-id race: ids used to be
    f'DESIGN-{len(_designs)+1:06d}', which two concurrent creates can compute
    identically, and _persist_design uses INSERT OR REPLACE — a silent
    overwrite rather than an error. Ids are now uuid4-based."""
    ids = []
    for _ in range(3):
        r = client.post("/api/v1/designs", params={"name": "id-uniqueness-test"})
        assert r.status_code == 200
        ids.append(r.json()["design"]["designId"])
    assert len(set(ids)) == len(ids)
    assert not any(i.endswith("-000001") or i.endswith("-000002") for i in ids)
