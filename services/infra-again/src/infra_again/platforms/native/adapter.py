"""
Native/VM Platform Adapter — PLAN_ONLY stub.

Full Native/VM adapter to be implemented in Phase 2+.
"""

from __future__ import annotations

from typing import Any

from ...core.domain import ExecutionTarget, Platform, TruthStatus, ValidationResult
from ..interface import PlatformAdapter, PlatformCapability


class NativeVMPlatformAdapter(PlatformAdapter):
    """Native/VM Platform Adapter — PLAN_ONLY stub."""

    @property
    def platform(self) -> Platform:
        return Platform.NATIVE_VM

    async def probe_status(self) -> TruthStatus:
        return TruthStatus.NOT_CONFIGURED

    async def get_capabilities(self) -> list[PlatformCapability]:
        return []

    async def deploy(self, target: ExecutionTarget, manifest: dict[str, Any]) -> dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED", "note": "NativeVM adapter: PLAN_ONLY stub"}

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED"}

    async def validate(self, desired: dict[str, Any], observed: dict[str, Any]) -> list[ValidationResult]:
        return []

    async def destroy(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        return {"status": "NOT_IMPLEMENTED"}
