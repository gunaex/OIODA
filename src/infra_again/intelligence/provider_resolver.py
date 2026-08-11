"""Shared Provider Service Resolution contract — Phase N1.

The ONE path AGAINPILOT (or anything else) uses to ask "does this AI-proposed
service actually have execution support" against the authoritative catalog
(intelligence.catalog.ProviderCatalog / get_catalog()).

Per the N1.0 audit, five other overlapping authorities already exist in this
codebase (registry.CapabilityRegistry, providers/aws/adapter.py's
AWS_CAPABILITY_MAP, core.domain.CapabilitySupportLifecycle, the unused
intelligence/interface.py ABCs, and AGAINPILOT's own static service dicts).
This module deliberately does NOT create a seventh — it wraps catalog.py,
which already has the most API integration and the is_safe_to_execute/
is_executable semantics this needs. Reconciling the other five is real but
separate technical debt, out of scope here.

Invariant: the LLM never sets SUPPORTED. AGAINPILOT (or any caller) supplies
only (provider, nativeService, platform); this module supplies everything
about verification/execution state, deterministically, from the catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .catalog import ProviderCatalog, get_catalog

# ═══════════════════════════════════════════════════════════════════
# Deterministic alias table
# ═══════════════════════════════════════════════════════════════════
#
# Only genuine spelling/naming variants of the SAME catalog entry — never an
# approximation of a different service. E.g. DynamoDB is never aliased to
# RDS; they are different services, and if dynamodb isn't catalogued yet it
# must resolve UNKNOWN_SERVICE, not silently become "rds". Fabricating an
# alias to a similar-sounding known service would be exactly the kind of
# false-completeness this phase exists to prevent.
SERVICE_ALIASES: dict[str, dict[str, str]] = {
    "AWS": {
        "ecs_fargate": "ecs", "ecs-fargate": "ecs", "fargate": "ecs", "aws_fargate": "ecs",
        "alb": "elb", "nlb": "elb", "application_load_balancer": "elb", "network_load_balancer": "elb",
        "secrets_manager": "secretsmanager", "aws_secrets_manager": "secretsmanager",
        "amazon_s3": "s3", "amazon_rds": "rds", "amazon_ecs": "ecs", "amazon_eks": "eks",
        "amazon_cloudfront": "cloudfront", "aws_kms": "kms", "amazon_cognito": "cognito",
        "route_53": "route53", "amazon_route_53": "route53",
        "amazon_cloudwatch": "cloudwatch", "amazon_elasticache": "elasticache",
        "aws_lambda": "lambda", "aws_waf": "waf", "amazon_ec2": "ec2",
    },
    "GCP": {
        "cloud_storage": "storage", "google_cloud_storage": "storage",
        "cloud_sql": "cloudsql", "google_kubernetes_engine": "gke",
        "cloud_run": "cloudrun", "secret_manager": "secretmanager",
        "cloud_pubsub": "pubsub", "cloud_monitoring": "monitoring", "cloud_dns": "dns",
        "cloud_load_balancing": "loadbalancing", "cloud_vpc": "vpc",
        "compute_engine": "compute", "google_compute_engine": "compute",
    },
    "ON_PREM": {
        "k8s": "kubernetes", "postgres": "postgresql", "haproxy_lb": "haproxy",
        "hashicorp_vault": "vault", "min_io": "minio", "rabbit_mq": "rabbitmq",
    },
}

# execution_support values that mean "nothing real backs this" — collapse to
# UNSUPPORTED rather than a misleadingly-specific-looking empty state.
_NOOP_SUPPORT = {"NOT_IMPLEMENTED", "NOT_TESTED", "NONE"}
# Highest-fidelity-first, for picking a single representative state out of a
# service's execution_support list.
_FIDELITY_ORDER = ["PRODUCTION", "CONTROLLED_REAL", "SANDBOX", "LOCAL_RUNTIME", "SIMULATED", "PLAN_ONLY"]


def normalize_service_id(provider: str, native_service: str) -> str:
    """Deterministic normalization ONLY: lowercase/underscore + exact alias
    lookup. Never fuzzy/substring matching — that is how a genuinely-unknown
    service silently becomes a wrong known one."""
    key = (native_service or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = SERVICE_ALIASES.get((provider or "").upper(), {})
    return aliases.get(key, key)


@dataclass
class ServiceResolution:
    provider: str = ""
    canonical_service_id: str = ""
    canonical_native_service: str = ""
    display_name: str = ""
    # COMPATIBLE | INCOMPATIBLE | NOT_PLATFORM_SPECIFIC | UNKNOWN
    platform_compatibility: str = "UNKNOWN"

    # UNKNOWN_SERVICE plus every CatalogLifecycle value
    provider_lifecycle_state: str = "UNKNOWN_SERVICE"
    # UNSUPPORTED plus every real (non-noop) ExecutionSupport value
    execution_support_state: str = "UNSUPPORTED"
    # NOT_VALIDATED | VALIDATED
    schema_validation_state: str = "NOT_VALIDATED"

    executor_available: bool = False
    observer_available: bool = False
    validator_available: bool = False
    verifier_available: bool = False

    metadata_source: str = ""
    metadata_version: str = ""
    last_verified_at: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "canonicalServiceId": self.canonical_service_id,
            "canonicalNativeService": self.canonical_native_service,
            "displayName": self.display_name,
            "platformCompatibility": self.platform_compatibility,
            "providerLifecycleState": self.provider_lifecycle_state,
            "executionSupportState": self.execution_support_state,
            "schemaValidationState": self.schema_validation_state,
            "executorAvailable": self.executor_available,
            "observerAvailable": self.observer_available,
            "validatorAvailable": self.validator_available,
            "verifierAvailable": self.verifier_available,
            "metadataSource": self.metadata_source,
            "metadataVersion": self.metadata_version,
            "lastVerifiedAt": self.last_verified_at,
            "warnings": self.warnings,
        }


class ProviderServiceResolver:
    """The single AGAINPILOT <-> Provider Intelligence contract.

    Never invoked by the LLM — only by backend code, after a proposal/delta
    already exists, so the model can influence WHICH service name gets
    proposed but never the verdict on whether it's actually supported.
    """

    def __init__(self, catalog: ProviderCatalog | None = None):
        self._catalog = catalog or get_catalog()

    def resolve(
        self, provider: str, native_service: str, platform: str = "",
        region: str | None = None, version: str | None = None,
    ) -> ServiceResolution:
        provider_u = (provider or "").upper()
        res = ServiceResolution(provider=provider_u)

        if not native_service:
            res.warnings.append("No nativeService provided — cannot resolve")
            return res

        canonical_id = normalize_service_id(provider_u, native_service)
        res.canonical_service_id = canonical_id

        svc = self._catalog.get_service(provider_u, canonical_id)
        if svc is None:
            # Genuinely unknown — do not guess, do not normalize to an
            # unrelated known service, do not mark supported.
            res.canonical_native_service = native_service
            res.provider_lifecycle_state = "UNKNOWN_SERVICE"
            res.execution_support_state = "UNSUPPORTED"
            res.warnings.append(
                f"'{native_service}' is not a known {provider_u} service in Provider "
                f"Intelligence — CANDIDATE only, not verified."
            )
            return res

        res.canonical_native_service = svc.service_id
        res.display_name = svc.display_name
        res.provider_lifecycle_state = svc.lifecycle.value
        res.metadata_source = svc.source_type.value
        res.metadata_version = svc.source_version
        res.last_verified_at = svc.verified_at

        real_support = [s for s in svc.execution_support if s not in _NOOP_SUPPORT]
        if not real_support:
            res.execution_support_state = "UNSUPPORTED"
        else:
            res.execution_support_state = next(
                (s for s in _FIDELITY_ORDER if s in real_support), real_support[0]
            )

        res.schema_validation_state = (
            "VALIDATED"
            if svc.lifecycle.value in ("SCHEMA_VALIDATED", "EXECUTION_SUPPORT_CHECKED", "VERIFIED", "SUPPORTED")
            else "NOT_VALIDATED"
        )

        # Provider and platform are separate axes — a service with no
        # platforms declared is not platform-specific (e.g. object storage),
        # not "supports no platforms."
        if not svc.platforms:
            res.platform_compatibility = "NOT_PLATFORM_SPECIFIC"
        elif not platform:
            res.platform_compatibility = "UNKNOWN"
        elif platform.upper() in [p.upper() for p in svc.platforms]:
            res.platform_compatibility = "COMPATIBLE"
        else:
            res.platform_compatibility = "INCOMPATIBLE"
            res.warnings.append(f"{svc.display_name} is not known to run on platform={platform}")

        # Executor/observer/validator/verifier availability is derived from
        # the SAME execution_support signal — never asserted independently,
        # never fabricated. PLAN_ONLY means a plan can exist but nothing
        # actually executes/observes it (matches N2.2's stated semantics).
        has_real_backing = res.execution_support_state not in ("UNSUPPORTED", "PLAN_ONLY")
        res.executor_available = has_real_backing
        res.observer_available = has_real_backing
        res.validator_available = has_real_backing
        # The verifier (execution/verifier.py's ExecutionVerifier) is generic
        # across services, not per-service-implemented — it's available
        # whenever there's real execution to independently check.
        res.verifier_available = has_real_backing

        if svc.deprecated:
            msg = f"{svc.display_name} is DEPRECATED"
            if svc.replaced_by:
                msg += f", replaced by {svc.replaced_by}"
            res.warnings.append(msg)

        return res

    def resolve_node(self, node: dict[str, Any]) -> ServiceResolution:
        """Convenience wrapper for a canonical AGAINPILOT node dict
        (nodeId/name/category/provider/nativeService/platform/...)."""
        return self.resolve(
            provider=node.get("provider", ""),
            native_service=node.get("nativeService", ""),
            platform=node.get("platform", ""),
        )


_resolver: ProviderServiceResolver | None = None


def get_resolver() -> ProviderServiceResolver:
    global _resolver
    if _resolver is None:
        _resolver = ProviderServiceResolver()
    return _resolver


def enrich_nodes_with_provider_intelligence(nodes: list[Any]) -> None:
    """Mutate GeneratedNode objects in place with Provider Intelligence
    resolution — the ONLY place these fields are ever set. Called after a
    proposal/delta already exists (generation or refine), so the LLM's
    influence stops at choosing which service to propose; it never sees or
    sets provider_lifecycle_state / execution_support_state itself.
    """
    resolver = get_resolver()
    for n in nodes:
        # USER/EXTERNAL nodes have no real provider service to resolve.
        if getattr(n, "category", "") in ("USER", "EXTERNAL") or not getattr(n, "native_service", ""):
            n.provider_lifecycle_state = "NOT_APPLICABLE"
            n.execution_support_state = "NOT_APPLICABLE"
            continue
        result = resolver.resolve(
            provider=getattr(n, "provider", ""),
            native_service=getattr(n, "native_service", ""),
            platform=getattr(n, "platform", ""),
        )
        n.provider_lifecycle_state = result.provider_lifecycle_state
        n.execution_support_state = result.execution_support_state
        n.provider_intelligence_ref = f"{result.provider}:{result.canonical_service_id}"
        n.provider_intelligence_version = result.metadata_version
