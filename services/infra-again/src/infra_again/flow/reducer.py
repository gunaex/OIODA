"""Flow State Reducer.

Derives FlowPlaybackState from FlowDefinition + FlowEvent[] at time T.
Event-sourced — no CSS animation state in backend.
"""

from __future__ import annotations

from .models import (
    FlowDefinition, FlowEvent, FlowEventType, FlowNodeState, FlowEdgeState,
    FlowPlaybackState, FlowBottleneck,
)
from .simulator import FlowSimulator


def reduce_state(
    flow: FlowDefinition,
    events: list[FlowEvent],
    at_timestamp_ms: int = -1,
    bottlenecks: list[FlowBottleneck] | None = None,
) -> FlowPlaybackState:
    """Derive playback state at a given timestamp.

    Args:
        flow: The flow definition
        events: All events for this simulation
        at_timestamp_ms: Timestamp to derive state at (-1 = all events)
        bottlenecks: Pre-computed bottlenecks
    """
    node_states: dict[str, FlowNodeState] = {}
    edge_states: dict[str, FlowEdgeState] = {}
    active_path: list[str] = []
    current_event: FlowEvent | None = None

    # Initialize all nodes as IDLE
    for node in flow.nodes:
        node_states[node.node_id] = FlowNodeState.IDLE

    # Initialize all edges as IDLE
    for edge in flow.edges:
        edge_states[edge.edge_id] = FlowEdgeState.IDLE

    # Replay events up to timestamp
    blocked_node: str | None = None
    last_node: str | None = None

    for evt in events:
        if at_timestamp_ms >= 0 and evt.timestamp_ms > at_timestamp_ms:
            break
        current_event = evt

        if evt.event_type == FlowEventType.FLOW_STARTED:
            pass

        elif evt.event_type == FlowEventType.NODE_ENTER:
            if blocked_node:
                node_states[evt.node_id] = FlowNodeState.NOT_REACHED
            else:
                node_states[evt.node_id] = FlowNodeState.ACTIVE
                active_path.append(evt.node_id)

        elif evt.event_type == FlowEventType.NODE_PASS:
            node_states[evt.node_id] = FlowNodeState.PASS
            # Activate outgoing edges
            for edge in flow.edges:
                if edge.source_id == evt.node_id:
                    edge_states[edge.edge_id] = FlowEdgeState.FLOWING

        elif evt.event_type == FlowEventType.NODE_BLOCK:
            node_states[evt.node_id] = FlowNodeState.BLOCKED
            blocked_node = evt.node_id
            # Mark outgoing edge as BLOCKED
            for edge in flow.edges:
                if edge.source_id == evt.node_id:
                    edge_states[edge.edge_id] = FlowEdgeState.BLOCKED

        elif evt.event_type == FlowEventType.NODE_FAIL:
            node_states[evt.node_id] = FlowNodeState.FAILED
            blocked_node = evt.node_id

        elif evt.event_type == FlowEventType.RETRY_START:
            node_states[evt.node_id] = FlowNodeState.RETRYING

        elif evt.event_type == FlowEventType.RETRY_END:
            pass  # node transitions handled by NODE_PASS after retry

        elif evt.event_type == FlowEventType.APPROVAL_REQUESTED:
            if evt.node_id:
                node_states[evt.node_id] = FlowNodeState.WAITING

        elif evt.event_type == FlowEventType.APPROVAL_GRANTED:
            if evt.node_id:
                node_states[evt.node_id] = FlowNodeState.PASS

        elif evt.event_type == FlowEventType.BOTTLENECK_DETECTED:
            if evt.node_id and node_states.get(evt.node_id) not in (
                FlowNodeState.BLOCKED, FlowNodeState.FAILED
            ):
                node_states[evt.node_id] = FlowNodeState.DEGRADED

        elif evt.event_type == FlowEventType.FLOW_COMPLETED:
            for nid, state in list(node_states.items()):
                if state == FlowNodeState.PASS:
                    node_states[nid] = FlowNodeState.COMPLETED
            for eid, state in list(edge_states.items()):
                if state == FlowEdgeState.FLOWING:
                    edge_states[eid] = FlowEdgeState.COMPLETED

    # For NOT_REACHED nodes downstream of blocked node
    if blocked_node:
        _propagate_not_reached(flow, node_states, edge_states, blocked_node)

    return FlowPlaybackState(
        flow_id=flow.flow_id,
        timestamp_ms=at_timestamp_ms if at_timestamp_ms >= 0 else (events[-1].timestamp_ms if events else 0),
        node_states=node_states,
        edge_states=edge_states,
        active_path=active_path,
        bottlenecks=bottlenecks or [],
        current_event=current_event,
    )


def _propagate_not_reached(
    flow: FlowDefinition,
    node_states: dict[str, FlowNodeState],
    edge_states: dict[str, FlowEdgeState],
    blocked_node: str,
) -> None:
    """Mark downstream nodes/edges as NOT_REACHED."""
    downstream: set[str] = set()
    queue = [blocked_node]
    while queue:
        nid = queue.pop(0)
        for edge in flow.edges:
            if edge.source_id == nid:
                if edge.target_id not in downstream:
                    downstream.add(edge.target_id)
                    queue.append(edge.target_id)
                if edge_states.get(edge.edge_id, FlowEdgeState.IDLE) == FlowEdgeState.IDLE:
                    edge_states[edge.edge_id] = FlowEdgeState.BLOCKED

    for nid in downstream:
        if nid != blocked_node:
            node_states[nid] = FlowNodeState.NOT_REACHED
