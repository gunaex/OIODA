"""Infra Pulse — Flow Domain Models.

Phase 5: Professional animated architecture/flow visualization.
Domain model only — no render library dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Enums
# ============================================================================


class FlowType(str, Enum):
    REQUEST = "REQUEST"
    DATA = "DATA"
    AUTH = "AUTH"
    CONTROL = "CONTROL"
    APPROVAL = "APPROVAL"
    OBSERVATION = "OBSERVATION"
    EVENT = "EVENT"
    RESPONSE = "RESPONSE"
    RETRY = "RETRY"


class FlowNodeState(str, Enum):
    IDLE = "IDLE"
    NOT_REACHED = "NOT_REACHED"
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    PASS = "PASS"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"


class FlowEdgeState(str, Enum):
    IDLE = "IDLE"
    FLOWING = "FLOWING"
    SLOW = "SLOW"
    CONGESTED = "CONGESTED"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"


class FlowEventType(str, Enum):
    FLOW_STARTED = "FLOW_STARTED"
    FLOW_COMPLETED = "FLOW_COMPLETED"
    NODE_ENTER = "NODE_ENTER"
    NODE_EXIT = "NODE_EXIT"
    NODE_WAIT = "NODE_WAIT"
    NODE_PASS = "NODE_PASS"
    NODE_BLOCK = "NODE_BLOCK"
    NODE_FAIL = "NODE_FAIL"
    EDGE_FLOW_START = "EDGE_FLOW_START"
    EDGE_FLOW_END = "EDGE_FLOW_END"
    EDGE_CONGESTED = "EDGE_CONGESTED"
    RETRY_START = "RETRY_START"
    RETRY_END = "RETRY_END"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    BOTTLENECK_DETECTED = "BOTTLENECK_DETECTED"


class MetricSource(str, Enum):
    SIMULATED = "SIMULATED"
    ESTIMATED = "ESTIMATED"
    OBSERVED = "OBSERVED"
    IMPORTED = "IMPORTED"


class NodeCategory(str, Enum):
    USER = "USER"
    IDENTITY = "IDENTITY"
    SECURITY = "SECURITY"
    NETWORK = "NETWORK"
    GATEWAY = "GATEWAY"
    APPLICATION = "APPLICATION"
    SERVICE = "SERVICE"
    WORKFLOW = "WORKFLOW"
    DATABASE = "DATABASE"
    STORAGE = "STORAGE"
    QUEUE = "QUEUE"
    CACHE = "CACHE"
    OBSERVABILITY = "OBSERVABILITY"
    EXTERNAL = "EXTERNAL"
    APPROVAL = "APPROVAL"
    PROVIDER = "PROVIDER"
    PLATFORM = "PLATFORM"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DesignStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    REVIEW_READY = "REVIEW_READY"
    USER_REVIEW = "USER_REVIEW"
    CHANGE_REQUESTED = "CHANGE_REQUESTED"
    ACCEPTED = "ACCEPTED"
    BASELINE_FROZEN = "BASELINE_FROZEN"
    DESIGN_CHANGED_AFTER_ACCEPTANCE = "DESIGN_CHANGED_AFTER_ACCEPTANCE"
    READY_FOR_IMPLEMENTATION = "READY_FOR_IMPLEMENTATION"


class SimulationMode(str, Enum):
    DESIGN_SIMULATION = "DESIGN_SIMULATION"
    RUNTIME_REPLAY = "RUNTIME_REPLAY"
    OBSERVED_RUNTIME = "OBSERVED_RUNTIME"


class ScenarioId(str, Enum):
    HAPPY_PATH = "HAPPY_PATH"
    AUTH_FAILURE = "AUTH_FAILURE"
    FIREWALL_BLOCK = "FIREWALL_BLOCK"
    DATABASE_SLOW = "DATABASE_SLOW"
    API_TIMEOUT = "API_TIMEOUT"
    APPROVAL_WAIT = "APPROVAL_WAIT"
    RETRY_RECOVERY = "RETRY_RECOVERY"


# ============================================================================
# Flow Node
# ============================================================================


@dataclass
class FlowNode:
    node_id: str = ""
    label: str = ""
    description: str = ""
    category: NodeCategory = NodeCategory.APPLICATION
    provider: str = ""
    platform: str = ""
    state: FlowNodeState = FlowNodeState.IDLE
    position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    group_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cat = self.category
        cat_val = cat.value if hasattr(cat, 'value') else str(cat)
        return {
            "nodeId": self.node_id, "label": self.label,
            "description": self.description, "category": cat_val,
            "provider": self.provider, "platform": self.platform,
            "state": self.state.value,
            "position": self.position, "groupId": self.group_id,
            "metadata": self.metadata,
        }


# ============================================================================
# Flow Edge
# ============================================================================


@dataclass
class FlowEdge:
    edge_id: str = ""
    source_id: str = ""
    target_id: str = ""
    flow_type: FlowType = FlowType.REQUEST
    state: FlowEdgeState = FlowEdgeState.IDLE
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "edgeId": self.edge_id, "sourceId": self.source_id,
            "targetId": self.target_id, "flowType": self.flow_type.value,
            "state": self.state.value, "label": self.label,
            "metadata": self.metadata,
        }


# ============================================================================
# Flow Metric
# ============================================================================


@dataclass
class FlowMetric:
    name: str = ""
    value: float = 0.0
    unit: str = "ms"
    source: MetricSource = MetricSource.SIMULATED
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "value": self.value, "unit": self.unit,
            "source": self.source.value, "confidence": self.confidence,
        }


# ============================================================================
# Flow Event
# ============================================================================


@dataclass
class FlowEvent:
    event_id: str = ""  # Set deterministically by simulator
    flow_id: str = ""
    timestamp_ms: int = 0
    event_type: FlowEventType = FlowEventType.FLOW_STARTED
    node_id: str = ""
    edge_id: str = ""
    severity: Severity = Severity.INFO
    source: MetricSource = MetricSource.SIMULATED
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id, "flowId": self.flow_id,
            "timestampMs": self.timestamp_ms,
            "eventType": self.event_type.value,
            "nodeId": self.node_id, "edgeId": self.edge_id,
            "severity": self.severity.value,
            "source": self.source.value,
            "message": self.message,
            "metadata": self.metadata,
        }


# ============================================================================
# Flow Definition
# ============================================================================


@dataclass
class FlowDefinition:
    flow_id: str = field(default_factory=lambda: f"flow-{uuid4().hex[:8]}")
    name: str = ""
    flow_type: FlowType = FlowType.REQUEST
    architecture_graph_id: str = ""
    entry_node_id: str = ""
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    scenario: str = ""
    simulation_seed: int = 42
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flowId": self.flow_id, "name": self.name,
            "flowType": self.flow_type.value,
            "architectureGraphId": self.architecture_graph_id,
            "entryNodeId": self.entry_node_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "groups": self.groups,
            "scenario": self.scenario,
            "simulationSeed": self.simulation_seed,
            "metadata": self.metadata,
        }


# ============================================================================
# Bottleneck
# ============================================================================


@dataclass
class FlowBottleneck:
    node_id: str = ""
    score: float | None = None  # 0-100; None if insufficient data
    severity: Severity = Severity.INFO
    factors: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "score": self.score,
            "severity": self.severity.value,
            "factors": self.factors,
            "explanation": self.explanation,
        }


# ============================================================================
# Flow Playback State
# ============================================================================


@dataclass
class FlowPlaybackState:
    flow_id: str = ""
    timestamp_ms: int = 0
    node_states: dict[str, FlowNodeState] = field(default_factory=dict)
    edge_states: dict[str, FlowEdgeState] = field(default_factory=dict)
    active_path: list[str] = field(default_factory=list)
    bottlenecks: list[FlowBottleneck] = field(default_factory=list)
    current_event: FlowEvent | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "flowId": self.flow_id,
            "timestampMs": self.timestamp_ms,
            "nodeStates": {k: v.value for k, v in self.node_states.items()},
            "edgeStates": {k: v.value for k, v in self.edge_states.items()},
            "activePath": self.active_path,
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "currentEvent": self.current_event.to_dict() if self.current_event else None,
        }


# ============================================================================
# Design Baseline
# ============================================================================


@dataclass
class DesignBaseline:
    design_id: str = field(default_factory=lambda: f"DESIGN-{uuid4().hex[:6].upper()}")
    revision: int = 1
    status: DesignStatus = DesignStatus.DRAFT
    requirements_checksum: str = ""
    architecture_checksum: str = ""
    flow_checksum: str = ""
    accepted_at: str = ""
    accepted_by: str = ""
    change_requests: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "designId": self.design_id, "revision": self.revision,
            "status": self.status.value,
            "requirementsChecksum": self.requirements_checksum,
            "architectureChecksum": self.architecture_checksum,
            "flowChecksum": self.flow_checksum,
            "acceptedAt": self.accepted_at,
            "acceptedBy": self.accepted_by,
            "changeRequests": self.change_requests,
            "createdAt": self.created_at,
            "metadata": self.metadata,
        }

    def accept(self, accepted_by: str = "") -> None:
        self.status = DesignStatus.ACCEPTED
        self.status = DesignStatus.BASELINE_FROZEN
        self.accepted_at = datetime.now(timezone.utc).isoformat()
        self.accepted_by = accepted_by

    def request_change(self, comment: str, node_id: str = "", severity: str = "INFO") -> None:
        self.status = DesignStatus.CHANGE_REQUESTED
        self.change_requests.append({
            "comment": comment, "nodeId": node_id,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def check_acceptance_invalidated(
        self, new_req_checksum: str, new_arch_checksum: str, new_flow_checksum: str
    ) -> bool:
        if self.status != DesignStatus.BASELINE_FROZEN:
            return False
        return (
            self.requirements_checksum != new_req_checksum
            or self.architecture_checksum != new_arch_checksum
            or self.flow_checksum != new_flow_checksum
        )
