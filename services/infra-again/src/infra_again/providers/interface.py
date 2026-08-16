"""
Provider Adapter Interface for INFRA-AGAIN.

Defines the provider-neutral adapter interface that all provider
implementations (AWS, GCP, On-Prem) must conform to.

Provider adapters MUST NOT contain destructive execution logic that
bypasses the policy/safety gate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..core.domain import (
    CapabilityMapping,
    CapabilityRequirement,
    ChangeSet,
    ExecutionTarget,
    InfrastructurePlan,
    Provider,
    TruthStatus,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Provider capability entry
# ---------------------------------------------------------------------------


@dataclass
class ProviderCapability:
    """A single capability entry in the provider catalog."""
    capability_id: str
    provider: Provider
    resource_type: str
    category: str
    properties_schema: dict[str, Any]
    region_availability: list[str] = None  # type: ignore[assignment]
    lifecycle: str = "DISCOVERED"
    deprecation_date: str | None = None
    api_version: str | None = None
    provenance_url: str | None = None
    collected_at: str | None = None

    def __post_init__(self):
        if self.region_availability is None:
            self.region_availability = []


# ---------------------------------------------------------------------------
# Provider adapter interface
# ---------------------------------------------------------------------------


class ProviderAdapter(ABC):
    """
    Provider-neutral adapter interface.

    All provider implementations (AWS, GCP, On-Prem) implement this.
    Destructive methods (apply, destroy) must not execute unless
    policy approval has been granted upstream.
    """

    @property
    @abstractmethod
    def provider(self) -> Provider:
        """Which provider this adapter serves."""
        ...

    @abstractmethod
    async def discover(self, target: ExecutionTarget) -> dict[str, Any]:
        """
        Discover current infrastructure state.

        Returns observed state, never fabricated data.
        Must return TruthStatus.NOT_CONFIGURED if credentials missing.
        """
        ...

    @abstractmethod
    async def plan(
        self,
        requirements: list[CapabilityRequirement],
        target: ExecutionTarget,
    ) -> InfrastructurePlan:
        """
        Generate a provider-specific plan from provider-neutral requirements.

        Maps capabilities to provider resources.
        Does NOT apply changes.
        """
        ...

    @abstractmethod
    async def validate_plan(self, plan: InfrastructurePlan) -> list[str]:
        """
        Validate a plan against provider constraints.

        Returns list of validation warnings/errors (empty = valid).
        """
        ...

    @abstractmethod
    async def apply(
        self,
        plan: InfrastructurePlan,
        target: ExecutionTarget,
    ) -> ChangeSet:
        """
        Execute the plan against the provider.

        WARNING: This method MUST be gated by policy approval.
        Must be safe to call in PLAN_ONLY mode (returns empty ChangeSet).
        """
        ...

    @abstractmethod
    async def observe(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Observe actual infrastructure state post-execution.

        Returns observed state keyed by resource identifier.
        """
        ...

    @abstractmethod
    async def validate(
        self,
        desired: dict[str, Any],
        observed: dict[str, Any],
    ) -> list[ValidationResult]:
        """
        Compare desired vs observed state.

        Returns validation results with drift detection.
        """
        ...

    @abstractmethod
    async def destroy(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> ChangeSet:
        """
        Destroy infrastructure resources.

        CRITICAL: BLOCKED by default — requires explicit policy approval.
        Must not execute without AIRLOCK clearance.
        """
        ...

    @abstractmethod
    async def probe_status(self) -> TruthStatus:
        """
        Truthfully report provider connection/availability status.

        Never return READY unless the provider is genuinely reachable
        and authenticated.
        """
        ...

    @abstractmethod
    async def get_capabilities(self) -> list[ProviderCapability]:
        """
        Return the provider's currently known capabilities.

        These should come from the Dynamic Capability Registry,
        not hardcoded values.
        """
        ...

    @abstractmethod
    async def map_capability(
        self,
        requirement: CapabilityRequirement,
    ) -> CapabilityMapping | None:
        """
        Map a provider-neutral requirement to a provider-specific resource.

        Returns None if no suitable mapping exists.
        """
        ...
