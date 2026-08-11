"""Local target registry + executor registry for Phase 7."""

from __future__ import annotations

import shutil
from typing import Any

from .phase7_models import (
    ExecutionTarget, ExecutionFidelity, ActionType,
)


class LocalExecutionTargetRegistry:
    """Registry of available local execution targets."""

    _targets: dict[str, ExecutionTarget] = {}

    @classmethod
    def register_defaults(cls) -> None:
        cls._targets["plan-only"] = ExecutionTarget(
            target_id="plan-only",
            target_type="PLAN_ONLY",
            fidelity=ExecutionFidelity.PLAN_ONLY,
            endpoint_reference="",
            environment_name="plan-only",
            isolated=True,
            ephemeral=True,
        )
        cls._targets["fakecloud"] = ExecutionTarget(
            target_id="fakecloud",
            target_type="FAKECLOUD",
            provider="AWS",
            fidelity=ExecutionFidelity.SIMULATED,
            endpoint_reference="http://localhost:4566",
            environment_name="fakecloud-local",
            isolated=True,
            ephemeral=True,
            capabilities=["S3_SIMULATED"],
        )
        cls._targets["kind"] = ExecutionTarget(
            target_id="kind",
            target_type="KIND",
            provider="",
            platform="KUBERNETES",
            fidelity=ExecutionFidelity.LOCAL_RUNTIME,
            endpoint_reference="",
            environment_name="kind-local",
            isolated=True,
            ephemeral=True,
            capabilities=["KUBERNETES_LOCAL"],
        )

    @classmethod
    def get(cls, target_id: str) -> ExecutionTarget | None:
        if not cls._targets:
            cls.register_defaults()
        return cls._targets.get(target_id)

    @classmethod
    def list_all(cls) -> list[ExecutionTarget]:
        if not cls._targets:
            cls.register_defaults()
        return list(cls._targets.values())

    @classmethod
    def probe_availability(cls, target_id: str) -> dict[str, Any]:
        target = cls.get(target_id)
        if not target:
            return {"available": False, "reason": "Unknown target"}
        if target_id == "plan-only":
            return {"available": True, "reason": "Always available"}
        if target_id == "fakecloud":
            fc = shutil.which("fakecloud")
            return {"available": bool(fc), "reason": "fakecloud found" if fc else "fakecloud not installed", "binary": fc}
        if target_id == "kind":
            kind = shutil.which("kind")
            kctl = shutil.which("kubectl")
            return {
                "available": bool(kind and kctl),
                "reason": "Ready" if (kind and kctl) else "kind and/or kubectl not installed",
                "kind_binary": kind,
                "kubectl_binary": kctl,
            }
        return {"available": False, "reason": "Unknown target"}


# ===========================================================================
# Executor Abstraction
# ===========================================================================

from abc import ABC, abstractmethod


class ExecutionAdapter(ABC):
    """Abstract executor for a specific target type."""

    @property
    @abstractmethod
    def supported_action_types(self) -> list[ActionType]:
        ...

    @property
    @abstractmethod
    def supported_fidelity(self) -> ExecutionFidelity:
        ...

    @abstractmethod
    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        ...

    @abstractmethod
    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        ...

    @abstractmethod
    async def destroy(self, task: Any, target: ExecutionTarget, correlation_id: str) -> dict[str, Any]:
        """Phase N4 — destroy EXACTLY the resource(s) this task's exact
        correlation_id/task_id created. Never a prefix/wildcard match —
        implementations must derive the exact same identifier execute()
        used, so a resource this run never created can never be touched."""
        ...


class ExecutionAdapterRegistry:
    """Registry mapping target types to executor adapters."""

    _adapters: dict[str, ExecutionAdapter] = {}

    @classmethod
    def register(cls, target_type: str, adapter: ExecutionAdapter) -> None:
        cls._adapters[target_type] = adapter

    @classmethod
    def get(cls, target_type: str) -> ExecutionAdapter | None:
        return cls._adapters.get(target_type)

    @classmethod
    def list_adapters(cls) -> dict[str, list[str]]:
        return {k: [a.value for a in v.supported_action_types] for k, v in cls._adapters.items()}
