"""IaC engine abstraction for INFRA-AGAIN."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    """Compute full SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def short_checksum(full: str) -> str:
    """Display-shortened checksum (first 16 chars)."""
    return full[:16] if len(full) >= 16 else full


class IaCStage(str, Enum):
    """Sub-stages within IaC execution."""
    NOT_STARTED = "NOT_STARTED"
    IAC_RENDERED = "IAC_RENDERED"
    IAC_INITIALIZED = "IAC_INITIALIZED"
    IAC_VALIDATED = "IAC_VALIDATED"
    IAC_PLANNED = "IAC_PLANNED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    IAC_APPLYING = "IAC_APPLYING"
    IAC_APPLIED = "IAC_APPLIED"


class IaCEngine(ABC):
    """Abstract IaC execution engine."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        ...

    @abstractmethod
    async def probe(self) -> str | None:
        """Return version string or None if not installed."""
        ...

    @abstractmethod
    async def fmt(self, working_dir: Path) -> IaCResult:
        """Format and check configuration."""
        ...

    @abstractmethod
    async def init(self, working_dir: Path) -> IaCResult:
        """Initialize provider plugins."""
        ...

    @abstractmethod
    async def validate(self, working_dir: Path) -> IaCResult:
        """Validate configuration syntax."""
        ...

    @abstractmethod
    async def plan(self, working_dir: Path, plan_path: Path) -> IaCResult:
        """Generate and save execution plan."""
        ...

    @abstractmethod
    async def apply(self, working_dir: Path, plan_path: Path) -> IaCResult:
        """Apply a saved plan."""
        ...

    @abstractmethod
    async def output(self, working_dir: Path) -> dict[str, Any]:
        """Get outputs as dict."""
        ...

    @abstractmethod
    async def show(self, plan_path: Path) -> dict[str, Any]:
        """Show plan in machine-readable format."""
        ...

    @abstractmethod
    def state_reference(self, working_dir: Path) -> str:
        """Return the path to the IaC state file."""
        ...

    @abstractmethod
    async def destroy(self, working_dir: Path) -> IaCResult:
        """Destroy resources (GATED by policy upstream)."""
        ...


@dataclass
class IaCResult:
    """Result of an IaC engine operation."""
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0


@dataclass
class PlanInfo:
    """Extracted plan metadata."""
    resource_changes: list[dict[str, Any]] = field(default_factory=list)
    create_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    plan_checksum: str = ""
    raw_plan_json: dict[str, Any] | None = None


@dataclass
class PlanIntegrity:
    """Plan integrity metadata for checksum enforcement."""
    plan_artifact_path: str = ""
    plan_sha256: str = ""                # Full SHA-256 of plan artifact file
    approved_plan_sha256: str = ""       # Checksum at approval time
    applied_plan_sha256: str = ""        # Checksum at apply time
    config_checksum: str = ""            # Configuration checksum
    approval_timestamp: str = ""
    integrity_verified: bool = False

    @property
    def checksums_match(self) -> bool:
        """True if the approved plan matches the plan being applied."""
        return bool(
            self.approved_plan_sha256
            and self.approved_plan_sha256 == self.applied_plan_sha256
        )
