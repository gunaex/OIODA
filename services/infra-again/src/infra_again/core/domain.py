"""
Provider-Neutral Domain Model for INFRA-AGAIN.

This module defines the provider-neutral types that Infrastructure Again
uses internally. These are distinct from the canonical contract types
in contracts/__init__.py — those are wire-format adapters.

Key separation:
- Provider (WHERE): AWS, GCP, ON_PREM
- Platform (HOW): KUBERNETES, OPENSHIFT_OCP, NATIVE_VM, BARE_METAL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Provider × Platform Model
# ============================================================================


class Provider(str, Enum):
    """Infrastructure provider (WHERE does this run)."""
    AWS = "AWS"
    GCP = "GCP"
    ON_PREM = "ON_PREM"
    PRIVATE_CLOUD = "PRIVATE_CLOUD"


class Platform(str, Enum):
    """Platform/runtime layer (HOW does this run)."""
    NATIVE_VM = "NATIVE_VM"
    KUBERNETES = "KUBERNETES"
    OPENSHIFT_OCP = "OPENSHIFT_OCP"
    BARE_METAL = "BARE_METAL"


# ============================================================================
# Execution Mode / Fidelity
# ============================================================================


class ExecutionMode(str, Enum):
    """Execution fidelity level — determines blast radius and safety."""
    PLAN_ONLY = "PLAN_ONLY"
    SIMULATED = "SIMULATED"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    LOCAL_PRIVATE_CLOUD = "LOCAL_PRIVATE_CLOUD"
    SANDBOX = "SANDBOX"
    CONTROLLED_REAL = "CONTROLLED_REAL"
    PRODUCTION = "PRODUCTION"


class ExecutionTargetType(str, Enum):
    """Specific execution target identifier."""
    # AWS
    FAKECLOUD = "FAKECLOUD"
    LOCALSTACK = "LOCALSTACK"
    AWS_SANDBOX = "AWS_SANDBOX"
    AWS_PRODUCTION = "AWS_PRODUCTION"

    # GCP
    GCP_EMULATOR = "GCP_EMULATOR"
    FAKE_GCS = "FAKE_GCS"
    GCP_SANDBOX = "GCP_SANDBOX"
    GCP_PRODUCTION = "GCP_PRODUCTION"

    # Kubernetes
    KIND = "KIND"
    MINIKUBE = "MINIKUBE"
    K3S = "K3S"

    # OpenShift
    CRC_OPENSHIFT = "CRC_OPENSHIFT"
    CRC_OKD = "CRC_OKD"
    MICROSHIFT = "MICROSHIFT"

    # Private Cloud
    DEVSTACK = "DEVSTACK"
    OPENSTACK = "OPENSTACK"

    # Virtualization
    VCSIM = "VCSIM"
    VSPHERE = "VSPHERE"
    KVM_LIBVIRT = "KVM_LIBVIRT"
    PROXMOX = "PROXMOX"

    # Generic
    LOCAL_DOCKER = "LOCAL_DOCKER"
    LOCAL_PODMAN = "LOCAL_PODMAN"
    BARE_METAL = "BARE_METAL"


# ============================================================================
# Capability Model
# ============================================================================


class CapabilityCategory(str, Enum):
    COMPUTE = "COMPUTE"
    DATABASE = "DATABASE"
    STORAGE = "STORAGE"
    NETWORKING = "NETWORKING"
    CONTAINER = "CONTAINER"
    SECURITY = "SECURITY"
    OBSERVABILITY = "OBSERVABILITY"
    MESSAGING = "MESSAGING"


class CapabilitySupportLifecycle(str, Enum):
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


@dataclass
class CapabilityRequirement:
    """A provider-neutral capability requirement."""
    category: CapabilityCategory
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityMapping:
    """Maps a provider-neutral requirement to a provider-specific resource."""
    requirement: CapabilityRequirement
    provider: Provider
    resource_type: str
    resource_properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # 0.0–1.0


# ============================================================================
# Execution Target Model
# ============================================================================


@dataclass
class ExecutionTarget:
    """Clean abstraction for where and how infrastructure runs."""
    mode: ExecutionMode
    provider: Provider
    platform: Platform
    target_type: ExecutionTargetType
    endpoint: str | None = None
    capabilities: list[str] = field(default_factory=list)
    fidelity_notes: dict[str, str] = field(default_factory=dict)
    safety_level: int = 0  # 0=PLAN_ONLY, 4=PRODUCTION
    provenance: str | None = None

    @property
    def is_safe(self) -> bool:
        """True if this target has no real infrastructure mutation risk."""
        return self.mode in (
            ExecutionMode.PLAN_ONLY,
            ExecutionMode.SIMULATED,
            ExecutionMode.LOCAL_RUNTIME,
            ExecutionMode.LOCAL_PRIVATE_CLOUD,
        )

    def fidelity_description(self) -> str:
        """Human-readable fidelity status."""
        return "\n".join(f"  {k}: {v}" for k, v in self.fidelity_notes.items())


# ============================================================================
# Infrastructure Plan
# ============================================================================


@dataclass
class InfrastructurePlan:
    """Provider-neutral infrastructure plan."""
    plan_id: str = field(default_factory=lambda: f"plan-{uuid4().hex[:8]}")
    request_id: str = ""
    correlation_id: str = ""
    provider: Provider | None = None
    platform: Platform | None = None
    execution_target: ExecutionTarget | None = None
    capability_mappings: list[CapabilityMapping] = field(default_factory=list)
    estimated_cost: dict[str, Any] = field(default_factory=dict)
    risk_assessment: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved: bool = False


# ============================================================================
# Change Set
# ============================================================================


class ChangeAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    NOOP = "NOOP"


@dataclass
class ChangeItem:
    """A single infrastructure change."""
    action: ChangeAction
    resource_type: str
    resource_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    is_destructive: bool = False


@dataclass
class ChangeSet:
    """Collection of infrastructure changes with safety metadata."""
    changes: list[ChangeItem] = field(default_factory=list)
    provider: Provider | None = None
    platform: Platform | None = None
    iac_tool: str | None = None

    @property
    def has_destructive_changes(self) -> bool:
        return any(c.is_destructive for c in self.changes)

    @property
    def summary(self) -> str:
        creates = sum(1 for c in self.changes if c.action == ChangeAction.CREATE)
        updates = sum(1 for c in self.changes if c.action == ChangeAction.UPDATE)
        deletes = sum(1 for c in self.changes if c.action == ChangeAction.DELETE)
        return f"Create={creates} Update={updates} Delete={deletes}"


# ============================================================================
# Execution State Machine
# ============================================================================


class ExecutionState(str, Enum):
    """Explicit persisted execution states."""
    DRAFT = "DRAFT"
    NORMALIZING = "NORMALIZING"
    PLANNING = "PLANNING"
    PLAN_READY = "PLAN_READY"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"


# Legal state transitions
VALID_TRANSITIONS: dict[ExecutionState, set[ExecutionState]] = {
    ExecutionState.DRAFT: {ExecutionState.NORMALIZING, ExecutionState.CANCELLED},
    ExecutionState.NORMALIZING: {ExecutionState.PLANNING, ExecutionState.FAILED, ExecutionState.CANCELLED},
    ExecutionState.PLANNING: {ExecutionState.PLAN_READY, ExecutionState.FAILED, ExecutionState.CANCELLED},
    ExecutionState.PLAN_READY: {ExecutionState.WAITING_FOR_APPROVAL, ExecutionState.FAILED, ExecutionState.CANCELLED, ExecutionState.COMPLETED},  # COMPLETED for PLAN_ONLY
    ExecutionState.WAITING_FOR_APPROVAL: {ExecutionState.APPROVED, ExecutionState.BLOCKED, ExecutionState.CANCELLED},
    ExecutionState.APPROVED: {ExecutionState.EXECUTING, ExecutionState.CANCELLED},
    ExecutionState.EXECUTING: {ExecutionState.OBSERVING, ExecutionState.FAILED, ExecutionState.BLOCKED, ExecutionState.REQUIRES_RECONCILIATION},
    ExecutionState.OBSERVING: {ExecutionState.VALIDATING, ExecutionState.FAILED, ExecutionState.BLOCKED},
    ExecutionState.VALIDATING: {ExecutionState.COMPLETED, ExecutionState.FAILED},
    ExecutionState.COMPLETED: set(),  # Terminal
    ExecutionState.FAILED: {ExecutionState.DRAFT},  # Can retry from DRAFT
    ExecutionState.BLOCKED: {ExecutionState.DRAFT, ExecutionState.CANCELLED},
    ExecutionState.CANCELLED: set(),  # Terminal
    ExecutionState.REQUIRES_RECONCILIATION: {ExecutionState.OBSERVING, ExecutionState.CANCELLED},
}


def can_transition(from_state: ExecutionState, to_state: ExecutionState) -> bool:
    """Check if a state transition is legal."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())


# ============================================================================
# Resource Ownership Model
# ============================================================================


class TargetScope(str, Enum):
    """Ownership scope for infrastructure resources."""
    ISOLATED = "ISOLATED"    # Created solely for this run, disposable
    SHARED = "SHARED"        # Shared infrastructure (existing clusters, DBs)
    EXTERNAL = "EXTERNAL"    # External/customer resources
    UNKNOWN = "UNKNOWN"      # Ownership cannot be determined


@dataclass
class ResourceOwnership:
    """Explicit resource ownership metadata."""
    managed_by: str = "INFRA_AGAIN"
    created_by_run_id: str = ""
    ephemeral: bool = True
    target_scope: TargetScope = TargetScope.ISOLATED

    def is_auto_destroy_allowed(self, current_run_id: str) -> bool:
        """AUTO destroy allowed only for owned, ephemeral, isolated resources from the same run."""
        return (
            self.managed_by == "INFRA_AGAIN"
            and self.created_by_run_id == current_run_id
            and self.ephemeral is True
            and self.target_scope == TargetScope.ISOLATED
        )


@dataclass
class OwnedResource:
    """A resource with ownership tracking."""
    resource_id: str
    resource_type: str
    provider: str
    ownership: ResourceOwnership = field(default_factory=ResourceOwnership)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Runtime Truth Status
# ============================================================================


class TruthStatus(str, Enum):
    """Truthful runtime states — no fake success."""
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_INSTALLED = "NOT_INSTALLED"
    OFFLINE = "OFFLINE"
    UNAVAILABLE = "UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_FAILED = "AUTH_FAILED"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIED = "UNVERIFIED"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    BLOCKED_BY_AIRLOCK = "BLOCKED_BY_AIRLOCK"
    REMOTE_ERROR = "REMOTE_ERROR"
    READY = "READY"


# ============================================================================
# Validation
# ============================================================================


@dataclass
class ValidationResult:
    """Result of observing actual infrastructure state vs desired."""
    resource_id: str
    desired_state: dict[str, Any]
    observed_state: dict[str, Any] | None = None
    matches: bool | None = None
    drift_detected: bool = False
    drift_details: str = ""
    observed_at: datetime | None = None


# ============================================================================
# Evidence
# ============================================================================


@dataclass
class Evidence:
    """Execution evidence record."""
    evidence_id: str = field(default_factory=lambda: f"ev-{uuid4().hex[:8]}")
    correlation_id: str = ""
    request_snapshot: dict[str, Any] | None = None
    normalized_intent: dict[str, Any] | None = None
    provider_catalog_version: str | None = None
    plan: InfrastructurePlan | None = None
    policy_decision: str | None = None
    approval: str | None = None
    iac_plan: str | None = None
    execution_logs: list[str] = field(default_factory=list)
    exit_codes: dict[str, int] = field(default_factory=dict)
    observed_resources: list[dict[str, Any]] = field(default_factory=list)
    validation_results: list[ValidationResult] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    platform_metadata: dict[str, Any] = field(default_factory=dict)
    execution_target: ExecutionTarget | None = None
    execution_fidelity: ExecutionMode | None = None
    timestamps: dict[str, datetime] = field(default_factory=dict)
    readiness_level: str = ""

    def to_canonical_evidence_items(self) -> list[dict[str, Any]]:
        """Convert to canonical InfrastructureResult evidence items."""
        items: list[dict[str, Any]] = []
        if self.plan:
            items.append({
                "type": "ARCHITECTURE_PLAN",
                "source": "infrastructure-again",
                "reference": self.plan.plan_id,
                "summary": f"Plan for {self.plan.provider}/{self.plan.platform}",
                "timestamp": self.plan.created_at.isoformat() if self.plan.created_at else None,
            })
        if self.iac_plan:
            items.append({
                "type": "IAC_OUTPUT",
                "source": "infrastructure-again",
                "reference": self.evidence_id,
                "summary": self.iac_plan[:200],
            })
        if self.validation_results:
            items.append({
                "type": "VALIDATION_RESULTS",
                "source": "infrastructure-again",
                "reference": self.evidence_id,
                "summary": f"{len(self.validation_results)} resources validated",
            })
        return items
