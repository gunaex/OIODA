from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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
