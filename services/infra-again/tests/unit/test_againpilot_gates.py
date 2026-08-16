"""AGAINPILOT quality/completeness gate tests — UNIT.

Pure function tests against validate_architecture_quality and
validate_architecture_completeness. No network, no FastAPI, no Ollama.

These did not exist before this review: AGAINPILOT (the real-AI architecture
generation engine) had zero test coverage anywhere in tests/ or
scripts/acceptance — the "golden_scenario" / "phase2b" / "phase3" suites all
exercise the unrelated infrastructure-execution engine. The tests here are
specifically designed to catch "false PASS" gates per the review's negative
test list (Phase 17): a gate that can be satisfied by evidence that doesn't
actually prove the property it claims to check.
"""

from __future__ import annotations

import pytest

from infra_again.intelligence.againpilot import (
    AgainPilotRequest,
    DetectedRequirement,
    ProviderPreference,
    PlatformPreference,
    QualityResult,
    generate_architecture,
    validate_architecture_completeness,
    validate_architecture_quality,
)


GOLDEN_BRIEF = (
    "Build a patient portal on AWS for 10,000 users/day. "
    "Use private database access, containerized workloads, "
    "high availability and PDPA-aligned security."
)


def _req(**overrides) -> DetectedRequirement:
    base = dict(
        provider="AWS", platform="KUBERNETES", expected_load="10000 users/day",
        availability=["HIGH_AVAILABILITY"], compliance=["PDPA"],
        security=["PRIVATE_DATABASE"], data_sensitivity=["PERSONAL_DATA"],
    )
    base.update(overrides)
    return DetectedRequirement(**base)


def _node(node_id, category, provider="AWS", native_service="", zone="private", name=None, platform="NATIVE_VM"):
    return {
        "nodeId": node_id, "name": name or node_id, "category": category,
        "provider": provider, "nativeService": native_service, "platform": platform,
        "securityZone": zone, "dataClassification": "internal", "owner": "", "source": "AI_GENERATED",
        "verificationState": "UNVERIFIED", "properties": {}, "serviceVerification": "SUPPORTED",
    }


def _edge(eid, src, tgt, etype="request", proto="HTTPS", sec="none"):
    return {
        "edgeId": eid, "sourceNodeId": src, "targetNodeId": tgt, "type": etype,
        "protocol": proto, "direction": "unidirectional", "dataType": "", "securityClassification": sec, "label": proto,
    }


# ---------------------------------------------------------------------------
# Golden scenario — PASS
# ---------------------------------------------------------------------------


class TestGoldenScenario:
    """AWS patient portal, 10k users/day, private DB, containers, PDPA, HA."""

    @pytest.fixture
    def proposal(self):
        req = AgainPilotRequest(
            brief=GOLDEN_BRIEF,
            provider_preference=ProviderPreference.AWS,
            platform_preference=PlatformPreference.KUBERNETES,
        )
        return generate_architecture(req)

    def test_provider_is_aws(self, proposal):
        assert proposal.detected_requirements.provider == "AWS"

    def test_no_exact_node_count_required_but_not_shallow(self, proposal):
        # Per review Phase 16: do not assert an exact node count — assert the
        # architecture isn't the 4-node/2-edge shallow shape this review exists
        # to catch.
        assert len(proposal.nodes) > 6
        assert len(proposal.edges) > 6

    def test_no_on_prem_nodes(self, proposal):
        assert all(n.provider != "ON_PREM" for n in proposal.nodes)

    def test_quality_and_completeness_pass(self, proposal):
        nd = [n.to_dict() for n in proposal.nodes]
        ed = [e.to_dict() for e in proposal.edges]
        gd = [g.to_dict() for g in proposal.groups]
        quality = validate_architecture_quality(nd, ed, gd, "AWS", proposal.detected_requirements, "TEST")
        completeness = validate_architecture_completeness(nd, ed, proposal.detected_requirements)
        assert quality.overall != QualityResult.FAIL, quality.to_dict()
        assert completeness.overall == QualityResult.PASS, completeness.to_dict()
        assert completeness.missing_roles == []

    def test_no_direct_internet_to_database(self, proposal):
        nd = [n.to_dict() for n in proposal.nodes]
        ed = [e.to_dict() for e in proposal.edges]
        gd = [g.to_dict() for g in proposal.groups]
        quality = validate_architecture_quality(nd, ed, gd, "AWS", proposal.detected_requirements, "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "NO_DIRECT_INTERNET_TO_DATABASE")
        assert gate["result"] == "PASS"

    def test_database_is_private(self, proposal):
        db_nodes = [n for n in proposal.nodes if n.category == "DATABASE"]
        assert db_nodes
        assert all(n.security_zone == "private" for n in db_nodes)


# ---------------------------------------------------------------------------
# Negative tests — Phase 17. Each of these must NOT pass.
# ---------------------------------------------------------------------------


class TestFalsePassPrevention:
    def test_private_db_requested_but_db_public_fails_completeness(self):
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-LB", "NETWORK", native_service="alb", zone="dmz"),
            _node("N-APP", "APPLICATION", native_service="ecs", zone="private"),
            _node("N-DB", "DATABASE", native_service="rds", zone="public"),  # NOT private
        ]
        edges = [
            _edge("E1", "N-USER", "N-LB"), _edge("E2", "N-LB", "N-APP"),
            _edge("E3", "N-APP", "N-DB", etype="data"),
        ]
        req = _req()
        completeness = validate_architecture_completeness(nodes, edges, req)
        assert "PRIVATE_DATABASE" in completeness.missing_roles
        assert completeness.overall == QualityResult.FAIL

    def test_ha_requested_single_app_runtime_fails(self):
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-LB", "NETWORK", native_service="alb", zone="dmz"),
            _node("N-APP", "APPLICATION", native_service="ecs", zone="private"),
            _node("N-DB", "DATABASE", native_service="rds", zone="private"),
        ]
        edges = [_edge("E1", "N-USER", "N-LB"), _edge("E2", "N-LB", "N-APP"), _edge("E3", "N-APP", "N-DB", etype="data")]
        quality = validate_architecture_quality(nodes, edges, [], "AWS", _req(), "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "HA_REQUIREMENT_SATISFIED")
        assert gate["result"] == "FAIL"

    def test_two_identical_app_nodes_do_not_auto_pass_ha(self):
        """Anti-pattern named explicitly in the review: HA=true purely because
        application node count >= 2, with no AZ/replica/standby distinction."""
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-LB", "NETWORK", native_service="alb", zone="dmz"),
            _node("N-APP-1", "APPLICATION", native_service="ecs", zone="private", name="Application"),
            _node("N-APP-2", "APPLICATION", native_service="ecs", zone="private", name="Application"),
            _node("N-DB", "DATABASE", native_service="rds", zone="private"),
        ]
        edges = [_edge("E1", "N-USER", "N-LB"), _edge("E2", "N-LB", "N-APP-1"), _edge("E3", "N-APP-1", "N-DB", etype="data")]
        quality = validate_architecture_quality(nodes, edges, [], "AWS", _req(), "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "HA_REQUIREMENT_SATISFIED")
        assert gate["result"] == "FAIL", "two unlabeled duplicate app nodes must not satisfy HA"

    def test_two_app_nodes_with_az_signal_passes_ha(self):
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-LB", "NETWORK", native_service="alb", zone="dmz"),
            _node("N-APP-1", "APPLICATION", native_service="ecs", zone="private", name="Application (AZ-A)"),
            _node("N-APP-2", "APPLICATION", native_service="ecs", zone="private", name="Application (AZ-B)"),
            _node("N-DB", "DATABASE", native_service="rds", zone="private"),
        ]
        edges = [_edge("E1", "N-USER", "N-LB"), _edge("E2", "N-LB", "N-APP-1"), _edge("E3", "N-APP-1", "N-DB", etype="data")]
        quality = validate_architecture_quality(nodes, edges, [], "AWS", _req(), "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "HA_REQUIREMENT_SATISFIED")
        assert gate["result"] == "PASS"

    def test_aws_requested_but_onprem_service_fails_provider_gate(self):
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-APP", "APPLICATION", provider="AWS", native_service="ecs", zone="private"),
            _node("N-DB", "DATABASE", provider="ON_PREM", native_service="postgresql", zone="private"),
        ]
        edges = [_edge("E1", "N-USER", "N-APP"), _edge("E2", "N-APP", "N-DB", etype="data")]
        quality = validate_architecture_quality(nodes, edges, [], "AWS", _req(), "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "PROVIDER_CONSISTENCY")
        assert gate["result"] == "FAIL"

    def test_no_secrets_management_with_compliance_fails_security_boundaries(self):
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-APP", "APPLICATION", native_service="ecs", zone="private"),
            _node("N-DB", "DATABASE", native_service="rds", zone="private"),
        ]
        edges = [_edge("E1", "N-USER", "N-APP"), _edge("E2", "N-APP", "N-DB", etype="data")]
        quality = validate_architecture_quality(nodes, edges, [], "AWS", _req(compliance=["PDPA"]), "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "SECURITY_BOUNDARIES")
        assert gate["result"] == "FAIL"
        completeness = validate_architecture_completeness(nodes, edges, _req(compliance=["PDPA"]))
        assert "SECRET_MANAGEMENT" in completeness.missing_roles
        assert "ENCRYPTION_KEY_MANAGEMENT" in completeness.missing_roles

    def test_four_node_shallow_patient_portal_fails_completeness(self):
        """The exact shape named in the review as the observed real-AI defect:
        a minimal graph that is internally consistent (no orphans, no
        duplicates, provider-consistent) but semantically shallow."""
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-APP", "APPLICATION", native_service="ecs", zone="private"),
            _node("N-DB", "DATABASE", native_service="rds", zone="private"),
            _node("N-OBS", "OBSERVABILITY", native_service="cloudwatch", zone="private"),
        ]
        edges = [
            _edge("E1", "N-USER", "N-APP"),
            _edge("E2", "N-APP", "N-DB", etype="data"),
        ]
        req = _req()
        quality = validate_architecture_quality(nodes, edges, [], "AWS", req, "TEST")
        completeness = validate_architecture_completeness(nodes, edges, req)
        # Quality alone (internal consistency) is not enough to catch this —
        # that is the whole point of the completeness validator.
        assert completeness.overall == QualityResult.FAIL, completeness.to_dict()
        assert "EDGE_INGRESS" in completeness.missing_roles
        assert "IDENTITY_AUTH" in completeness.missing_roles
        assert "SECRET_MANAGEMENT" in completeness.missing_roles
        assert "ENCRYPTION_KEY_MANAGEMENT" in completeness.missing_roles

    def test_internet_directly_connected_to_db_fails(self):
        nodes = [
            _node("N-USER", "USER", provider="EXTERNAL"),
            _node("N-DB", "DATABASE", native_service="rds", zone="private"),
        ]
        edges = [_edge("E1", "N-USER", "N-DB", etype="data")]
        quality = validate_architecture_quality(nodes, edges, [], "AWS", _req(), "TEST")
        gate = next(c for c in quality.checks if c["gate"] == "NO_DIRECT_INTERNET_TO_DATABASE")
        assert gate["result"] == "FAIL"
