"""
Provider Intelligence Interfaces for INFRA-AGAIN.

Dynamic Provider Intelligence ensures the system discovers provider
capabilities from official sources rather than hardcoding them.
The LLM is NOT the authoritative cloud catalog.

Flow:
    Official Provider Sources
            ↓
    Catalog Synchronizer
            ↓
    Raw Provider Metadata
            ↓
    Normalization / Classification
            ↓
    Dynamic Capability Registry
            ↓
    Provider-Neutral Planner + AI Reasoning
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from ..core.domain import Provider


# ---------------------------------------------------------------------------
# Catalog entry types
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"
    THIRD_PARTY_SOURCE = "THIRD_PARTY_SOURCE"
    SIMULATOR = "SIMULATOR"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    REAL_PROVIDER = "REAL_PROVIDER"


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


@dataclass
class CatalogEntry:
    """A single entry in the Dynamic Capability Registry."""
    entry_id: str = field(default_factory=lambda: f"cat-{uuid4().hex[:8]}")
    provider: Provider | None = None
    service_name: str = ""
    resource_type: str = ""
    category: str = ""
    api_version: str | None = None
    region_availability: list[str] = field(default_factory=list)
    properties_schema: dict[str, Any] = field(default_factory=dict)
    pricing_metadata: dict[str, Any] = field(default_factory=dict)
    lifecycle: CatalogLifecycle = CatalogLifecycle.DISCOVERED
    deprecation_date: str | None = None
    source_type: SourceType = SourceType.OFFICIAL_SOURCE
    provenance_url: str = ""
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str = ""
    previous_checksum: str | None = None
    changes_detected: list[str] = field(default_factory=list)


@dataclass
class CatalogSnapshot:
    """A versioned snapshot of the entire capability catalog."""
    snapshot_id: str = field(default_factory=lambda: f"snap-{uuid4().hex[:8]}")
    provider: Provider | None = None
    version: str = "1"
    entries: list[CatalogEntry] = field(default_factory=list)
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_api_version: str | None = None
    checksum: str = ""


# ---------------------------------------------------------------------------
# Catalog Synchronizer interface
# ---------------------------------------------------------------------------


class CatalogSynchronizer(ABC):
    """
    Synchronizes provider capability data from official sources.

    Implementations pull data from:
    - AWS: CloudFormation Registry, Cloud Control API, Pricing API
    - GCP: Service Usage API, Cloud Asset Inventory, Cloud Billing
    - On-Prem: Manual registration or discovery agents
    """

    @abstractmethod
    async def sync(self, provider: Provider) -> CatalogSnapshot:
        """
        Pull latest capability data from official provider sources.

        Returns a versioned snapshot with provenance.
        """
        ...

    @abstractmethod
    async def detect_changes(
        self,
        current: CatalogSnapshot,
        previous: CatalogSnapshot,
    ) -> list[str]:
        """Detect changes between two catalog snapshots."""
        ...

    @abstractmethod
    async def get_provenance(self, entry: CatalogEntry) -> dict[str, Any]:
        """
        Return provenance information for a catalog entry:
        - Source API endpoint
        - Collection timestamp
        - Schema version at collection time
        """
        ...


# ---------------------------------------------------------------------------
# Capability Mapper interface
# ---------------------------------------------------------------------------


class CapabilityMapper(ABC):
    """
    Maps provider-neutral intent to provider-specific resources.

    Input:  { database: { engine: postgresql, availability: production } }
    Output: { aws: RDS, gcp: Cloud SQL, onprem: PostgreSQL VM }
    """

    @abstractmethod
    async def map_requirement(
        self,
        requirement: dict[str, Any],
        provider: Provider,
        catalog: CatalogSnapshot,
    ) -> dict[str, Any] | None:
        """
        Map a provider-neutral requirement to provider-specific resources.

        Returns None if no suitable mapping exists.
        """
        ...

    @abstractmethod
    async def get_alternatives(
        self,
        requirement: dict[str, Any],
        provider: Provider,
        catalog: CatalogSnapshot,
    ) -> list[dict[str, Any]]:
        """Return alternative provider resource options."""
        ...


# ---------------------------------------------------------------------------
# Dynamic Capability Registry interface
# ---------------------------------------------------------------------------


class DynamicCapabilityRegistry(ABC):
    """
    Central registry of provider capabilities.

    All provider capability knowledge flows through this registry.
    The LLM/AI reasons using registry data, not its own memory.
    """

    @abstractmethod
    async def register_entry(self, entry: CatalogEntry) -> None:
        """Register or update a capability entry."""
        ...

    @abstractmethod
    async def get_entry(self, entry_id: str) -> CatalogEntry | None:
        """Retrieve a specific capability entry."""
        ...

    @abstractmethod
    async def query(
        self,
        provider: Provider | None = None,
        category: str | None = None,
        lifecycle: CatalogLifecycle | None = None,
        resource_type: str | None = None,
    ) -> list[CatalogEntry]:
        """Query the registry with filters."""
        ...

    @abstractmethod
    async def get_supported_entries(
        self,
        provider: Provider,
    ) -> list[CatalogEntry]:
        """Get all entries in SUPPORTED lifecycle state."""
        ...

    @abstractmethod
    async def update_lifecycle(
        self,
        entry_id: str,
        lifecycle: CatalogLifecycle,
    ) -> None:
        """Update the lifecycle state of a catalog entry."""
        ...

    @abstractmethod
    async def get_snapshot(self, provider: Provider) -> CatalogSnapshot:
        """Get the current catalog snapshot for a provider."""
        ...
