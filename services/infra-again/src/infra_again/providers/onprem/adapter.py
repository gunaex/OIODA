"""
On-Prem Provider Adapter — PLAN_ONLY stub.

Full On-Prem adapter to be implemented in Phase 2+.
Currently supports PLAN_ONLY mode only.
"""

from __future__ import annotations

from typing import Any

from ...core.domain import (
    CapabilityMapping,
    CapabilityRequirement,
    ChangeSet,
    ExecutionMode,
    ExecutionTarget,
    InfrastructurePlan,
    Provider,
    TruthStatus,
    ValidationResult,
)
from ..interface import ProviderAdapter, ProviderCapability


class OnPremProviderAdapter(ProviderAdapter):
    """On-Prem Provider Adapter — PLAN_ONLY stub."""

    @property
    def provider(self) -> Provider:
        return Provider.ON_PREM

    async def discover(self, target: ExecutionTarget) -> dict[str, Any]:
        return {"status": TruthStatus.NOT_CONFIGURED.value, "note": "OnPrem adapter: PLAN_ONLY stub"}

    async def plan(self, requirements: list[CapabilityRequirement], target: ExecutionTarget) -> InfrastructurePlan:
        return InfrastructurePlan(provider=Provider.ON_PREM, platform=target.platform, execution_target=target)

    async def validate_plan(self, plan: InfrastructurePlan) -> list[str]:
        return []

    async def apply(self, plan: InfrastructurePlan, target: ExecutionTarget) -> ChangeSet:
        if target.mode == ExecutionMode.PLAN_ONLY:
            return ChangeSet(provider=Provider.ON_PREM)
        return ChangeSet(provider=Provider.ON_PREM)

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED"}

    async def validate(self, desired: dict[str, Any], observed: dict[str, Any]) -> list[ValidationResult]:
        return []

    async def destroy(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> ChangeSet:
        return ChangeSet(provider=Provider.ON_PREM)

    async def probe_status(self) -> TruthStatus:
        return TruthStatus.NOT_CONFIGURED

    async def get_capabilities(self) -> list[ProviderCapability]:
        return []

    async def map_capability(self, requirement: CapabilityRequirement) -> CapabilityMapping | None:
        return None
