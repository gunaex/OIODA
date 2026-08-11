"""Dynamic Provider Intelligence — Domain Model + Catalog System.

Phase 4: DISCOVERED != SUPPORTED != SAFE_TO_EXECUTE
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Lifecycle
# ============================================================================


class CatalogLifecycle(str, Enum):
    DISCOVERED = "DISCOVERED"
    METADATA_COLLECTED = "METADATA_COLLECTED"
    CAPABILITY_MAPPED = "CAPABILITY_MAPPED"
    SCHEMA_VALIDATED = "SCHEMA_VALIDATED"
    EXECUTION_SUPPORT_CHECKED = "EXECUTION_SUPPORT_CHECKED"
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    UNVERIFIED = "UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"
    BLOCKED = "BLOCKED"


class ExecutionSupport(str, Enum):
    NONE = "NONE"
    PLAN_ONLY = "PLAN_ONLY"
    SIMULATED = "SIMULATED"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    SANDBOX = "SANDBOX"
    CONTROLLED_REAL = "CONTROLLED_REAL"
    PRODUCTION = "PRODUCTION"
    NOT_TESTED = "NOT_TESTED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class SourceType(str, Enum):
    OFFICIAL_API = "OFFICIAL_API"
    OFFICIAL_SCHEMA = "OFFICIAL_SCHEMA"
    OFFICIAL_DOC = "OFFICIAL_DOC"
    STATIC_SEED = "STATIC_SEED"
    MANUAL_VERIFIED = "MANUAL_VERIFIED"


class CapabilityCategory(str, Enum):
    OBJECT_STORAGE = "OBJECT_STORAGE"
    RELATIONAL_DATABASE = "RELATIONAL_DATABASE"
    COMPUTE_VM = "COMPUTE_VM"
    CONTAINER_RUNTIME = "CONTAINER_RUNTIME"
    KUBERNETES = "KUBERNETES"
    LOAD_BALANCING = "LOAD_BALANCING"
    NETWORKING = "NETWORKING"
    DNS = "DNS"
    SECRETS = "SECRETS"
    MESSAGING = "MESSAGING"
    OBSERVABILITY = "OBSERVABILITY"
    IAM = "IAM"
    CACHE = "CACHE"
    SERVERLESS = "SERVERLESS"
    SECURITY = "SECURITY"
    CDN = "CDN"
    KEY_MANAGEMENT = "KEY_MANAGEMENT"
    IDENTITY = "IDENTITY"


class FreshnessStatus(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


# Default threshold for catalog staleness
CATALOG_STALE_AFTER_DAYS = 7


def evaluate_freshness(
    retrieved_at: str | None,
    now: datetime | None = None,
    stale_after_days: int = CATALOG_STALE_AFTER_DAYS,
) -> FreshnessStatus:
    """Deterministic freshness evaluation.

    Args:
        retrieved_at: ISO-8601 timestamp string (or empty/None)
        now: Frozen 'now' for deterministic testing (defaults to real now)
        stale_after_days: Days after which a snapshot is considered STALE

    Returns:
        CURRENT if within threshold, STALE if exceeded, UNKNOWN if no timestamp.
    """
    if not retrieved_at:
        return FreshnessStatus.UNKNOWN

    now = now or datetime.now(timezone.utc)
    try:
        retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return FreshnessStatus.UNKNOWN

    age = now - retrieved
    if age.days > stale_after_days:
        return FreshnessStatus.STALE
    return FreshnessStatus.CURRENT


# ============================================================================
# Provider Service
# ============================================================================


@dataclass
class ProviderService:
    provider: str = ""
    service_id: str = ""
    display_name: str = ""
    category: str = ""
    lifecycle: CatalogLifecycle = CatalogLifecycle.DISCOVERED
    execution_support: list[str] = field(default_factory=list)
    # Platforms this service is compatible with (NATIVE_VM/KUBERNETES/
    # OPENSHIFT_OCP/BARE_METAL). Empty = not platform-specific (e.g. object
    # storage, managed databases) rather than "no platforms supported" —
    # platform compatibility is only meaningful for compute/container/
    # orchestration-category services. Provider and platform are separate
    # concepts (Phase N invariant); this field lets the resolver check
    # platform fit without conflating it with provider identity.
    platforms: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    source_type: SourceType = SourceType.STATIC_SEED
    source_reference: str = ""
    source_version: str = "1.0"
    retrieved_at: str = ""
    verified_at: str = ""
    service_checksum: str = ""
    deprecated: bool = False
    deprecated_at: str = ""
    replaced_by: str = ""
    notes: str = ""

    # Phase N2 — per-launch-mode/runtime-mode execution support. Keyed by a
    # deterministic runtime-mode marker (e.g. "FARGATE", "EC2"). A launch
    # mode NOT present here has NO verified execution support even if the
    # service family (execution_support above) does — family-level support
    # must never be silently inherited by a specific launch mode (e.g. "AWS
    # ECS supports X" must never imply "AWS ECS Fargate supports X").
    launch_types: dict[str, list[str]] = field(default_factory=dict)

    # Phase N2 — independent executor/observer/validator/verifier support,
    # each its own list of fidelities. None (the default) means "not
    # independently tracked" and falls back to execution_support (see
    # support_for()) so every pre-N2 seed entry keeps its existing
    # collapsed-to-one-signal behavior unchanged. An explicit [] is NOT the
    # same as None — it means "independently declared, and genuinely zero
    # support" (e.g. an executor exists but nothing observes it yet).
    executor_support: list[str] | None = None
    observer_support: list[str] | None = None
    validator_support: list[str] | None = None
    verifier_support: list[str] | None = None

    @property
    def is_safe_to_execute(self) -> bool:
        return self.lifecycle in (CatalogLifecycle.VERIFIED, CatalogLifecycle.SUPPORTED)

    @property
    def is_executable(self) -> bool:
        return any(s not in ("NONE", "PLAN_ONLY", "NOT_TESTED", "NOT_IMPLEMENTED")
                   for s in self.execution_support)

    def support_for(self, aspect: str) -> list[str]:
        """Fidelities at which `aspect` (EXECUTOR|OBSERVER|VALIDATOR|VERIFIER)
        is independently available. Falls back to execution_support only
        when the aspect was never declared (None) — an explicit [] means
        genuinely zero support for that aspect and is NOT overridden."""
        specific = {
            "EXECUTOR": self.executor_support, "OBSERVER": self.observer_support,
            "VALIDATOR": self.validator_support, "VERIFIER": self.verifier_support,
        }.get(aspect.upper())
        return specific if specific is not None else self.execution_support

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider, "serviceId": self.service_id,
            "displayName": self.display_name, "category": self.category,
            "lifecycle": self.lifecycle.value,
            "executionSupport": self.execution_support,
            "launchTypes": self.launch_types,
            "executorSupport": self.executor_support,
            "observerSupport": self.observer_support,
            "validatorSupport": self.validator_support,
            "verifierSupport": self.verifier_support,
            "platforms": self.platforms,
            "regions": self.regions, "resourceTypes": self.resource_types,
            "capabilities": self.capabilities,
            "sourceType": self.source_type.value, "sourceReference": self.source_reference,
            "sourceVersion": self.source_version,
            "retrievedAt": self.retrieved_at, "verifiedAt": self.verified_at,
            "serviceChecksum": self.service_checksum,
            "deprecated": self.deprecated, "deprecatedAt": self.deprecated_at,
            "replacedBy": self.replaced_by, "notes": self.notes,
            "isExecutable": self.is_executable,
            "isSafeToExecute": self.is_safe_to_execute,
        }


    def compute_service_checksum(self) -> str:
        """Compute a deterministic checksum for this single service."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class SyncMode(str, Enum):
    LOCAL_REFRESH = "LOCAL_REFRESH"
    LIVE_OFFICIAL_SYNC = "LIVE_OFFICIAL_SYNC"


# ============================================================================
# Provider Catalog Source Adapter (Phase 4.1)
# ============================================================================


class ProviderCatalogSource:
    """ABC for provider catalog data sources.

    Explicit about STATIC_FIXTURE vs OFFICIAL_LIVE.
    No hidden fallback.
    """

    source_kind: str = "STATIC_FIXTURE"  # STATIC_FIXTURE | OFFICIAL_LIVE

    async def fetch_services(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def fetch_service_schema(self, service_id: str) -> dict[str, Any] | None:
        return None


class StaticSeedSource(ProviderCatalogSource):
    """STATIC_FIXTURE source — seeded at build time."""
    source_kind = "STATIC_FIXTURE"

    def __init__(self, services: list[ProviderService]):
        self._services = services

    async def fetch_services(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._services]


class AwsCatalogSource(ProviderCatalogSource):
    """AWS official source adapter.

    Currently STATIC_FIXTURE — will become OFFICIAL_LIVE when
    actual CloudFormation resource spec retrieval is implemented.
    """
    source_kind = "STATIC_FIXTURE"

    def __init__(self, services: list[ProviderService]):
        self._services = services

    async def fetch_services(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._services]


class GcpCatalogSource(ProviderCatalogSource):
    """GCP official source adapter.

    Currently STATIC_FIXTURE.
    """
    source_kind = "STATIC_FIXTURE"

    def __init__(self, services: list[ProviderService]):
        self._services = services

    async def fetch_services(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._services]


# ============================================================================
# Capability Mapping
# ============================================================================


@dataclass
class CapabilityMapping:
    capability: str = ""     # provider-neutral capability
    provider: str = ""
    service_id: str = ""
    resource_type: str = ""
    lifecycle: CatalogLifecycle = CatalogLifecycle.DISCOVERED
    execution_support: list[str] = field(default_factory=list)
    confidence: float = 0.0   # 0..1 based on evidence
    selection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability, "provider": self.provider,
            "serviceId": self.service_id, "resourceType": self.resource_type,
            "lifecycle": self.lifecycle.value,
            "executionSupport": self.execution_support,
            "confidence": self.confidence,
            "selectionReason": self.selection_reason,
        }


# ============================================================================
# Catalog Snapshot
# ============================================================================


@dataclass
class CatalogSnapshot:
    snapshot_id: str = field(default_factory=lambda: f"snap-{uuid4().hex[:8]}")
    provider: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_version: str = "1.0"
    checksum: str = ""
    services: list[ProviderService] = field(default_factory=list)
    service_count: int = 0
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN

    def compute_checksum(self) -> str:
        data = json.dumps([s.to_dict() for s in self.services], sort_keys=True)
        self.checksum = hashlib.sha256(data.encode()).hexdigest()[:16]
        self.service_count = len(self.services)
        return self.checksum


# ============================================================================
# Catalog Diff
# ============================================================================


class DiffAction(str, Enum):
    SERVICE_ADDED = "SERVICE_ADDED"
    SERVICE_REMOVED = "SERVICE_REMOVED"
    RESOURCE_ADDED = "RESOURCE_ADDED"
    RESOURCE_REMOVED = "RESOURCE_REMOVED"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    REGION_ADDED = "REGION_ADDED"
    REGION_REMOVED = "REGION_REMOVED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


@dataclass
class CatalogDiff:
    provider: str = ""
    previous_snapshot_id: str = ""
    current_snapshot_id: str = ""
    changes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "previousSnapshotId": self.previous_snapshot_id,
            "currentSnapshotId": self.current_snapshot_id,
            "changes": self.changes,
        }


# ============================================================================
# Provider Catalog
# ============================================================================


class ProviderCatalog:
    """Central provider catalog with snapshots and capability registry."""

    def __init__(self):
        self._services: dict[str, ProviderService] = {}
        self._snapshots: list[CatalogSnapshot] = []
        self._mappings: list[CapabilityMapping] = []
        self._seed()

    def _seed(self):
        """Seed with verified AWS and GCP services."""
        now = datetime.now(timezone.utc).isoformat()
        # AWS services
        aws_services = [
            ProviderService(provider="AWS", service_id="s3", display_name="Amazon S3",
                category="OBJECT_STORAGE", lifecycle=CatalogLifecycle.VERIFIED,
                execution_support=["SIMULATED"], resource_types=["AWS::S3::Bucket"],
                capabilities=["OBJECT_STORAGE"], source_type=SourceType.MANUAL_VERIFIED,
                notes="Verified: fakecloud S3 create/observe/validate/destroy"),
            ProviderService(provider="AWS", service_id="rds", display_name="Amazon RDS",
                category="RELATIONAL_DATABASE", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], resource_types=["AWS::RDS::DBInstance"],
                capabilities=["RELATIONAL_DATABASE"], source_type=SourceType.MANUAL_VERIFIED,
                notes="PLAN_ONLY only — fakecloud RDS not verified"),
            ProviderService(provider="AWS", service_id="ec2", display_name="Amazon EC2",
                category="COMPUTE_VM", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], resource_types=["AWS::EC2::Instance"],
                capabilities=["COMPUTE_VM"]),
            ProviderService(provider="AWS", service_id="eks", display_name="Amazon EKS",
                category="KUBERNETES", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["KUBERNETES"],
                platforms=["KUBERNETES"]),
            ProviderService(provider="AWS", service_id="ecs", display_name="Amazon ECS",
                category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CONTAINER_RUNTIME"],
                platforms=["KUBERNETES"]),
            ProviderService(provider="AWS", service_id="elb", display_name="Elastic Load Balancing",
                category="LOAD_BALANCING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["LOAD_BALANCING"]),
            ProviderService(provider="AWS", service_id="cloudfront", display_name="CloudFront",
                category="CDN", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CDN"]),
            ProviderService(provider="AWS", service_id="waf", display_name="AWS WAF",
                category="SECURITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SECURITY"]),
            ProviderService(provider="AWS", service_id="kms", display_name="AWS KMS",
                category="KEY_MANAGEMENT", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["KEY_MANAGEMENT"]),
            ProviderService(provider="AWS", service_id="cognito", display_name="Amazon Cognito",
                category="IDENTITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["IDENTITY"]),
            ProviderService(provider="AWS", service_id="route53", display_name="Route 53",
                category="DNS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["DNS"]),
            ProviderService(provider="AWS", service_id="secretsmanager", display_name="Secrets Manager",
                category="SECRETS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SECRETS"]),
            ProviderService(provider="AWS", service_id="sqs", display_name="Amazon SQS",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="AWS", service_id="sns", display_name="Amazon SNS",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="AWS", service_id="cloudwatch", display_name="CloudWatch",
                category="OBSERVABILITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBSERVABILITY"]),
            ProviderService(provider="AWS", service_id="iam", display_name="IAM",
                category="IAM", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["IAM"]),
            ProviderService(provider="AWS", service_id="elasticache", display_name="ElastiCache",
                category="CACHE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CACHE"]),
            ProviderService(provider="AWS", service_id="lambda", display_name="Lambda",
                category="SERVERLESS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SERVERLESS"]),
        ]
        # GCP services
        gcp_services = [
            ProviderService(provider="GCP", service_id="storage", display_name="Cloud Storage",
                category="OBJECT_STORAGE", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], resource_types=["google_storage_bucket"],
                capabilities=["OBJECT_STORAGE"], source_type=SourceType.STATIC_SEED,
                notes="PLAN_ONLY only — GCP execution not implemented"),
            ProviderService(provider="GCP", service_id="compute", display_name="Compute Engine",
                category="COMPUTE_VM", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["COMPUTE_VM"]),
            ProviderService(provider="GCP", service_id="cloudsql", display_name="Cloud SQL",
                category="RELATIONAL_DATABASE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["RELATIONAL_DATABASE"]),
            ProviderService(provider="GCP", service_id="gke", display_name="GKE",
                category="KUBERNETES", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["KUBERNETES"],
                platforms=["KUBERNETES"]),
            ProviderService(provider="GCP", service_id="cloudrun", display_name="Cloud Run",
                category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CONTAINER_RUNTIME"],
                platforms=["KUBERNETES"]),
            ProviderService(provider="GCP", service_id="vpc", display_name="VPC",
                category="NETWORKING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["NETWORKING"]),
            ProviderService(provider="GCP", service_id="loadbalancing", display_name="Cloud Load Balancing",
                category="LOAD_BALANCING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["LOAD_BALANCING"]),
            ProviderService(provider="GCP", service_id="secretmanager", display_name="Secret Manager",
                category="SECRETS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SECRETS"]),
            ProviderService(provider="GCP", service_id="pubsub", display_name="Pub/Sub",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="GCP", service_id="monitoring", display_name="Cloud Monitoring",
                category="OBSERVABILITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBSERVABILITY"]),
            ProviderService(provider="GCP", service_id="dns", display_name="Cloud DNS",
                category="DNS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["DNS"]),
        ]
        # ON_PREM services — previously absent entirely from this catalog,
        # meaning every on-prem AGAINPILOT node resolved as UNKNOWN_SERVICE
        # regardless of how well-known the software actually is (nginx,
        # postgresql, ...). kubernetes/docker are the two entries genuinely
        # backed by real execution today (KindExecutor / KubernetesPlatformAdapter
        # in platforms/kubernetes/runtime.py, kind-based, LOCAL_RUNTIME only —
        # not SANDBOX/CONTROLLED_REAL). Everything else stays DISCOVERED/
        # NOT_IMPLEMENTED — no fake green.
        onprem_services = [
            ProviderService(provider="ON_PREM", service_id="kubernetes", display_name="Kubernetes",
                category="KUBERNETES", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["LOCAL_RUNTIME"], capabilities=["KUBERNETES"],
                platforms=["KUBERNETES"], source_type=SourceType.MANUAL_VERIFIED,
                notes="LOCAL_RUNTIME only — verified via kind (KindExecutor / KubernetesPlatformAdapter)"),
            ProviderService(provider="ON_PREM", service_id="docker", display_name="Docker",
                category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["LOCAL_RUNTIME"], capabilities=["CONTAINER_RUNTIME"],
                platforms=["KUBERNETES"], source_type=SourceType.MANUAL_VERIFIED,
                notes="LOCAL_RUNTIME only — container runtime underlying kind"),
            ProviderService(provider="ON_PREM", service_id="bind", display_name="BIND DNS",
                category="DNS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["DNS"]),
            ProviderService(provider="ON_PREM", service_id="nginx", display_name="NGINX",
                category="LOAD_BALANCING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["LOAD_BALANCING"]),
            ProviderService(provider="ON_PREM", service_id="haproxy", display_name="HAProxy",
                category="LOAD_BALANCING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["LOAD_BALANCING"]),
            ProviderService(provider="ON_PREM", service_id="traefik", display_name="Traefik",
                category="NETWORKING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["NETWORKING"]),
            ProviderService(provider="ON_PREM", service_id="vault", display_name="HashiCorp Vault",
                category="SECRETS", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["SECRETS"]),
            ProviderService(provider="ON_PREM", service_id="postgresql", display_name="PostgreSQL",
                category="RELATIONAL_DATABASE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["RELATIONAL_DATABASE"]),
            ProviderService(provider="ON_PREM", service_id="mysql", display_name="MySQL",
                category="RELATIONAL_DATABASE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["RELATIONAL_DATABASE"]),
            ProviderService(provider="ON_PREM", service_id="redis", display_name="Redis",
                category="CACHE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["CACHE"]),
            ProviderService(provider="ON_PREM", service_id="minio", display_name="MinIO",
                category="OBJECT_STORAGE", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBJECT_STORAGE"]),
            ProviderService(provider="ON_PREM", service_id="rabbitmq", display_name="RabbitMQ",
                category="MESSAGING", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["MESSAGING"]),
            ProviderService(provider="ON_PREM", service_id="prometheus", display_name="Prometheus",
                category="OBSERVABILITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBSERVABILITY"]),
            ProviderService(provider="ON_PREM", service_id="grafana", display_name="Grafana",
                category="OBSERVABILITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["OBSERVABILITY"]),
            ProviderService(provider="ON_PREM", service_id="keycloak", display_name="Keycloak",
                category="IDENTITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["IDENTITY"]),
            ProviderService(provider="ON_PREM", service_id="openldap", display_name="OpenLDAP",
                category="IDENTITY", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], capabilities=["IDENTITY"]),
        ]

        for s in aws_services + gcp_services + onprem_services:
            self._services[f"{s.provider}:{s.service_id}"] = s

        # Create initial snapshots
        for provider in ["AWS", "GCP", "ON_PREM"]:
            svcs = [s for s in self._services.values() if s.provider == provider]
            snap = CatalogSnapshot(provider=provider, freshness=FreshnessStatus.CURRENT)
            snap.services = svcs
            snap.compute_checksum()
            self._snapshots.append(snap)

        # Seed capability mappings
        self._mappings = [
            CapabilityMapping(capability="OBJECT_STORAGE", provider="AWS", service_id="s3",
                resource_type="AWS::S3::Bucket", lifecycle=CatalogLifecycle.VERIFIED,
                execution_support=["SIMULATED"], confidence=1.0,
                selection_reason="SIMULATED execution VERIFIED via fakecloud"),
            CapabilityMapping(capability="OBJECT_STORAGE", provider="GCP", service_id="storage",
                resource_type="google_storage_bucket", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], confidence=0.8,
                selection_reason="Catalog mapped, PLAN_ONLY only"),
            CapabilityMapping(capability="RELATIONAL_DATABASE", provider="AWS", service_id="rds",
                resource_type="AWS::RDS::DBInstance", lifecycle=CatalogLifecycle.CAPABILITY_MAPPED,
                execution_support=["PLAN_ONLY"], confidence=0.7,
                selection_reason="PLAN_ONLY only"),
            CapabilityMapping(capability="RELATIONAL_DATABASE", provider="GCP", service_id="cloudsql",
                resource_type="google_sql_database_instance", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], confidence=0.5),
            CapabilityMapping(capability="KUBERNETES", provider="AWS", service_id="eks",
                resource_type="AWS::EKS::Cluster", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], confidence=0.5),
            CapabilityMapping(capability="KUBERNETES", provider="GCP", service_id="gke",
                resource_type="google_container_cluster", lifecycle=CatalogLifecycle.DISCOVERED,
                execution_support=["NOT_IMPLEMENTED"], confidence=0.5),
        ]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_service(self, provider: str, service_id: str) -> ProviderService | None:
        return self._services.get(f"{provider}:{service_id}")

    def get_services(self, provider: str | None = None) -> list[ProviderService]:
        if provider:
            return [s for s in self._services.values() if s.provider == provider]
        return list(self._services.values())

    def get_mappings(self, capability: str | None = None, provider: str | None = None) -> list[CapabilityMapping]:
        results = self._mappings
        if capability:
            results = [m for m in results if m.capability == capability]
        if provider:
            results = [m for m in results if m.provider == provider]
        return results

    def get_snapshot(self, provider: str) -> CatalogSnapshot | None:
        for s in self._snapshots:
            if s.provider == provider:
                return s
        return None

    def get_snapshots(self) -> list[CatalogSnapshot]:
        return list(self._snapshots)

    def version(self) -> str:
        """Phase N3 — deterministic version identifier for the current
        catalog content. Changes whenever any service's lifecycle/
        execution_support/launch_types/etc. changes, so a plan bound to
        this value can detect Provider Intelligence drift (e.g. a service
        going DISCOVERED -> SUPPORTED after a plan was approved) without
        needing a separately-maintained version counter."""
        digest = hashlib.sha256(
            json.dumps(
                sorted(s.compute_service_checksum() for s in self._services.values()),
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        return f"PI-{digest}"

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(self, capability: str, execution_mode: str = "") -> list[dict[str, Any]]:
        """Compare providers for a given capability."""
        mappings = self.get_mappings(capability=capability)
        results = []
        for m in mappings:
            svc = self.get_service(m.provider, m.service_id)
            fit = "FULL" if m.confidence >= 0.8 else "PARTIAL"
            # Filter by execution_mode if provided
            if execution_mode and execution_mode not in m.execution_support:
                fit = "PLAN_ONLY" if "PLAN_ONLY" in m.execution_support else "UNSUPPORTED"
            results.append({
                "provider": m.provider, "serviceId": m.service_id,
                "resourceType": m.resource_type, "fit": fit,
                "executionSupport": m.execution_support,
                "lifecycle": m.lifecycle.value, "confidence": m.confidence,
                "selectionReason": m.selection_reason,
                "service": svc.to_dict() if svc else None,
            })
        return results

    def diff_snapshots(self, provider: str, prev_id: str, curr_id: str) -> CatalogDiff:
        prev = next((s for s in self._snapshots if s.snapshot_id == prev_id), None)
        curr = next((s for s in self._snapshots if s.snapshot_id == curr_id), None)
        return ProviderCatalog.compute_diff(provider, prev, curr)

    @staticmethod
    def compute_diff(
        provider: str,
        prev: CatalogSnapshot | None,
        curr: CatalogSnapshot | None,
    ) -> CatalogDiff:
        """Production diff: compare two catalog snapshots.

        This is the single canonical implementation — no duplicate algorithm
        exists in acceptance tests.
        """
        diff = CatalogDiff(
            provider=provider,
            previous_snapshot_id=prev.snapshot_id if prev else "",
            current_snapshot_id=curr.snapshot_id if curr else "",
        )
        if not prev or not curr:
            return diff

        prev_ids = {s.service_id for s in prev.services}
        curr_ids = {s.service_id for s in curr.services}

        for sid in curr_ids - prev_ids:
            diff.changes.append({"action": "SERVICE_ADDED", "serviceId": sid})
        for sid in prev_ids - curr_ids:
            diff.changes.append({"action": "SERVICE_REMOVED", "serviceId": sid})

        for s in curr.services:
            ps = next((ps for ps in prev.services if ps.service_id == s.service_id), None)
            if ps:
                if s.deprecated and not ps.deprecated:
                    diff.changes.append({"action": "DEPRECATED", "serviceId": s.service_id})
                if not s.deprecated and ps.deprecated:
                    diff.changes.append({"action": "RETIRED", "serviceId": s.service_id})
                cs_prev = ps.compute_service_checksum()
                cs_curr = s.compute_service_checksum()
                if cs_prev != cs_curr:
                    diff.changes.append({
                        "action": "SCHEMA_CHANGED", "serviceId": s.service_id,
                        "previousChecksum": cs_prev, "currentChecksum": cs_curr,
                    })

        return diff

    # ------------------------------------------------------------------
    # Persistence (Phase 4.1)
    # ------------------------------------------------------------------

    def persist(self, db_path: str = ".ai/infra-again.db") -> bool:
        """Persist catalog state to SQLite for restart durability."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS catalog_services (
                    key TEXT PRIMARY KEY,
                    provider TEXT, service_id TEXT, display_name TEXT,
                    category TEXT, lifecycle TEXT,
                    execution_support TEXT,  -- JSON array
                    regions TEXT, resource_types TEXT, capabilities TEXT,
                    source_type TEXT, source_reference TEXT,
                    source_version TEXT, retrieved_at TEXT, verified_at TEXT,
                    service_checksum TEXT,
                    deprecated INTEGER, deprecated_at TEXT, replaced_by TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS catalog_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    provider TEXT, retrieved_at TEXT,
                    source_version TEXT, checksum TEXT,
                    service_count INTEGER, freshness TEXT,
                    services_json TEXT  -- full serialization for restart
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS catalog_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability TEXT, provider TEXT, service_id TEXT,
                    resource_type TEXT, lifecycle TEXT,
                    execution_support TEXT, confidence REAL,
                    selection_reason TEXT
                )
            """)
            # Upsert services
            for s in self._services.values():
                conn.execute("""
                    INSERT OR REPLACE INTO catalog_services VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    f"{s.provider}:{s.service_id}", s.provider, s.service_id, s.display_name,
                    s.category, s.lifecycle.value,
                    json.dumps(s.execution_support),
                    json.dumps(s.regions), json.dumps(s.resource_types), json.dumps(s.capabilities),
                    s.source_type.value, s.source_reference,
                    s.source_version, s.retrieved_at, s.verified_at,
                    s.service_checksum,
                    1 if s.deprecated else 0, s.deprecated_at, s.replaced_by,
                    s.notes,
                ))
            # Upsert snapshots
            for snap in self._snapshots:
                conn.execute("""
                    INSERT OR REPLACE INTO catalog_snapshots VALUES (?,?,?,?,?,?,?,?)
                """, (
                    snap.snapshot_id, snap.provider, snap.retrieved_at,
                    snap.source_version, snap.checksum,
                    snap.service_count, snap.freshness.value,
                    json.dumps([s.to_dict() for s in snap.services], sort_keys=True),
                ))
            # Upsert mappings
            conn.execute("DELETE FROM catalog_mappings")
            for m in self._mappings:
                conn.execute("""
                    INSERT INTO catalog_mappings
                    (capability, provider, service_id, resource_type, lifecycle,
                     execution_support, confidence, selection_reason)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (
                    m.capability, m.provider, m.service_id, m.resource_type,
                    m.lifecycle.value, json.dumps(m.execution_support),
                    m.confidence, m.selection_reason,
                ))
            conn.commit()
            return True
        except Exception as e:
            return False
        finally:
            conn.close()

    @classmethod
    def load_persisted(cls, db_path: str = ".ai/infra-again.db") -> "ProviderCatalog | None":
        """Load catalog from SQLite. Returns None if no persisted state exists."""
        import sqlite3, os
        if not os.path.exists(db_path):
            return None
        try:
            conn = sqlite3.connect(str(db_path))
            # Check if catalog tables exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_services'"
            ).fetchall()
            if not tables:
                conn.close()
                return None

            catalog = cls.__new__(cls)
            catalog._services = {}
            catalog._snapshots = []
            catalog._mappings = []

            # Load services
            rows = conn.execute("SELECT * FROM catalog_services").fetchall()
            for r in rows:
                s = ProviderService(
                    provider=r[1], service_id=r[2], display_name=r[3] or "",
                    category=r[4] or "", lifecycle=CatalogLifecycle(r[5] if r[5] else "DISCOVERED"),
                    execution_support=json.loads(r[6]) if r[6] else [],
                    regions=json.loads(r[7]) if r[7] else [],
                    resource_types=json.loads(r[8]) if r[8] else [],
                    capabilities=json.loads(r[9]) if r[9] else [],
                    source_type=SourceType(r[10]) if r[10] else SourceType.STATIC_SEED,
                    source_reference=r[11] or "", source_version=r[12] or "1.0",
                    retrieved_at=r[13] or "", verified_at=r[14] or "",
                    service_checksum=r[15] or "",
                    deprecated=bool(r[16]), deprecated_at=r[17] or "",
                    replaced_by=r[18] or "", notes=r[19] or "",
                )
                catalog._services[f"{s.provider}:{s.service_id}"] = s

            # Load snapshots
            snap_rows = conn.execute("SELECT * FROM catalog_snapshots").fetchall()
            for r in snap_rows:
                snap = CatalogSnapshot(
                    snapshot_id=r[0], provider=r[1] or "",
                    retrieved_at=r[2] or "", source_version=r[3] or "1.0",
                    checksum=r[4] or "", service_count=r[5] or 0,
                    freshness=FreshnessStatus(r[6]) if r[6] else FreshnessStatus.UNKNOWN,
                )
                if r[7]:
                    try:
                        svc_dicts = json.loads(r[7])
                        snap.services = [
                            next((s for s in catalog._services.values()
                                  if s.provider == d.get("provider") and s.service_id == d.get("serviceId")),
                                 ProviderService(**{k: v for k, v in d.items() if k != "serviceChecksum"}))
                            for d in svc_dicts
                        ]
                    except Exception:
                        pass
                catalog._snapshots.append(snap)

            # Load mappings
            map_rows = conn.execute("SELECT * FROM catalog_mappings").fetchall()
            for r in map_rows:
                catalog._mappings.append(CapabilityMapping(
                    capability=r[1] or "", provider=r[2] or "", service_id=r[3] or "",
                    resource_type=r[4] or "", lifecycle=CatalogLifecycle(r[5]) if r[5] else CatalogLifecycle.DISCOVERED,
                    execution_support=json.loads(r[6]) if r[6] else [],
                    confidence=r[7] or 0.0, selection_reason=r[8] or "",
                ))

            conn.close()
            return catalog
        except Exception:
            return None


# Global instance
_provider_catalog = ProviderCatalog()


def get_catalog() -> ProviderCatalog:
    return _provider_catalog
