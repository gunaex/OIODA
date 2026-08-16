"""Dynamic Capability Registry for INFRA-AGAIN — Phase 3.

Central registry of provider and platform capabilities with
truthful lifecycle tracking. Every entry must be verified before
claiming support.

Critical invariant: DISCOVERED != SUPPORTED != SAFE_TO_EXECUTE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class CapabilityLifecycle(str, Enum):
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


class ExecutionFidelity(str, Enum):
    PLAN_ONLY = "PLAN_ONLY"
    SIMULATED = "SIMULATED"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    LOCAL_PRIVATE_CLOUD = "LOCAL_PRIVATE_CLOUD"
    SANDBOX = "SANDBOX"
    CONTROLLED_REAL = "CONTROLLED_REAL"
    PRODUCTION = "PRODUCTION"
    NOT_TESTED = "NOT_TESTED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class SourceType(str, Enum):
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"
    THIRD_PARTY = "THIRD_PARTY"
    BUILTIN = "BUILTIN"
    DISCOVERED_AT_RUNTIME = "DISCOVERED_AT_RUNTIME"


@dataclass
class CapabilityRecord:
    """A single capability entry in the registry."""
    capability_id: str = field(default_factory=lambda: f"cap-{uuid4().hex[:8]}")
    name: str = ""
    category: str = ""          # COMPUTE, STORAGE, NETWORKING, etc.
    provider: str = ""          # AWS, GCP, ON_PREM, KUBERNETES, OPENSHIFT_OCP
    platform: str = ""          # NATIVE_VM, KUBERNETES, OPENSHIFT_OCP
    resource_type: str = ""     # AWS::S3::Bucket, kubernetes_deployment, etc.
    lifecycle: CapabilityLifecycle = CapabilityLifecycle.DISCOVERED
    fidelity: ExecutionFidelity = ExecutionFidelity.NOT_IMPLEMENTED
    targets: list[str] = field(default_factory=list)  # FAKECLOUD, KIND, etc.
    source_type: SourceType = SourceType.BUILTIN
    source: str = ""
    version: str = ""
    discovered_at: str | None = None
    verified_at: str | None = None
    adapter_version: str = ""
    notes: str = ""
    properties_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe_to_execute(self) -> bool:
        return self.lifecycle in (
            CapabilityLifecycle.VERIFIED,
            CapabilityLifecycle.SUPPORTED,
        ) and self.fidelity != ExecutionFidelity.NOT_TESTED

    @property
    def is_discovered_only(self) -> bool:
        return self.lifecycle in (
            CapabilityLifecycle.DISCOVERED,
            CapabilityLifecycle.METADATA_COLLECTED,
            CapabilityLifecycle.UNVERIFIED,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name, "category": self.category,
            "provider": self.provider, "platform": self.platform,
            "resource_type": self.resource_type,
            "lifecycle": self.lifecycle.value,
            "fidelity": self.fidelity.value,
            "targets": self.targets,
            "source_type": self.source_type.value,
            "source": self.source, "version": self.version,
            "discovered_at": self.discovered_at,
            "verified_at": self.verified_at,
            "is_safe_to_execute": self.is_safe_to_execute,
            "notes": self.notes,
        }


class CapabilityRegistry:
    """Central dynamic capability registry."""

    def __init__(self):
        self._entries: dict[str, CapabilityRecord] = {}
        self._seed()

    def _seed(self) -> None:
        """Seed with verified and known capabilities."""
        now = datetime.now(timezone.utc).isoformat()
        seed = [
            # AWS S3 — VERIFIED via fakecloud
            CapabilityRecord(
                capability_id="cap-aws-s3", name="S3", category="STORAGE",
                provider="AWS", resource_type="AWS::S3::Bucket",
                lifecycle=CapabilityLifecycle.VERIFIED,
                fidelity=ExecutionFidelity.SIMULATED,
                targets=["FAKECLOUD"], source_type=SourceType.BUILTIN,
                source="fakecloud v0.44.9", version="1.0",
                discovered_at=now, verified_at=now,
                notes="Verified: create/observe/validate/destroy via fakecloud"),
            CapabilityRecord(
                capability_id="cap-aws-rds", name="RDS", category="DATABASE",
                provider="AWS", resource_type="AWS::RDS::DBInstance",
                lifecycle=CapabilityLifecycle.CAPABILITY_MAPPED,
                fidelity=ExecutionFidelity.PLAN_ONLY,
                targets=["FAKECLOUD"], source_type=SourceType.BUILTIN,
                discovered_at=now, notes="PLAN_ONLY — fakecloud RDS not verified"),
            # Kubernetes — VERIFIED via kind
            CapabilityRecord(
                capability_id="cap-k8s-deployment", name="Deployment", category="COMPUTE",
                provider="ON_PREM", platform="KUBERNETES",
                resource_type="kubernetes_deployment",
                lifecycle=CapabilityLifecycle.VERIFIED,
                fidelity=ExecutionFidelity.LOCAL_RUNTIME,
                targets=["KIND"], source_type=SourceType.BUILTIN,
                source="kind v0.32.0", version="1.0",
                discovered_at=now, verified_at=now,
                notes="Verified: apply/observe/validate via kind"),
            CapabilityRecord(
                capability_id="cap-k8s-service", name="Service", category="NETWORKING",
                provider="ON_PREM", platform="KUBERNETES",
                resource_type="kubernetes_service",
                lifecycle=CapabilityLifecycle.VERIFIED,
                fidelity=ExecutionFidelity.LOCAL_RUNTIME,
                targets=["KIND"], source_type=SourceType.BUILTIN,
                source="kind v0.32.0", discovered_at=now, verified_at=now,
                notes="Verified: ClusterIP service via kind"),
            CapabilityRecord(
                capability_id="cap-k8s-namespace", name="Namespace", category="COMPUTE",
                provider="ON_PREM", platform="KUBERNETES",
                resource_type="kubernetes_namespace",
                lifecycle=CapabilityLifecycle.VERIFIED,
                fidelity=ExecutionFidelity.LOCAL_RUNTIME,
                targets=["KIND"], source_type=SourceType.BUILTIN,
                source="kind v0.32.0", discovered_at=now, verified_at=now,
                notes="Verified: namespace isolation via kind"),
            # OpenShift — model only
            CapabilityRecord(
                capability_id="cap-ocp-deployment", name="Deployment", category="COMPUTE",
                provider="ON_PREM", platform="OPENSHIFT_OCP",
                resource_type="openshift_deployment",
                lifecycle=CapabilityLifecycle.DISCOVERED,
                fidelity=ExecutionFidelity.PLAN_ONLY,
                targets=["CRC_OPENSHIFT"], source_type=SourceType.BUILTIN,
                discovered_at=now, notes="CRC not installed — PLAN_ONLY only"),
            CapabilityRecord(
                capability_id="cap-ocp-route", name="Route", category="NETWORKING",
                provider="ON_PREM", platform="OPENSHIFT_OCP",
                resource_type="openshift_route",
                lifecycle=CapabilityLifecycle.DISCOVERED,
                fidelity=ExecutionFidelity.PLAN_ONLY,
                targets=["CRC_OPENSHIFT"], source_type=SourceType.BUILTIN,
                discovered_at=now, notes="CRC not installed — PLAN_ONLY only"),
            # Minikube — model, optional
            CapabilityRecord(
                capability_id="cap-k8s-minikube-deploy", name="Deployment (minikube)",
                category="COMPUTE", provider="ON_PREM", platform="KUBERNETES",
                resource_type="kubernetes_deployment",
                lifecycle=CapabilityLifecycle.UNVERIFIED,
                fidelity=ExecutionFidelity.NOT_IMPLEMENTED,
                targets=["MINIKUBE"], source_type=SourceType.BUILTIN,
                discovered_at=now, notes="minikube not installed — NOT_IMPLEMENTED"),
            # OpenTofu
            CapabilityRecord(
                capability_id="cap-iac-opentofu", name="OpenTofu IaC Engine",
                category="COMPUTE", provider="AWS", platform="NATIVE_VM",
                resource_type="iac_engine",
                lifecycle=CapabilityLifecycle.VERIFIED,
                fidelity=ExecutionFidelity.SIMULATED,
                targets=["FAKECLOUD"], source_type=SourceType.BUILTIN,
                source="OpenTofu v1.12.5 + AWS provider v5.100.0",
                discovered_at=now, verified_at=now,
                notes="Verified: plan/apply against fakecloud S3"),
        ]
        for entry in seed:
            self._entries[entry.capability_id] = entry

    def register(self, record: CapabilityRecord) -> None:
        self._entries[record.capability_id] = record

    def get(self, capability_id: str) -> CapabilityRecord | None:
        return self._entries.get(capability_id)

    def query(
        self,
        provider: str | None = None,
        platform: str | None = None,
        category: str | None = None,
        lifecycle: CapabilityLifecycle | None = None,
    ) -> list[CapabilityRecord]:
        results = list(self._entries.values())
        if provider:
            results = [r for r in results if r.provider == provider]
        if platform:
            results = [r for r in results if r.platform == platform]
        if category:
            results = [r for r in results if r.category == category]
        if lifecycle:
            results = [r for r in results if r.lifecycle == lifecycle]
        return results

    def get_verified(self) -> list[CapabilityRecord]:
        return [r for r in self._entries.values() if r.lifecycle == CapabilityLifecycle.VERIFIED]

    def get_supported(self) -> list[CapabilityRecord]:
        return [r for r in self._entries.values() if r.lifecycle == CapabilityLifecycle.SUPPORTED]

    def get_safe_to_execute(self) -> list[CapabilityRecord]:
        return [r for r in self._entries.values() if r.is_safe_to_execute]

    def get_all(self) -> list[CapabilityRecord]:
        return list(self._entries.values())

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._entries.values()]
