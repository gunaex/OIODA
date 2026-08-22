from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import briefing
from app import models as m
from app.db import Base
from app.deliverables.models import ProjectReviewCheckpoint


@pytest.fixture()
def context(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'brief.db'}",connect_args={"check_same_thread":False})
    @event.listens_for(engine,"connect")
    def _fk(conn,_): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine); db=sessionmaker(bind=engine,expire_on_commit=False)()
    project=m.Project(key="BRIEF",name="Briefing"); db.add(project); db.commit()
    yield db,project; db.close(); engine.dispose()


def center(project, evidence, *, resolutions=None, changes=None, warnings=None):
    return {"project":{"id":project.id,"key":project.key,"name":project.name},
        "health":{"delivery":"ATTENTION"}, "recent_changes":changes or [],
        "resolution_summary":{"active":resolutions or [],"recently_resolved":[]},
        "copilot_context":{"context_hash":"CTX","evidence":evidence},
        "freshness":{"overall":"FRESH","sources":{"PM":"OK","QA":"OK","INFRA":"UNBOUND"}},
        "warnings":warnings or [], "performance":{"command_center_latency_ms":2}}


def attention(summary="QA not started"):
    return {"evidence_id":"ATTN-qa","domain":"QA","kind":"ATTENTION","summary":summary,
            "source_label":"QA Again","authority":"OWNER_TRUTH_DERIVED",
            "data":{"priority":"BLOCKER","code":"QA_ROOT"}}


def mark(db,project,user,brief):
    m=brief["mark_reviewed"]
    return briefing.acknowledge(db,project,user_id=user,cutoff=m["cutoff"],
        briefing_cursor=m["briefing_cursor"],evidence_cursors=m["evidence_cursors"],actor_id=user)


def test_first_review_creates_user_project_checkpoint_and_is_idempotent(context):
    db,project=context; now=datetime.now(timezone.utc)-timedelta(seconds=1)
    first=briefing.generate(db,project,user_id="A",center=center(project,[attention()]),cutoff=now)
    assert first["briefing_mode"]=="FIRST_VIEW_CURRENT_BRIEF" and first["checkpoint"] is None
    saved=mark(db,project,"A",first); replay=mark(db,project,"A",first)
    assert saved["idempotent_replay"] is False and replay["idempotent_replay"] is True
    assert db.query(ProjectReviewCheckpoint).count()==1


def test_race_safe_late_evidence_remains_new(context):
    db,project=context; t1=datetime.now(timezone.utc)-timedelta(minutes=2)
    loaded=briefing.generate(db,project,user_id="A",center=center(project,[attention()]),cutoff=t1)
    late={**attention("QA became blocked"),"evidence_id":"ATTN-late","data":{"priority":"BLOCKER"}}
    mark(db,project,"A",loaded)
    next_brief=briefing.generate(db,project,user_id="A",center=center(project,[attention(),late]),cutoff=t1+timedelta(minutes=1))
    assert [x["evidence_ids"] for x in next_brief["new_attention"]]==[["ATTN-late"]]
    assert [x["evidence_ids"] for x in next_brief["still_open"]]==[["ATTN-qa"]]


def test_user_and_project_isolation(context):
    db,project=context; other=m.Project(key="OTHER",name="Other"); db.add(other); db.commit()
    brief=briefing.generate(db,project,user_id="A",center=center(project,[attention()]),cutoff=datetime.now(timezone.utc)-timedelta(seconds=1))
    mark(db,project,"A",brief)
    assert briefing.generate(db,project,user_id="B",center=center(project,[attention()]))["checkpoint"] is None
    assert briefing.generate(db,other,user_id="A",center=center(other,[attention()]))["checkpoint"] is None


def test_no_change_still_open_and_partial_service_are_honest(context):
    db,project=context; t=datetime.now(timezone.utc)-timedelta(minutes=2)
    first=briefing.generate(db,project,user_id="A",center=center(project,[attention()]),cutoff=t); mark(db,project,"A",first)
    out=briefing.generate(db,project,user_id="A",center=center(project,[attention()],warnings=["QA unavailable"]),cutoff=t+timedelta(minutes=1))
    assert out["changed_since_review"]==[] and len(out["still_open"])==1
    assert any("QA unavailable" in x for x in out["limitations"])
    assert any("INFRA source is UNBOUND" in x for x in out["limitations"])


def test_resolution_event_classifies_resolved_and_reopened(context):
    db,project=context; t=datetime.now(timezone.utc)-timedelta(minutes=3)
    initial=briefing.generate(db,project,user_id="A",center=center(project,[attention()]),cutoff=t); mark(db,project,"A",initial)
    res_e={"evidence_id":"RES-r1","domain":"RESOLUTION","kind":"IMPACT_RESOLUTION",
        "summary":"Resolution reopened","source_label":"OIDA resolution engine","authority":"DETERMINISTIC_RULE",
        "data":{"resolution_id":"r1","impact_candidate_id":"i1","resolution_state":"WAITING_ON_OWNER"}}
    histories=[{"resolution_id":"r1","impact_candidate_id":"i1","resolution_state":"WAITING_ON_OWNER",
        "history":[{"event_type":"IMPACT_RESOLVED","state":"RESOLVED","timestamp":(t+timedelta(seconds=10)).isoformat()},
                   {"event_type":"IMPACT_RESOLUTION_REOPENED","state":"WAITING_ON_OWNER","timestamp":(t+timedelta(seconds=20)).isoformat()}]}]
    out=briefing.generate(db,project,user_id="A",center=center(project,[res_e],resolutions=histories),cutoff=t+timedelta(minutes=1))
    assert len(out["resolved_since_review"])==1 and len(out["reopened"])==1
    assert out["reopened"][0]["priority"]=="P1"


def test_ai_not_configured_keeps_deterministic_brief(context,monkeypatch):
    db,project=context
    packet=briefing.generate(db,project,user_id="A",center=center(project,[attention()]))
    monkeypatch.setattr(briefing.reviewer,"_provider",lambda:None)
    out=briefing.ai_explain(packet)
    assert out["status"]=="NOT_CONFIGURED" and out["focus_today"]
    assert out["auto_execution"] is False and out["ai_authority"]=="NONE"


def test_ai_cannot_call_old_issue_new_or_waiting_resolution_resolved(context):
    db,project=context; t=datetime.now(timezone.utc)-timedelta(minutes=2)
    first=briefing.generate(db,project,user_id="A",center=center(project,[attention()]),cutoff=t); mark(db,project,"A",first)
    res={"evidence_id":"RES-wait","domain":"RESOLUTION","kind":"IMPACT_RESOLUTION","summary":"QA is waiting",
         "source_label":"OIDA resolution engine","authority":"DETERMINISTIC_RULE",
         "data":{"resolution_state":"WAITING_ON_OWNER"}}
    packet=briefing.generate(db,project,user_id="A",center=center(project,[attention(),res],resolutions=[]),cutoff=t+timedelta(minutes=1))
    raw={"focus_today":[{"item":"Old blocker","why":"A new QA blocker appeared","evidence_ids":["ATTN-qa"]},
                        {"item":"QA","why":"Review QA","evidence_ids":["RES-wait"],"action_type":"DEPLOY_INFRA"},
                        {"item":"QA","why":"QA impact resolved","evidence_ids":["RES-wait"]}]}
    out=briefing.validate_ai_brief(raw,packet)
    assert not out["focus_today"]
    assert {x["reason"] for x in out["rejected_claims"]}=={"TIME_WINDOW_UNSUPPORTED","UNKNOWN_ACTION","RESOLUTION_UNSUPPORTED"}
