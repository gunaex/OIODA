"""
Provider-Neutral Architecture Graph Model for INFRA-AGAIN.

Defines ArchitectureGraph, ArchitectureNode, ArchitectureEdge,
and ArchitectureDiff for Before/After infrastructure visualization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class GraphType(str, Enum):
    PROPOSED = "PROPOSED"
    PLANNED = "PLANNED"
    OBSERVED = "OBSERVED"


class NodeStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PLANNED = "PLANNED"
    OBSERVED = "OBSERVED"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"
    NOT_TESTED = "NOT_TESTED"


class DiffAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    UNCHANGED = "UNCHANGED"
    MISSING = "MISSING"
    UNEXPECTED = "UNEXPECTED"
    DRIFT = "DRIFT"


class Relationship(str, Enum):
    REALIZED_AS = "REALIZED_AS"
    DEPENDS_ON = "DEPENDS_ON"
    HOSTS = "HOSTS"
    CONNECTS_TO = "CONNECTS_TO"
    CONTAINS = "CONTAINS"


@dataclass
class ArchitectureNode:
    """A single node in the architecture graph."""
    id: str
    type: str                 # Provider-neutral capability type
    label: str
    provider: str = ""
    platform: str = ""
    capability: str = ""
    status: NodeStatus = NodeStatus.PROPOSED
    managed_by: str = ""
    resource_reference: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitectureEdge:
    """A relationship edge between two nodes."""
    source: str
    target: str
    relationship: Relationship = Relationship.REALIZED_AS


@dataclass
class ArchitectureGraph:
    """Provider-neutral architecture graph."""
    graph_type: GraphType
    nodes: list[ArchitectureNode] = field(default_factory=list)
    edges: list[ArchitectureEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_type": self.graph_type.value,
            "nodes": [
                {
                    "id": n.id, "type": n.type, "label": n.label,
                    "provider": n.provider, "platform": n.platform,
                    "capability": n.capability, "status": n.status.value,
                    "managed_by": n.managed_by, "resource_reference": n.resource_reference,
                    "properties": n.properties,
                }
                for n in self.nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target, "relationship": e.relationship.value}
                for e in self.edges
            ],
            "metadata": self.metadata,
            "generated_at": self.generated_at,
        }


@dataclass
class DiffEntry:
    """A single entry in the architecture diff."""
    node_id: str
    planned_status: NodeStatus | None = None
    observed_status: NodeStatus | None = None
    action: DiffAction = DiffAction.UNCHANGED
    detail: str = ""


@dataclass
class ArchitectureDiff:
    """Before/After architecture comparison."""
    planned_graph: ArchitectureGraph | None = None
    observed_graph: ArchitectureGraph | None = None
    entries: list[DiffEntry] = field(default_factory=list)
    summary: str = ""
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def match_count(self) -> int:
        return sum(1 for e in self.entries if e.action == DiffAction.UNCHANGED)

    @property
    def missing_count(self) -> int:
        return sum(1 for e in self.entries if e.action == DiffAction.MISSING)

    @property
    def unexpected_count(self) -> int:
        return sum(1 for e in self.entries if e.action == DiffAction.UNEXPECTED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [
                {"node_id": e.node_id, "planned_status": e.planned_status.value if e.planned_status else None,
                 "observed_status": e.observed_status.value if e.observed_status else None,
                 "action": e.action.value, "detail": e.detail}
                for e in self.entries
            ],
            "summary": self.summary,
            "match_count": self.match_count,
            "missing_count": self.missing_count,
            "unexpected_count": self.unexpected_count,
            "generated_at": self.generated_at,
        }
