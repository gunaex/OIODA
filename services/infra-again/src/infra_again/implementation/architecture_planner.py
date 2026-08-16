"""Architecture-aware Implementation Planner — Phase N3.

Generates an ImplementationPlan directly from a canonical AGAINPILOT
architecture (nodes/edges enriched by N1 Provider Intelligence) plus an N2
ArchitectureFeasibilityAssessment — never from the flow-nodeId-substring
heuristics in planner.py (that generator is untouched; it remains available
for designs with no canonical service data).

Every task traces back to real architecture nodes/edges. Execution
classification (EXECUTABLE/PLAN_ONLY/UNEXECUTABLE/BLOCKED) comes directly
from N2's per-node, per-fidelity capability — this module never re-derives
or overrides that verdict, and never lets an incoming node dict claim its
own executability (same invariant as N2).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from ..intelligence.catalog import get_catalog
from ..intelligence.feasibility import (
    ArchitectureFeasibilityAssessment,
    assess_architecture_feasibility,
    feasibility_digest,
)
from ..intelligence.provider_resolver import ProviderServiceResolver
from .models import (
    AutomationEligibility,
    ImplementationBlocker,
    ImplementationDependency,
    ImplementationEstimate,
    ImplementationGate,
    ImplementationPlan,
    ImplementationTask,
    ImplementationWorkPackage,
    EffortUnit,
    EstimateSource,
    GateState,
    PlanStatus,
    ReadinessState,
    RiskSeverity,
    RollbackCapability,
    TaskExecutionClassification,
    WorkPackageType,
)

_NON_EXECUTABLE_CATEGORIES = {"USER", "EXTERNAL"}

# Deterministic node-category -> logical package mapping. Anything not
# listed falls back to INFRASTRUCTURE rather than being silently dropped.
_CATEGORY_TO_PACKAGE: dict[str, WorkPackageType] = {
    "APPLICATION": WorkPackageType.COMPUTE,
    "DATABASE": WorkPackageType.DATA,
    "STORAGE": WorkPackageType.DATA,
    "CACHE": WorkPackageType.DATA,
    "QUEUE": WorkPackageType.INTEGRATION,
    "NETWORK": WorkPackageType.NETWORK,
    "GATEWAY": WorkPackageType.NETWORK,
    "SECURITY": WorkPackageType.SECURITY,
    "IDENTITY": WorkPackageType.IDENTITY,
    "OBSERVABILITY": WorkPackageType.OBSERVABILITY,
    "CICD": WorkPackageType.INTEGRATION,
}

# Deterministic provisioning order — NOT visual position. Matches standard
# infra sequencing: connectivity and access control before the workloads
# that depend on them, workloads before cross-cutting integration/
# observability wiring.
_PACKAGE_ORDER: list[WorkPackageType] = [
    WorkPackageType.NETWORK,
    WorkPackageType.IDENTITY,
    WorkPackageType.SECURITY,
    WorkPackageType.DATA,
    WorkPackageType.COMPUTE,
    WorkPackageType.INTEGRATION,
    WorkPackageType.OBSERVABILITY,
]

# CONTROLLED_REAL/PRODUCTION are always policy-BLOCKed (mirrors
# execution.policy.PHASE7_BLOCK) — a task targeting either is BLOCKED
# regardless of what Provider Intelligence says about the service.
_POLICY_HARD_BLOCKED_FIDELITIES = {"CONTROLLED_REAL", "PRODUCTION"}


def _package_category(node: dict[str, Any]) -> WorkPackageType:
    return _CATEGORY_TO_PACKAGE.get((node.get("category") or "").upper(), WorkPackageType.INFRASTRUCTURE)


def _is_required_node(node: dict[str, Any]) -> bool:
    return node.get("category") not in _NON_EXECUTABLE_CATEGORIES and bool(node.get("nativeService"))


def _classify_task(node_fidelity_ready: bool, provider_lifecycle_state: str, target_fidelity: str) -> TaskExecutionClassification:
    if target_fidelity in _POLICY_HARD_BLOCKED_FIDELITIES:
        return TaskExecutionClassification.BLOCKED
    if provider_lifecycle_state == "UNKNOWN_SERVICE":
        return TaskExecutionClassification.UNEXECUTABLE
    if target_fidelity == "PLAN_ONLY":
        return TaskExecutionClassification.PLAN_ONLY
    return TaskExecutionClassification.EXECUTABLE if node_fidelity_ready else TaskExecutionClassification.UNEXECUTABLE


def _automation_for(classification: TaskExecutionClassification) -> AutomationEligibility:
    """Maps N2/N3 execution classification onto the downstream execution
    mapper's automation eligibility — without this, every task defaults to
    MANUAL and ImplementationExecutionMapper silently drops all of them
    (see execution/mapper.py's automation == "MANUAL" skip)."""
    return {
        TaskExecutionClassification.EXECUTABLE: AutomationEligibility.AUTO,
        TaskExecutionClassification.PLAN_ONLY: AutomationEligibility.AUTO,
        TaskExecutionClassification.UNEXECUTABLE: AutomationEligibility.MANUAL,
        TaskExecutionClassification.BLOCKED: AutomationEligibility.BLOCKED,
    }.get(classification, AutomationEligibility.MANUAL)


def _classify_rollback(package: WorkPackageType, classification: TaskExecutionClassification) -> RollbackCapability:
    if classification in (TaskExecutionClassification.PLAN_ONLY, TaskExecutionClassification.UNEXECUTABLE,
                          TaskExecutionClassification.BLOCKED, TaskExecutionClassification.UNKNOWN):
        # Nothing will actually mutate anything at this fidelity/state.
        return RollbackCapability.NOT_APPLICABLE
    if package == WorkPackageType.DATA:
        return RollbackCapability.PARTIAL  # stateful — rollback risks data loss
    if package in (WorkPackageType.SECURITY, WorkPackageType.IDENTITY, WorkPackageType.NETWORK):
        return RollbackCapability.MANUAL  # wide blast radius, human review preferred
    if package == WorkPackageType.COMPUTE:
        return RollbackCapability.AUTOMATIC  # stateless — local teardown is automatable
    return RollbackCapability.MANUAL


def _package_readiness(classifications: list[str]) -> str:
    if not classifications:
        return "UNKNOWN"
    if any(c == "BLOCKED" for c in classifications):
        return "BLOCKED"
    if all(c == "EXECUTABLE" for c in classifications):
        return "EXECUTABLE"
    if all(c == "PLAN_ONLY" for c in classifications):
        return "PLAN_ONLY"
    if any(c == "UNEXECUTABLE" for c in classifications):
        has_any_viable = any(c in ("EXECUTABLE", "PLAN_ONLY") for c in classifications)
        return "PARTIALLY_EXECUTABLE" if has_any_viable else "NOT_EXECUTABLE"
    return "PARTIALLY_EXECUTABLE"  # mix of EXECUTABLE and PLAN_ONLY


def _detect_task_cycle(task_ids: list[str], deps: dict[str, list[str]]) -> list[str]:
    """DFS cycle detection over task-level dependencies. Returns the cycle
    (list of task ids) if one exists, else []. Never reorders — the caller
    must leave dependencies exactly as generated and surface the cycle."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in task_ids}
    path: list[str] = []

    def visit(node: str) -> list[str]:
        color[node] = GRAY
        path.append(node)
        for dep in deps.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                cycle_start = path.index(dep)
                return path[cycle_start:] + [dep]
            if color[dep] == WHITE:
                result = visit(dep)
                if result:
                    return result
        path.pop()
        color[node] = BLACK
        return []

    for tid in task_ids:
        if color[tid] == WHITE:
            result = visit(tid)
            if result:
                return result
    return []


def generate_implementation_plan_from_architecture(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]] | None = None,
    architecture_id: str = "",
    architecture_revision: int = 1,
    provider: str = "",
    platform: str = "",
    target_fidelity: str = "SIMULATED",
    correlation_id: str = "",
    created_by: str = "",
    resolver: ProviderServiceResolver | None = None,
    feasibility: ArchitectureFeasibilityAssessment | None = None,
) -> ImplementationPlan:
    edges = edges or []
    target_fidelity = (target_fidelity or "SIMULATED").upper()

    # N2 is the ONLY authority on executability — never re-derived here.
    assessment = feasibility or assess_architecture_feasibility(
        nodes, architecture_id=architecture_id, architecture_revision=str(architecture_revision),
        provider=provider, platform=platform, requested_fidelity=target_fidelity, resolver=resolver,
    )
    nf_by_node_id = {nf.node_id: nf for nf in assessment.node_feasibility}
    pi_version = get_catalog().version()

    required_nodes = [n for n in nodes if _is_required_node(n)]

    plan_id = f"IMPL-{uuid4().hex[:6].upper()}"
    plan = ImplementationPlan(
        plan_id=plan_id,
        design_id=architecture_id, design_revision=architecture_revision,
        architecture_id=architecture_id, architecture_revision=architecture_revision,
        status=PlanStatus.GENERATED,
        summary=f"Architecture-aware implementation plan for {architecture_id} rev {architecture_revision} @ {target_fidelity}",
        provider_intelligence_version=pi_version,
        feasibility_digest=feasibility_digest(assessment),
        feasibility_assessment_id=f"{architecture_id}@{architecture_revision}:{target_fidelity}",
        target_fidelity=target_fidelity,
        correlation_id=correlation_id, created_by=created_by,
        generation_method="ARCHITECTURE_AWARE",
    )

    # ── One task per required node, grouped into logical packages ──
    packages: dict[WorkPackageType, ImplementationWorkPackage] = {}
    task_by_node_id: dict[str, ImplementationTask] = {}
    task_counter = 0

    for node in required_nodes:
        node_id = node.get("nodeId", "")
        nf = nf_by_node_id.get(node_id)
        if nf is None:
            continue  # defensive — every required node has a feasibility entry

        pkg_type = _package_category(node)
        req_fidelity_cap = nf.fidelity.get(target_fidelity)
        ready = bool(req_fidelity_cap and req_fidelity_cap.ready)
        classification = _classify_task(ready, nf.provider_lifecycle_state, target_fidelity)

        task_counter += 1
        task_id = f"T-{task_counter:03d}"
        wp = packages.get(pkg_type)
        if wp is None:
            wp = ImplementationWorkPackage(
                package_id=f"WP-{pkg_type.value}-{len(packages) + 1:03d}", plan_id=plan_id,
                title=f"{pkg_type.value.title()} Implementation",
                description=f"{pkg_type.value.title()} work derived from architecture {architecture_id} rev {architecture_revision}.",
                package_type=pkg_type,
                estimated_effort=ImplementationEstimate(0.0, EffortUnit.PERSON_DAYS, EstimateSource.UNKNOWN, 0.3),
            )
            packages[pkg_type] = wp

        task = ImplementationTask(
            task_id=task_id, work_package_id=wp.package_id,
            title=f"Implement {node.get('name') or nf.canonical_service_id or node.get('nativeService', '')}",
            description=f"Provision/configure {nf.canonical_service_id or node.get('nativeService', '')} "
                        f"({nf.provider}) at {target_fidelity} fidelity.",
            category=pkg_type,
            execution_mode=target_fidelity,
            acceptance_criteria=[f"{nf.canonical_service_id or node.get('nativeService','')} reaches "
                                  f"execution classification EXECUTABLE or PLAN_ONLY at {target_fidelity}"],
            risk_level=RiskSeverity.HIGH if classification == TaskExecutionClassification.BLOCKED else RiskSeverity.LOW,
            estimated_effort=ImplementationEstimate(0.0, EffortUnit.PERSON_DAYS, EstimateSource.UNKNOWN, 0.3),
            owner_role="Infrastructure Engineer",
            automation=_automation_for(classification),
            derived_from=[{"type": "NODE", "id": node_id}],
            local_validatable=target_fidelity in ("LOCAL_RUNTIME", "SIMULATED", "PLAN_ONLY"),
            source_node_ids=[node_id],
            provider=nf.provider, canonical_service_id=nf.canonical_service_id, runtime_mode=nf.runtime_mode,
            provider_intelligence_ref=f"{nf.provider}:{nf.canonical_service_id}",
            provider_intelligence_version=pi_version,
            target_fidelity=target_fidelity,
            execution_classification=classification,
            blocking_issues=list(nf.blocking_issues),
            estimated_cost="UNKNOWN", blast_radius="UNKNOWN",
            rollback_capability=_classify_rollback(pkg_type, classification),
        )
        wp.tasks.append(task)
        task_by_node_id[node_id] = task

    # ── Edge-derived task-level dependencies (never visual position) ──
    for edge in edges:
        src_id = edge.get("sourceNodeId") or edge.get("from") or edge.get("sourceId", "")
        tgt_id = edge.get("targetNodeId") or edge.get("to") or edge.get("targetId", "")
        src_task = task_by_node_id.get(src_id)
        tgt_task = task_by_node_id.get(tgt_id)
        if src_task and tgt_task and src_task.task_id not in tgt_task.dependencies:
            tgt_task.dependencies.append(src_task.task_id)
            tgt_task.source_edge_ids.append(edge.get("edgeId", f"{src_id}->{tgt_id}"))

    # ── Category-order dependencies, package-level ──
    plan.work_packages = list(packages.values())
    ordered_present = [p for p in _PACKAGE_ORDER if p in packages]
    plan_deps: list[ImplementationDependency] = []
    dep_counter = 0
    for i, earlier in enumerate(ordered_present):
        for later in ordered_present[i + 1:]:
            dep_counter += 1
            plan_deps.append(ImplementationDependency(
                dep_id=f"DEP-{dep_counter:03d}", from_package=packages[earlier].package_id,
                to_package=packages[later].package_id,
                description=f"{earlier.value} before {later.value}",
            ))
            if packages[earlier].package_id not in packages[later].dependencies:
                packages[later].dependencies.append(packages[earlier].package_id)
    plan.dependencies = plan_deps

    # ── Cycle detection over the task-level graph (edges only — category
    # order is a DAG by construction and can't itself cycle) ──
    all_task_ids = [t.task_id for wp in plan.work_packages for t in wp.tasks]
    task_deps = {t.task_id: t.dependencies for wp in plan.work_packages for t in wp.tasks}
    cycle = _detect_task_cycle(all_task_ids, task_deps)
    if cycle:
        plan.dependency_cycle_detected = True
        plan.cycle_nodes = cycle

    # ── Package-level readiness/blocking rollup ──
    for wp in plan.work_packages:
        classes = [t.execution_classification.value for t in wp.tasks]
        wp.execution_readiness = _package_readiness(classes)
        wp.blocking_issues = [b for t in wp.tasks for b in t.blocking_issues]

    # ── Plan-level readiness ──
    all_classes = [t.execution_classification.value for wp in plan.work_packages for t in wp.tasks]
    if plan.dependency_cycle_detected:
        plan.readiness = ReadinessState.NOT_READY
    elif any(c == "BLOCKED" for c in all_classes):
        plan.readiness = ReadinessState.NOT_READY
    elif all_classes and all(c == "EXECUTABLE" for c in all_classes):
        fidelity_readiness = {
            "PLAN_ONLY": ReadinessState.READY_FOR_LOCAL_IMPLEMENTATION,
            "SIMULATED": ReadinessState.READY_FOR_LOCAL_IMPLEMENTATION,
            "LOCAL_RUNTIME": ReadinessState.READY_FOR_LOCAL_IMPLEMENTATION,
            "LOCAL_PRIVATE_CLOUD": ReadinessState.READY_FOR_LOCAL_IMPLEMENTATION,
            "SANDBOX": ReadinessState.READY_FOR_SANDBOX,
            "CONTROLLED_REAL": ReadinessState.READY_FOR_CONTROLLED_REAL,
            "PRODUCTION": ReadinessState.READY_FOR_PRODUCTION,
        }
        plan.readiness = fidelity_readiness.get(target_fidelity, ReadinessState.PARTIALLY_READY)
    elif all_classes and all(c == "PLAN_ONLY" for c in all_classes):
        plan.readiness = ReadinessState.PARTIALLY_READY
    elif all_classes:
        plan.readiness = ReadinessState.PARTIALLY_READY
    else:
        plan.readiness = ReadinessState.NOT_READY

    # ── Blockers — visible, never hidden inside aggregates ──
    blockers: list[ImplementationBlocker] = []
    if plan.dependency_cycle_detected:
        blockers.append(ImplementationBlocker(
            blocker_id="BLOCK-CYCLE", severity=RiskSeverity.CRITICAL,
            description=f"Dependency cycle detected: {' -> '.join(plan.cycle_nodes)}",
            resolution_required="Remove the circular dependency between the listed tasks",
        ))
    blocked_or_unexec = [t for wp in plan.work_packages for t in wp.tasks
                          if t.execution_classification in (TaskExecutionClassification.BLOCKED, TaskExecutionClassification.UNEXECUTABLE)]
    for t in blocked_or_unexec:
        blockers.append(ImplementationBlocker(
            blocker_id=f"BLOCK-{t.task_id}",
            severity=RiskSeverity.HIGH if t.execution_classification == TaskExecutionClassification.BLOCKED else RiskSeverity.MEDIUM,
            description="; ".join(t.blocking_issues) or f"{t.task_id} is {t.execution_classification.value} at {target_fidelity}",
            affected_tasks=[t.task_id],
            resolution_required="Regenerate plan at a supported fidelity or extend Provider Intelligence support"
                                 if t.execution_classification == TaskExecutionClassification.UNEXECUTABLE
                                 else "Not permitted under current safety policy",
        ))
    plan.blockers = blockers

    plan.gates = [
        ImplementationGate(gate_id="GATE-001", name="ARCHITECTURE_ACCEPTED", state=GateState.PASS,
                            description=f"Generated from architecture {architecture_id} rev {architecture_revision}"),
        ImplementationGate(gate_id="GATE-002", name="PROVIDER_INTELLIGENCE_BOUND", state=GateState.PASS,
                            description=f"Bound to Provider Intelligence {pi_version}"),
        ImplementationGate(gate_id="GATE-003", name="NO_DEPENDENCY_CYCLES",
                            state=GateState.BLOCKED if plan.dependency_cycle_detected else GateState.PASS,
                            description="Task dependency graph is acyclic"),
    ]

    plan.baseline_checksums = {
        "providerIntelligenceVersion": pi_version,
        "feasibilityDigest": plan.feasibility_digest,
    }
    plan.compute_digest()
    plan.status = PlanStatus.REVIEW_READY
    return plan


def check_plan_freshness(
    plan: ImplementationPlan,
    current_architecture_revision: int,
    current_provider_intelligence_version: str,
    current_feasibility_digest: str,
) -> dict[str, Any]:
    """Phase N3 — compare a plan's bound snapshot against the CURRENT state
    of the world, without recomputing or mutating the plan's content. A
    positive result here means the plan must be regenerated/reassessed
    before it can be trusted for execution; it never silently rewrites the
    plan to match."""
    reasons: list[str] = []
    bound_rev = plan.architecture_revision or plan.design_revision
    if plan.generation_method == "ARCHITECTURE_AWARE" and bound_rev != current_architecture_revision:
        reasons.append(f"ARCHITECTURE_REVISION_CHANGED: plan bound to rev {bound_rev}, current is rev {current_architecture_revision}")
    if plan.generation_method == "ARCHITECTURE_AWARE" and plan.provider_intelligence_version \
            and plan.provider_intelligence_version != current_provider_intelligence_version:
        reasons.append(
            f"PROVIDER_INTELLIGENCE_CHANGED: plan bound to {plan.provider_intelligence_version}, "
            f"current is {current_provider_intelligence_version}"
        )
    if plan.generation_method == "ARCHITECTURE_AWARE" and plan.feasibility_digest \
            and plan.feasibility_digest != current_feasibility_digest:
        reasons.append(
            f"FEASIBILITY_DRIFT: plan bound to feasibility {plan.feasibility_digest}, "
            f"current is {current_feasibility_digest}"
        )
    return {"stale": bool(reasons), "reasons": reasons}


def apply_freshness_check(
    plan: ImplementationPlan,
    current_architecture_revision: int,
    current_provider_intelligence_version: str,
    current_feasibility_digest: str,
) -> tuple[ImplementationPlan, bool]:
    """Runs check_plan_freshness and, if the plan is APPROVED_FOR_EXECUTION
    and drift is found, transitions its status to BASELINE_INVALIDATED
    (the existing domain vocabulary for "no longer valid, needs
    regeneration") — a status/metadata change only, never a content
    rewrite. Returns (plan, mutated)."""
    result = check_plan_freshness(
        plan, current_architecture_revision, current_provider_intelligence_version, current_feasibility_digest,
    )
    if not result["stale"]:
        return plan, False

    mutated = False
    plan.stale = True
    plan.stale_reason = "; ".join(result["reasons"])
    if plan.status == PlanStatus.APPROVED_FOR_EXECUTION:
        plan.status = PlanStatus.BASELINE_INVALIDATED
        mutated = True
    return plan, mutated
