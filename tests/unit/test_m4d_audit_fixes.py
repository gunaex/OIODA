"""M4-D.1 — Regression tests for the three audited defects.

1. AgainPilotProviderRouter's hybrid-router gate was `hr is not None and
   self._ollama` — self._ollama is a STARTUP-TIME snapshot of local Ollama
   availability, so CLOUD_FIRST (whose entire purpose is to route around
   local) was unreachable whenever Ollama happened to be down at process
   start. Fixed to gate on `hr is not None` only; the router itself does a
   live per-request local-availability check and already knows how to
   handle "local down" per policy.

2. _apply_refine_delta hardcoded generation_provider="LOCAL_LLM" and
   generation_model=OLLAMA_MODEL regardless of which provider (local,
   DeepSeek, OpenAI) actually produced the delta. Fixed by having callers
   pass authoritative generation_provider/generation_model. This also
   uncovered and fixed a pre-existing, independent bug: the OpenAI provider
   called _apply_refine_delta with the wrong argument shape (`provider`
   bound positionally to the `req` parameter, plus a `base_req=` keyword
   that doesn't exist), which meant OpenAI refine ALWAYS raised inside its
   own try/except and silently reported CLOUD_DELTA_APPLY_FAILED — it had
   never worked.

These tests use provider doubles throughout — no live network calls, no
API keys required.
"""

from __future__ import annotations

import json

import pytest

from infra_again.intelligence.againpilot import (
    AgainPilotRequest, DetectedRequirement, ProviderPreference, PlatformPreference,
    RealAIGenerationFailed, get_againpilot, _apply_refine_delta,
)
from infra_again.intelligence.model_router import (
    HybridModelRouter, ExecutionPolicy, ModelRole,
    PassingTestProvider, TestProviderBase,
)


GOLDEN_BRIEF = (
    "Build a patient portal on AWS for 10,000 users/day. Use private database "
    "access, containerized workloads, high availability and PDPA-aligned security."
)


@pytest.fixture
def router():
    r = get_againpilot()
    saved = (r._ollama, r._hybrid_router, r._policy, r._last_provenance, r._last_result_mode, r._last_routing_provenance)
    yield r
    r._ollama, r._hybrid_router, r._policy, r._last_provenance, r._last_result_mode, r._last_routing_provenance = saved


def _unavailable_local(name: str = "local-down") -> TestProviderBase:
    return TestProviderBase(name, role=ModelRole.LOCAL_ARCHITECT, available=False)


# ═══════════════════════════════════════════════════════════════════
# Fix 1 — CLOUD_FIRST / LOCAL_FIRST / LOCAL_ONLY with Ollama down
# ═══════════════════════════════════════════════════════════════════

def test_cloud_first_with_ollama_down(router):
    """CLOUD_FIRST must reach the cloud provider even when self._ollama is
    False (the old bug: the wrapper-level gate skipped the hybrid router
    entirely whenever Ollama was down, regardless of policy)."""
    local = _unavailable_local()
    cloud = PassingTestProvider("cloud-expert", role=ModelRole.CLOUD_EXPERT)
    router._ollama = False
    router._hybrid_router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.CLOUD_FIRST)
    router._policy = "CLOUD_FIRST"

    request = AgainPilotRequest(brief=GOLDEN_BRIEF, provider_preference=ProviderPreference.AWS, platform_preference=PlatformPreference.KUBERNETES)
    proposal = router.generate(request)

    assert proposal is not None
    assert cloud.call_count == 1
    assert local.call_count == 0, "CLOUD_FIRST must not touch local at all"
    assert router.last_result_mode in ("CLOUD_DIRECT", "CLOUD_ESCALATED")


def test_local_first_with_ollama_down_escalates(router):
    """LOCAL_FIRST with local unavailable must escalate to cloud, not fall
    through to the deterministic generator."""
    local = _unavailable_local()
    cloud = PassingTestProvider("cloud-expert", role=ModelRole.CLOUD_EXPERT)
    router._ollama = False
    router._hybrid_router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)
    router._policy = "LOCAL_FIRST"

    request = AgainPilotRequest(brief=GOLDEN_BRIEF, provider_preference=ProviderPreference.AWS, platform_preference=PlatformPreference.KUBERNETES)
    proposal = router.generate(request)

    assert proposal is not None
    assert proposal.generation_provider == "TEST"  # PassingTestProvider marks its own output
    assert cloud.call_count == 1
    assert router.last_provenance.get("escalated") is True
    assert router.last_provenance.get("escalationReason") == "LOCAL_MODEL_UNAVAILABLE"


def test_local_only_with_ollama_down_no_cloud(router):
    """LOCAL_ONLY with local unavailable must BLOCK — no cloud call, no
    silent deterministic substitution."""
    local = _unavailable_local()
    cloud = PassingTestProvider("cloud-must-not-be-called", role=ModelRole.CLOUD_EXPERT)
    router._ollama = False
    router._hybrid_router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_ONLY)
    router._policy = "LOCAL_ONLY"

    request = AgainPilotRequest(brief=GOLDEN_BRIEF, provider_preference=ProviderPreference.AWS, platform_preference=PlatformPreference.KUBERNETES)
    with pytest.raises(RealAIGenerationFailed) as exc_info:
        router.generate(request)

    assert cloud.call_count == 0, "LOCAL_ONLY must never call cloud"
    assert exc_info.value.provenance.get("finalResultMode") == "BLOCKED"


def test_local_first_refine_with_ollama_down_escalates(router):
    """Same fix, refine path."""
    local = _unavailable_local()
    cloud = PassingTestProvider("cloud-expert-refine", role=ModelRole.CLOUD_EXPERT)
    router._ollama = False
    router._hybrid_router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)
    router._policy = "LOCAL_FIRST"

    proposal, delta = router.refine([], [], "Use ECS Fargate for the application tier", "AWS")
    assert proposal is not None
    assert cloud.call_count == 1


# ═══════════════════════════════════════════════════════════════════
# Fix 2 — refine provenance is caller-authoritative, not inferred
# ═══════════════════════════════════════════════════════════════════

_ONE_NODE = [{
    "nodeId": "app", "name": "App", "category": "APPLICATION", "provider": "AWS",
    "nativeService": "ecs", "platform": "KUBERNETES", "securityZone": "private",
    "dataClassification": "internal", "owner": "", "source": "AI_GENERATED",
    "verificationState": "UNVERIFIED", "properties": {}, "serviceVerification": "SUPPORTED",
}]
_REQ = DetectedRequirement(provider="AWS", platform="KUBERNETES", expected_load="M",
                            availability=["HIGH_AVAILABILITY"], compliance=["PDPA"],
                            security=["PRIVATE_DATABASE"], data_sensitivity=["PERSONAL_DATA"])


def _full_fixture():
    """A complete architecture (via the same PassingTestProvider fixture the
    M3/M4 test suites already use) so refine's post-change quality/
    completeness re-check has something that can actually PASS — a lone
    orphan node would correctly fail NO_ORPHAN_NODES regardless of this
    fix, which would test the wrong thing."""
    proposal, _ = PassingTestProvider().generate_architecture("x", "AWS", "KUBERNETES", _REQ)
    return [n.to_dict() for n in proposal.nodes], [e.to_dict() for e in proposal.edges]


def test_local_refine_provenance():
    nodes, edges = _full_fixture()
    proposal, _ = _apply_refine_delta(nodes, edges, {"changedNodes": [{"id": "app", "svc": "ecs_fargate"}]}, _REQ, "AWS", "x")
    assert proposal.generation_provider == "LOCAL_LLM"
    assert proposal.generation_model  # non-empty, reflects actual configured local model


def test_deepseek_refine_provenance():
    """DeepSeek refine (mocked HTTP layer, no network/key) must label the
    resulting proposal as DEEPSEEK with the actual configured model, not
    LOCAL_LLM/OLLAMA_MODEL."""
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider
    nodes, edges = _full_fixture()
    p = DeepSeekArchitectureProvider(model="deepseek-v4-pro", api_key="test-key-not-real")
    p._chat = lambda *a, **kw: (json.dumps({"changedNodes": [{"id": "app", "svc": "ecs_fargate"}]}), None)

    result, meta = p.refine_architecture(nodes, edges, "Use ECS Fargate", "AWS", _REQ)
    assert result is not None, meta
    proposal, delta = result
    assert proposal.generation_provider == "DEEPSEEK"
    assert proposal.generation_model == "deepseek-v4-pro"
    assert delta.changed_nodes  # non-empty delta


def test_openai_refine_provenance():
    """OpenAI refine (mocked HTTP layer) must label the resulting proposal
    as OPENAI with the actual configured model. This also regression-tests
    a previously-undetected bug: the OpenAI provider called
    _apply_refine_delta with mismatched arguments (provider bound
    positionally to the req parameter, plus a nonexistent base_req=
    keyword), which meant OpenAI refine always raised internally and
    silently reported CLOUD_DELTA_APPLY_FAILED — it had never worked."""
    from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider
    nodes, edges = _full_fixture()
    p = OpenAIArchitectureProvider(model="gpt-4o", api_key="test-key-not-real")
    p._chat = lambda *a, **kw: (json.dumps({"changedNodes": [{"id": "app", "svc": "ecs_fargate"}]}), None)

    result, meta = p.refine_architecture(nodes, edges, "Use ECS Fargate", "AWS", _REQ)
    assert result is not None, meta
    assert meta["result"] != "CLOUD_DELTA_APPLY_FAILED"
    proposal, delta = result
    assert proposal.generation_provider == "OPENAI"
    assert proposal.generation_model == "gpt-4o"
    assert delta.changed_nodes


# ═══════════════════════════════════════════════════════════════════
# Fix 4 — API contract: hybrid-router provenance must actually surface
# ═══════════════════════════════════════════════════════════════════
#
# _provenance_dict() in againpilot_api.py previously only understood the
# single-provider shape (mode/result/provider/model/stage1Ms/...).
# RoutingProvenance.to_dict() (what the hybrid router produces) is a
# disjoint field set (requestPolicy/localModel/cloudProvider/finalResultMode/
# ...), so every hybrid-routed response — including every real DeepSeek/
# OpenAI call — surfaced an all-empty/default provenance block to API
# callers despite the router having captured everything correctly
# internally. This is what the frontend's new Execution Path UI reads.

def test_api_surfaces_hybrid_provenance_fields(router):
    from fastapi.testclient import TestClient
    from infra_again.api import app

    local = TestProviderBase("llama3.1:8b", role=ModelRole.LOCAL_ARCHITECT, available=False)
    cloud = PassingTestProvider("deepseek-v4-pro", role=ModelRole.CLOUD_EXPERT)
    router._ollama = False
    router._hybrid_router = HybridModelRouter(local_architect=local, cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)
    router._policy = "LOCAL_FIRST"

    client = TestClient(app)
    resp = client.post("/api/v1/againpilot/generate", json={
        "brief": GOLDEN_BRIEF, "providerPreference": "AWS", "platformPreference": "KUBERNETES",
    })
    assert resp.status_code == 200
    body = resp.json()
    prov = body["provenance"]

    assert prov["requestPolicy"] == "LOCAL_FIRST"
    assert prov["escalated"] is True
    assert prov["escalationReason"] == "LOCAL_MODEL_UNAVAILABLE"
    assert prov["cloudProvider"] == "TEST"  # PassingTestProvider's provider_name
    assert prov["cloudModel"] == "deepseek-v4-pro"
    assert prov["finalResultMode"] == "CLOUD_ESCALATED"
    # Derived canonical fields must reflect the ACTUAL generator (cloud, since
    # local was unavailable and it escalated) — not be left empty/default.
    assert prov["generationProvider"] == "TEST"
    assert prov["generationModel"] == "deepseek-v4-pro"
    assert prov["generationResultMode"] == "CLOUD_ESCALATED"
    # No raw model text / reasoning content anywhere in the response.
    body_text = json.dumps(body)
    assert "reasoning_content" not in body_text
