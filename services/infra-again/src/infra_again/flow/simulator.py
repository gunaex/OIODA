"""Deterministic Flow Simulator.

Same flow + scenario + seed → identical event sequence.
No LLM used for event generation.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone

from .models import (
    FlowDefinition, FlowEvent, FlowEventType, FlowNodeState, FlowEdgeState,
    FlowBottleneck, Severity, MetricSource, ScenarioId, FlowNode, FlowEdge,
    FlowType, FlowMetric, FlowPlaybackState, NodeCategory,
)


# ============================================================================
# Scenario configuration
# ============================================================================

SCENARIO_CONFIG: dict[str, dict] = {
    ScenarioId.HAPPY_PATH.value: {
        "description": "All nodes pass, flow completes successfully",
        "node_outcomes": {},  # Empty = all PASS
        "bottleneck": None,
    },
    ScenarioId.AUTH_FAILURE.value: {
        "description": "Credential validation fails at identity gate",
        "node_outcomes": {"credential-gate": "BLOCKED"},
        "bottleneck": None,
    },
    ScenarioId.FIREWALL_BLOCK.value: {
        "description": "Firewall blocks the request",
        "node_outcomes": {"firewall": "BLOCKED"},
        "bottleneck": None,
    },
    ScenarioId.DATABASE_SLOW.value: {
        "description": "Database responds slowly, bottleneck detected",
        "node_outcomes": {"postgresql": "DEGRADED"},
        "bottleneck": {
            "node_id": "postgresql",
            "severity": "HIGH",
            "latency_ms": 650,
            "explanation": "Database represents 72% of simulated end-to-end latency.",
        },
    },
    ScenarioId.API_TIMEOUT.value: {
        "description": "API gateway times out, retry may occur",
        "node_outcomes": {"api-gateway": "FAILED"},
        "bottleneck": None,
    },
    ScenarioId.APPROVAL_WAIT.value: {
        "description": "Flow pauses at approval gate, then continues",
        "node_outcomes": {"approval-gate": "WAITING"},
        "bottleneck": None,
    },
    ScenarioId.RETRY_RECOVERY.value: {
        "description": "First attempt fails transiently, retry succeeds",
        "node_outcomes": {"application-service": "RETRYING"},
        "bottleneck": None,
    },
}


# ============================================================================
# Default demo flow
# ============================================================================

def create_demo_flow() -> FlowDefinition:
    """Create the 'Customer API Request' demo flow."""
    nodes = [
        FlowNode(node_id="user", label="User", description="End user / client",
                 category=NodeCategory.USER),
        FlowNode(node_id="credential-gate", label="Credential Gate",
                 description="Validates user credentials",
                 category=NodeCategory.IDENTITY, provider="AWS"),
        FlowNode(node_id="waf", label="WAF",
                 description="Web Application Firewall",
                 category=NodeCategory.SECURITY, provider="AWS"),
        FlowNode(node_id="firewall", label="Firewall",
                 description="Network firewall policy enforcement",
                 category=NodeCategory.SECURITY),
        FlowNode(node_id="api-gateway", label="API Gateway",
                 description="Entry point for application requests",
                 category=NodeCategory.GATEWAY, provider="AWS"),
        FlowNode(node_id="application-service", label="Application Service",
                 description="Core business application",
                 category=NodeCategory.APPLICATION),
        FlowNode(node_id="postgresql", label="PostgreSQL",
                 description="Stores application business data",
                 category=NodeCategory.DATABASE, provider="AWS"),
        FlowNode(node_id="approval-gate", label="Approval Gate",
                 description="Human approval checkpoint",
                 category=NodeCategory.APPROVAL),
    ]
    edges = [
        FlowEdge(edge_id="e-user-auth", source_id="user", target_id="credential-gate",
                 flow_type=FlowType.AUTH, label="Credentials"),
        FlowEdge(edge_id="e-auth-waf", source_id="credential-gate", target_id="waf",
                 flow_type=FlowType.REQUEST, label="Validated"),
        FlowEdge(edge_id="e-waf-fw", source_id="waf", target_id="firewall",
                 flow_type=FlowType.REQUEST, label="Passed"),
        FlowEdge(edge_id="e-fw-api", source_id="firewall", target_id="api-gateway",
                 flow_type=FlowType.REQUEST, label="Allowed"),
        FlowEdge(edge_id="e-api-app", source_id="api-gateway", target_id="application-service",
                 flow_type=FlowType.REQUEST, label="Routed"),
        FlowEdge(edge_id="e-app-db", source_id="application-service", target_id="postgresql",
                 flow_type=FlowType.DATA, label="Query"),
        FlowEdge(edge_id="e-app-approval", source_id="application-service", target_id="approval-gate",
                 flow_type=FlowType.APPROVAL, label="Requires"),
    ]
    groups = [
        {"groupId": "public-zone", "label": "Public Internet", "type": "SECURITY_BOUNDARY"},
        {"groupId": "edge-security", "label": "Edge Security", "type": "SECURITY_BOUNDARY"},
        {"groupId": "private-zone", "label": "Private Network", "type": "SECURITY_BOUNDARY"},
        {"groupId": "data-zone", "label": "Data Layer", "type": "SECURITY_BOUNDARY"},
    ]
    return FlowDefinition(
        name="Customer API Request",
        flow_type=FlowType.REQUEST,
        entry_node_id="user",
        nodes=nodes, edges=edges, groups=groups,
    )


# ============================================================================
# Deterministic Simulator
# ============================================================================


class FlowSimulator:
    """Deterministic flow event generator.

    Same flow + scenario + seed → identical event sequence.
    """

    def __init__(self, flow: FlowDefinition, scenario: str, seed: int | None = None):
        self.flow = flow
        self.scenario = scenario
        self.seed = seed if seed is not None else flow.simulation_seed
        self._rng = random.Random(self.seed)
        self.events: list[FlowEvent] = []
        self._t_ms = 0
        self._seq = 0
        self._config = SCENARIO_CONFIG.get(scenario, SCENARIO_CONFIG[ScenarioId.HAPPY_PATH.value])

    def simulate(self) -> list[FlowEvent]:
        """Generate the full event sequence."""
        self.events = []
        self._t_ms = 0

        config = self._config
        node_outcomes = config.get("node_outcomes", {})

        # Build topological path from entry
        path = self._build_path()
        blocked_node = None

        self._emit(FlowEventType.FLOW_STARTED, message=f"Flow started: {self.flow.name} [{self.scenario}]")

        for node_id in path:
            node = self._get_node(node_id)
            if not node:
                continue

            # If a blocking node was encountered upstream, mark NOT_REACHED
            if blocked_node:
                self._emit(FlowEventType.NODE_ENTER, node_id=node_id,
                           message=f"NOT_REACHED: blocked upstream at {blocked_node}", severity=Severity.INFO)
                continue

            outcome = node_outcomes.get(node_id)

            # Special handling for approval wait
            if outcome == "WAITING" and self.scenario == ScenarioId.APPROVAL_WAIT.value:
                self._emit(FlowEventType.NODE_ENTER, node_id=node_id,
                           message=f"Entered {node.label}")
                self._advance(200)
                self._emit(FlowEventType.APPROVAL_REQUESTED, node_id=node_id,
                           message="Approval required", severity=Severity.WARNING)
                self._advance(500)
                self._emit(FlowEventType.APPROVAL_GRANTED, node_id=node_id,
                           message="Approval granted")
                self._emit(FlowEventType.NODE_PASS, node_id=node_id,
                           message=f"{node.label}: PASS (approved)")
                continue

            # Special handling for retry
            if outcome == "RETRYING" and self.scenario == ScenarioId.RETRY_RECOVERY.value:
                self._emit(FlowEventType.NODE_ENTER, node_id=node_id,
                           message=f"Entered {node.label}")
                self._advance(100)
                self._emit(FlowEventType.NODE_FAIL, node_id=node_id,
                           message=f"{node.label}: transient failure", severity=Severity.WARNING)
                self._emit(FlowEventType.RETRY_START, node_id=node_id,
                           message="Initiating retry...")
                self._advance(300)
                self._emit(FlowEventType.RETRY_END, node_id=node_id,
                           message="Retry succeeded")
                self._emit(FlowEventType.NODE_PASS, node_id=node_id,
                           message=f"{node.label}: PASS (after retry)")
                continue

            # Normal flow
            self._emit(FlowEventType.NODE_ENTER, node_id=node_id,
                       message=f"Entered {node.label}")
            self._advance(50 + self._rng.randint(0, 100))

            if outcome == "BLOCKED":
                self._emit(FlowEventType.NODE_BLOCK, node_id=node_id,
                           message=f"{node.label}: BLOCKED", severity=Severity.CRITICAL)
                blocked_node = node_id
                continue
            elif outcome == "FAILED":
                self._emit(FlowEventType.NODE_FAIL, node_id=node_id,
                           message=f"{node.label}: FAILED", severity=Severity.HIGH)
                blocked_node = node_id
                continue
            elif outcome == "DEGRADED":
                self._advance(500)  # extra latency
                self._emit(FlowEventType.NODE_PASS, node_id=node_id,
                           message=f"{node.label}: PASS (degraded, +500ms)", severity=Severity.WARNING)
                # Check bottleneck
                bottleneck_cfg = config.get("bottleneck")
                if bottleneck_cfg and bottleneck_cfg.get("node_id") == node_id:
                    self._emit(FlowEventType.BOTTLENECK_DETECTED, node_id=node_id,
                               message=bottleneck_cfg.get("explanation", ""),
                               severity=Severity.HIGH)
            else:
                self._emit(FlowEventType.NODE_PASS, node_id=node_id,
                           message=f"{node.label}: PASS")

        self._advance(50)
        self._emit(FlowEventType.FLOW_COMPLETED,
                   message=f"Flow completed [{self.scenario}]"
                   if not blocked_node else f"Flow terminated early at {blocked_node}")

        return self.events

    def _build_path(self) -> list[str]:
        """Build topological path from entry following edges."""
        path: list[str] = []
        visited: set[str] = set()
        queue = [self.flow.entry_node_id]

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            path.append(node_id)
            for edge in self.flow.edges:
                if edge.source_id == node_id:
                    if edge.target_id not in visited:
                        queue.append(edge.target_id)

        return path

    def _get_node(self, node_id: str) -> FlowNode | None:
        for n in self.flow.nodes:
            if n.node_id == node_id:
                return n
        return None

    def _advance(self, ms: int) -> None:
        self._t_ms += ms

    def _emit(self, event_type: FlowEventType, node_id: str = "", edge_id: str = "",
              message: str = "", severity: Severity = Severity.INFO) -> None:
        self._seq += 1
        evt_id = f"evt-{self.flow.flow_id[:8]}-{self.scenario}-{self.seed}-{self._seq:04d}"
        evt = FlowEvent(
            event_id=evt_id,
            flow_id=self.flow.flow_id,
            timestamp_ms=self._t_ms,
            event_type=event_type,
            node_id=node_id,
            edge_id=edge_id,
            severity=severity,
            source=MetricSource.SIMULATED,
            message=message,
        )
        self.events.append(evt)

    def get_bottlenecks(self) -> list[FlowBottleneck]:
        """Compute bottlenecks from simulation config."""
        bottlenecks: list[FlowBottleneck] = []
        b_cfg = self._config.get("bottleneck")
        if b_cfg:
            bottlenecks.append(FlowBottleneck(
                node_id=b_cfg["node_id"],
                score=82.0,
                severity=Severity(b_cfg.get("severity", "HIGH")),
                factors=[{
                    "type": "LATENCY",
                    "value": b_cfg.get("latency_ms", 650),
                    "source": "SIMULATED",
                }],
                explanation=b_cfg.get("explanation", ""),
            ))
        return bottlenecks
