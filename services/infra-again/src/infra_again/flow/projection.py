"""Flow Projections — derive HIGH_LEVEL, DETAILED, SECURITY, DATA views.

All projections derive from the same FlowDefinition.
No semantic facts are invented — only filtered/reorganized.
"""

from __future__ import annotations

from .models import FlowDefinition, FlowNode, FlowEdge, FlowType, NodeCategory, FlowNodeState, FlowEdgeState


# Security-relevant node IDs in the demo flow
SECURITY_NODES = {"credential-gate", "waf", "firewall"}
APPROVAL_NODES = {"approval-gate"}

# High-level groups
HIGH_LEVEL_GROUPS = [
    {"id": "security-layer", "label": "Security Layer", "members": {"credential-gate", "waf", "firewall"}},
    {"id": "api-layer", "label": "API Layer", "members": {"api-gateway"}},
    {"id": "application-layer", "label": "Application Layer", "members": {"application-service", "approval-gate"}},
    {"id": "data-layer", "label": "Data Layer", "members": {"postgresql"}},
]


def project_high_level(flow: FlowDefinition) -> FlowDefinition:
    """Collapse groups into summary nodes. One node per logical layer."""
    nodes = []
    for grp in HIGH_LEVEL_GROUPS:
        members_in_flow = [n for n in flow.nodes if n.node_id in grp["members"]]
        if not members_in_flow:
            continue
        nodes.append(FlowNode(
            node_id=grp["id"],
            label=grp["label"],
            description=f'{len(members_in_flow)} components',
            category=NodeCategory.SERVICE,
            state=FlowNodeState.IDLE,
        ))

    # Build edges between adjacent groups
    edges = []
    node_ids = [n.node_id for n in nodes]
    for i in range(len(node_ids) - 1):
        edges.append(FlowEdge(
            edge_id=f"hl-e-{node_ids[i]}-{node_ids[i+1]}",
            source_id=node_ids[i],
            target_id=node_ids[i + 1],
            flow_type=FlowType.REQUEST,
            state=FlowEdgeState.IDLE,
        ))

    # Keep user as entry
    user_node = next((n for n in flow.nodes if n.node_id == "user"), None)
    if user_node and nodes:
        edges.insert(0, FlowEdge(
            edge_id="hl-e-user-security",
            source_id="user", target_id=nodes[0].node_id,
            flow_type=FlowType.REQUEST, state=FlowEdgeState.IDLE,
        ))
        nodes.insert(0, FlowNode(
            node_id="user", label="User", description="End user",
            category=NodeCategory.USER, state=FlowNodeState.IDLE,
        ))

    return FlowDefinition(
        flow_id=f"{flow.flow_id}-high",
        name=f"{flow.name} (High-Level)",
        flow_type=flow.flow_type,
        architecture_graph_id=flow.architecture_graph_id,
        entry_node_id="user",
        nodes=nodes, edges=edges,
        groups=[{"groupId": g["id"], "label": g["label"], "type": "LOGICAL_GROUP"} for g in HIGH_LEVEL_GROUPS if any(n.node_id in g["members"] for n in flow.nodes)],
    )


def project_detailed(flow: FlowDefinition) -> FlowDefinition:
    """Return the full detailed flow — original graph, no changes."""
    return FlowDefinition(
        flow_id=f"{flow.flow_id}-detail",
        name=f"{flow.name} (Detailed)",
        flow_type=flow.flow_type,
        architecture_graph_id=flow.architecture_graph_id,
        entry_node_id=flow.entry_node_id,
        nodes=list(flow.nodes),
        edges=list(flow.edges),
        groups=list(flow.groups) if flow.groups else [],
    )


def project_security(flow: FlowDefinition) -> FlowDefinition:
    """Highlight security-relevant nodes. Keep all nodes but mark emphasis."""
    nodes = []
    for n in flow.nodes:
        emphasis = n.node_id in SECURITY_NODES or n.node_id in APPROVAL_NODES
        nodes.append(FlowNode(
            node_id=n.node_id, label=n.label, description=n.description,
            category=n.category, provider=n.provider,
            state=FlowNodeState.IDLE,
            metadata={"emphasis": "SECURITY" if emphasis else "DIM"},
        ))

    edges = []
    for e in flow.edges:
        is_security = (e.source_id in SECURITY_NODES or e.target_id in SECURITY_NODES or
                       e.source_id in APPROVAL_NODES or e.target_id in APPROVAL_NODES)
        edges.append(FlowEdge(
            edge_id=e.edge_id, source_id=e.source_id, target_id=e.target_id,
            flow_type=e.flow_type, state=FlowEdgeState.IDLE,
            metadata={"emphasis": "SECURITY" if is_security else "DIM"},
        ))

    return FlowDefinition(
        flow_id=f"{flow.flow_id}-security",
        name=f"{flow.name} (Security)",
        flow_type=flow.flow_type,
        architecture_graph_id=flow.architecture_graph_id,
        entry_node_id=flow.entry_node_id,
        nodes=nodes, edges=edges,
        groups=[{"groupId": "security-zone", "label": "Security Boundary", "type": "SECURITY_BOUNDARY"}],
    )


def project_data(flow: FlowDefinition) -> FlowDefinition:
    """Highlight DATA edges. Dim non-data flows."""
    nodes = list(flow.nodes)
    edges = []
    for e in flow.edges:
        is_data = e.flow_type == FlowType.DATA
        edges.append(FlowEdge(
            edge_id=e.edge_id, source_id=e.source_id, target_id=e.target_id,
            flow_type=e.flow_type, state=FlowEdgeState.IDLE,
            metadata={"emphasis": "DATA" if is_data else "DIM"},
        ))

    return FlowDefinition(
        flow_id=f"{flow.flow_id}-data",
        name=f"{flow.name} (Data Flow)",
        flow_type=flow.flow_type,
        architecture_graph_id=flow.architecture_graph_id,
        entry_node_id=flow.entry_node_id,
        nodes=nodes, edges=edges,
        groups=[{"groupId": "data-layer", "label": "Data Layer", "type": "DATA_ZONE"}],
    )


def generate_large_graph(node_count: int = 100, edge_count: int = 200) -> FlowDefinition:
    """Generate a deterministic synthetic graph for performance testing."""
    import hashlib
    nodes = []
    for i in range(node_count):
        cat = list(NodeCategory)[i % len(list(NodeCategory))]
        nodes.append(FlowNode(
            node_id=f"n{i:04d}",
            label=f"Component {i}",
            description=f"Auto-generated node {i}",
            category=cat,
            state=FlowNodeState.IDLE,
        ))

    edges = []
    for i in range(min(edge_count, node_count * 2 - 2)):
        src = i % node_count
        tgt = (i + 1 + (i // node_count)) % node_count
        if src != tgt:
            edges.append(FlowEdge(
                edge_id=f"e-{src:04d}-{tgt:04d}",
                source_id=f"n{src:04d}",
                target_id=f"n{tgt:04d}",
                flow_type=list(FlowType)[i % len(list(FlowType))],
                state=FlowEdgeState.IDLE,
            ))

    return FlowDefinition(
        flow_id="large-graph-test",
        name=f"Large Graph ({node_count} nodes, {len(edges)} edges)",
        flow_type=FlowType.REQUEST,
        entry_node_id="n0000",
        nodes=nodes, edges=edges,
    )
