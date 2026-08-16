"""
Architecture Graph Builders and Renderers for INFRA-AGAIN.

Builds ArchitectureGraph from InfrastructurePlan (PROPOSED/PLANNED)
and from observed provider state (OBSERVED). Generates Mermaid diagrams.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..core.domain import InfrastructurePlan, Provider, Platform, ExecutionMode
from .graph import (
    ArchitectureGraph, ArchitectureNode, ArchitectureEdge,
    ArchitectureDiff, DiffEntry,
    GraphType, NodeStatus, DiffAction, Relationship,
)


def build_proposed_graph(plan: InfrastructurePlan) -> ArchitectureGraph:
    """Build a PROPOSED architecture graph from provider-neutral plan capabilities."""
    graph = ArchitectureGraph(
        graph_type=GraphType.PROPOSED,
        metadata={
            "plan_id": plan.plan_id,
            "correlation_id": plan.correlation_id,
            "provider": plan.provider.value if plan.provider else "UNKNOWN",
            "platform": plan.platform.value if plan.platform else "UNKNOWN",
        },
    )

    for i, mapping in enumerate(plan.capability_mappings):
        req = mapping.requirement
        node = ArchitectureNode(
            id=f"proposed-{i}",
            type=req.category.value if hasattr(req.category, 'value') else str(req.category),
            label=req.name,
            capability=req.name,
            status=NodeStatus.PROPOSED,
            properties=req.properties,
        )
        graph.nodes.append(node)

    return graph


def build_planned_graph(plan: InfrastructurePlan, execution_mode: ExecutionMode = ExecutionMode.SIMULATED) -> ArchitectureGraph:
    """Build a PLANNED architecture graph with provider-resolved resource types."""
    graph = ArchitectureGraph(
        graph_type=GraphType.PLANNED,
        metadata={
            "plan_id": plan.plan_id,
            "correlation_id": plan.correlation_id,
            "provider": plan.provider.value if plan.provider else "UNKNOWN",
            "platform": plan.platform.value if plan.platform else "UNKNOWN",
            "execution_mode": execution_mode.value,
        },
    )

    for i, mapping in enumerate(plan.capability_mappings):
        # Proposed capability node
        proposed_id = f"proposed-{i}"
        req = mapping.requirement
        proposed_node = ArchitectureNode(
            id=proposed_id,
            type=req.category.value if hasattr(req.category, 'value') else str(req.category),
            label=req.name,
            capability=req.name,
            status=NodeStatus.PLANNED,
        )
        graph.nodes.append(proposed_node)

        # Resolved provider resource node
        resolved_id = f"resolved-{i}"
        resolved_node = ArchitectureNode(
            id=resolved_id,
            type=mapping.resource_type,
            label=mapping.resource_type.split("::")[-1] if "::" in mapping.resource_type else mapping.resource_type,
            provider=mapping.provider.value,
            platform=plan.platform.value if plan.platform else "",
            status=NodeStatus.PLANNED,
            resource_reference=mapping.resource_properties.get("bucket_name", resolved_id),
            properties=mapping.resource_properties,
        )
        graph.nodes.append(resolved_node)

        # Edge: proposed → resolved
        graph.edges.append(ArchitectureEdge(
            source=proposed_id, target=resolved_id, relationship=Relationship.REALIZED_AS,
        ))

    return graph


def build_observed_graph(
    observed_state: dict[str, Any],
    plan: InfrastructurePlan | None = None,
    validation_results: list[Any] | None = None,
    execution_mode: ExecutionMode = ExecutionMode.SIMULATED,
    target_endpoint: str = "",
) -> ArchitectureGraph:
    """Build an OBSERVED architecture graph from actual provider observation."""
    graph = ArchitectureGraph(
        graph_type=GraphType.OBSERVED,
        metadata={
            "execution_mode": execution_mode.value,
            "endpoint": target_endpoint,
            "fidelity": "SIMULATED" if execution_mode == ExecutionMode.SIMULATED else execution_mode.value,
        },
    )

    observed_data = observed_state.get("observed", observed_state)
    validation_by_id: dict[str, Any] = {}
    if validation_results:
        for v in validation_results:
            validation_by_id[getattr(v, 'resource_id', '')] = v

    if isinstance(observed_data, dict):
        for rid, rdata in observed_data.items():
            name = rdata.get("name", rid) if isinstance(rdata, dict) else rid
            val = validation_by_id.get(rid)
            if val is not None:
                matches = getattr(val, 'matches', None)
                status = NodeStatus.VALIDATED if matches else NodeStatus.FAILED
            else:
                status = NodeStatus.OBSERVED

            node = ArchitectureNode(
                id=f"observed-{rid}",
                type="AWS::S3::Bucket" if "bucket" in rid.lower() or "s3" in rid.lower() else "resource",
                label=name,
                provider="AWS",
                status=status,
                resource_reference=rid,
                properties=rdata if isinstance(rdata, dict) else {"name": name},
            )
            graph.nodes.append(node)

    # Mark planned-but-not-observed as MISSING
    if plan:
        for i, mapping in enumerate(plan.capability_mappings):
            bucket_name = mapping.resource_properties.get("bucket_name", "")
            if bucket_name and bucket_name not in observed_data:
                graph.nodes.append(ArchitectureNode(
                    id=f"missing-{i}",
                    type=mapping.resource_type,
                    label=bucket_name,
                    provider=mapping.provider.value,
                    status=NodeStatus.MISSING,
                    resource_reference=bucket_name,
                ))

    return graph


def build_diff(planned: ArchitectureGraph, observed: ArchitectureGraph) -> ArchitectureDiff:
    """Build Before/After ArchitectureDiff from planned and observed graphs."""
    diff = ArchitectureDiff(planned_graph=planned, observed_graph=observed)

    planned_ids = {n.resource_reference: n for n in planned.nodes if n.resource_reference}
    observed_ids = {n.resource_reference: n for n in observed.nodes if n.resource_reference}

    all_refs = set(planned_ids.keys()) | set(observed_ids.keys())

    for ref in all_refs:
        p_node = planned_ids.get(ref)
        o_node = observed_ids.get(ref)

        if p_node and o_node:
            # If observed node is MISSING, it means planned but not observed → MISSING
            if o_node.status == NodeStatus.MISSING:
                action = DiffAction.MISSING
                detail = f"MISSING: {ref} planned but not observed"
            elif o_node.status == NodeStatus.VALIDATED:
                action = DiffAction.UNCHANGED
                detail = f"MATCH: {ref}"
            elif o_node.status == NodeStatus.FAILED:
                action = DiffAction.DRIFT
                detail = f"DRIFT: {ref} observed but validation failed"
            else:
                action = DiffAction.UNCHANGED
                detail = f"EXISTS: {ref}"
            diff.entries.append(DiffEntry(
                node_id=ref,
                planned_status=p_node.status,
                observed_status=o_node.status,
                action=action, detail=detail,
            ))
        elif p_node and not o_node:
            diff.entries.append(DiffEntry(
                node_id=ref,
                planned_status=p_node.status,
                observed_status=None,
                action=DiffAction.MISSING,
                detail=f"MISSING: {ref} planned but not observed",
            ))
        elif not p_node and o_node:
            diff.entries.append(DiffEntry(
                node_id=ref,
                planned_status=None,
                observed_status=o_node.status,
                action=DiffAction.UNEXPECTED,
                detail=f"UNEXPECTED: {ref} observed but not planned",
            ))

    diff.summary = (
        f"Match={diff.match_count} Missing={diff.missing_count} "
        f"Unexpected={diff.unexpected_count}"
    )
    return diff


# ---------------------------------------------------------------------------
# Mermaid Renderer
# ---------------------------------------------------------------------------


def render_mermaid_before_after(
    planned: ArchitectureGraph,
    observed: ArchitectureGraph,
    diff: ArchitectureDiff,
    run_id: str = "",
    correlation_id: str = "",
) -> str:
    """Render a Before/After Mermaid diagram as a markdown artifact."""

    def status_icon(status: NodeStatus | None) -> str:
        if status is None:
            return "❓"
        mapping = {
            NodeStatus.VALIDATED: "✅",
            NodeStatus.OBSERVED: "👁️",
            NodeStatus.FAILED: "❌",
            NodeStatus.MISSING: "⚠️",
            NodeStatus.PLANNED: "📋",
            NodeStatus.PROPOSED: "💡",
            NodeStatus.UNVERIFIED: "❓",
            NodeStatus.NOT_TESTED: "⏸️",
        }
        return mapping.get(status, "❓")

    lines = [
        "# Architecture — Before / After",
        "",
        f"**Run:** `{run_id}`  ",
        f"**Correlation:** `{correlation_id}`  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        "",
        "```mermaid",
        "flowchart LR",
        "",
        "  subgraph BEFORE[\"📋 BEFORE — Planned Architecture\"]",
        "    direction TB",
    ]

    for node in planned.nodes:
        lines.append(f"    BP{node.id.replace('-','').replace('.','')}[\"{node.label}\"]")

    lines.append("  end")
    lines.append("")
    lines.append("  subgraph AFTER[\"👁️ AFTER — Observed Architecture\"]")
    lines.append("    direction TB")

    for node in observed.nodes:
        icon = status_icon(node.status)
        lines.append(f"    AF{node.id.replace('-','').replace('.','')}[\"{icon} {node.label}\"]")

    lines.append("  end")
    lines.append("")

    # Diff summary
    lines.append("  subgraph DIFF[\"📊 Change Summary\"]")
    lines.append(f"    D1[\"Match: {diff.match_count}\"]")
    lines.append(f"    D2[\"Missing: {diff.missing_count}\"]")
    lines.append(f"    D3[\"Unexpected: {diff.unexpected_count}\"]")
    lines.append("  end")
    lines.append("")

    # Connect planned to observed
    for entry in diff.entries:
        if entry.action == DiffAction.UNCHANGED:
            planned_node = next((n for n in planned.nodes if n.resource_reference == entry.node_id), None)
            observed_node = next((n for n in observed.nodes if n.resource_reference == entry.node_id), None)
            if planned_node and observed_node:
                p_id = f"BP{planned_node.id.replace('-','').replace('.','')}"
                o_id = f"AF{observed_node.id.replace('-','').replace('.','')}"
                lines.append(f"  {p_id} -.->|{status_icon(entry.observed_status)}| {o_id}")

    lines.append("```")
    lines.append("")
    lines.append("## Fidelity")
    lines.append("")
    for k, v in planned.metadata.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    lines.append("> ⚠️ SIMULATED execution — not real AWS. Production readiness: NOT_VERIFIED.")

    return "\n".join(lines)
