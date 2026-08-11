"""Phase N1 — Provider Intelligence Integration acceptance tests.

Covers the ProviderServiceResolver contract (src/infra_again/intelligence/
provider_resolver.py) and its wiring into AGAINPILOT's generate/refine node
construction paths. Maps directly to the N1 ACCEPTANCE fields:
SHARED_PROVIDER_RESOLVER, NO_DUPLICATE_AUTHORITY, KNOWN_SUPPORTED_SERVICE,
KNOWN_UNSUPPORTED_SERVICE, UNKNOWN_SERVICE, LLM_CANNOT_SET_SUPPORTED,
AGAINPILOT_PROVIDER_ENRICHMENT, REFINE_PROVIDER_ENRICHMENT.
"""

from __future__ import annotations

from infra_again.intelligence.catalog import get_catalog
from infra_again.intelligence.provider_resolver import (
    ProviderServiceResolver,
    ServiceResolution,
    enrich_nodes_with_provider_intelligence,
    get_resolver,
    normalize_service_id,
)


# ═══════════════════════════════════════════════════════════════════
# SHARED_PROVIDER_RESOLVER / NO_DUPLICATE_AUTHORITY
# ═══════════════════════════════════════════════════════════════════


def test_resolver_wraps_the_single_authoritative_catalog():
    resolver = get_resolver()
    assert resolver._catalog is get_catalog()


def test_get_resolver_returns_singleton():
    assert get_resolver() is get_resolver()


# ═══════════════════════════════════════════════════════════════════
# KNOWN_SUPPORTED_SERVICE
# ═══════════════════════════════════════════════════════════════════


def test_known_supported_service_resolves_with_real_execution_backing():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="s3")
    assert result.provider_lifecycle_state not in ("UNKNOWN_SERVICE",)
    assert result.execution_support_state != "UNSUPPORTED"
    assert result.executor_available is True
    assert result.observer_available is True
    assert result.validator_available is True
    assert result.verifier_available is True


def test_onprem_kubernetes_is_local_runtime_supported():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="ON_PREM", native_service="kubernetes")
    assert result.execution_support_state == "LOCAL_RUNTIME"
    assert result.executor_available is True


# ═══════════════════════════════════════════════════════════════════
# KNOWN_UNSUPPORTED_SERVICE
# ═══════════════════════════════════════════════════════════════════


def test_known_but_unsupported_service_reports_unsupported_not_error():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="elasticache")
    assert result.provider_lifecycle_state != "UNKNOWN_SERVICE"
    assert result.execution_support_state == "UNSUPPORTED"
    assert result.executor_available is False
    assert result.observer_available is False
    assert result.validator_available is False
    assert result.verifier_available is False


def test_plan_only_service_has_no_execution_backing():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="rds")
    assert result.execution_support_state == "PLAN_ONLY"
    assert result.executor_available is False


# ═══════════════════════════════════════════════════════════════════
# UNKNOWN_SERVICE — never silently normalized to a different known service
# ═══════════════════════════════════════════════════════════════════


def test_unknown_service_is_never_guessed_or_conflated():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="magic_database_service")
    assert result.provider_lifecycle_state == "UNKNOWN_SERVICE"
    assert result.execution_support_state == "UNSUPPORTED"
    assert result.canonical_service_id != "rds"
    assert result.canonical_service_id != "dynamodb"
    assert result.warnings


def test_unknown_service_never_marked_supported():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="totally_made_up_thing")
    assert result.execution_support_state == "UNSUPPORTED"
    assert result.executor_available is False


def test_missing_native_service_does_not_crash_or_fabricate():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="")
    assert result.provider_lifecycle_state == "UNKNOWN_SERVICE"
    assert result.warnings


def test_dissimilar_service_names_are_never_conflated():
    """DynamoDB must never resolve to RDS (or vice versa) just because both
    are 'databases' — that would be exactly the false-completeness this
    resolver exists to prevent."""
    resolver = ProviderServiceResolver()
    dynamo = resolver.resolve(provider="AWS", native_service="dynamodb")
    rds = resolver.resolve(provider="AWS", native_service="rds")
    assert dynamo.canonical_service_id != rds.canonical_service_id
    # dynamodb isn't catalogued — must surface as unknown, not silently
    # become rds.
    assert dynamo.provider_lifecycle_state == "UNKNOWN_SERVICE"
    assert rds.provider_lifecycle_state != "UNKNOWN_SERVICE"


# ═══════════════════════════════════════════════════════════════════
# Deterministic alias normalization only (no fuzzy matching)
# ═══════════════════════════════════════════════════════════════════


def test_alias_variants_resolve_to_the_same_canonical_service():
    variants = ["ecs_fargate", "ecs-fargate", "fargate", "aws_fargate"]
    for v in variants:
        assert normalize_service_id("AWS", v) == "ecs"


def test_alias_normalization_is_case_and_separator_insensitive():
    assert normalize_service_id("AWS", "Amazon S3") == "s3"
    assert normalize_service_id("AWS", "AMAZON-S3".replace("-", " ")) == "s3"


def test_alias_normalization_never_maps_across_providers():
    # A GCP-only alias must not resolve for AWS.
    assert normalize_service_id("AWS", "cloud_run") == "cloud_run"  # untouched, not "cloudrun"
    assert normalize_service_id("GCP", "cloud_run") == "cloudrun"


def test_alias_resolution_end_to_end_through_resolve():
    resolver = ProviderServiceResolver()
    result = resolver.resolve(provider="AWS", native_service="alb")
    assert result.canonical_service_id == "elb"
    assert result.provider_lifecycle_state != "UNKNOWN_SERVICE"


def test_platform_compatibility_flags_mismatch_without_fabricating_support():
    resolver = ProviderServiceResolver()
    compatible = resolver.resolve(provider="AWS", native_service="ecs", platform="KUBERNETES")
    incompatible = resolver.resolve(provider="AWS", native_service="ecs", platform="NATIVE_VM")
    no_platform_given = resolver.resolve(provider="AWS", native_service="ecs")
    assert compatible.platform_compatibility == "COMPATIBLE"
    assert incompatible.platform_compatibility == "INCOMPATIBLE"
    assert incompatible.warnings
    assert no_platform_given.platform_compatibility == "UNKNOWN"


def test_service_resolution_to_dict_uses_camel_case_contract():
    result = ServiceResolution(provider="AWS", canonical_service_id="s3")
    d = result.to_dict()
    assert "canonicalServiceId" in d
    assert "providerLifecycleState" in d
    assert "executorAvailable" in d
    assert "canonical_service_id" not in d


# ═══════════════════════════════════════════════════════════════════
# LLM_CANNOT_SET_SUPPORTED / AGAINPILOT_PROVIDER_ENRICHMENT
# ═══════════════════════════════════════════════════════════════════


class _FakeNode:
    """Stand-in for GeneratedNode — enrichment must work purely off
    provider/native_service/category attributes, never trust an
    incoming 'supported' flag from the LLM."""

    def __init__(self, category, provider, native_service, platform=""):
        self.category = category
        self.provider = provider
        self.native_service = native_service
        self.platform = platform
        self.provider_lifecycle_state = "UNRESOLVED"
        self.execution_support_state = "UNRESOLVED"
        self.provider_intelligence_ref = ""
        self.provider_intelligence_version = ""
        # Simulate an LLM/API caller trying to claim supported directly —
        # enrichment must overwrite this deterministically, never trust it.
        self.service_verification = "SUPPORTED"


def test_enrichment_overwrites_llm_claimed_state_deterministically():
    node = _FakeNode("DATABASE", "AWS", "elasticache")
    enrich_nodes_with_provider_intelligence([node])
    assert node.execution_support_state == "UNSUPPORTED"
    assert node.provider_lifecycle_state != "SUPPORTED"


def test_enrichment_sets_ref_and_version_for_known_service():
    node = _FakeNode("STORAGE", "AWS", "s3")
    enrich_nodes_with_provider_intelligence([node])
    assert node.provider_intelligence_ref == "AWS:s3"
    assert node.provider_lifecycle_state != "UNRESOLVED"
    assert node.execution_support_state != "UNRESOLVED"


def test_enrichment_marks_user_external_nodes_not_applicable():
    node = _FakeNode("USER", "", "")
    enrich_nodes_with_provider_intelligence([node])
    assert node.provider_lifecycle_state == "NOT_APPLICABLE"
    assert node.execution_support_state == "NOT_APPLICABLE"


def test_enrichment_resolves_alias_in_node_native_service():
    node = _FakeNode("APPLICATION", "AWS", "ecs_fargate", platform="KUBERNETES")
    enrich_nodes_with_provider_intelligence([node])
    assert node.provider_intelligence_ref == "AWS:ecs"


def test_enrichment_leaves_unknown_service_unknown():
    node = _FakeNode("APPLICATION", "AWS", "nonexistent_service_xyz")
    enrich_nodes_with_provider_intelligence([node])
    assert node.provider_lifecycle_state == "UNKNOWN_SERVICE"
    assert node.execution_support_state == "UNSUPPORTED"


# ═══════════════════════════════════════════════════════════════════
# AGAINPILOT_PROVIDER_ENRICHMENT / REFINE_PROVIDER_ENRICHMENT (integration)
# ═══════════════════════════════════════════════════════════════════


def test_generate_architecture_enriches_every_node():
    from infra_again.intelligence.againpilot import (
        AgainPilotRequest, ProviderPreference, generate_architecture,
    )

    request = AgainPilotRequest(
        brief="A web app on AWS with a database, load balancer and object storage, "
              "needs high availability and encryption at rest",
        provider_preference=ProviderPreference.AWS,
    )
    proposal = generate_architecture(request)
    assert proposal.nodes
    for n in proposal.nodes:
        assert n.provider_lifecycle_state != "UNRESOLVED"
        assert n.execution_support_state != "UNRESOLVED"


def test_deterministic_refine_enriches_nodes_and_resolves_alias():
    from infra_again.intelligence.againpilot import refine_architecture

    nodes = [{
        "nodeId": "N1", "name": "App", "category": "APPLICATION", "provider": "AWS",
        "nativeService": "ecs", "platform": "KUBERNETES", "securityZone": "private",
        "dataClassification": "internal", "owner": "", "source": "AI_GENERATED",
        "verificationState": "UNVERIFIED", "properties": {}, "serviceVerification": "SUPPORTED",
    }]
    proposal, _delta = refine_architecture(nodes, [], "Use ecs_fargate instead of ecs", "AWS")
    target = next(n for n in proposal.nodes if n.node_id == "N1")
    assert target.native_service == "ecs_fargate"
    assert target.provider_intelligence_ref == "AWS:ecs"
    assert target.provider_lifecycle_state != "UNRESOLVED"


def test_generated_node_to_dict_exposes_provider_intelligence_fields():
    from infra_again.intelligence.againpilot import GeneratedNode

    node = GeneratedNode(
        node_id="N1", name="App", category="APPLICATION", provider="AWS",
        native_service="s3", platform="NATIVE_VM",
        security_zone="private", data_classification="internal", owner="",
    )
    enrich_nodes_with_provider_intelligence([node])
    d = node.to_dict()
    assert "providerLifecycleState" in d
    assert "executionSupportState" in d
    assert "providerIntelligenceRef" in d
    assert "providerIntelligenceVersion" in d
    assert d["providerLifecycleState"] != "UNRESOLVED"
