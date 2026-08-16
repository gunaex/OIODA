"""Phase N2 — Architecture Feasibility / Executability acceptance tests.

Covers the N2 entry audit (service granularity, fidelity-scoped capability),
the fidelity matrix, blocking semantics, coverage/blocker-override rules,
quality-vs-executability separation, and the required test scenarios A-I
from the N2 master prompt.
"""

from __future__ import annotations

from infra_again.intelligence.catalog import CatalogLifecycle, ProviderCatalog, ProviderService
from infra_again.intelligence.feasibility import assess_architecture_feasibility
from infra_again.intelligence.provider_resolver import ProviderServiceResolver


def _resolver_with(*services: ProviderService) -> ProviderServiceResolver:
    cat = ProviderCatalog()
    for s in services:
        cat._services[f"{s.provider}:{s.service_id}"] = s
    return ProviderServiceResolver(catalog=cat)


def _node(node_id, category, provider, native_service, platform="") -> dict:
    return {"nodeId": node_id, "category": category, "provider": provider,
            "nativeService": native_service, "platform": platform}


# ═══════════════════════════════════════════════════════════════════
# 0.1 SERVICE_FAMILY_NOT_EQUAL_EXECUTION_MODE / ECS_FARGATE_EXECUTION_CAPABILITY_DISTINCT
# ═══════════════════════════════════════════════════════════════════


def test_ecs_family_support_does_not_imply_fargate_support():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="ecs", display_name="Amazon ECS",
        category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["LOCAL_RUNTIME"],
    ))
    family = resolver.resolve("AWS", "ecs")
    fargate = resolver.resolve("AWS", "ecs_fargate")
    assert family.execution_support_state == "LOCAL_RUNTIME"
    assert family.executor_available is True
    assert fargate.runtime_mode == "FARGATE"
    assert fargate.execution_support_state == "UNSUPPORTED"
    assert fargate.executor_available is False


def test_ecs_fargate_gains_support_only_via_explicit_launch_types():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="ecs", display_name="Amazon ECS",
        category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["LOCAL_RUNTIME"],
        launch_types={"FARGATE": ["SIMULATED"]},
    ))
    fargate = resolver.resolve("AWS", "ecs_fargate")
    assert fargate.execution_support_state == "SIMULATED"
    assert fargate.executor_available is True
    # Family list (LOCAL_RUNTIME) must not leak into the Fargate-specific state.
    assert fargate.execution_support_state != "LOCAL_RUNTIME"


# ═══════════════════════════════════════════════════════════════════
# 0.2 CAPABILITY_IS_FIDELITY_SCOPED
# ═══════════════════════════════════════════════════════════════════


def test_capability_is_scoped_per_fidelity_not_global():
    resolver = ProviderServiceResolver()
    sim = resolver.resolve_fidelity("AWS", "s3", "SIMULATED")
    sandbox = resolver.resolve_fidelity("AWS", "s3", "SANDBOX")
    assert sim.ready is True and sim.executor_available is True
    assert sandbox.ready is False and sandbox.executor_available is False


# ═══════════════════════════════════════════════════════════════════
# Section 3 — fidelity matrix
# ═══════════════════════════════════════════════════════════════════


def test_plan_only_independent_of_executor():
    resolver = ProviderServiceResolver()
    fc = resolver.resolve_fidelity("AWS", "elasticache", "PLAN_ONLY")  # known, unsupported
    assert fc.ready is True
    assert fc.executor_available is False


def test_simulated_capability_distinct_from_other_fidelities():
    resolver = ProviderServiceResolver()
    assert resolver.resolve_fidelity("AWS", "s3", "SIMULATED").ready is True
    assert resolver.resolve_fidelity("AWS", "s3", "LOCAL_RUNTIME").ready is False


def test_sandbox_capability_distinct_and_requires_approval_when_ready():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["SANDBOX"],
    ))
    fc = resolver.resolve_fidelity("AWS", "widget", "SANDBOX")
    assert fc.ready is True
    assert fc.policy_verdict == "ASK"


def test_controlled_real_always_policy_blocked():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["CONTROLLED_REAL"],  # even if catalog claims support
    ))
    fc = resolver.resolve_fidelity("AWS", "widget", "CONTROLLED_REAL")
    assert fc.ready is False
    assert fc.policy_verdict == "BLOCK"


def test_production_always_policy_blocked():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["PRODUCTION"],
    ))
    fc = resolver.resolve_fidelity("AWS", "widget", "PRODUCTION")
    assert fc.ready is False
    assert fc.policy_verdict == "BLOCK"


# ═══════════════════════════════════════════════════════════════════
# Section 4 — blocking semantics
# ═══════════════════════════════════════════════════════════════════


def test_unknown_service_blocks_execution():
    nodes = [_node("N1", "DATABASE", "AWS", "totally_made_up_service")]
    a = assess_architecture_feasibility(nodes)
    assert a.overall_executability == "NOT_EXECUTABLE"
    assert a.unknown_count == 1
    assert a.blocking_issues


def test_unsupported_service_blocks_execution_but_not_plan_only():
    nodes = [_node("N1", "DATABASE", "AWS", "elasticache")]  # known, NOT_IMPLEMENTED
    at_sim = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    at_plan = assess_architecture_feasibility(nodes, requested_fidelity="PLAN_ONLY")
    assert at_sim.overall_executability == "NOT_EXECUTABLE"
    assert at_sim.blocking_issues
    assert at_plan.plan_only_ready is True
    assert not at_plan.blocking_issues


def test_executor_gap_blocks_execution():
    nodes = [_node("N1", "DATABASE", "AWS", "rds")]  # PLAN_ONLY only
    a = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    assert a.executable_nodes == 0
    assert a.overall_executability == "NOT_EXECUTABLE"


def test_observer_gap_blocks_verified_success_not_execution():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["LOCAL_RUNTIME"], executor_support=["LOCAL_RUNTIME"],
        observer_support=[],  # explicitly zero
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    a = assess_architecture_feasibility(nodes, requested_fidelity="LOCAL_RUNTIME", resolver=resolver)
    nf = a.node_feasibility[0]
    assert nf.executor_available is True
    assert nf.observer_available is False
    assert nf.verified_success_available is False
    assert a.overall_executability == "EXECUTABLE"  # execution itself is not blocked


def test_validator_gap_blocks_verified_success():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["LOCAL_RUNTIME"], executor_support=["LOCAL_RUNTIME"],
        validator_support=[],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    a = assess_architecture_feasibility(nodes, requested_fidelity="LOCAL_RUNTIME", resolver=resolver)
    nf = a.node_feasibility[0]
    assert nf.validator_available is False
    assert nf.verified_success_available is False


def test_verifier_gap_blocks_final_verification():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["LOCAL_RUNTIME"], executor_support=["LOCAL_RUNTIME"],
        verifier_support=[],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    a = assess_architecture_feasibility(nodes, requested_fidelity="LOCAL_RUNTIME", resolver=resolver)
    nf = a.node_feasibility[0]
    assert nf.verifier_available is False
    assert nf.verified_success_available is False


def test_schema_gap_blocks_required_execution_at_high_fidelity_only():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.DISCOVERED,  # not schema-validated
        execution_support=["SANDBOX"],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    at_sandbox = assess_architecture_feasibility(nodes, requested_fidelity="SANDBOX", resolver=resolver)
    assert any("schema" in b.lower() for b in at_sandbox.blocking_issues)


# ═══════════════════════════════════════════════════════════════════
# Section 5 — BLOCKER_OVERRIDES_PERCENTAGE
# ═══════════════════════════════════════════════════════════════════


def test_blocker_overrides_percentage():
    # 9 supported nodes (S3) + 1 unsupported (ElastiCache) = 90% coverage,
    # but the architecture must still be reported PARTIALLY/NOT executable —
    # a high percentage never silently overrides a real per-node blocker.
    nodes = [_node(f"N{i}", "STORAGE", "AWS", "s3") for i in range(9)]
    nodes.append(_node("N9", "DATABASE", "AWS", "elasticache"))
    a = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    assert a.executor_coverage == 0.9
    assert a.overall_executability != "EXECUTABLE"
    assert a.blocking_issues


# ═══════════════════════════════════════════════════════════════════
# Section 6 — QUALITY_NOT_EQUAL_EXECUTABILITY
# ═══════════════════════════════════════════════════════════════════


def test_quality_pass_can_coexist_with_not_executable():
    # A real, quality-passing generated architecture (RDS is a required role
    # here and is catalogued PLAN_ONLY-only) still has a genuine execution
    # gap at SIMULATED fidelity — quality and executability are independent
    # dimensions, and QUALITY=PASS must never be read as EXECUTABILITY=YES.
    from infra_again.intelligence.againpilot import (
        AgainPilotRequest, ProviderPreference, generate_architecture,
        validate_architecture_quality,
    )

    request = AgainPilotRequest(
        brief="Build a patient portal on AWS for 10,000 users/day. "
              "Use private database access, containerized workloads, "
              "high availability and PDPA-aligned security.",
        provider_preference=ProviderPreference.AWS,
    )
    proposal = generate_architecture(request)
    node_dicts = [n.to_dict() for n in proposal.nodes]
    edge_dicts = [e.to_dict() for e in proposal.edges]
    group_dicts = [g.to_dict() for g in proposal.groups]
    quality = validate_architecture_quality(
        node_dicts, edge_dicts, group_dicts, "AWS", proposal.detected_requirements, "TEST",
    )
    assert quality.overall.value == "PASS"

    feasibility = assess_architecture_feasibility(node_dicts, requested_fidelity="SIMULATED")
    assert feasibility.overall_executability != "EXECUTABLE"
    assert feasibility.blocking_issues


# ═══════════════════════════════════════════════════════════════════
# Section 9 — required test scenarios A-I
# ═══════════════════════════════════════════════════════════════════


def test_scenario_a_fully_simulated_supported_architecture():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    a = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    assert a.simulated_ready is True
    assert a.overall_executability == "EXECUTABLE"


def test_scenario_b_unknown_service():
    nodes = [_node("N1", "DATABASE", "AWS", "nonexistent_xyz")]
    b = assess_architecture_feasibility(nodes)
    assert b.overall_executability == "NOT_EXECUTABLE"


def test_scenario_c_executor_missing_blocks_execution():
    nodes = [_node("N1", "DATABASE", "AWS", "elasticache")]
    c = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    assert c.executable_nodes == 0
    assert c.overall_executability == "NOT_EXECUTABLE"


def test_scenario_d_executor_exists_observer_missing():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["SIMULATED"], executor_support=["SIMULATED"], observer_support=[],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    d = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED", resolver=resolver)
    nf = d.node_feasibility[0]
    assert nf.executor_available is True
    assert nf.verified_success_available is False


def test_scenario_e_validator_missing():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["SIMULATED"], validator_support=[],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    e = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED", resolver=resolver)
    assert e.node_feasibility[0].verified_success_available is False


def test_scenario_f_verifier_missing():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="widget", display_name="Widget",
        category="COMPUTE", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["SIMULATED"], verifier_support=[],
    ))
    nodes = [_node("N1", "APPLICATION", "AWS", "widget")]
    f = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED", resolver=resolver)
    assert f.node_feasibility[0].verified_success_available is False


def test_scenario_g_s3_simulated_only():
    nodes = [_node("N1", "STORAGE", "AWS", "s3")]
    sim = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    assert sim.simulated_ready is True
    assert sim.sandbox_ready is False


def test_scenario_h_ecs_family_vs_fargate_no_accidental_inheritance():
    resolver = _resolver_with(ProviderService(
        provider="AWS", service_id="ecs", display_name="Amazon ECS",
        category="CONTAINER_RUNTIME", lifecycle=CatalogLifecycle.VERIFIED,
        execution_support=["LOCAL_RUNTIME"],
    ))
    family_nodes = [_node("N1", "APPLICATION", "AWS", "ecs")]
    fargate_nodes = [_node("N1", "APPLICATION", "AWS", "ecs_fargate")]
    family = assess_architecture_feasibility(family_nodes, requested_fidelity="LOCAL_RUNTIME", resolver=resolver)
    fargate = assess_architecture_feasibility(fargate_nodes, requested_fidelity="LOCAL_RUNTIME", resolver=resolver)
    assert family.overall_executability == "EXECUTABLE"
    assert fargate.overall_executability == "NOT_EXECUTABLE"


def test_scenario_i_quality_pass_execution_gap():
    nodes = [_node("N1", "DATABASE", "AWS", "rds")]
    i = assess_architecture_feasibility(nodes, requested_fidelity="SIMULATED")
    assert i.overall_executability == "NOT_EXECUTABLE"


# ═══════════════════════════════════════════════════════════════════
# Section 12 — LLM_CANNOT_SET_EXECUTABILITY / FRONTEND_CANNOT_SET_EXECUTABILITY
# ═══════════════════════════════════════════════════════════════════


def test_incoming_node_cannot_claim_its_own_executability():
    node = _node("N1", "DATABASE", "AWS", "elasticache")
    # Simulate an LLM- or frontend-supplied node dict that already claims
    # full support/executability — these fields must be completely ignored.
    node["providerLifecycleState"] = "SUPPORTED"
    node["executionSupportState"] = "PRODUCTION"
    node["executorAvailable"] = True
    node["overallExecutability"] = "EXECUTABLE"
    a = assess_architecture_feasibility([node], requested_fidelity="SIMULATED")
    assert a.overall_executability == "NOT_EXECUTABLE"
    assert a.node_feasibility[0].execution_support_state == "UNSUPPORTED"
