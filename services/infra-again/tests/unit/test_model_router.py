"""M3 Hybrid Model Router Acceptance Tests.

Seven scenarios:
  1. Local PASS → no cloud
  2. Local correction PASS → no cloud
  3. Local FAIL → cloud escalation
  4. LOCAL_ONLY prevents cloud
  5. CLOUD_FIRST skips local
  6. Refine routes to cloud
  7. Cloud fail → BLOCKED

All tests use provider doubles — no real cloud credentials required.
"""

from __future__ import annotations

import os, sys, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from infra_again.intelligence.model_router import (
    HybridModelRouter, ExecutionPolicy, FinalResultMode, EscalationReason,
    PassingTestProvider, FailingTestProvider, TestProviderBase,
    LocalOllamaProvider, CloudProviderAdapter,
)


class PassThenFailProvider(TestProviderBase):
    """Provider that passes on first call, fails on second."""
    def __init__(self, name: str = "pass-then-fail"):
        super().__init__(name)
        self._first = True

    def generate_architecture(self, brief: str, provider_pref: str, platform_pref: str, req):
        self.call_count += 1
        if self._first:
            self._first = False
            # Delegate to passing provider
            p = PassingTestProvider(self._name)
            return p.generate_architecture(brief, provider_pref, platform_pref, req)
        return None, {"result": "FAIL"}

    def refine_architecture(self, nodes, edges, instruction, provider, base_req):
        self.call_count += 1
        if self._first:
            self._first = False
            p = PassingTestProvider(self._name)
            return p.refine_architecture(nodes, edges, instruction, provider, base_req)
        return None, {"result": "FAIL"}


class UnavailableProvider(TestProviderBase):
    def __init__(self, name: str = "unavailable"):
        super().__init__(name, available=False)


def _dummy_req():
    from infra_again.intelligence.againpilot import DetectedRequirement
    return DetectedRequirement(
        provider="AWS", platform="KUBERNETES", expected_load="MODERATE",
        availability=[], compliance=[], security=[], data_sensitivity=[],
    )


# ═══════════════════════════════════════════════════════════════════
# Scenario 1: Local PASS → no cloud
# ═══════════════════════════════════════════════════════════════════

def test_local_pass_no_cloud():
    """When local passes quality + completeness, cloud is never called."""
    local = PassingTestProvider("local-pass")
    cloud = FailingTestProvider("cloud-never-called")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        "3-tier web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None, "Should return a valid proposal"
    assert prov.final_result_mode == FinalResultMode.LOCAL_ACCEPTED.value
    assert not prov.escalated, "Must NOT escalate to cloud"
    assert cloud.call_count == 0, "Cloud provider must never be called"


# ═══════════════════════════════════════════════════════════════════
# Scenario 2: Local correction PASS → no cloud (simulated)
# ═══════════════════════════════════════════════════════════════════

def test_local_correction_pass_no_cloud():
    """When local passes (even after correction simulated), cloud not called."""
    local = PassingTestProvider("local-correction")
    cloud = TestProviderBase("cloud", available=True)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        "3-tier web app with HA on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None
    assert prov.final_result_mode == FinalResultMode.LOCAL_ACCEPTED.value
    assert not prov.escalated
    assert cloud.call_count == 0, "Cloud should not be called when local passes"


# ═══════════════════════════════════════════════════════════════════
# Scenario 3: Local FAIL → cloud escalation
# ═══════════════════════════════════════════════════════════════════

def test_local_fail_escalates_to_cloud():
    """When local fails, escalate to cloud under LOCAL_FIRST."""
    local = FailingTestProvider("local-fail")
    cloud = PassingTestProvider("cloud-pass")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        "microservices on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None, "Cloud should produce a valid proposal"
    assert prov.escalated, "Must escalate to cloud"
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value
    assert prov.escalation_reason != ""
    assert cloud.call_count == 1, "Cloud must be called exactly once"
    assert local.call_count == 1, "Local must be called exactly once"


# ═══════════════════════════════════════════════════════════════════
# Scenario 4: LOCAL_ONLY prevents cloud
# ═══════════════════════════════════════════════════════════════════

def test_local_only_prevents_cloud():
    """Under LOCAL_ONLY, local failure → BLOCKED, never calls cloud."""
    local = FailingTestProvider("local-fail")
    cloud = PassingTestProvider("cloud-must-not-be-called")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_ONLY)

    proposal, prov = router.route_generation(
        "web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None, "Must return None when blocked"
    assert prov.final_result_mode == FinalResultMode.BLOCKED.value
    assert not prov.escalated, "Must NOT escalate"
    assert cloud.call_count == 0, "Cloud must never be called under LOCAL_ONLY"


# ═══════════════════════════════════════════════════════════════════
# Scenario 5: CLOUD_FIRST skips local
# ═══════════════════════════════════════════════════════════════════

def test_cloud_first_skips_local():
    """Under CLOUD_FIRST, local is never called."""
    local = FailingTestProvider("local-should-not-be-called")
    cloud = PassingTestProvider("cloud-primary")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.CLOUD_FIRST)

    proposal, prov = router.route_generation(
        "complex ML pipeline on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None, "Cloud must produce valid proposal"
    assert prov.final_result_mode == FinalResultMode.CLOUD_DIRECT.value
    assert not prov.escalated, "CLOUD_FIRST is not escalation; it's the chosen policy"
    assert local.call_count == 0, "Local must never be called under CLOUD_FIRST"
    assert cloud.call_count == 1


# ═══════════════════════════════════════════════════════════════════
# Scenario 6: Refine routes to cloud (complex semantic)
# ═══════════════════════════════════════════════════════════════════

def test_complex_refine_routes_to_cloud():
    """Complex refines (ECS Fargate, topology) route to cloud under LOCAL_FIRST."""
    local = FailingTestProvider("local-should-be-skipped")
    cloud = PassingTestProvider("cloud-refine")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    result, prov = router.route_refine(
        nodes=[{"id": "app", "name": "App", "category": "APPLICATION", "provider": "AWS",
                "nativeService": "ecs", "platform": "KUBERNETES", "zone": "private",
                "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"}],
        edges=[],
        instruction="Change application runtime from ECS to ECS Fargate for serverless scaling",
        provider="AWS",
    )

    assert result is not None, "Cloud should handle complex refine"
    assert prov.escalated, "Must escalate complex refine to cloud"
    assert prov.escalation_reason == EscalationReason.REFINE_COMPLEX_SEMANTIC.value
    assert cloud.call_count == 1
    # Local should be skipped for complex semantic refines
    assert local.call_count == 0, "Local should be skipped for complex refine"


# ═══════════════════════════════════════════════════════════════════
# Scenario 7: Cloud fail → BLOCKED
# ═══════════════════════════════════════════════════════════════════

def test_cloud_fail_blocked():
    """When both local and cloud fail, result is BLOCKED (not silent fallback)."""
    local = FailingTestProvider("local-fail")
    cloud = FailingTestProvider("cloud-fail")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        "web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None, "Must return None when both fail"
    assert prov.final_result_mode == FinalResultMode.NEEDS_USER_REVIEW.value
    assert prov.escalated, "Must have tried escalation"
    assert local.call_count == 1
    assert cloud.call_count == 1, "Cloud must have been attempted"


# ═══════════════════════════════════════════════════════════════════
# Additional edge cases
# ═══════════════════════════════════════════════════════════════════

def test_local_unavailable_escalates():
    """When local is unavailable, escalate to cloud."""
    local = UnavailableProvider("unavailable")
    cloud = PassingTestProvider("cloud")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        "web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None
    assert prov.escalated
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value
    assert prov.escalation_reason == EscalationReason.LOCAL_MODEL_UNAVAILABLE.value


def test_local_unavailable_local_only_blocks():
    """LOCAL_ONLY + unavailable local → BLOCKED."""
    local = UnavailableProvider("unavailable")
    cloud = PassingTestProvider("cloud")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_ONLY)

    proposal, prov = router.route_generation(
        "web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None
    assert prov.final_result_mode == FinalResultMode.BLOCKED.value
    assert cloud.call_count == 0


def test_cloud_unavailable_under_cloud_first():
    """CLOUD_FIRST + unavailable cloud → BLOCKED, no local fallback."""
    local = PassingTestProvider("local")
    cloud = UnavailableProvider("cloud-unavailable")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.CLOUD_FIRST)

    proposal, prov = router.route_generation(
        "web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None
    assert prov.final_result_mode == FinalResultMode.BLOCKED.value
    assert prov.escalation_reason == EscalationReason.CLOUD_UNAVAILABLE.value
    assert local.call_count == 0, "No silent local fallback from CLOUD_FIRST"


def test_provenance_completeness():
    """Verify provenance dict has all required fields."""
    local = PassingTestProvider("local")
    cloud = TestProviderBase("cloud", available=True)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        "web app on AWS", "AWS", "KUBERNETES", _dummy_req(),
    )

    d = prov.to_dict()
    required = ["requestPolicy", "requestType", "localModel", "localResult",
                "localLatencyMs", "escalated", "escalationReason",
                "cloudProvider", "cloudResult", "finalResultMode", "briefHash"]
    for key in required:
        assert key in d, f"Provenance must include '{key}'"


def test_againpilot_router_integration():
    """Verify AgainPilotProviderRouter delegates to hybrid router when cloud configured."""
    from infra_again.intelligence.againpilot import AgainPilotProviderRouter, AgainPilotRequest
    from infra_again.intelligence.againpilot import ProviderPreference, PlatformPreference

    # Without cloud key → should use original path
    old_key = os.environ.pop("AGAINPILOT_CLOUD_API_KEY", None)
    old_openai = os.environ.pop("OPENAI_API_KEY", None)
    old_mode = os.environ.pop("AGAINPILOT_ROUTER_MODE", None)
    try:
        router = AgainPilotProviderRouter()
        hr = router._get_hybrid_router()
        assert hr is None, "Without CLOUD_API_KEY or OPENAI_API_KEY, no hybrid router"
    finally:
        if old_key: os.environ["AGAINPILOT_CLOUD_API_KEY"] = old_key
        if old_openai: os.environ["OPENAI_API_KEY"] = old_openai
        if old_mode: os.environ["AGAINPILOT_ROUTER_MODE"] = old_mode


def test_policy_from_env():
    """Verify policy is read from environment."""
    os.environ["AGAINPILOT_ROUTING_POLICY"] = "LOCAL_ONLY"
    os.environ["AGAINPILOT_CLOUD_API_KEY"] = "test-key"
    try:
        from infra_again.intelligence.againpilot import AgainPilotProviderRouter
        router = AgainPilotProviderRouter()
        assert router._policy == "LOCAL_ONLY"
    finally:
        del os.environ["AGAINPILOT_ROUTING_POLICY"]
        del os.environ["AGAINPILOT_CLOUD_API_KEY"]


def test_complex_refine_detection():
    """Verify complex refine heuristic."""
    from infra_again.intelligence.model_router import _is_complex_refine

    assert _is_complex_refine("Change runtime to ECS Fargate")
    assert _is_complex_refine("Add Redis cache layer")
    assert _is_complex_refine("Add WAF for security")
    assert not _is_complex_refine("Rename node NODE-APP-001 to web-server")
    assert not _is_complex_refine("Add a tag to the app node")
