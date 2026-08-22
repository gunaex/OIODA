import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app import models as m
from app.db import Base
from app.deliverables import action_routing, impact
from app.deliverables.models import ImpactActionRoute, ImpactConfirmation


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'routing.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(conn, _): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close(); engine.dispose()


@pytest.fixture()
def context(db):
    project = m.Project(key="ROUTE", name="Routing", project_meta={"workspace_bindings": {"v1": {
        "pm": {"service": "PM_AGAIN", "external_project_id": "pm-route", "binding_status": "BOUND"},
        "qa": [{"service": "QA_AGAIN", "external_project_id": "qa-route", "scope_id": "scope-1", "binding_status": "BOUND"}],
        "infra": {"service": "INFRA_AGAIN", "binding_status": "UNBOUND"}}}})
    db.add(project); db.flush()
    rel = impact.relationship(project_id=project.id, source_type="DOCUMENT_VERSION", source_id="D1",
        target_type="PM_CONTEXT", target_id="UNRESOLVED:PM", relationship_type="AFFECTS",
        relationship_class="UNKNOWN", source_authority="NO_RELIABLE_RELATIONSHIP_RECORDED",
        provenance={"snapshot_hash": "H1"}, observed_at="2026-08-22T00:00:00Z", status="UNRESOLVED")
    confirmation = ImpactConfirmation(project_id=project.id, relationship_id=rel["relationship_id"],
        relationship_class_at_review="UNKNOWN", relationship_snapshot=rel, decision="CONFIRMED",
        actor_user_id="human", actor_name="Human", evidence_hash="H1", idempotency_key="confirm-key")
    db.add(confirmation); db.commit()
    return project, confirmation, SimpleNamespace(id="human", name="Human")


class FakeOwner:
    def __init__(self, exc=None): self.calls = 0; self.exc = exc
    def execute(self, db, project, action_type, parameters, actor):
        self.calls += 1
        if self.exc: raise self.exc
        return ({"service": "PM_AGAIN", "entity_id": "pm-ref-1", "handoff_id": "h1",
                 "status": "ACKNOWLEDGED", "created_at": datetime.now(timezone.utc).isoformat()}, 2.0, 1.0)


def test_preview_is_deterministic_and_never_executes_owner(db, context):
    project, confirmation, _actor = context
    out = action_routing.preview(db, project, action_type="ROUTE_PM_DELIVERY_HANDOFF",
        confirmation_id=confirmation.id, current_evidence_hash="H1")
    assert out["status"] == "READY" and out["human_trigger_required"] is True
    assert out["what_will_change"].startswith("PM Again")
    assert db.query(ImpactActionRoute).count() == 0
    assert action_routing.preview(db, project, action_type="DEPLOY_INFRA",
        confirmation_id=confirmation.id, current_evidence_hash="H1")["failure_category"] == "PROHIBITED"
    assert action_routing.preview(db, project, action_type="AI_INVENTED_TOOL",
        confirmation_id=confirmation.id, current_evidence_hash="H1")["failure_category"] == "NOT_SUPPORTED"


def test_human_execute_success_idempotency_audit_and_truth_refresh(db, context, monkeypatch):
    project, confirmation, actor = context
    owner = FakeOwner()
    monkeypatch.setattr(action_routing, "build_project_truth", lambda *_: {
        "contract_version": "project_truth/v1", "sources": {"pm": {"source_status": "OK"}}})
    first = action_routing.execute(db, project, action_type="ROUTE_PM_DELIVERY_HANDOFF",
        confirmation_id=confirmation.id, current_evidence_hash="H1", parameters={}, actor=actor, owner_router=owner)
    second = action_routing.execute(db, project, action_type="ROUTE_PM_DELIVERY_HANDOFF",
        confirmation_id=confirmation.id, current_evidence_hash="H1", parameters={}, actor=actor, owner_router=owner)
    assert first["status"] == "SUCCEEDED" and first["result_ref"]["entity_id"] == "pm-ref-1"
    assert first["result_ref"]["truth_contract"] == "project_truth/v1"
    assert second["idempotent_replay"] is True and owner.calls == 1
    assert db.query(ImpactActionRoute).count() == 1
    audit = db.execute(select(m.AuditEvent).where(m.AuditEvent.object_id == first["action_route_id"])).scalar_one()
    assert audit.action == "ACTION_SUCCEEDED" and audit.metadata_json["human_executed"] is True
    assert audit.metadata_json["customer_acceptance"] is False


def test_stale_or_unconfirmed_context_blocks_with_zero_owner_calls(db, context):
    project, confirmation, actor = context
    owner = FakeOwner()
    with pytest.raises(Exception, match="STALE"):
        action_routing.execute(db, project, action_type="ROUTE_PM_DELIVERY_HANDOFF",
            confirmation_id=confirmation.id, current_evidence_hash="H2", parameters={}, actor=actor, owner_router=owner)
    confirmation.decision = "REJECTED"; db.commit()
    with pytest.raises(Exception, match="CONFIRMED"):
        action_routing.execute(db, project, action_type="ROUTE_PM_DELIVERY_HANDOFF",
            confirmation_id=confirmation.id, current_evidence_hash="H1", parameters={}, actor=actor, owner_router=owner)
    assert owner.calls == 0


def test_qa_multiple_scope_requires_human_input(db, context):
    project, confirmation, _actor = context
    confirmation.relationship_snapshot = {**confirmation.relationship_snapshot, "target_id": "UNRESOLVED:QA"}
    meta = json.loads(json.dumps(project.project_meta))
    meta["workspace_bindings"]["v1"]["qa"].append(
        {"service": "QA_AGAIN", "external_project_id": "qa-2", "scope_id": "scope-2", "binding_status": "BOUND"})
    project.project_meta = meta
    db.commit()
    out = action_routing.preview(db, project, action_type="ROUTE_QA_VALIDATION_HANDOFF",
        confirmation_id=confirmation.id, current_evidence_hash="H1", parameters={})
    assert out["status"] == "REQUIRES_INPUT" and out["required_input"] == ["qa_scope_id"]
    ready = action_routing.preview(db, project, action_type="ROUTE_QA_VALIDATION_HANDOFF",
        confirmation_id=confirmation.id, current_evidence_hash="H1", parameters={"qa_scope_id": "scope-2"})
    assert ready["status"] == "READY" and ready["target_entity_id"] == "scope-2"


@pytest.mark.parametrize("exc,expected", [
    (TimeoutError("timeout after send"), "UNKNOWN_RESULT"),
    (RuntimeError("owner unavailable"), "OWNER_UNAVAILABLE"),
])
def test_owner_failure_is_never_fake_success_or_auto_retry(db, context, monkeypatch, exc, expected):
    project, confirmation, actor = context
    owner = FakeOwner(exc)
    monkeypatch.setattr(action_routing, "build_project_truth", lambda *_: {})
    result = action_routing.execute(db, project, action_type="ROUTE_PM_DELIVERY_HANDOFF",
        confirmation_id=confirmation.id, current_evidence_hash="H1", parameters={}, actor=actor, owner_router=owner)
    assert result["status"] == expected and result["result_ref"] is None
    assert result["reconciliation_attempted"] is True
    assert result["retry_policy"] == "RECONCILE_BEFORE_MANUAL_RETRY"
    assert owner.calls == 1


def test_registry_has_only_two_low_risk_owner_routes():
    reg = action_routing.registry()
    assert set(reg["actions"]) == {"ROUTE_PM_DELIVERY_HANDOFF", "ROUTE_QA_VALIDATION_HANDOFF"}
    assert all(spec["risk_class"] == "LOW" for spec in reg["actions"].values())
    assert reg["arbitrary_actions"] is False
