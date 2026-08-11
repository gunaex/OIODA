"""Phase N4 — AIRLOCK (PreflightEngine) gate acceptance tests.

Covers the gates that were previously unconditional-PASS stubs
(PLAN_APPROVED, DESIGN_BASELINE_VALID, CAPABILITY_SUPPORTED) plus the new
PLAN_NOT_STALE gate, and the safety-policy BLOCK behavior for
CONTROLLED_REAL/PRODUCTION. No fakecloud/tofu/kind dependency — pure
in-process object construction.
"""

from __future__ import annotations

from infra_again.execution.phase7_models import (
    ExecutionPackage, ExecutionTarget, ExecutionFidelity, ExecutionTask, ActionType,
)
from infra_again.execution.policy import ExecutionPolicyEngine
from infra_again.execution.preflight import PreflightEngine
from infra_again.implementation.architecture_planner import generate_implementation_plan_from_architecture
from infra_again.implementation.models import PlanStatus


def _node(node_id, category, provider, native_service):
    return {"nodeId": node_id, "name": node_id, "category": category, "provider": provider, "nativeService": native_service}


def _package(plan, target_type="FAKECLOUD", fidelity=ExecutionFidelity.SIMULATED) -> ExecutionPackage:
    return ExecutionPackage(
        execution_package_id="EXECP-TEST", plan_id=plan.plan_id, plan_revision=plan.design_revision,
        plan_checksum=plan.plan_checksum, design_id=plan.design_id, design_revision=plan.design_revision,
        correlation_id="EXEC-TEST",
        target=ExecutionTarget(target_id="fakecloud", target_type=target_type, fidelity=fidelity,
                                endpoint_reference="http://localhost:4566"),
        fidelity=fidelity,
    )


def _find(checks, check_id):
    return next(c for c in checks if c.check_id == check_id)


# ═══════════════════════════════════════════════════════════════════
# PLAN_APPROVED — previously an unconditional-PASS stub
# ═══════════════════════════════════════════════════════════════════


def test_plan_approved_gate_blocks_unapproved_plan():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    assert plan.status == PlanStatus.REVIEW_READY  # never approved
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=1)
    check = _find(checks, "PLAN_APPROVED")
    assert check.status.value == "BLOCK"


def test_plan_approved_gate_passes_approved_plan():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=1,
                                  current_provider_intelligence_version=plan.provider_intelligence_version,
                                  current_feasibility_digest=plan.feasibility_digest)
    check = _find(checks, "PLAN_APPROVED")
    assert check.status.value == "PASS"


def test_plan_approved_gate_blocks_when_plan_missing():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=None)
    check = _find(checks, "PLAN_APPROVED")
    assert check.status.value == "FAIL"


# ═══════════════════════════════════════════════════════════════════
# DESIGN_BASELINE_VALID — architecture revision gate
# ═══════════════════════════════════════════════════════════════════


def test_design_baseline_valid_blocks_on_revision_mismatch():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=2)  # live rev differs
    check = _find(checks, "DESIGN_BASELINE_VALID")
    assert check.status.value == "BLOCK"
    assert "ARCHITECTURE_REVISION_CHANGED" in check.message


def test_design_baseline_valid_passes_on_matching_revision():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=1)
    check = _find(checks, "DESIGN_BASELINE_VALID")
    assert check.status.value == "PASS"


# ═══════════════════════════════════════════════════════════════════
# CAPABILITY_SUPPORTED — mandatory unsupported/blocked task gate (section 5)
# ═══════════════════════════════════════════════════════════════════


def test_capability_supported_blocks_when_unexecutable_task_present():
    nodes = [
        _node("N1", "STORAGE", "AWS", "s3"),
        _node("N2", "CACHE", "AWS", "elasticache"),  # known, NOT_IMPLEMENTED -> UNEXECUTABLE
    ]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=1)
    check = _find(checks, "CAPABILITY_SUPPORTED")
    assert check.status.value == "BLOCK"


def test_capability_supported_passes_when_all_executable():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=1)
    check = _find(checks, "CAPABILITY_SUPPORTED")
    assert check.status.value == "PASS"


# ═══════════════════════════════════════════════════════════════════
# PLAN_NOT_STALE — architecture/PI/feasibility drift gate
# ═══════════════════════════════════════════════════════════════════


def test_plan_not_stale_blocks_on_drift():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(
        pkg, current_plan=plan, current_architecture_revision=2,  # drifted
        current_provider_intelligence_version=plan.provider_intelligence_version,
        current_feasibility_digest=plan.feasibility_digest,
    )
    check = _find(checks, "PLAN_NOT_STALE")
    assert check.status.value == "BLOCK"


def test_plan_not_stale_passes_when_current():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1)
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(
        pkg, current_plan=plan, current_architecture_revision=1,
        current_provider_intelligence_version=plan.provider_intelligence_version,
        current_feasibility_digest=plan.feasibility_digest,
    )
    check = _find(checks, "PLAN_NOT_STALE")
    assert check.status.value == "PASS"


def test_airlock_overall_status_reflects_any_block():
    nodes = [_node("N1", "CACHE", "AWS", "elasticache")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    plan.approve("tester")
    pkg = _package(plan)
    checks = PreflightEngine.run(pkg, current_plan=plan, current_architecture_revision=1)
    assert PreflightEngine.has_fail_or_block(checks) is True


# ═══════════════════════════════════════════════════════════════════
# Safety policy — reused, never weakened (section 4 / D+E)
# ═══════════════════════════════════════════════════════════════════


def test_controlled_real_always_blocked_by_policy():
    task = ExecutionTask(execution_task_id="ET-1", implementation_task_id="T-1", work_package_id="WP-1",
                          title="t", action_type=ActionType.APPLY_LOCAL_IAC)
    target = ExecutionTarget(target_id="x", target_type="FAKECLOUD", fidelity=ExecutionFidelity.CONTROLLED_REAL)
    decision = ExecutionPolicyEngine.evaluate(task, target)
    assert decision.verdict.value == "BLOCK"
    assert decision.reason_code == "CONTROLLED_REAL_BLOCKED"


def test_production_always_blocked_by_policy():
    task = ExecutionTask(execution_task_id="ET-1", implementation_task_id="T-1", work_package_id="WP-1",
                          title="t", action_type=ActionType.APPLY_LOCAL_IAC)
    target = ExecutionTarget(target_id="x", target_type="FAKECLOUD", fidelity=ExecutionFidelity.PRODUCTION)
    decision = ExecutionPolicyEngine.evaluate(task, target)
    assert decision.verdict.value == "BLOCK"
    assert decision.reason_code == "PRODUCTION_BLOCKED"


def test_plan_only_zero_mutation_classification():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="PLAN_ONLY")
    task = plan.work_packages[0].tasks[0]
    assert task.execution_classification.value == "PLAN_ONLY"
    assert task.rollback_capability.value == "NOT_APPLICABLE"  # nothing mutates


def test_controlled_real_and_production_tasks_are_blocked_not_executable():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    for fid in ("CONTROLLED_REAL", "PRODUCTION"):
        plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity=fid)
        task = plan.work_packages[0].tasks[0]
        assert task.execution_classification.value == "BLOCKED"


# ═══════════════════════════════════════════════════════════════════
# Mapper — BLOCKED tasks never leak into an ExecutionPackage (section 5)
# ═══════════════════════════════════════════════════════════════════


def test_mapper_excludes_blocked_tasks():
    from infra_again.execution.mapper import ImplementationExecutionMapper

    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="PRODUCTION")
    target = ExecutionTarget(target_id="t", target_type="PLAN_ONLY", fidelity=ExecutionFidelity.PRODUCTION)
    exec_tasks = ImplementationExecutionMapper.map_to_execution_tasks(plan, target)
    assert exec_tasks == []


def test_mapper_excludes_unexecutable_tasks():
    from infra_again.execution.mapper import ImplementationExecutionMapper

    nodes = [_node("N1", "CACHE", "AWS", "elasticache")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    target = ExecutionTarget(target_id="t", target_type="FAKECLOUD", fidelity=ExecutionFidelity.SIMULATED)
    exec_tasks = ImplementationExecutionMapper.map_to_execution_tasks(plan, target)
    assert exec_tasks == []


def test_mapper_includes_executable_tasks():
    from infra_again.execution.mapper import ImplementationExecutionMapper

    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    plan = generate_implementation_plan_from_architecture(nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED")
    target = ExecutionTarget(target_id="t", target_type="FAKECLOUD", fidelity=ExecutionFidelity.SIMULATED)
    exec_tasks = ImplementationExecutionMapper.map_to_execution_tasks(plan, target)
    assert len(exec_tasks) == 1
