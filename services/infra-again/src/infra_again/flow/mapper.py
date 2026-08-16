"""Architecture → Flow Mapper.

Converts ArchitectureGraph to FlowDefinition.
"""

from __future__ import annotations

from ..visualization.graph import ArchitectureGraph
from .models import (
    FlowDefinition, FlowNode, FlowEdge, FlowType, NodeCategory, FlowNodeState, FlowEdgeState,
)


def map_architecture_to_flow(
    graph: ArchitectureGraph,
    flow_name: str = "",
    entry_node_id: str | None = None,
) -> FlowDefinition:
    """Convert an ArchitectureGraph into a FlowDefinition.

    NOTE: Architecture edges may not represent runtime request flow.
    If edge semantics are unknown, mark FLOW_SEMANTICS_REQUIRED.
    """
    nodes = []
    for node in graph.nodes:
        category = _infer_category(node.node_type if hasattr(node, 'node_type') else "")
        nodes.append(FlowNode(
            node_id=node.node_id,
            label=node.label if hasattr(node, 'label') else node.node_id,
            description=node.description if hasattr(node, 'description') else "",
            category=category,
            provider=node.provider.value if hasattr(node, 'provider') and node.provider else "",
            state=FlowNodeState.IDLE,
        ))

    edges = []
    for edge in graph.edges:
        edges.append(FlowEdge(
            edge_id=edge.edge_id if hasattr(edge, 'edge_id') else f"e-{edge.source_id}-{edge.target_id}",
            source_id=edge.source_id,
            target_id=edge.target_id,
            flow_type=FlowType.REQUEST,  # default — may need manual override
            state=FlowEdgeState.IDLE,
        ))

    entry = entry_node_id or (nodes[0].node_id if nodes else "")

    return FlowDefinition(
        name=flow_name or f"Flow from {graph.graph_id if hasattr(graph, 'graph_id') else 'architecture'}",
        flow_type=FlowType.REQUEST,
        architecture_graph_id=getattr(graph, 'graph_id', ''),
        entry_node_id=entry,
        nodes=nodes,
        edges=edges,
    )


def _infer_category(node_type: str) -> NodeCategory:
    """Infer flow node category from architecture node type."""
    mapping = {
        "user": NodeCategory.USER,
        "identity": NodeCategory.IDENTITY,
        "security": NodeCategory.SECURITY,
        "waf": NodeCategory.SECURITY,
        "firewall": NodeCategory.SECURITY,
        "gateway": NodeCategory.GATEWAY,
        "api": NodeCategory.GATEWAY,
        "application": NodeCategory.APPLICATION,
        "service": NodeCategory.SERVICE,
        "workflow": NodeCategory.WORKFLOW,
        "database": NodeCategory.DATABASE,
        "storage": NodeCategory.STORAGE,
        "queue": NodeCategory.QUEUE,
        "cache": NodeCategory.CACHE,
        "observability": NodeCategory.OBSERVABILITY,
        "external": NodeCategory.EXTERNAL,
        "approval": NodeCategory.APPROVAL,
    }
    return mapping.get(node_type.lower(), NodeCategory.APPLICATION)
