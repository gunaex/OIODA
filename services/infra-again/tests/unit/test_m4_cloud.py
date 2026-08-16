"""M4 — REAL CLOUD EXPERT ACCEPTANCE: OPENAI FIRST

Tests M4.1–M4.10 for the OpenAI cloud provider integration.

Tests that require a real OPENAI_API_KEY are automatically skipped.
Tests that use provider doubles run in all environments.
"""

from __future__ import annotations

import os, sys, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

_OPENAI_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("AGAINPILOT_CLOUD_API_KEY")
_requires_openai = pytest.mark.skipif(
    not _OPENAI_KEY,
    reason="OPENAI_API_KEY not set (set it for REAL cloud acceptance tests)",
)

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

PATIENT_PORTAL_BRIEF = (
    "Build a patient portal on AWS for 10000 users/day. "
    "The database must be private. Use containers. "
    "High availability. Include PDPA privacy."
)

PATIENT_PORTAL_NODES = [
    {"nodeId": "user", "name": "User", "category": "USER", "provider": "AWS",
     "nativeService": "", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "dns", "name": "Route53", "category": "DNS", "provider": "AWS",
     "nativeService": "route53", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "cdn", "name": "CloudFront", "category": "CDN", "provider": "AWS",
     "nativeService": "cloudfront", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "waf", "name": "WAF", "category": "WAF", "provider": "AWS",
     "nativeService": "waf", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "lb", "name": "ALB", "category": "NETWORK", "provider": "AWS",
     "nativeService": "alb", "platform": "KUBERNETES", "securityZone": "private",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "app", "name": "App AZ-A", "category": "APPLICATION", "provider": "AWS",
     "nativeService": "ecs", "platform": "KUBERNETES", "securityZone": "private",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "app-b", "name": "App AZ-B", "category": "APPLICATION", "provider": "AWS",
     "nativeService": "ecs", "platform": "KUBERNETES", "securityZone": "private",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "db", "name": "DB AZ-A", "category": "DATABASE", "provider": "AWS",
     "nativeService": "rds", "platform": "KUBERNETES", "securityZone": "private-data",
     "dataClass": "pii", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "db-b", "name": "DB AZ-B", "category": "DATABASE", "provider": "AWS",
     "nativeService": "rds", "platform": "KUBERNETES", "securityZone": "private-data",
     "dataClass": "pii", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "kms", "name": "KMS", "category": "SECURITY", "provider": "AWS",
     "nativeService": "kms", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "secrets", "name": "Secrets", "category": "SECURITY", "provider": "AWS",
     "nativeService": "secrets_manager", "platform": "KUBERNETES", "securityZone": "private",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "identity", "name": "Cognito", "category": "IDENTITY", "provider": "AWS",
     "nativeService": "cognito", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
    {"nodeId": "obs", "name": "CloudWatch", "category": "OBSERVABILITY", "provider": "AWS",
     "nativeService": "cloudwatch", "platform": "KUBERNETES", "securityZone": "public",
     "dataClass": "internal", "notes": "", "source": "AI_GENERATED", "trust": "UNVERIFIED"},
]

PATIENT_PORTAL_EDGES = [
    {"edgeId": "e1", "sourceNodeId": "user", "targetNodeId": "dns", "type": "request",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "User"},
    {"edgeId": "e2", "sourceNodeId": "dns", "targetNodeId": "cdn", "type": "request",
     "protocol": "DNS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "DNS"},
    {"edgeId": "e3", "sourceNodeId": "cdn", "targetNodeId": "waf", "type": "request",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "CDN"},
    {"edgeId": "e4", "sourceNodeId": "waf", "targetNodeId": "lb", "type": "request",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "WAF"},
    {"edgeId": "e5", "sourceNodeId": "lb", "targetNodeId": "app", "type": "request",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "LB"},
    {"edgeId": "e5b", "sourceNodeId": "lb", "targetNodeId": "app-b", "type": "request",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "LB"},
    {"edgeId": "e6", "sourceNodeId": "app", "targetNodeId": "db", "type": "data",
     "protocol": "TLS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "DB"},
    {"edgeId": "e6b", "sourceNodeId": "app-b", "targetNodeId": "db-b", "type": "data",
     "protocol": "TLS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "DB"},
]


def _dummy_req():
    from infra_again.intelligence.againpilot import DetectedRequirement
    return DetectedRequirement(
        provider="AWS", platform="KUBERNETES", expected_load="MODERATE",
        availability=["HIGH_AVAILABILITY"], compliance=["PDPA"],
        security=["PRIVATE_DATABASE", "ENCRYPTION_REQUIRED"],
        data_sensitivity=["PERSONAL_DATA"],
    )


# ═══════════════════════════════════════════════════════════════════
# M4.1 — Provider Adapter: OpenAI Provider instantiation
# ═══════════════════════════════════════════════════════════════════

def test_openai_provider_instantiation():
    """OpenAI provider can be constructed with or without API key."""
    from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider

    # Without key — should not be available
    old_key = os.environ.pop("OPENAI_API_KEY", None)
    old_legacy = os.environ.pop("AGAINPILOT_CLOUD_API_KEY", None)
    try:
        p = OpenAIArchitectureProvider(api_key=None)
        assert not p.is_available()
        assert p.provider_name == "OPENAI"
        assert p.role.value == "CLOUD_EXPERT"
    finally:
        if old_key: os.environ["OPENAI_API_KEY"] = old_key
        if old_legacy: os.environ["AGAINPILOT_CLOUD_API_KEY"] = old_legacy

    # With key — should be available
    if _OPENAI_KEY:
        p2 = OpenAIArchitectureProvider(api_key=_OPENAI_KEY, model="gpt-4o")
        assert p2.is_available()
        assert p2.model_name == "gpt-4o"


def test_openai_provider_model_from_env():
    """Model resolved from OPENAI_MODEL env var, not hard-coded."""
    os.environ["OPENAI_MODEL"] = "gpt-4o-mini"
    try:
        from infra_again.intelligence.providers.openai_provider import _resolve_openai_model
        assert _resolve_openai_model() == "gpt-4o-mini"
    finally:
        del os.environ["OPENAI_MODEL"]


def test_openai_provider_key_not_logged():
    """API key never appears in repr/log output."""
    from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider
    p = OpenAIArchitectureProvider(api_key="sk-test-12345", model="gpt-4o")
    r = repr(p)
    assert "sk-test-12345" not in r, f"API key must not appear in repr: {r}"
    # Verify repr shows model but not key
    assert "gpt-4o" in r
    assert "has_key=True" in r


# ═══════════════════════════════════════════════════════════════════
# M4.4a — Local accepted: no cloud
# ═══════════════════════════════════════════════════════════════════

def test_local_accepted_no_cloud():
    """When local passes quality+completeness, cloud is never called."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, PassingTestProvider, FailingTestProvider,
        FinalResultMode,
    )
    local = PassingTestProvider("local-pass")
    cloud = FailingTestProvider("cloud-never-called", role=__import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole.CLOUD_EXPERT)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None, "Should return valid proposal"
    assert not prov.escalated, "Must NOT escalate"
    assert prov.final_result_mode == FinalResultMode.LOCAL_ACCEPTED.value
    assert cloud.call_count == 0, "Cloud must never be called"


# ═══════════════════════════════════════════════════════════════════
# M4.4b — Local failure escalates to cloud
# ═══════════════════════════════════════════════════════════════════

def test_local_failure_escalates():
    """When local fails, escalate to cloud."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, PassingTestProvider,
        FinalResultMode,
    )
    ModelRole = __import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole
    local = FailingTestProvider("local-fail")
    cloud = PassingTestProvider("cloud-pass", role=ModelRole.CLOUD_EXPERT)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None
    assert prov.escalated
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value
    assert cloud.call_count == 1
    assert local.call_count == 1


# ═══════════════════════════════════════════════════════════════════
# M4.7 — Cloud output cannot bypass validation
# ═══════════════════════════════════════════════════════════════════

class InvalidCloudProvider(__import__(
    "infra_again.intelligence.model_router", fromlist=["TestProviderBase"]
).TestProviderBase):
    __test__ = False

    def __init__(self):
        super().__init__("invalid-cloud", role=__import__(
            "infra_again.intelligence.model_router", fromlist=["ModelRole"]
        ).ModelRole.CLOUD_EXPERT)

    def generate_architecture(self, brief, provider_pref, platform_pref, req):
        self.call_count += 1
        from infra_again.intelligence.againpilot import (
            AgainPilotProposal, GeneratedNode, GeneratedEdge, _derive_views,
        )
        # Deliberately invalid: public DB, missing app runtime
        nodes = [
            GeneratedNode("db", "DB", "DATABASE", provider_pref, "rds", "KUBERNETES",
                         "public", "pii", "", "AI_GENERATED", "UNVERIFIED"),
        ]
        edges = [
            GeneratedEdge("e1", "user", "db", "data", "HTTP", "unidirectional",
                         "", "none", "User"),
        ]
        nd = [n.to_dict() for n in nodes]
        ed = [e.to_dict() for e in edges]
        proposal = AgainPilotProposal(
            title="Invalid", summary="Public DB, no app",
            detected_requirements=req or _dummy_req(),
            nodes=nodes, edges=edges, groups=[],
            views=_derive_views(nd, ed),
            native_service_recommendations=[],
            assumptions=[], risks=[], clarifying_questions=[], rationale="",
            generation_provider="TEST", generation_model="invalid",
            brief_hash="invalid",
        )
        return proposal, {"result": "TEST_INVALID"}

    def refine_architecture(self, nodes, edges, instruction, provider, base_req):
        self.call_count += 1
        return None, {"result": "TEST_INVALID"}


def test_cloud_output_cannot_bypass_validation():
    """Cloud output goes through same validators — invalid output is BLOCKED."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, FinalResultMode,
    )
    ModelRole = __import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole
    local = FailingTestProvider("local-fail")
    cloud = InvalidCloudProvider()
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None, "Invalid cloud output must be blocked"
    assert prov.final_result_mode in (FinalResultMode.BLOCKED.value, FinalResultMode.NEEDS_USER_REVIEW.value), \
        f"Expected BLOCKED or NEEDS_USER_REVIEW, got {prov.final_result_mode}"
    assert prov.escalated, "Must have escalated to cloud"


# ═══════════════════════════════════════════════════════════════════
# M4.8 — Cloud failure: no silent fallback
# ═══════════════════════════════════════════════════════════════════

class TimeoutCloudProvider(__import__(
    "infra_again.intelligence.model_router", fromlist=["TestProviderBase"]
).TestProviderBase):
    __test__ = False

    def __init__(self):
        super().__init__("timeout-cloud", role=__import__(
            "infra_again.intelligence.model_router", fromlist=["ModelRole"]
        ).ModelRole.CLOUD_EXPERT)

    def generate_architecture(self, brief, provider_pref, platform_pref, req):
        self.call_count += 1
        return None, {"result": "CLOUD_TIMEOUT"}

    def refine_architecture(self, nodes, edges, instruction, provider, base_req):
        self.call_count += 1
        return None, {"result": "CLOUD_TIMEOUT"}


class InvalidJsonCloudProvider(__import__(
    "infra_again.intelligence.model_router", fromlist=["TestProviderBase"]
).TestProviderBase):
    __test__ = False

    def __init__(self):
        super().__init__("invalid-json-cloud", role=__import__(
            "infra_again.intelligence.model_router", fromlist=["ModelRole"]
        ).ModelRole.CLOUD_EXPERT)

    def generate_architecture(self, brief, provider_pref, platform_pref, req):
        self.call_count += 1
        return None, {"result": "CLOUD_INVALID_JSON"}

    def refine_architecture(self, nodes, edges, instruction, provider, base_req):
        self.call_count += 1
        return None, {"result": "CLOUD_INVALID_JSON"}


def test_cloud_timeout_no_silent_fallback():
    """Cloud timeout → BLOCKED, no silent local/deterministic fallback."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, FinalResultMode,
    )
    ModelRole = __import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole
    local = FailingTestProvider("local-fail")
    cloud = TimeoutCloudProvider()
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None, "Must not silently fall back"
    assert prov.final_result_mode in (FinalResultMode.BLOCKED.value, FinalResultMode.NEEDS_USER_REVIEW.value)
    assert prov.escalated


def test_cloud_invalid_json_no_silent_fallback():
    """Cloud returns invalid JSON → BLOCKED, no silent fallback."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, FinalResultMode,
    )
    ModelRole = __import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole
    local = FailingTestProvider("local-fail")
    cloud = InvalidJsonCloudProvider()
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None
    assert prov.final_result_mode in (FinalResultMode.BLOCKED.value, FinalResultMode.NEEDS_USER_REVIEW.value)


# ═══════════════════════════════════════════════════════════════════
# M4.9 — Privacy: CLOUD_ALLOWED=false blocks cloud
# ═══════════════════════════════════════════════════════════════════

def test_cloud_policy_block():
    """CLOUD_ALLOWED=false + local failure → BLOCKED, cloud not called."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, PassingTestProvider,
        FinalResultMode,
    )
    ModelRole = __import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole
    local = FailingTestProvider("local-fail")
    cloud = PassingTestProvider("cloud-must-not-be-called", role=ModelRole.CLOUD_EXPERT)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST,
                               cloud_allowed=False)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None
    assert prov.final_result_mode == FinalResultMode.BLOCKED.value
    assert cloud.call_count == 0, "Cloud must not be called when CLOUD_ALLOWED=false"


# ═══════════════════════════════════════════════════════════════════
# M4.10 — Provenance completeness
# ═══════════════════════════════════════════════════════════════════

def test_provenance_completeness():
    """Provenance dict includes all required fields."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, PassingTestProvider, FinalResultMode,
    )
    ModelRole = __import__(
        "infra_again.intelligence.model_router", fromlist=["ModelRole"]
    ).ModelRole
    local = PassingTestProvider("local")
    cloud = PassingTestProvider("cloud", role=ModelRole.CLOUD_EXPERT)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    d = prov.to_dict()
    required = [
        "requestPolicy", "requestType",
        "localModel", "localResult", "localLatencyMs",
        "localCorrectionUsed", "localCorrectionResult",
        "escalated", "escalationReason",
        "cloudProvider", "cloudModel", "cloudResult", "cloudLatencyMs",
        "finalResultMode", "briefHash", "generationTimestamp",
    ]
    for key in required:
        assert key in d, f"Provenance must include '{key}'"


# ═══════════════════════════════════════════════════════════════════
# M4.5/6 — Cloud Refine (requires real OPENAI_API_KEY)
# ═══════════════════════════════════════════════════════════════════

@_requires_openai
def test_cloud_refine_ecs_fargate():
    """M4.5: OpenAI refines architecture to use ECS Fargate, DB private."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode, EscalationReason,
    )
    from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider

    cloud = OpenAIArchitectureProvider()
    router = HybridModelRouter(cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)

    result, prov = router.route_refine(
        nodes=PATIENT_PORTAL_NODES,
        edges=PATIENT_PORTAL_EDGES,
        instruction="Use ECS Fargate for the application tier and ensure the database has no public route.",
        provider="AWS",
    )

    assert result is not None, "Cloud refine must produce result"
    proposal, delta = result
    assert delta is not None, "RefineDelta must be non-empty"

    # Check Fargate
    changed_ids = {c.get("nodeId") or c.get("id") for c in delta.changed_nodes}
    app_nodes = [n for n in proposal.nodes if n.node_id in changed_ids or n.node_id.startswith("app")]
    has_fargate = any(
        "fargate" in (n.native_service or "").lower() for n in proposal.nodes
    )
    assert has_fargate or any(
        "fargate" in str(c.get("svc", "")).lower() for c in delta.changed_nodes
    ), "ECS Fargate must appear in changed nodes"

    # Check DB private zone
    db_nodes = [n for n in proposal.nodes if n.category == "DATABASE"]
    db_zones = {n.security_zone for n in db_nodes}
    assert all("private" in z for z in db_zones), \
        f"All DB nodes must be private, got zones: {db_zones}"

    # Provenance
    assert prov.escalated
    assert prov.escalation_reason == EscalationReason.REFINE_COMPLEX_SEMANTIC.value
    assert prov.cloud_provider == "OPENAI"
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value


@_requires_openai
def test_cloud_refine_add_redis():
    """M4.6: OpenAI adds Redis/ElastiCache between app and DB."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode,
    )
    from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider

    cloud = OpenAIArchitectureProvider()
    router = HybridModelRouter(cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)

    result, prov = router.route_refine(
        nodes=PATIENT_PORTAL_NODES,
        edges=PATIENT_PORTAL_EDGES,
        instruction="Add Redis cache between application and database.",
        provider="AWS",
    )

    assert result is not None, "Cloud refine must produce result"
    proposal, delta = result

    # Check Redis/ElastiCache
    cache_nodes = [
        n for n in proposal.nodes
        if "cache" in n.category.lower() or "redis" in (n.native_service or "").lower()
        or "elasticache" in (n.native_service or "").lower()
    ]
    has_cache = bool(cache_nodes) or any(
        "redis" in str(c.get("svc", "")).lower() or "elasticache" in str(c.get("svc", "")).lower()
        for c in delta.added_nodes if isinstance(c, dict)
    )
    assert has_cache, "Redis/ElastiCache must be present in result"


@_requires_openai
def test_cloud_generation_patient_portal():
    """M4.4b-real: Full OpenAI generation of patient portal architecture."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode,
        FailingTestProvider,
    )
    from infra_again.intelligence.providers.openai_provider import OpenAIArchitectureProvider

    cloud = OpenAIArchitectureProvider()
    local = FailingTestProvider("force-local-fail")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None, "OpenAI must generate valid architecture"
    assert prov.escalated
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value
    assert prov.cloud_provider == "OPENAI"
    assert prov.cloud_model != ""

    # Token usage recorded
    assert prov.cloud_input_tokens >= 0
    assert prov.cloud_output_tokens >= 0

    # Nodes and edges present
    assert len(proposal.nodes) >= 10, f"Expected >=10 nodes, got {len(proposal.nodes)}"
    assert len(proposal.edges) >= 5


# ═══════════════════════════════════════════════════════════════════
# M4 — Router mode configuration tests
# ═══════════════════════════════════════════════════════════════════

def test_router_mode_env_config():
    """AGAINPILOT_ROUTER_MODE=HYBRID enables hybrid router."""
    os.environ["AGAINPILOT_ROUTER_MODE"] = "HYBRID"
    os.environ["OPENAI_API_KEY"] = "sk-test"
    try:
        from infra_again.intelligence.againpilot import AgainPilotProviderRouter
        router = AgainPilotProviderRouter()
        hr = router._get_hybrid_router()
        assert hr is not None, "HYBRID mode should create hybrid router"
    finally:
        del os.environ["AGAINPILOT_ROUTER_MODE"]
        del os.environ["OPENAI_API_KEY"]


def test_router_mode_off_no_hybrid():
    """Without AGAINPILOT_ROUTER_MODE=HYBRID and no legacy key, no hybrid."""
    old_mode = os.environ.pop("AGAINPILOT_ROUTER_MODE", None)
    old_key = os.environ.pop("OPENAI_API_KEY", None)
    old_legacy = os.environ.pop("AGAINPILOT_CLOUD_API_KEY", None)
    try:
        from infra_again.intelligence.againpilot import AgainPilotProviderRouter
        router = AgainPilotProviderRouter()
        hr = router._get_hybrid_router()
        assert hr is None, "No hybrid router without config"
    finally:
        if old_mode: os.environ["AGAINPILOT_ROUTER_MODE"] = old_mode
        if old_key: os.environ["OPENAI_API_KEY"] = old_key
        if old_legacy: os.environ["AGAINPILOT_CLOUD_API_KEY"] = old_legacy


def test_legacy_key_still_works():
    """AGAINPILOT_CLOUD_API_KEY (deprecated) still works."""
    os.environ["AGAINPILOT_CLOUD_API_KEY"] = "sk-legacy"
    try:
        from infra_again.intelligence.againpilot import AgainPilotProviderRouter
        router = AgainPilotProviderRouter()
        hr = router._get_hybrid_router()
        assert hr is not None, "Legacy key should still work"
    finally:
        del os.environ["AGAINPILOT_CLOUD_API_KEY"]


# ═══════════════════════════════════════════════════════════════════
# M4 — Token usage / cost observability
# ═══════════════════════════════════════════════════════════════════

def test_token_usage_dataclass():
    """TokenUsage records input/output tokens."""
    from infra_again.intelligence.providers.openai_provider import TokenUsage
    u = TokenUsage(input_tokens=150, output_tokens=500, model="gpt-4o")
    d = u.to_dict()
    assert d["inputTokens"] == 150
    assert d["outputTokens"] == 500
    assert d["model"] == "gpt-4o"
    assert d["provider"] == "OPENAI"
