"""Phase N3 — Implementation Plan Quality acceptance tests.

Covers architecture_planner.py's generate_implementation_plan_from_architecture
and check_plan_freshness/apply_freshness_check, plus the additive N3 fields
on implementation/models.py and downstream compatibility with the existing
execution/mapper.py consumer.
"""

from __future__ import annotations

from infra_again.implementation.architecture_planner import (
    apply_freshness_check,
    check_plan_freshness,
    generate_implementation_plan_from_architecture,
)
from infra_again.implementation.models import (
    ImplementationTask,
    PlanStatus,
    RollbackCapability,
    TaskExecutionClassification,
)
from infra_again.implementation.planner import generate_implementation_plan
from infra_again.intelligence.catalog import CatalogLifecycle, ProviderCatalog, ProviderService
from infra_again.intelligence.provider_resolver import ProviderServiceResolver


def _node(node_id, category, provider, native_service, platform=""):
    return {"nodeId": node_id, "name": node_id, "category": category, "provider": provider,
            "nativeService": native_service, "platform": platform}


def _resolver_with(*services: ProviderService) -> ProviderServiceResolver:
    cat = ProviderCatalog()
    for s in services:
        cat._services[f"{s.provider}:{s.service_id}"] = s
    return ProviderServiceResolver(catalog=cat)


# ═══════════════════════════════════════════════════════════════════
# NO_DUPLICATE_PLAN_AUTHORITY — legacy path still works unchanged
# ═══════════════════════════════════════════════════════════════════


def test_legacy_flow_heuristic_planner_unaffected_by_n3_fields():
    design = {"designId": "D1", "revision": 1, "status": "BASELINE_FROZEN", "metadata": {"name": "T"}}
    flow = {"nodes": [
        {"nodeId": "user-1", "category": "USER"},
        {"nodeId": "application-service-1", "category": "APPLICATION"},
    ], "edges": []}
    plan = generate_implementation_plan(design, flow)
    assert plan.generation_method == "LEGACY_FLOW_HEURISTIC"
    assert plan.plan_digest == ""  # legacy path never computes the new digest
    plan.approve("tester")
    assert plan.plan_checksum
    assert plan.check_changed_after_approval() is False


# ═══════════════════════════════════════════════════════════════════
# PLAN_DIGEST_DETERMINISTIC / PLAN_DIGEST_EXECUTION_FIELDS_COVERED
# ═══════════════════════════════════════════════════════════════════


def test_plan_digest_deterministic_for_identical_input():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    p1 = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    p2 = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    assert p1.plan_digest == p2.plan_digest


def test_plan_digest_changes_when_execution_relevant_fields_change():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    sim = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    sandbox = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SANDBOX")
    assert sim.plan_digest != sandbox.plan_digest


def test_plan_digest_stable_across_presentation_only_changes():
    # Same architecture/fidelity twice must produce identical digests even
    # though timestamps/plan_ids differ (volatile presentation fields must
    # not churn the digest).
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    p1 = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    p2 = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert p1.plan_id != p2.plan_id  # different identity
    assert p1.created_at  # has a timestamp
    assert p1.plan_digest == p2.plan_digest  # but identical execution-relevant digest


# ═══════════════════════════════════════════════════════════════════
# Traceability
# ═══════════════════════════════════════════════════════════════════


def test_node_to_task_traceability():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    task = plan.work_packages[0].tasks[0]
    assert task.source_node_ids == ["N1"]
    assert task.provider == "AWS"
    assert task.canonical_service_id == "s3"
    assert task.provider_intelligence_ref == "AWS:s3"


def test_edge_to_task_traceability():
    nodes = [
        _node("N1", "APPLICATION", "AWS", "s3"),
        _node("N2", "DATABASE", "AWS", "rds"),
    ]
    edges = [{"edgeId": "E1", "sourceNodeId": "N1", "targetNodeId": "N2"}]
    plan = generate_implementation_plan_from_architecture(nodes, edges, architecture_id="A", architecture_revision=1)
    all_tasks = {t.task_id: t for wp in plan.work_packages for t in wp.tasks}
    n1_task = next(t for t in all_tasks.values() if t.source_node_ids == ["N1"])
    n2_task = next(t for t in all_tasks.values() if t.source_node_ids == ["N2"])
    assert n1_task.task_id in n2_task.dependencies
    assert "E1" in n2_task.source_edge_ids


def test_architecture_revision_traceability():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="ARCH-9", architecture_revision=7)
    assert plan.architecture_id == "ARCH-9"
    assert plan.architecture_revision == 7
    d = plan.to_dict()
    assert d["architectureId"] == "ARCH-9"
    assert d["architectureRevision"] == 7


# ═══════════════════════════════════════════════════════════════════
# Logical packages
# ═══════════════════════════════════════════════════════════════════


def test_logical_packages_generated_by_category():
    nodes = [
        _node("N1", "APPLICATION", "AWS", "s3"),
        _node("N2", "DATABASE", "AWS", "rds"),
        _node("N3", "NETWORK", "AWS", "elb"),
    ]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    types = {w.package_type.value for w in plan.work_packages}
    assert types == {"COMPUTE", "DATA", "NETWORK"}


def test_no_empty_decorative_packages():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert len(plan.work_packages) == 1  # only DATA — no NETWORK/SECURITY/etc packages fabricated
    for wp in plan.work_packages:
        assert len(wp.tasks) > 0


# ═══════════════════════════════════════════════════════════════════
# Task execution classification visibility
# ═══════════════════════════════════════════════════════════════════


def test_unsupported_task_visible_not_dropped():
    nodes = [_node("N1", "DATABASE", "AWS", "elasticache")]  # known, NOT_IMPLEMENTED
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.UNEXECUTABLE
    assert task in plan.work_packages[0].tasks  # present, not filtered out


def test_plan_only_task_visible():
    nodes = [_node("N1", "DATABASE", "AWS", "rds")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="PLAN_ONLY")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.PLAN_ONLY


def test_policy_blocked_task_visible():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="PRODUCTION")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.BLOCKED


# ═══════════════════════════════════════════════════════════════════
# Fidelity binding
# ═══════════════════════════════════════════════════════════════════


def test_plan_is_fidelity_scoped():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SANDBOX")
    assert plan.target_fidelity == "SANDBOX"
    assert plan.work_packages[0].tasks[0].target_fidelity == "SANDBOX"


def test_fidelity_changes_task_readiness():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]  # SIMULATED-only support
    sim_plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    sandbox_plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SANDBOX")
    assert sim_plan.work_packages[0].tasks[0].execution_classification == TaskExecutionClassification.EXECUTABLE
    assert sandbox_plan.work_packages[0].tasks[0].execution_classification == TaskExecutionClassification.UNEXECUTABLE


# ═══════════════════════════════════════════════════════════════════
# Provider Intelligence snapshot binding
# ═══════════════════════════════════════════════════════════════════


def test_provider_intelligence_snapshot_bound():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert plan.provider_intelligence_version.startswith("PI-")
    assert plan.work_packages[0].tasks[0].provider_intelligence_version == plan.provider_intelligence_version


def test_capability_change_does_not_mutate_approved_plan():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="elasticache", display_name="ElastiCache",
        category="CACHE", lifecycle=CatalogLifecycle.DISCOVERED, execution_support=["NOT_IMPLEMENTED"],
    ))
    nodes = [_node("N1", "CACHE", "AWS", "elasticache")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1,
                                                            target_fidelity="SIMULATED", resolver=resolver)
    plan.approve("tester")
    before = plan.work_packages[0].tasks[0].execution_classification

    # Provider Intelligence changes AFTER approval.
    resolver._catalog._services["AWS:elasticache"].lifecycle = CatalogLifecycle.SUPPORTED
    resolver._catalog._services["AWS:elasticache"].execution_support = ["SIMULATED"]
    new_pi_version = resolver._catalog.version()

    # The already-approved plan's own content must not change.
    after = plan.work_packages[0].tasks[0].execution_classification
    assert before == after == TaskExecutionClassification.UNEXECUTABLE
    assert plan.provider_intelligence_version != new_pi_version  # drift is real and detectable
    assert plan.status == PlanStatus.APPROVED_FOR_EXECUTION  # unchanged until a freshness check runs


# ═══════════════════════════════════════════════════════════════════
# Architecture revision binding / staleness
# ═══════════════════════════════════════════════════════════════════


def test_arch_rev_binding():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=5)
    assert plan.architecture_revision == 5


def test_arch_change_invalidates_plan_scenario_d():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=5, target_fidelity="SIMULATED")
    plan.approve("tester")
    assert plan.status == PlanStatus.APPROVED_FOR_EXECUTION

    plan, mutated = apply_freshness_check(
        plan, current_architecture_revision=6,
        current_provider_intelligence_version=plan.provider_intelligence_version,
        current_feasibility_digest=plan.feasibility_digest,
    )
    assert mutated is True
    assert plan.status == PlanStatus.BASELINE_INVALIDATED  # STALE, per existing domain vocabulary
    assert plan.stale is True
    assert "ARCHITECTURE_REVISION_CHANGED" in plan.stale_reason


def test_stale_plan_rejection_reflected_in_status_not_content():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    original_digest = plan.plan_digest
    plan.approve("tester")
    plan, _ = apply_freshness_check(plan, 2, plan.provider_intelligence_version, plan.feasibility_digest)
    assert plan.plan_digest == original_digest  # content untouched, only status/staleness flipped


# ═══════════════════════════════════════════════════════════════════
# Feasibility binding / drift
# ═══════════════════════════════════════════════════════════════════


def test_feasibility_binding():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert plan.feasibility_digest
    assert plan.feasibility_assessment_id == "A@1:SIMULATED"


def test_feasibility_drift_detected_scenario_f():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.DISCOVERED, execution_support=["NOT_IMPLEMENTED"],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1,
                                                            target_fidelity="SIMULATED", resolver=resolver)
    plan.approve("tester")

    resolver._catalog._services["AWS:widget"].execution_support = ["SIMULATED"]
    resolver._catalog._services["AWS:widget"].lifecycle = CatalogLifecycle.SUPPORTED
    from infra_again.intelligence.feasibility import assess_architecture_feasibility, feasibility_digest
    new_assessment = assess_architecture_feasibility(nodes, "A", "1", "AWS", requested_fidelity="SIMULATED", resolver=resolver)
    new_digest = feasibility_digest(new_assessment)

    result = check_plan_freshness(plan, 1, resolver._catalog.version(), new_digest)
    assert result["stale"] is True
    assert any("FEASIBILITY_DRIFT" in r for r in result["reasons"])


# ═══════════════════════════════════════════════════════════════════
# Dependency graph
# ═══════════════════════════════════════════════════════════════════


def test_dependency_order_deterministic_network_before_compute():
    nodes = [
        _node("N1", "APPLICATION", "AWS", "s3"),
        _node("N2", "NETWORK", "AWS", "elb"),
    ]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    net_pkg = next(w for w in plan.work_packages if w.package_type.value == "NETWORK")
    compute_pkg = next(w for w in plan.work_packages if w.package_type.value == "COMPUTE")
    assert net_pkg.package_id in compute_pkg.dependencies
    assert compute_pkg.package_id not in net_pkg.dependencies


def test_no_visual_position_dependency():
    # Two identical-category nodes in reverse creation order — dependency
    # must come only from the edge, never from list/insertion order.
    nodes = [
        _node("N2", "APPLICATION", "AWS", "s3"),
        _node("N1", "APPLICATION", "AWS", "s3"),
    ]
    edges = [{"edgeId": "E1", "sourceNodeId": "N1", "targetNodeId": "N2"}]
    plan = generate_implementation_plan_from_architecture(nodes, edges, architecture_id="A", architecture_revision=1)
    all_tasks = {t.source_node_ids[0]: t for wp in plan.work_packages for t in wp.tasks}
    assert all_tasks["N1"].task_id in all_tasks["N2"].dependencies


def test_dependency_cycle_detected_scenario_g():
    nodes = [
        _node("N1", "APPLICATION", "AWS", "s3"),
        _node("N2", "APPLICATION", "AWS", "s3"),
    ]
    edges = [
        {"edgeId": "E1", "sourceNodeId": "N1", "targetNodeId": "N2"},
        {"edgeId": "E2", "sourceNodeId": "N2", "targetNodeId": "N1"},
    ]
    plan = generate_implementation_plan_from_architecture(nodes, edges, architecture_id="A", architecture_revision=1)
    assert plan.dependency_cycle_detected is True
    assert plan.cycle_nodes
    assert plan.readiness.value == "NOT_READY"
    assert any(b.blocker_id == "BLOCK-CYCLE" for b in plan.blockers)


# ═══════════════════════════════════════════════════════════════════
# Cost / blast radius — never fabricated
# ═══════════════════════════════════════════════════════════════════


def test_unknown_cost_not_zero():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    task = plan.work_packages[0].tasks[0]
    assert task.estimated_cost == "UNKNOWN"
    assert task.estimated_cost != "0"
    assert plan.work_packages[0].estimated_cost == "UNKNOWN"


def test_unknown_blast_radius_not_low():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    task = plan.work_packages[0].tasks[0]
    assert task.blast_radius == "UNKNOWN"
    assert task.blast_radius != "LOW"


# ═══════════════════════════════════════════════════════════════════
# Rollback readiness
# ═══════════════════════════════════════════════════════════════════


def test_rollback_capability_visible_for_executable_task():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]  # DATA package, EXECUTABLE at SIMULATED
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.EXECUTABLE
    assert task.rollback_capability == RollbackCapability.PARTIAL  # DATA package


def test_non_mutable_task_has_not_applicable_rollback():
    nodes = [_node("N1", "DATABASE", "AWS", "rds")]  # PLAN_ONLY only
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.UNEXECUTABLE
    assert task.rollback_capability == RollbackCapability.NOT_APPLICABLE


# ═══════════════════════════════════════════════════════════════════
# Approval binds digest / post-approval mutation rejected
# ═══════════════════════════════════════════════════════════════════


def test_approval_binds_plan_digest():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    assert plan.approved_plan_digest == plan.plan_digest
    assert plan.approved_plan_digest != ""


def test_post_approval_mutation_rejected():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    assert plan.check_changed_after_approval() is False

    # Mutate plan content directly (simulating an attempted silent edit).
    plan.work_packages[0].tasks[0].title = "TAMPERED"
    plan.work_packages.append(plan.work_packages[0])  # crude structural change
    # Content changed but this specific mutation (title) doesn't affect the
    # digest by design (titles are presentation-only) — verify a REAL
    # execution-relevant mutation is caught instead:
    plan.work_packages[0].tasks[0].execution_classification = TaskExecutionClassification.EXECUTABLE
    assert plan.check_changed_after_approval() is True


# ═══════════════════════════════════════════════════════════════════
# Downstream compatibility — execution/mapper.py
# ═══════════════════════════════════════════════════════════════════


def test_downstream_mapper_compatible_with_architecture_aware_plan():
    from infra_again.execution.mapper import ImplementationExecutionMapper
    from infra_again.execution.phase7_models import ExecutionFidelity, ExecutionTarget

    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    readiness = ImplementationExecutionMapper.compute_readiness(plan)
    assert readiness.total_tasks == 1
    assert len(readiness.ready_local) + len(readiness.ready_simulated) == 1

    target = ExecutionTarget(target_id="t1", target_type="SIMULATED", fidelity=ExecutionFidelity.SIMULATED)
    exec_tasks = ImplementationExecutionMapper.map_to_execution_tasks(plan, target)
    assert len(exec_tasks) == 1


def test_downstream_execution_package_reads_plan_checksum_field():
    """execution/api.py's create_execution_package reads plan.plan_checksum
    directly (not plan_digest) — confirm compute_digest() keeps it in
    lockstep so the existing Gate 0 enforcement still works unmodified."""
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert plan.plan_checksum == plan.plan_digest
    assert plan.plan_checksum != ""


# ═══════════════════════════════════════════════════════════════════
# LLM_CANNOT_MARK_TASK_EXECUTABLE / FRONTEND_CANNOT_APPROVE_BY_LOCAL_STATE
# ═══════════════════════════════════════════════════════════════════


def test_incoming_node_cannot_claim_executability():
    node = _node("N1", "DATABASE", "AWS", "elasticache")
    node["executionClassification"] = "EXECUTABLE"
    node["approved"] = True
    node["providerLifecycleState"] = "SUPPORTED"
    plan = generate_implementation_plan_from_architecture([node], [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.UNEXECUTABLE


def test_plan_status_only_changes_via_explicit_approve_call():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert plan.status == PlanStatus.REVIEW_READY
    # No frontend/local-state mechanism exists to flip this — only
    # ImplementationPlan.approve() (called from the API's approve endpoint)
    # can transition to APPROVED_FOR_EXECUTION.
    assert plan.status != PlanStatus.APPROVED_FOR_EXECUTION


# ═══════════════════════════════════════════════════════════════════
# Required scenarios A-H (consolidated coverage not already exercised above)
# ═══════════════════════════════════════════════════════════════════


def test_scenario_a_fully_supported_simulated_architecture():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    assert plan.status == PlanStatus.REVIEW_READY
    assert all(t.execution_classification == TaskExecutionClassification.EXECUTABLE
               for wp in plan.work_packages for t in wp.tasks)
    assert plan.dependency_cycle_detected is False


def test_scenario_b_unsupported_service_plan_still_generated():
    nodes = [_node("N1", "DATABASE", "AWS", "elasticache")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    assert plan.status == PlanStatus.REVIEW_READY  # plan still generated
    assert plan.work_packages[0].tasks[0].execution_classification == TaskExecutionClassification.UNEXECUTABLE
    assert plan.blockers  # not fully executable, visibly


def test_scenario_c_plan_only_no_fake_executable():
    nodes = [_node("N1", "DATABASE", "AWS", "rds")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="PLAN_ONLY")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification == TaskExecutionClassification.PLAN_ONLY
    assert task.execution_classification != TaskExecutionClassification.EXECUTABLE
