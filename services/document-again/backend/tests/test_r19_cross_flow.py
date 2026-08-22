"""R19 deterministic dogfood: prove the product loops without production noise."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import briefing, command_center, models as m, portfolio
from app.db import Base
from app.deliverables import action_routing, impact, reviewer
from app.deliverables.models import DeliverableSignoff, HumanDeliverableInstance
from app.tenant import set_current_tenant


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'r19.db'}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(conn, _): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    set_current_tenant(None); session.close(); engine.dispose()


def _truth(complete=False):
    return {"contract_version":"project_truth/v1", "overall_freshness":"FRESH",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "sources":{"pm":{"source_status":"OK"},"qa":{"source_status":"OK"},
                   "infra":{"source_status":"UNBOUND"}},
        "pm":{"attention":{}}, "qa":{"readiness_status":"READY" if complete else "IN_PROGRESS",
            "evidence_status":"COMPLETE" if complete else "MISSING",
            "remaining_test_count":0 if complete else 1,"failed_test_count":0,
            "blocked_test_count":0,"blocking_defect_count":0}, "infra":None,
        "attention":{"contract_version":"project_attention/v1","counts":{"blocker":0,"issue":0,"unverified":1},
            "items":[{"id":"infra","domain":"INFRA","priority":"UNVERIFIED","code":"SOURCE_UNBOUND","title":"Infra is unbound"}]},
        "warnings":[],"downstream_call_count":0}


class Owner:
    def __init__(self): self.calls=0
    def execute(self, *_args):
        self.calls += 1
        return ({"service":"QA_AGAIN","entity_id":"qa-result","status":"ACKNOWLEDGED",
                 "created_at":datetime.now(timezone.utc).isoformat()},1.0,1.0)


def test_change_to_waiting_resolution_to_briefing_closed_loop(db, monkeypatch):
    project=m.Project(key="R19",name="R19 Loop",project_meta={"workspace_bindings":{"v1":{
        "pm":{"service":"PM_AGAIN","external_project_id":"pm-r19","binding_status":"BOUND"},
        "qa":[{"service":"QA_AGAIN","external_project_id":"qa-r19","scope_id":"qa-scope","binding_status":"BOUND"}],
        "infra":{"service":"INFRA_AGAIN","binding_status":"UNBOUND"}}}})
    db.add(project); db.flush()
    change=impact.change_event(change_id="CHANGE-R19",project_id=project.id,entity_type="DOCUMENT_VERSION",
        entity_id="doc-v2",change_type="UPDATED",source_service="DOCUMENT_AGAIN",
        timestamp=datetime.now(timezone.utc).isoformat(),provenance={"snapshot_hash":"H1"},
        before="v1",after="v2",actor="human")
    rel=impact.relationship(project_id=project.id,source_type="DOCUMENT_VERSION",source_id="doc-v2",
        target_type="QA_CONTEXT",target_id="UNRESOLVED:QA",relationship_type="AFFECTS",
        relationship_class="UNKNOWN",source_authority="NO_RELIABLE_RELATIONSHIP_RECORDED",
        provenance={"change_id":change["change_id"]},status="UNRESOLVED")
    actor=SimpleNamespace(id="human",name="Human")
    confirmed=impact.review_relationship(db,project,relationship_snapshot=rel,evidence_hash="H1",
        current_evidence_hash="H1",impact_candidate_id="IMP-R19",decision="CONFIRMED",
        reason="QA scope needs validation",actor=actor,change_id=change["change_id"])
    preview=action_routing.preview(db,project,action_type="ROUTE_QA_VALIDATION_HANDOFF",
        confirmation_id=confirmed["confirmation_id"],current_evidence_hash="H1",
        parameters={"qa_scope_id":"qa-scope"})
    assert preview["status"]=="READY" and preview["human_trigger_required"] is True
    owner=Owner(); monkeypatch.setattr(action_routing,"build_project_truth",lambda *_:_truth(False))
    result=action_routing.execute(db,project,action_type="ROUTE_QA_VALIDATION_HANDOFF",
        confirmation_id=confirmed["confirmation_id"],current_evidence_hash="H1",
        parameters={"qa_scope_id":"qa-scope"},actor=actor,owner_router=owner)
    assert result["status"]=="SUCCEEDED" and owner.calls==1
    assert result["impact_resolution"]["resolution_state"]=="WAITING_ON_OWNER"
    center=command_center.compose(db,project,truth=_truth(False))
    daily=briefing.generate(db,project,user_id="human",center=center)
    assert center["resolution_intelligence"]["waiting"]
    assert daily["waiting_on"] and not daily["resolved_since_review"]
    assert center["acceptance"]["customer_accepted"] is False


def test_source_revision_marks_document_stale_and_keeps_old_version_immutable(db):
    project=m.Project(key="DOC",name="Document Loop"); db.add(project); db.flush()
    req=m.Requirement(project_id=project.id,code="R1",title="Encrypt traffic",status=m.RequirementStatus.CONFIRMED)
    db.add(req); db.flush(); now=datetime.now(timezone.utc)
    db.add_all([m.RequirementRevision(requirement_id=req.id,revision_number=1,title=req.title,status=m.RequirementStatus.CONFIRMED,confirmed_at=now),
                m.RequirementRevision(requirement_id=req.id,revision_number=2,title="Encrypt all traffic",status=m.RequirementStatus.CONFIRMED,confirmed_at=now)])
    old=HumanDeliverableInstance(id="old",project_id=project.id,human_code="HD-01",name="Scope",document_id="DOC-HD",version="1.0",
        lifecycle_status="BASELINED",source_snapshot={"requirements":[{"id":req.id,"revision":1}]},snapshot_hash="immutable-v1",created_at=now)
    current=HumanDeliverableInstance(id="new",project_id=project.id,human_code="HD-01",name="Scope",document_id="DOC-HD",version="1.1",
        lifecycle_status="DRAFT",source_snapshot={"requirements":[{"id":req.id,"revision":1}]},snapshot_hash="v11",supersedes_id=old.id,created_at=now+timedelta(seconds=1))
    db.add_all([old,current]); db.commit()
    packet=reviewer.build_packet(db,project,"HD-01",purpose="REVIEW")
    assert any(x["impact_type"]=="POTENTIALLY_STALE" for x in packet["change_impact"]["known_impacts"])
    assert packet["comparison"]["from_hash"]=="immutable-v1"
    assert db.get(HumanDeliverableInstance,"old").snapshot_hash=="immutable-v1"


def test_tenant_isolation_and_test_evidence_never_become_customer_acceptance(db):
    mine=m.Project(key="MINE",name="Mine",tenant_id="tenant-a"); other=m.Project(key="OTHER",name="Other",tenant_id="tenant-b")
    db.add_all([mine,other]); db.flush()
    doc=HumanDeliverableInstance(project_id=mine.id,human_code="HD-01",name="Scope",document_id="M-HD",version="1",
        lifecycle_status="BASELINED",source_snapshot={},snapshot_hash="h")
    db.add(doc); db.flush(); db.add(DeliverableSignoff(project_id=mine.id,human_code="HD-01",instance_id=doc.id,
        document_id=doc.document_id,document_version="1",snapshot_hash="h",signoff_type="ACCEPT",decision="ACCEPT",
        evidence_class="TEST",purpose="ACCEPTANCE",signer_user_id="tester",signer_name="Tester")); db.commit()
    set_current_tenant("tenant-a")
    packet=portfolio.compose(db,user_id="actor-a",projects=[mine],composer=lambda p: command_center.compose(db,p,truth=_truth(True)))
    assert packet["authorized_project_count"]==1 and "Other" not in str(packet)
    center=command_center.compose(db,mine,truth=_truth(True))
    assert center["acceptance"]["customer_accepted"] is False
    from app import services
    with pytest.raises(Exception, match="Cross-tenant"):
        services.guard_project(db,other.id)
