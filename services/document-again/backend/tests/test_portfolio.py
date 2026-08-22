import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app import models as m,portfolio
from app.db import Base
from app.deliverables.models import PortfolioReviewCheckpoint,ProjectReviewCheckpoint

@pytest.fixture()
def db(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'portfolio.db'}",connect_args={"check_same_thread":False})
    @event.listens_for(engine,"connect")
    def _fk(conn,_): conn.execute("pragma foreign_keys=ON")
    Base.metadata.create_all(engine); s=sessionmaker(bind=engine,expire_on_commit=False)(); yield s; s.close(); engine.dispose()

def projects(db,n):
    rows=[m.Project(key=f"P{i}",name=f"Project {i}") for i in range(n)]; db.add_all(rows); db.commit(); return rows

def center(p,state="OK",version=1,blocked=False):
    att={"id":"root","domain":"QA","priority":"BLOCKER" if blocked else "ISSUE","title":"QA attention"}
    ev={"evidence_id":"ATTN-root","domain":"QA","kind":"ATTENTION","summary":"QA attention","source_label":"QA Again","authority":"OWNER_TRUTH_DERIVED","data":{**att,"version":version}}
    return {"project":{"id":p.id,"key":p.key,"name":p.name},"health":{"delivery":"ATTENTION"},
      "attention":{"counts":{"blocker":1 if blocked else 0,"issue":0 if blocked else 1,"unverified":0},"items":[att]},
      "active_impacts":[],"resolution_summary":{"active":[],"recently_resolved":[]},"recent_changes":[],
      "copilot_context":{"context_hash":f"CTX{version}","evidence":[ev]},
      "freshness":{"overall":"FRESH","sources":{"PM":"OK","QA":state,"INFRA":"OK"}},"warnings":[],
      "performance":{"command_center_latency_ms":1,"downstream_calls":2}}

def mark(db,user,out): return portfolio.acknowledge(db,user,out["briefing"]["mark_reviewed"],user)

@pytest.mark.parametrize("count",[1,5,20,50])
def test_scale_and_authorized_project_set_only(db,count):
    rows=projects(db,count+1); authorized=rows[:count]
    out=portfolio.compose(db,user_id="A",projects=authorized,composer=lambda p:center(p))
    assert out["authorized_project_count"]==count and len(out["project_summaries"])==count
    assert rows[-1].name not in str(out) and out["performance"]["concurrency"]==1

def test_blocked_priority_and_partial_project_failure(db):
    a,b,c=projects(db,3)
    def compose(p):
        if p.id==c.id: raise RuntimeError("owner timeout")
        return center(p,blocked=p.id==b.id)
    out=portfolio.compose(db,user_id="A",projects=[a,b,c],composer=compose)
    assert out["project_summaries"][0]["project_id"]==b.id
    assert out["project_summaries"][0]["priority_tier"]=="P1"
    assert out["partial_status"]["unavailable_projects"]==1 and len(out["project_summaries"])==2

def test_portfolio_checkpoint_race_and_project_checkpoint_independence(db):
    p=projects(db,1)[0]; db.add(ProjectReviewCheckpoint(project_id=p.id,user_id="A",reviewed_through=portfolio._now(),reviewed_evidence_cursors=[],briefing_cursor="X"*64)); db.commit()
    loaded=portfolio.compose(db,user_id="A",projects=[p],composer=lambda x:center(x,version=1)); mark(db,"A",loaded)
    later=portfolio.compose(db,user_id="A",projects=[p],composer=lambda x:center(x,version=2))
    assert later["project_summaries"][0]["new_attention_count"]==1
    assert db.query(ProjectReviewCheckpoint).one().briefing_cursor=="X"*64
    assert db.query(PortfolioReviewCheckpoint).count()==1

def test_new_project_first_seen_and_removed_project_disappears(db):
    a,b=projects(db,2); initial=portfolio.compose(db,user_id="A",projects=[a],composer=center); mark(db,"A",initial)
    added=portfolio.compose(db,user_id="A",projects=[a,b],composer=center)
    assert added["project_summaries"][1]["first_seen"] is True
    removed=portfolio.compose(db,user_id="A",projects=[b],composer=center)
    assert removed["briefing"]["removed_project_ids"]==[a.id]
    assert a.name not in str(removed["project_summaries"])+str(removed["evidence"])

def test_project_scoped_citations_and_ai_absent(db,monkeypatch):
    a,b=projects(db,2); out=portfolio.compose(db,user_id="A",projects=[a,b],composer=center)
    monkeypatch.setattr(portfolio.reviewer,"_provider",lambda:None); ai=portfolio.copilot(out)
    assert ai["status"]=="NOT_CONFIGURED" and ai["auto_execution"] is False
    assert all(c.startswith((a.id+":",b.id+":")) for c in ai["evidence_citations"])
