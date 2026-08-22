from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app import models as m
from app.db import Base
from app.deliverables import impact
from app.deliverables.models import DeliverableSignoff, HumanDeliverableInstance
from app.main import app
from app.routers.deps import db_session


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'impact.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close(); engine.dispose()


def _fixture(db):
    now = datetime.now(timezone.utc)
    project = m.Project(key="IMP", name="Impact Project")
    db.add(project); db.flush()
    req = m.Requirement(project_id=project.id, code="R1", title="Encryption", status=m.RequirementStatus.CONFIRMED)
    db.add(req); db.flush()
    db.add_all([
        m.RequirementRevision(requirement_id=req.id, revision_number=4, title=req.title,
                              status=m.RequirementStatus.CONFIRMED, confirmed_at=now),
        m.RequirementRevision(requirement_id=req.id, revision_number=5, title=req.title,
                              status=m.RequirementStatus.CONFIRMED, confirmed_at=now),
    ])
    old = HumanDeliverableInstance(id="hd-v12", project_id=project.id, human_code="HD-01", name="Design",
        document_id="IMP-HD-01", version="1.2", source_snapshot={"requirements": [{"id": req.id, "revision": 4}]},
        snapshot_hash="v12", generated_at=now, created_at=now)
    current = HumanDeliverableInstance(id="hd-v13", project_id=project.id, human_code="HD-01", name="Design",
        document_id="IMP-HD-01", version="1.3", source_snapshot={"requirements": [{"id": req.id, "revision": 4}]},
        snapshot_hash="v13", supersedes_id=old.id, generated_at=now, created_at=now)
    signoff = DeliverableSignoff(id="accept-v12", project_id=project.id, human_code="HD-01",
        instance_id=old.id, document_id=old.document_id, document_version="1.2", snapshot_hash="v12",
        signoff_type="ACCEPT", decision="ACCEPT", evidence_class="CUSTOMER", purpose="ACCEPTANCE",
        signer_user_id="customer", signer_name="Customer", signed_at=now)
    db.add_all([old, current, signoff]); db.commit()
    return project, req, old, current, signoff


def test_document_impact_contract_stale_and_old_acceptance(db):
    project, req, old, current, signoff = _fixture(db)
    result = impact.document_impact(db, project, current, old, [signoff])
    assert result["contract_version"] == "impact_candidates/v1"
    assert result["relationship_contract"] == "impact_relationships/v1"
    assert {r["relationship_class"] for r in result["relationships"]} == {"EXPLICIT", "DETERMINISTIC"}
    assert any(r["relationship_type"] == "DERIVED_FROM" and r["source_id"] == req.id for r in result["relationships"])
    stale = next(i for i in result["known_impacts"] if i["impact_type"] == "POTENTIALLY_STALE")
    assert stale["rule"]["rule_id"] == "R17.3-SOURCE-REVISION-STALE"
    accepted = next(i for i in result["known_impacts"] if i["impact_type"] == "EVIDENCE_REVIEW_RECOMMENDED")
    assert accepted["target_entity"]["accepted_version"] == "1.2"
    assert accepted["target_entity"]["current_version"] == "1.3"
    assert "invalid" not in accepted["rationale"].lower()
    assert {x["domain"] for x in result["unknown"]} == {"PM", "QA", "INFRA"}
    assert result["write_actions"] == 0
    assert {x["code"] for x in result["project_attention_contribution"]["items"]} == {
        "POTENTIALLY_STALE", "EVIDENCE_REVIEW_RECOMMENDED"}


def test_explicit_one_hop_deduplicates_and_permission_filter_omits_target():
    change = impact.change_event(change_id="C1", project_id="P1", entity_type="REQUIREMENT",
        entity_id="R1", change_type="UPDATED", source_service="DOCUMENT_AGAIN", timestamp="2026-08-22T00:00:00Z",
        provenance={"revision": 5})
    rels = [impact.relationship(project_id="P1", source_type="REQUIREMENT", source_id="R1",
        target_type="QA_SCOPE", target_id="Q1", relationship_type="VERIFIES", relationship_class="EXPLICIT",
        source_authority="QA_AGAIN", provenance={"record_id": suffix}) for suffix in ("a", "b")]
    known = impact.project_impacts(change, rels, coverage=["QA", "PM"])
    assert len(known["known_impacts"]) == 1
    assert len(known["known_impacts"][0]["relationship_reasons"]) == 2
    assert known["known_impacts"][0]["relationship_class"] == "EXPLICIT"
    assert [x["domain"] for x in known["unknown"]] == ["PM"]
    hidden = impact.project_impacts(change, rels, visible=lambda _r: False, coverage=["QA"])
    assert hidden["known_impacts"] == []
    assert "Q1" not in str(hidden)


def test_ai_suggestion_never_promotes_and_unsupported_claim_is_rejected():
    base = {"project_id": "P1", "source_type": "REQUIREMENT", "source_id": "R1",
            "target_type": "INFRA_COMPONENT", "target_id": "C4", "evidence_ids": ["E1"]}
    accepted, rejected = impact.validate_ai_suggestions(
        [{**base, "reason": "The cited requirement may deserve infrastructure review.", "confidence": "MEDIUM"},
         {**base, "reason": "This will delay go-live by 2 weeks."}], {"E1"},
        provider="local", model="test", prompt_version="impact_ai_prompt/v1")
    assert len(accepted) == 1 and accepted[0]["relationship_class"] == "AI_SUGGESTED"
    assert accepted[0]["advisory"]["confirmation_status"] == "UNCONFIRMED"
    assert rejected == [{"reason": "UNSUPPORTED_IMPACT", "statement": "This will delay go-live by 2 weeks."}]


def test_impact_endpoint_is_authorized_and_ai_not_required(db, monkeypatch):
    project, _req, _old, _current, _signoff = _fixture(db)
    app.dependency_overrides[db_session] = lambda: (yield db)
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/projects/{project.id}/human-deliverables/HD-01/impact")
        assert response.status_code == 200
        assert response.json()["provider_status"] == "NOT_REQUESTED"
        assert response.json()["known_impacts"]
    finally:
        app.dependency_overrides.clear()


def test_unknown_is_valid_and_cycles_are_bounded():
    change = impact.change_event(change_id="C", project_id="P", entity_type="REQUIREMENT", entity_id="R",
        change_type="UPDATED", source_service="DOCUMENT_AGAIN", timestamp="2026-08-22T00:00:00Z", provenance={"id": "C"})
    rel = impact.relationship(project_id="P", source_type="OTHER", source_id="X", target_type="REQUIREMENT",
        target_id="R", relationship_type="DEPENDS_ON", relationship_class="EXPLICIT", source_authority="PM_AGAIN",
        provenance={"id": "REL"})
    result = impact.project_impacts(change, [rel], coverage=["PM", "QA", "INFRA"])
    assert result["known_impacts"] == []
    assert all(x["relationship_class"] == "UNKNOWN" for x in result["unknown"])
    assert result["traversal"] == {"depth": 1, "cycle_protection": True, "deduplication": "TARGET_STABLE_ID"}


def test_confirmation_preserves_origin_audits_and_is_idempotent(db):
    project, _req, old, current, signoff = _fixture(db)
    projection = impact.document_impact(db, project, current, old, [signoff])
    rel = projection["unknown"][0]["relationship"]
    actor = SimpleNamespace(id="human-1", name="Reviewer One")
    first = impact.review_relationship(
        db, project, relationship_snapshot=rel, evidence_hash="H1", current_evidence_hash="H1",
        impact_candidate_id=None, decision="CONFIRMED", reason="Relevant project context",
        actor=actor, change_id="C1")
    replay = impact.review_relationship(
        db, project, relationship_snapshot=rel, evidence_hash="H1", current_evidence_hash="H1",
        impact_candidate_id=None, decision="CONFIRMED", reason="Relevant project context",
        actor=actor, change_id="C1")
    assert first["relationship_class_at_review"] == "UNKNOWN"
    assert first["effective_context"] == "HUMAN_CONFIRMED"
    assert first["origin_relationship"]["relationship_class"] == "UNKNOWN"
    assert replay["confirmation_id"] == first["confirmation_id"]
    assert replay["idempotent_replay"] is True
    events = db.execute(select(m.AuditEvent).where(m.AuditEvent.object_id == rel["relationship_id"])).scalars().all()
    assert len(events) == 1 and events[0].action == "IMPACT_RELATIONSHIP_CONFIRMED"
    assert events[0].metadata_json["customer_acceptance"] is False


def test_reject_conflict_history_reopen_and_stale_confirmation(db):
    project, _req, old, current, signoff = _fixture(db)
    rel = impact.document_impact(db, project, current, old, [signoff])["unknown"][1]["relationship"]
    actor1 = SimpleNamespace(id="human-1", name="Reviewer One")
    actor2 = SimpleNamespace(id="human-2", name="Reviewer Two")
    impact.review_relationship(db, project, relationship_snapshot=rel, evidence_hash="H1", current_evidence_hash="H1",
                               impact_candidate_id=None, decision="REJECTED", reason="Not applicable", actor=actor1)
    impact.review_relationship(db, project, relationship_snapshot=rel, evidence_hash="H1", current_evidence_hash="H1",
                               impact_candidate_id=None, decision="CONFIRMED", reason=None, actor=actor2)
    history = impact.confirmation_history(db, project.id, current_evidence_hash="H1")
    assert len(history["history"]) == 2
    assert history["effective"][0]["decision"] == "CONFIRMED"
    stale = impact.confirmation_history(db, project.id, current_evidence_hash="H2")
    assert all(row["human_review_status"] == "STALE" for row in stale["history"])
    impact.review_relationship(db, project, relationship_snapshot=rel, evidence_hash="H1", current_evidence_hash="H1",
                               impact_candidate_id=None, decision="UNRESOLVED", reason="Reopened", actor=actor2)
    actions = db.execute(select(m.AuditEvent).where(m.AuditEvent.object_id == rel["relationship_id"])
                         .order_by(m.AuditEvent.created_at)).scalars().all()
    assert actions[-1].action == "IMPACT_RELATIONSHIP_REOPENED"


def test_rejection_memory_and_guardrails(db):
    project, _req, old, current, signoff = _fixture(db)
    projection = impact.document_impact(db, project, current, old, [signoff])
    rel = projection["unknown"][2]["relationship"]
    actor = SimpleNamespace(id="human", name="Reviewer")
    with pytest.raises(Exception, match="reason is required"):
        impact.review_relationship(db, project, relationship_snapshot=rel, evidence_hash="H", current_evidence_hash="H",
                                   impact_candidate_id=None, decision="REJECTED", reason=None, actor=actor)
    with pytest.raises(Exception, match="do not require confirmation"):
        impact.review_relationship(db, project, relationship_snapshot=projection["relationships"][0],
                                   evidence_hash="H", current_evidence_hash="H", impact_candidate_id=None,
                                   decision="CONFIRMED", reason=None, actor=actor)
    rejected = impact.review_relationship(db, project, relationship_snapshot=rel, evidence_hash="H", current_evidence_hash="H",
                                          impact_candidate_id=None, decision="REJECTED", reason="Incorrect", actor=actor)
    history = impact.confirmation_history(db, project.id, current_evidence_hash="H")
    suggestions = [{"relationship_id": rel["relationship_id"]}, {"relationship_id": "REL-new"}]
    assert impact.suppress_reviewed_suggestions(suggestions, history) == [{"relationship_id": "REL-new"}]
    assert rejected["decision"] == "REJECTED"
    with pytest.raises(Exception, match="evidence changed"):
        impact.review_relationship(db, project, relationship_snapshot=rel, evidence_hash="H", current_evidence_hash="H2",
                                   impact_candidate_id=None, decision="CONFIRMED", reason=None, actor=actor)


def test_actions_are_safe_and_owner_truth_is_unchanged(db):
    project, _req, old, current, signoff = _fixture(db)
    before_signoffs = db.query(DeliverableSignoff).count()
    result = impact.document_impact(db, project, current, old, [signoff])
    types = {row["action_type"] for row in result["suggested_actions"]["actions"]}
    assert {"REVIEW_DOCUMENT", "CONSIDER_DOCUMENT_REVISION", "REVIEW_ACCEPTANCE_VERSION", "REVIEW_EVIDENCE"} <= types
    assert not types & {"RUN_TESTS", "CHANGE_MILESTONE", "DEPLOY_INFRA", "APPROVE", "SIGN", "CREATE_CR"}
    assert result["suggested_actions"]["cross_service_domain_writes"] == 0
    assert db.query(DeliverableSignoff).count() == before_signoffs


def test_confirmation_api_and_forbidden_project_mismatch(db):
    project, _req, old, current, signoff = _fixture(db)
    projection = impact.document_impact(db, project, current, old, [signoff])
    rel = projection["unknown"][0]["relationship"]
    app.dependency_overrides[db_session] = lambda: (yield db)
    try:
        with TestClient(app) as client:
            packet = client.get(f"/api/projects/{project.id}/human-deliverables/HD-01/reviewer-evidence").json()
            response = client.post(f"/api/projects/{project.id}/human-deliverables/HD-01/impact-confirmations", json={
                "relationship": rel, "evidence_hash": packet["evidence_packet_hash"],
                "decision": "UNRESOLVED", "reason": "Need owner evidence"})
            assert response.status_code == 200
            history = client.get(f"/api/projects/{project.id}/human-deliverables/HD-01/impact-confirmations")
            assert history.status_code == 200 and len(history.json()["history"]) == 1
            forbidden = {**rel, "project_id": "another-project"}
            response = client.post(f"/api/projects/{project.id}/human-deliverables/HD-01/impact-confirmations", json={
                "relationship": forbidden, "evidence_hash": packet["evidence_packet_hash"], "decision": "CONFIRMED"})
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
