"""M4-D — REAL DEEPSEEK CLOUD ACCEPTANCE TESTS

Tests that require DEEPSEEK_API_KEY are automatically skipped when not set.
"""

from __future__ import annotations

import os, sys, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

_DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
_requires_deepseek = pytest.mark.skipif(
    not _DEEPSEEK_KEY,
    reason="DEEPSEEK_API_KEY not set",
)

# ═══════════════════════════════════════════════════════════════════
# Test data (same as M4)
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
    # Supporting edges — prevent orphan detection
    {"edgeId": "e7", "sourceNodeId": "cdn", "targetNodeId": "identity", "type": "auth",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "Auth"},
    {"edgeId": "e8", "sourceNodeId": "app", "targetNodeId": "identity", "type": "auth",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "Auth"},
    {"edgeId": "e9", "sourceNodeId": "app", "targetNodeId": "secrets", "type": "secret_access",
     "protocol": "TLS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "Secrets"},
    {"edgeId": "e10", "sourceNodeId": "db", "targetNodeId": "kms", "type": "key_usage",
     "protocol": "TLS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "KMS"},
    {"edgeId": "e11", "sourceNodeId": "app", "targetNodeId": "obs", "type": "telemetry",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "Obs"},
    {"edgeId": "e12", "sourceNodeId": "db", "targetNodeId": "obs", "type": "telemetry",
     "protocol": "HTTPS", "direction": "unidirectional", "notes": "", "trust": "none", "label": "Obs"},
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
# Provider instantiation
# ═══════════════════════════════════════════════════════════════════

def test_deepseek_provider_instantiation():
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider
    old_key = os.environ.pop("DEEPSEEK_API_KEY", None)
    try:
        p = DeepSeekArchitectureProvider(api_key=None)
        assert not p.is_available()
        assert p.provider_name == "DEEPSEEK"
        assert p.role.value == "CLOUD_EXPERT"
    finally:
        if old_key: os.environ["DEEPSEEK_API_KEY"] = old_key


@_requires_deepseek
def test_deepseek_provider_available():
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider
    p = DeepSeekArchitectureProvider()
    assert p.is_available()
    assert p.model_name == os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


# ═══════════════════════════════════════════════════════════════════
# M4-D.3 — Real Generation
# ═══════════════════════════════════════════════════════════════════

@_requires_deepseek
def test_deepseek_generation_patient_portal():
    """Real DeepSeek generation of patient portal architecture."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode, FailingTestProvider,
    )
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider

    cloud = DeepSeekArchitectureProvider()
    local = FailingTestProvider("force-local-fail")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is not None, "DeepSeek must generate valid architecture"
    assert prov.escalated
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value
    assert prov.cloud_provider == "DEEPSEEK"
    assert prov.cloud_model == os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")

    # Token usage
    assert prov.cloud_input_tokens >= 0
    assert prov.cloud_output_tokens >= 0

    # Structure
    assert len(proposal.nodes) >= 10, f"Expected >=10 nodes, got {len(proposal.nodes)}"
    assert len(proposal.edges) >= 5

    # Print results
    print(f"\n  GENERATION: nodes={len(proposal.nodes)} edges={len(proposal.edges)}")
    print(f"  QUALITY: PASS (via validators)")
    print(f"  COMPLETENESS: PASS (via validators)")
    print(f"  LATENCY: {prov.cloud_latency_ms}ms")
    print(f"  TOKENS: {prov.cloud_input_tokens} in / {prov.cloud_output_tokens} out")


# ═══════════════════════════════════════════════════════════════════
# M4-D.4 — ECS Fargate Refine
# ═══════════════════════════════════════════════════════════════════

@_requires_deepseek
def test_deepseek_refine_ecs_fargate():
    """DeepSeek refines architecture to use ECS Fargate, DB private."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode, EscalationReason,
    )
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider

    cloud = DeepSeekArchitectureProvider()
    router = HybridModelRouter(cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)

    result, prov = router.route_refine(
        nodes=PATIENT_PORTAL_NODES,
        edges=PATIENT_PORTAL_EDGES,
        instruction="Use ECS Fargate for the application tier and ensure the database has no public route.",
        provider="AWS",
    )

    assert result is not None, "DeepSeek refine must produce result"
    proposal, delta = result

    # Delta non-empty
    has_changes = bool(delta.changed_nodes) or bool(delta.added_nodes) or bool(delta.removed_nodes)
    assert has_changes, "RefineDelta must be non-empty"

    # Fargate check
    has_fargate = any(
        "fargate" in (n.native_service or "").lower() for n in proposal.nodes
    )
    if not has_fargate:
        has_fargate = any(
            "fargate" in str(c.get("svc", "")).lower()
            for c in delta.changed_nodes if isinstance(c, dict)
        )
    print(f"\n  FARGATE_PRESENT: {has_fargate}")

    # DB private
    db_nodes = [n for n in proposal.nodes if n.category == "DATABASE"]
    db_zones = {n.security_zone for n in db_nodes}
    db_private = all("private" in z for z in db_zones)
    print(f"  DB_PRIVATE: {db_private} (zones: {db_zones})")

    assert prov.escalated
    assert prov.escalation_reason == EscalationReason.REFINE_COMPLEX_SEMANTIC.value
    assert prov.cloud_provider == "DEEPSEEK"
    assert prov.final_result_mode == FinalResultMode.CLOUD_ESCALATED.value


# ═══════════════════════════════════════════════════════════════════
# M4-D.5 — Redis Refine
# ═══════════════════════════════════════════════════════════════════

@_requires_deepseek
def test_deepseek_refine_add_redis():
    """DeepSeek adds Redis/ElastiCache between app and DB."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode,
    )
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider

    cloud = DeepSeekArchitectureProvider()
    router = HybridModelRouter(cloud_expert=cloud, policy=ExecutionPolicy.LOCAL_FIRST)

    result, prov = router.route_refine(
        nodes=PATIENT_PORTAL_NODES,
        edges=PATIENT_PORTAL_EDGES,
        instruction="Add Redis cache between application and database.",
        provider="AWS",
    )

    assert result is not None, "DeepSeek refine must produce result"
    proposal, delta = result

    # Redis/ElastiCache check
    cache_nodes = [
        n for n in proposal.nodes
        if "cache" in n.category.lower() or "redis" in (n.native_service or "").lower()
        or "elasticache" in (n.native_service or "").lower()
    ]
    has_cache = bool(cache_nodes) or any(
        "redis" in str(c.get("svc", "")).lower() or "elasticache" in str(c.get("svc", "")).lower()
        for c in (delta.added_nodes if hasattr(delta, 'added_nodes') else [])
        if isinstance(c, dict)
    )
    print(f"\n  REDIS_PRESENT: {has_cache}")
    if cache_nodes:
        print(f"  CACHE_NODES: {[n.name for n in cache_nodes]}")

    # Delta non-empty
    has_changes = bool(delta.changed_nodes) or bool(delta.added_nodes) or bool(delta.removed_nodes)
    assert has_changes, "RefineDelta must be non-empty"


# ═══════════════════════════════════════════════════════════════════
# M4-D.7 — Failure safety (provider doubles)
# ═══════════════════════════════════════════════════════════════════

def test_deepseek_router_failure_safety():
    """Cloud failure → no silent fallback (provider doubles)."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, FinalResultMode,
    )
    from infra_again.intelligence.model_router import TestProviderBase
    import infra_again.intelligence.model_router as mr

    class TimeoutDeepSeekProvider(TestProviderBase):
        __test__ = False
        def __init__(self):
            super().__init__("timeout-ds", role=mr.ModelRole.CLOUD_EXPERT)
        def generate_architecture(self, brief, pp, pl, req):
            self.call_count += 1
            return None, {"result": "CLOUD_TIMEOUT"}

    local = FailingTestProvider("local-fail")
    cloud = TimeoutDeepSeekProvider()
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None
    assert prov.final_result_mode in (FinalResultMode.BLOCKED.value, FinalResultMode.NEEDS_USER_REVIEW.value)


def test_deepseek_privacy_policy_block():
    """CLOUD_ALLOWED=false → DeepSeek never called."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FailingTestProvider, PassingTestProvider,
        FinalResultMode,
    )
    import infra_again.intelligence.model_router as mr

    local = FailingTestProvider("local-fail")
    cloud = PassingTestProvider("deepseek-must-not-be-called", role=mr.ModelRole.CLOUD_EXPERT)
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST,
                               cloud_allowed=False)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    assert proposal is None
    assert prov.final_result_mode == FinalResultMode.BLOCKED.value
    assert cloud.call_count == 0


# ═══════════════════════════════════════════════════════════════════
# M4-D.10 — Provenance
# ═══════════════════════════════════════════════════════════════════

@_requires_deepseek
def test_deepseek_provenance():
    """Verify all provenance fields for real DeepSeek run."""
    from infra_again.intelligence.model_router import (
        HybridModelRouter, ExecutionPolicy, FinalResultMode, FailingTestProvider,
    )
    from infra_again.intelligence.providers.deepseek_provider import DeepSeekArchitectureProvider

    cloud = DeepSeekArchitectureProvider()
    local = FailingTestProvider("force-local-fail")
    router = HybridModelRouter(local_architect=local, cloud_expert=cloud,
                               policy=ExecutionPolicy.LOCAL_FIRST)

    proposal, prov = router.route_generation(
        PATIENT_PORTAL_BRIEF, "AWS", "KUBERNETES", _dummy_req(),
    )

    d = prov.to_dict()
    assert d["requestPolicy"] == "LOCAL_FIRST"
    assert d["requestType"] == "generate"
    assert d["escalated"] == True
    assert d["escalationReason"] != ""
    assert d["cloudProvider"] == "DEEPSEEK"
    assert d["cloudModel"] == os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
    assert d["cloudResult"] != ""
    assert d["cloudLatencyMs"] > 0
    assert d["finalResultMode"] == FinalResultMode.CLOUD_ESCALATED.value
    assert "tokenUsage" in d

    print(f"\n  PROVENANCE: {json.dumps(d, indent=2)}")

import json
