"""
Platform Adapter Interface for INFRA-AGAIN.

Platform adapters handle the runtime layer:
- Kubernetes
- OpenShift/OCP
- Native/VM

Platform is separate from Provider. OCP is a platform, not a provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..core.domain import ExecutionTarget, Platform, TruthStatus, ValidationResult


@dataclass
class PlatformCapability:
    """A capability provided by a platform runtime."""
    name: str
    version: str | None = None
    features: list[str] = None  # type: ignore[assignment]
    limitations: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.features is None:
            self.features = []
        if self.limitations is None:
            self.limitations = []


class PlatformAdapter(ABC):
    """
    Platform/runtime adapter interface.

    Platform adapters handle the runtime layer (Kubernetes, OCP, Native VM).
    They are independent of the infrastructure provider.
    """

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Which platform this adapter serves."""
        ...

    @abstractmethod
    async def probe_status(self) -> TruthStatus:
        """Truthfully report platform availability."""
        ...

    @abstractmethod
    async def get_capabilities(self) -> list[PlatformCapability]:
        """Return platform runtime capabilities."""
        ...

    @abstractmethod
    async def deploy(
        self,
        target: ExecutionTarget,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Deploy application workload to the platform.

        Returns deployment status and endpoint information.
        """
        ...

    @abstractmethod
    async def observe(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Observe current platform workload state."""
        ...

    @abstractmethod
    async def validate(
        self,
        desired: dict[str, Any],
        observed: dict[str, Any],
    ) -> list[ValidationResult]:
        """Compare desired vs observed platform state."""
        ...

    @abstractmethod
    async def destroy(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Remove application workload from platform.

        Must be gated by policy approval.
        """
        ...
