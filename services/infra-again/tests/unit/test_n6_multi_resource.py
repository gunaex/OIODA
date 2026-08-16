"""Phase N6 — multi-resource execution support acceptance tests.

Covers the minimal catalog+executor extension approved for N6 (ELB/Lambda/
CloudWatch, each genuinely fakecloud-verified — see catalog.py notes) and
proves the specific structural finding that motivated it: AGAINPILOT's
completeness validator unconditionally requires EDGE_INGRESS/
APPLICATION_ENTRY/OBSERVABILITY roles, and — before N6 — no service in any
of those categories had real execution backing, making a SIMULATED,
zero-blocking-task, completeness-passing architecture impossible.
No fakecloud dependency — pure logic / catalog inspection.
"""

from __future__ import annotations

from infra_again.execution.phase7_models import ExecutionTask, ActionType
from infra_again.execution.executor import FakecloudExecutor
from infra_again.implementation.architecture_planner import generate_implementation_plan_from_architecture
from infra_again.intelligence.catalog import get_catalog


def _task(canonical_service_id: str, task_id: str = "ET-ABCDEF12") -> ExecutionTask:
    return ExecutionTask(
        execution_task_id=task_id, implementation_task_id="T-1", work_package_id="WP-1",
        title="t", action_type=ActionType.APPLY_LOCAL_IAC, canonical_service_id=canonical_service_id,
    )


# ═══════════════════════════════════════════════════════════════════
# Catalog — genuinely verified SIMULATED support for elb/lambda/cloudwatch
# ═══════════════════════════════════════════════════════════════════


def test_catalog_has_verified_simulated_support_for_n6_services():
    cat = get_catalog()
    for sid in ("elb", "lambda", "cloudwatch", "s3"):
        svc = cat.get_service("AWS", sid)
        assert svc is not None
        assert svc.lifecycle.value in ("VERIFIED", "SUPPORTED")
        assert "SIMULATED" in svc.execution_support


def test_n6_services_span_the_previously_missing_completeness_roles():
    """elb=NETWORK/GATEWAY-ish (EDGE_INGRESS), lambda=APPLICATION
    (APPLICATION_ENTRY), cloudwatch=OBSERVABILITY — exactly the three
    unconditionally-required completeness roles that had zero execution
    backing before N6."""
    cat = get_catalog()
    assert cat.get_service("AWS", "elb").category == "LOAD_BALANCING"
    assert cat.get_service("AWS", "lambda").category == "SERVERLESS"
    assert cat.get_service("AWS", "cloudwatch").category == "OBSERVABILITY"


# ═══════════════════════════════════════════════════════════════════
# Executor — service-aware resource identity dispatch
# ═══════════════════════════════════════════════════════════════════


def test_resource_name_dispatches_by_canonical_service_id():
    corr = "EXEC-ABCD1234"
    s3_name = FakecloudExecutor.resource_name(_task("s3"), corr)
    elb_name = FakecloudExecutor.resource_name(_task("elb"), corr)
    lambda_name = FakecloudExecutor.resource_name(_task("lambda"), corr)
    cw_name = FakecloudExecutor.resource_name(_task("cloudwatch"), corr)
    assert s3_name.startswith("infra-again-")
    assert elb_name.startswith("ia-")
    assert lambda_name.startswith("infra-again-")
    assert cw_name.startswith("/infra-again/")
    # All four must be distinguishable from each other for the same task id.
    assert len({s3_name, elb_name, lambda_name, cw_name}) == 4


def test_resource_name_defaults_to_s3_for_unset_service_id():
    """Pre-N6 tasks never set canonical_service_id — must fall back to the
    original S3-only behavior exactly, so N4/N5 callers are unaffected."""
    task = _task("")
    assert FakecloudExecutor.resource_name(task, "EXEC-ABCD1234") == FakecloudExecutor._bucket_name(task, "EXEC-ABCD1234")


def test_observed_ids_for_scopes_to_the_right_resource_list():
    obs = {"observed": {"buckets": ["b1"], "loadBalancers": ["lb1"], "functions": ["f1"], "logGroups": ["g1"]}}
    assert FakecloudExecutor.observed_ids_for(_task("s3"), obs) == ["b1"]
    assert FakecloudExecutor.observed_ids_for(_task("elb"), obs) == ["lb1"]
    assert FakecloudExecutor.observed_ids_for(_task("lambda"), obs) == ["f1"]
    assert FakecloudExecutor.observed_ids_for(_task("cloudwatch"), obs) == ["g1"]


# ═══════════════════════════════════════════════════════════════════
# The structural finding this phase resolved
# ═══════════════════════════════════════════════════════════════════


def _node(node_id, category, native_service):
    return {"nodeId": node_id, "name": node_id, "category": category, "provider": "AWS", "nativeService": native_service}


def test_completeness_required_roles_are_now_simulated_executable():
    """Before N6: any completeness-passing architecture (which unconditionally
    needs EDGE_INGRESS/APPLICATION_ENTRY/OBSERVABILITY nodes) necessarily
    contained UNEXECUTABLE tasks at SIMULATED fidelity, since none of those
    categories had real backing. After N6, a minimal architecture using
    exactly those three roles plus S3 is fully EXECUTABLE with zero
    blocking tasks."""
    nodes = [
        _node("N1", "NETWORK", "alb"),        # -> elb via alias
        _node("N2", "APPLICATION", "lambda"),
        _node("N3", "STORAGE", "s3"),
        _node("N4", "OBSERVABILITY", "cloudwatch"),
    ]
    plan = generate_implementation_plan_from_architecture(
        nodes, [], architecture_id="A", architecture_revision=1, target_fidelity="SIMULATED",
    )
    classifications = [t.execution_classification.value for wp in plan.work_packages for t in wp.tasks]
    assert classifications == ["EXECUTABLE"] * 4
    assert plan.blockers == []
    assert plan.readiness.value == "READY_FOR_LOCAL_IMPLEMENTATION"


def test_completeness_gate_passes_for_the_same_minimal_architecture():
    from infra_again.intelligence.againpilot import validate_architecture_completeness, DetectedRequirement

    nodes = [
        _node("N1", "NETWORK", "alb"),
        _node("N2", "APPLICATION", "lambda"),
        _node("N3", "STORAGE", "s3"),
        _node("N4", "OBSERVABILITY", "cloudwatch"),
    ]
    req = DetectedRequirement(provider="AWS", platform="NATIVE_VM", expected_load="", availability=[],
                               compliance=[], security=[], data_sensitivity=[])
    report = validate_architecture_completeness(nodes, [], req)
    assert report.overall.value == "PASS"
    assert report.missing_roles == []
