import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import command_center
from app import models as m
from app.db import Base
from app.deliverables.models import (DeliverableSignoff, HumanDeliverableInstance,
                                     ImpactActionRoute, ImpactConfirmation,
                                     ImpactResolution)


@pytest.fixture()
def fixture(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'center.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(conn, _): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    project = m.Project(key="CENTER", name="Command Center")
    db.add(project); db.flush()
    confirmation = ImpactConfirmation(project_id=project.id, relationship_id="REL-QA",
        impact_candidate_id="IMP-QA", relationship_class_at_review="AI_SUGGESTED",
        relationship_snapshot={"target_type":"QA_CONTEXT"}, decision="CONFIRMED",
        actor_user_id="human", actor_name="Human", evidence_hash="H1", idempotency_key="center-confirm")
    db.add(confirmation); db.flush()
    route = ImpactActionRoute(project_id=project.id, impact_candidate_id="IMP-QA",
        confirmation_id=confirmation.id, action_type="ROUTE_QA_VALIDATION_HANDOFF",
        target_service="QA_AGAIN", target_entity_id="qa-1", requested_by="human", parameters={},
        precondition_snapshot={}, evidence_hash="H1", idempotency_key="center-route", status="SUCCEEDED",
        result_ref={"service":"QA_AGAIN","entity_id":"qa-result"})
    db.add(route); db.flush()
    db.add(ImpactResolution(project_id=project.id, impact_candidate_id="IMP-QA",
        confirmation_id=confirmation.id, latest_action_route_id=route.id, owner_result_ref=route.result_ref,
        resolution_state="WAITING_ON_OWNER", resolution_reason="QA evidence is not present.",
        evaluation_rule_id="QA-VALIDATION-EVIDENCE-COMPLETE", evaluation_rule_version="1",
        pre_action_truth_ref={"snapshot_hash":"H0"}, post_action_truth_ref={"snapshot_hash":"H1"},
        evidence_refs=["H1"], evidence_hash="H1"))
    doc = HumanDeliverableInstance(project_id=project.id, human_code="HD-01", name="Design",
        document_id="DOC-1", version="1.0", readiness="READY_WITH_GAPS", freshness="STALE")
    db.add(doc); db.flush()
    db.add(DeliverableSignoff(project_id=project.id, human_code="HD-01", instance_id=doc.id,
        document_id="DOC-1", document_version="1.0", signoff_type="APPROVE", decision="APPROVE",
        evidence_class="TEST", purpose="APPROVAL", signer_user_id="tester", signer_name="Tester"))
    db.commit()
    yield db, project
    db.close(); engine.dispose()


def truth(qa_status="OK"):
    return {"contract_version":"project_truth/v1", "overall_freshness":"FRESH",
        "sources":{"pm":{"source_status":"OK"},"qa":{"source_status":qa_status},
                   "infra":{"source_status":"UNBOUND"}},
        "pm":{"attention":{"blocked_dependency_count":1,"slipping_item_count":1}},
        "qa":None if qa_status != "OK" else {"readiness_status":"NOT_STARTED"}, "infra":None,
        "attention":{"contract_version":"project_attention/v1",
            "counts":{"blocker":1,"issue":1,"unverified":1},
            "items":[{"id":"qa-root","domain":"QA","priority":"BLOCKER","code":"QA_ROOT","title":"QA not started"}]},
        "warnings":[] if qa_status == "OK" else ["QA source is UNAVAILABLE"], "downstream_call_count":7}


def test_command_center_composes_and_deduplicates_current_state(fixture):
    db, project = fixture
    out = command_center.compose(db, project, truth=truth())
    assert out["contract_version"] == "project_command_center/v1"
    assert out["attention"]["counts"]["blocker"] == 1
    assert len(out["resolution_summary"]["active"]) == 1
    assert not out["resolution_summary"]["recently_resolved"]
    assert out["waiting_on"] == {"QA_AGAIN": 1}
    assert out["governance"]["flag_count"] == 1
    assert out["acceptance"]["customer_accepted"] is False
    assert out["freshness"]["sources"]["INFRA"] == "UNBOUND"
    assert out["performance"]["extra_owner_calls"] == 0


def test_partial_qa_failure_does_not_fail_workspace(fixture):
    db, project = fixture
    out = command_center.compose(db, project, truth=truth("UNAVAILABLE"))
    assert out["health"]["qa"] == "UNAVAILABLE"
    assert out["health"]["infra"] == "UNBOUND"
    assert out["delivery"] is not None and out["active_impacts"]
    assert "QA source is UNAVAILABLE" in out["warnings"]


def test_resolved_is_history_not_current_blocker(fixture):
    db, project = fixture
    row = db.query(ImpactResolution).one()
    row.resolution_state = "RESOLVED"; db.commit()
    out = command_center.compose(db, project, truth=truth())
    assert not out["resolution_summary"]["active"]
    assert len(out["resolution_summary"]["recently_resolved"]) == 1
    assert out["attention"]["counts"]["blocker"] == 1


def test_ai_not_configured_keeps_deterministic_focus(fixture, monkeypatch):
    db, project = fixture
    center = command_center.compose(db, project, truth=truth())
    monkeypatch.setattr(command_center.reviewer, "_provider", lambda: None)
    out = command_center.copilot(center, query_type="FOCUS_TODAY")
    assert out["status"] == "NOT_CONFIGURED" and out["focus_items"]
    assert out["auto_execution"] is False and out["ai_authority"] == "NONE"
    assert all(i in {e["evidence_id"] for e in center["copilot_context"]["evidence"]}
               for i in out["evidence_citations"])


def test_copilot_rejects_unknown_action_false_acceptance_and_false_resolution(fixture):
    db, project = fixture
    center = command_center.compose(db, project, truth=truth())
    evidence = center["copilot_context"]["evidence"]
    test_acceptance = next(e["evidence_id"] for e in evidence if e["kind"] == "ACCEPTANCE_EVIDENCE")
    waiting = next(e["evidence_id"] for e in evidence if e["kind"] == "IMPACT_RESOLUTION")
    raw = {"focus_items":[
        {"why":"Customer accepted this project.","evidence_ids":[test_acceptance]},
        {"why":"This impact is resolved.","evidence_ids":[waiting]},
        {"why":"QA validation needs review.","evidence_ids":[waiting],"action_type":"DEPLOY_INFRA"},
    ]}
    result = command_center.validate_copilot_output(raw, center)
    assert not result["focus_items"]
    assert {x["reason"] for x in result["rejected_claims"]} == {
        "CUSTOMER_ACCEPTANCE_UNSUPPORTED", "RESOLUTION_UNSUPPORTED", "UNKNOWN_ACTION"}


def test_grounded_ai_output_is_cited_and_never_executable(fixture, monkeypatch):
    db, project = fixture
    center = command_center.compose(db, project, truth=truth())
    eid = next(e["evidence_id"] for e in center["copilot_context"]["evidence"] if e["kind"] == "ATTENTION")
    monkeypatch.setattr(command_center.reviewer, "_provider", lambda: {
        "provider_id":"local","model":"test","supports_json_mode":True})
    class Provider:
        def generate_grounded_review(self, _system, _user):
            return json.dumps({"focus_items":[{"title":"QA focus","why":"QA not started needs attention",
                "status":"BLOCKER","evidence_ids":[eid],"action_type":"ROUTE_QA_VALIDATION_HANDOFF"}]})
    out = command_center.copilot(center, query_type="FOCUS_TODAY", provider_factory=lambda _: Provider())
    assert out["status"] == "AVAILABLE" and len(out["focus_items"]) == 1
    assert out["focus_items"][0]["executable"] is False
    assert out["focus_items"][0]["action_type"] == "ROUTE_QA_VALIDATION_HANDOFF"


def test_ai_failure_falls_back_without_blocking_center(fixture, monkeypatch):
    db, project = fixture
    center = command_center.compose(db, project, truth=truth())
    monkeypatch.setattr(command_center.reviewer, "_provider", lambda: {
        "provider_id":"local","model":"test","supports_json_mode":True})
    class Broken:
        def generate_grounded_review(self, _system, _user): raise TimeoutError("provider timeout")
    out = command_center.copilot(center, query_type="PROJECT_STATUS", provider_factory=lambda _: Broken())
    assert out["status"] == "TIMEOUT" and out["focus_items"]
    assert out["operational_status"] == "AI_UNAVAILABLE"
