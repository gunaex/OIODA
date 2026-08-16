"""M4-D.3 — Quality/completeness failure observability for cloud refine.

Before this change, a cloud refine that failed quality/completeness
validation returned only a bare result code (e.g. "CLOUD_QUALITY_FAIL")
with no detail on WHICH gate failed or why — reproduced live against a
real DeepSeek response during M4-D.2 acceptance, where the only visible
diagnostic was `cloudResult=CLOUD_QUALITY_FAIL` with no further detail.

These tests prove the failure detail (gate/result/detail — deterministic
validator output only, never model text) now survives:
  DeepSeek/OpenAI provider -> HybridModelRouter -> RoutingProvenance -> API.

No live network calls, no API keys required — provider doubles and a
mocked DeepSeek _chat() only.
"""

from __future__ import annotations

import json

import pytest

from infra_again.intelligence.againpilot import DetectedRequirement
from infra_again.intelligence.model_router import (
    HybridModelRouter, ExecutionPolicy, ModelRole, PassingTestProvider, TestProviderBase,
)


_REQ = DetectedRequirement(provider="AWS", platform="KUBERNETES", expected_load="M",
                            availability=["HIGH_AVAILABILITY"], compliance=["PDPA"],
                            security=["PRIVATE_DATABASE"], data_sensitivity=["PERSONAL_DATA"])


def _full_fixture():
    proposal, _ = PassingTestProvider().generate_architecture("x", "AWS", "KUBERNETES", _REQ)
    return [n.to_dict() for n in proposal.nodes], [e.to_dict() for e in proposal.edges]


# ═══════════════════════════════════════════════════════════════════
# 1. Provider-level: DeepSeek surfaces qualityFailures on rejection
# ═══════════════════════════════════════════════════════════════════

def test_deepseek_quality_failure_details_surfaced():
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider
    nodes, edges = _full_fixture()

    # A delta that adds a node with no edges referencing it — a reliable,
    # deterministic NO_ORPHAN_NODES quality failure.
    delta = {"addedNodes": [{"id": "orphan-1", "role": "APPLICATION", "svc": "ecs", "zone": "private"}]}
    p = DeepSeekArchitectureProvider(model="deepseek-v4-pro", api_key="test-key-not-real")
    p._chat = lambda *a, **kw: (json.dumps(delta), None)

    result, meta = p.refine_architecture(nodes, edges, "Add an orphan node", "AWS", _REQ)

    assert result is None
    assert meta["result"] == "CLOUD_QUALITY_FAIL"
    assert meta["qualityResult"] == "FAIL"
    assert "qualityFailures" in meta
    assert isinstance(meta["qualityFailures"], list) and len(meta["qualityFailures"]) >= 1
    for f in meta["qualityFailures"]:
        assert set(f.keys()) == {"gate", "result", "detail"}
        assert f["result"] == "FAIL"
    gates = {f["gate"] for f in meta["qualityFailures"]}
    assert "NO_ORPHAN_NODES" in gates


def test_quality_failures_not_secret_and_no_reasoning_content():
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider
    nodes, edges = _full_fixture()
    delta = {"addedNodes": [{"id": "orphan-2", "role": "APPLICATION", "svc": "ecs", "zone": "private"}]}
    p = DeepSeekArchitectureProvider(model="deepseek-v4-pro", api_key="test-key-not-real")
    # Simulate a reasoning-model response shape (reasoning_content present) —
    # _chat() already only ever returns extracted `content` text, never the
    # raw provider payload, so meta must not contain it either.
    p._chat = lambda *a, **kw: (json.dumps(delta), None)

    _, meta = p.refine_architecture(nodes, edges, "Add an orphan node", "AWS", _REQ)

    blob = json.dumps(meta)
    assert "reasoning_content" not in blob
    assert "test-key-not-real" not in blob  # the api key must never appear
    assert "Authorization" not in blob


# ═══════════════════════════════════════════════════════════════════
# 2. Router-level: propagates into RoutingProvenance
# ═══════════════════════════════════════════════════════════════════

class QualityFailingCloudDouble(TestProviderBase):
    """Cloud test double that fails with structured quality detail, the
    same meta shape the real DeepSeek/OpenAI providers now produce."""
    def __init__(self):
        super().__init__("deepseek-v4-pro", role=ModelRole.CLOUD_EXPERT)

    def refine_architecture(self, nodes, edges, instruction, provider, base_req):
        self.call_count += 1
        return None, {
            "result": "CLOUD_QUALITY_FAIL", "provider": "DEEPSEEK", "model": "deepseek-v4-pro",
            "qualityResult": "FAIL",
            "qualityFailures": [{"gate": "NO_ORPHAN_NODES", "result": "FAIL", "detail": "Orphaned: ['orphan-1']"}],
        }


def test_router_propagates_quality_failures_from_cloud_provider():
    local = TestProviderBase("local-fail", role=ModelRole.LOCAL_ARCHITECT, available=False)
    cloud = QualityFailingCloudDouble()
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)

    result, prov = router.route_refine(
        nodes=[], edges=[], instruction="Use ECS Fargate for the application tier", provider="AWS", base_req=_REQ,
    )

    assert result is None
    assert prov.final_result_mode == "NEEDS_USER_REVIEW"
    d = prov.to_dict()
    assert d["qualityFailures"] == [{"gate": "NO_ORPHAN_NODES", "result": "FAIL", "detail": "Orphaned: ['orphan-1']"}]


# ═══════════════════════════════════════════════════════════════════
# 3. API contract: qualityFailures reaches the HTTP response
# ═══════════════════════════════════════════════════════════════════

def test_api_surfaces_quality_failures_on_refine_rejection():
    from fastapi.testclient import TestClient
    from infra_again.api import app
    from infra_again.intelligence.againpilot import get_againpilot

    router = get_againpilot()
    saved = (router._ollama, router._hybrid_router, router._policy)
    try:
        local = TestProviderBase("local-fail", role=ModelRole.LOCAL_ARCHITECT, available=False)
        cloud = QualityFailingCloudDouble()
        router._ollama = False
        router._hybrid_router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)
        router._policy = "LOCAL_FIRST"

        client = TestClient(app)
        resp = client.post("/api/v1/againpilot/refine", json={
            "instruction": "Use ECS Fargate for the application tier and ensure the database has no public route.",
            "nodes": [], "edges": [], "provider": "AWS",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["needsFallbackConsent"] is True
        prov = body["provenance"]
        assert prov["qualityFailures"] == [{"gate": "NO_ORPHAN_NODES", "result": "FAIL", "detail": "Orphaned: ['orphan-1']"}]

        body_text = json.dumps(body)
        assert "reasoning_content" not in body_text
        assert "Authorization" not in body_text
    finally:
        router._ollama, router._hybrid_router, router._policy = saved
