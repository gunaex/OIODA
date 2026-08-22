from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models as m
from app.db import Base
from app.deliverables import impact, resolution
from app.deliverables.models import (ImpactActionRoute, ImpactConfirmation,
                                     ImpactResolutionEvent)


@pytest.fixture()
def context(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'resolution.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(conn, _): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    project = m.Project(key="RESOLVE", name="Resolve")
    db.add(project); db.flush()
    rel = impact.relationship(project_id=project.id, source_type="DOCUMENT_VERSION", source_id="D1",
        target_type="QA_CONTEXT", target_id="UNRESOLVED:QA", relationship_type="AFFECTS",
        relationship_class="UNKNOWN", source_authority="NO_RELIABLE_RELATIONSHIP_RECORDED",
        provenance={"snapshot_hash": "H1"}, observed_at="2026-08-22T00:00:00Z", status="UNRESOLVED")
    confirmation = ImpactConfirmation(project_id=project.id, relationship_id=rel["relationship_id"],
        impact_candidate_id="IMP-1", relationship_class_at_review="UNKNOWN", relationship_snapshot=rel,
        decision="CONFIRMED", actor_user_id="human", actor_name="Human", evidence_hash="H1",
        change_id="CHANGE-1", idempotency_key="confirm-resolution")
    db.add(confirmation); db.flush()
    route = ImpactActionRoute(project_id=project.id, impact_candidate_id="IMP-1",
        confirmation_id=confirmation.id, action_type="ROUTE_QA_VALIDATION_HANDOFF",
        target_service="QA_AGAIN", target_entity_id="qa-1", requested_by="human", parameters={},
        precondition_snapshot={"evidence": "H1"}, evidence_hash="H1", idempotency_key="route-resolution",
        status="SUCCEEDED", result_ref={"service": "QA_AGAIN", "entity_id": "qa-result-1"})
    db.add(route); db.commit()
    yield db, project, confirmation, route
    db.close(); engine.dispose()


def truth(status="OK", *, complete=False):
    return {"contract_version": "project_truth/v1", "generated_at": "2026-08-22T01:00:00Z",
        "sources": {"qa": {"source_status": status, "source_revision": "q1"}},
        "qa": {"evidence_status": "COMPLETE" if complete else "MISSING",
               "remaining_test_count": 0 if complete else 1, "failed_test_count": 0,
               "blocked_test_count": 0, "blocking_defect_count": 0}, "downstream_call_count": 3}


def test_action_success_is_waiting_not_resolved(context):
    db, project, confirmation, _route = context
    result = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth())
    assert result["resolution_state"] == "WAITING_ON_OWNER"
    assert result["owner_result_ref"]["entity_id"] == "qa-result-1"
    assert result["customer_acceptance"] is False


def test_authoritative_qa_evidence_resolves_and_history_is_immutable(context):
    db, project, confirmation, _route = context
    first = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth())
    second = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth(complete=True))
    third = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth(complete=True))
    assert first["resolution_state"] == "WAITING_ON_OWNER"
    assert second["resolution_state"] == third["resolution_state"] == "RESOLVED"
    assert [x["state"] for x in third["history"]] == ["WAITING_ON_OWNER", "RESOLVED"]
    assert db.query(ImpactResolutionEvent).count() == 2


def test_unknown_stale_and_reopen_are_never_false_green(context):
    db, project, confirmation, _route = context
    unknown = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth("UNAVAILABLE"))
    resolved = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth(complete=True))
    reopened = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth())
    stale = resolution.evaluate(db, project, confirmation, current_evidence_hash="H2",
        authorization=None, actor_id="human", truth=truth(complete=True))
    assert unknown["resolution_state"] == "UNKNOWN"
    assert resolved["resolution_state"] == "RESOLVED"
    assert reopened["resolution_state"] == "WAITING_ON_OWNER"
    assert reopened["history"][-1]["event_type"] == "IMPACT_RESOLUTION_REOPENED"
    assert stale["resolution_state"] == "RECHECK_REQUIRED"


def test_ai_claim_has_no_resolution_authority(context):
    db, project, confirmation, _route = context
    result = resolution.evaluate(db, project, confirmation, current_evidence_hash="H1",
        authorization=None, actor_id="human", truth=truth())
    ai_output = {"summary": "This issue is resolved."}
    assert ai_output and result["resolution_state"] == "WAITING_ON_OWNER"
    assert resolution.registry()["ai_resolution_authority"] == "NONE"
