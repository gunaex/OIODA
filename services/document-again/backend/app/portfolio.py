"""R18.1 authorized Portfolio Command Center, briefing, and Copilot."""
from __future__ import annotations
import hashlib,json,time
from datetime import datetime,timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import command_center,briefing,services as svc
from .deliverables import reviewer
from .deliverables.models import PortfolioReviewCheckpoint

CONTRACT="portfolio_command_center/v1"; BRIEF="portfolio_briefing/v1"; CHECKPOINT="portfolio_review_checkpoint/v1"; COPILOT="portfolio_copilot/v1"
SCOPE="MY_AUTHORIZED_PROJECTS"; MAX_PROJECTS=50; CONCURRENCY=1
def _now(): return datetime.now(timezone.utc)
def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,default=str,separators=(",",":")).encode()).hexdigest()
def _cursor(e): return f"{e['evidence_id']}@{_hash(e.get('data'))[:16]}"
def _checkpoint(db,user): return db.execute(select(PortfolioReviewCheckpoint).where(PortfolioReviewCheckpoint.user_id==user,PortfolioReviewCheckpoint.scope_key==SCOPE)).scalar_one_or_none()

def _tier(center,brief):
    intelligence=center.get("resolution_intelligence",{})
    blocked=(center.get("attention",{}).get("counts",{}).get("blocker",0)>0 or bool(intelligence.get("blocked")))
    reopened=len(brief.get("reopened",[])) or any(x.get("reopened") for x in intelligence.get("unresolved_items",[]))
    recheck=bool(intelligence.get("recheck_required"))
    waiting=len(brief.get("waiting_on",[])); new=len(brief.get("new_attention",[])); changed=len(brief.get("changed_since_review",[]))
    if blocked or reopened: return "P1", "Blocked or reopened project evidence requires attention."
    if recheck or new: return "P2", "New attention or deterministic recheck is present."
    if waiting: return "P3", "Project is waiting on supported owner evidence."
    if changed: return "P4", "Recorded project changes are available."
    return "P5", "No higher-tier current project evidence is recorded."

def compose(db:Session,*,user_id:str,authorization=None,projects=None,composer=None):
    started=time.monotonic(); projects=list(projects if projects is not None else svc.list_projects(db,state="ACTIVE"))[:MAX_PROJECTS]
    checkpoint=_checkpoint(db,user_id); previous_ids=set(checkpoint.included_project_ids or []) if checkpoint else set()
    summaries=[]; failures=[]; total_calls=0
    for project in projects:
        try:
            center=(composer(project) if composer else command_center.compose(db,project,authorization=authorization))
            # Portfolio classification is independent of detailed project checkpoint.
            current=briefing.generate(db,project,user_id=user_id,center=center)
            tier,reason=_tier(center,current); evidence=[]
            for e in center["copilot_context"]["evidence"]:
                evidence.append({**e,"evidence_id":f"{project.id}:{e['evidence_id']}","local_evidence_id":e["evidence_id"],"project_id":project.id})
            visible=[_cursor(e) for e in center["copilot_context"]["evidence"]]
            prior=set((checkpoint.project_evidence_cursors or {}).get(project.id,[])) if checkpoint else set()
            new_count=sum(_cursor(e) not in prior for e in center["copilot_context"]["evidence"]) if checkpoint else 0
            source=center.get("freshness",{}).get("sources",{}); unverified=any(v not in {"OK","EMPTY"} for v in source.values())
            intelligence=center.get("resolution_intelligence",{})
            summaries.append({"project_id":project.id,"project_key":project.key,"project_name":project.name,
                "state":"BLOCKED" if tier=="P1" else "ATTENTION" if tier in {"P2","P3"} else "UNVERIFIED" if unverified else "HEALTHY",
                "priority_tier":tier,"priority_reason":reason,"health":center["health"],
                "new_attention_count":new_count,"waiting_count":len(current["waiting_on"]),
                "open_impact_count":len(center.get("active_impacts",[])),
                "blocked_count":max(center.get("attention",{}).get("counts",{}).get("blocker",0),len(intelligence.get("blocked",[]))),
                "resolution_intelligence":{"contract_version":intelligence.get("contract_version"),
                    "unresolved_count":len(intelligence.get("unresolved_items",[])),
                    "waiting_count":len(intelligence.get("waiting",[])),
                    "recheck_count":len(intelligence.get("recheck_required",[])),
                    "focus_items":intelligence.get("focus_items",[])[:3]},
                "resolved_count":len(current["resolved_since_review"]),"reopened_count":len(current["reopened"]),
                "unverified":unverified,"freshness":center.get("freshness"),"focus":current["deterministic_focus"][:3],
                "changed":current["changed_since_review"],"waiting":current["waiting_on"],
                "resolved":current["resolved_since_review"],"reopened":current["reopened"],
                "first_seen":bool(checkpoint and project.id not in previous_ids),"evidence":evidence,
                "cutoff":current["briefing_window"]["to"],"visible_cursors":visible})
            total_calls+=center.get("performance",{}).get("downstream_calls",0)
        except Exception as exc:
            failures.append({"project_id":project.id,"project_name":project.name,"status":"UNAVAILABLE","reason":str(exc)[:300]})
    summaries.sort(key=lambda x:(x["priority_tier"],-x["reopened_count"],-x["blocked_count"],x["project_name"]))
    scoped_evidence=[e for s in summaries for e in s["evidence"]]
    current_ids={s["project_id"] for s in summaries}; removed=sorted(previous_ids-current_ids); first=[s for s in summaries if s["first_seen"]]
    briefing_payload={"contract_version":BRIEF,"mode":"SINCE_LAST_PORTFOLIO_REVIEW" if checkpoint else "FIRST_VIEW_CURRENT_PORTFOLIO",
        "project_scope":[s["project_id"] for s in summaries],"focus_projects":summaries[:7],
        "new_project_attention":[s for s in summaries if s["new_attention_count"]],
        "cross_project_changes":[{"project_id":s["project_id"],**x} for s in summaries for x in s["changed"]][:20],
        "still_waiting":[{"project_id":s["project_id"],**x} for s in summaries for x in s["waiting"]][:20],
        "resolved_since_review":[{"project_id":s["project_id"],**x} for s in summaries for x in s["resolved"]][:20],
        "reopened":[{"project_id":s["project_id"],**x} for s in summaries for x in s["reopened"]][:20],
        "new_projects":[{"project_id":s["project_id"],"project_name":s["project_name"],"classification":"FIRST_SEEN"} for s in first],
        "removed_project_ids":removed,"limitations":[f"{x['project_name']} could not be evaluated." for x in failures]}
    cutoff_map={s["project_id"]:s["cutoff"] for s in summaries}; cursor_map={s["project_id"]:s["visible_cursors"] for s in summaries}
    token=_hash({"user":user_id,"cutoffs":cutoff_map,"cursors":cursor_map,"projects":sorted(current_ids)})
    briefing_payload["mark_reviewed"]={"portfolio_cursor":token,"project_cutoffs":cutoff_map,"project_evidence_cursors":cursor_map,"included_project_ids":sorted(current_ids)}
    return {"contract_version":CONTRACT,"user_context":{"user_id":user_id,"scope":SCOPE},"generated_at":_now().isoformat(),
        "authorized_project_count":len(projects),"project_summaries":summaries,
        "portfolio_attention":{"blocked_projects":sum(s["state"]=="BLOCKED" for s in summaries),"attention_projects":sum(s["state"]=="ATTENTION" for s in summaries),"unverified_projects":sum(s["unverified"] for s in summaries),"waiting_projects":sum(bool(s["waiting_count"]) for s in summaries)},
        "focus_projects":summaries[:7],"unverified_projects":[s for s in summaries if s["unverified"]],
        "briefing":briefing_payload,"evidence":scoped_evidence,"partial_status":{"complete_projects":len(summaries),"unavailable_projects":len(failures),"failures":failures},
        "provenance":{"source_contracts":["project_command_center/v1","project_briefing/v1","resolution_intelligence/v1"],"authorized_scope_first":True,"project_checkpoint_independent":True},
        "performance":{"portfolio_latency_ms":round((time.monotonic()-started)*1000,2),"downstream_calls":total_calls,"concurrency":CONCURRENCY,"project_limit":MAX_PROJECTS}}

def acknowledge(db,user_id,payload,actor_id):
    started=time.monotonic(); row=_checkpoint(db,user_id)
    if row and row.portfolio_cursor==payload["portfolio_cursor"]: return {"checkpoint_id":row.id,"idempotent_replay":True}
    if not row:
        row=PortfolioReviewCheckpoint(user_id=user_id,scope_key=SCOPE,project_cutoffs=payload["project_cutoffs"],project_evidence_cursors=payload["project_evidence_cursors"],included_project_ids=payload["included_project_ids"],portfolio_cursor=payload["portfolio_cursor"]); db.add(row); db.flush()
    else:
        row.project_cutoffs=payload["project_cutoffs"]; row.project_evidence_cursors=payload["project_evidence_cursors"]; row.included_project_ids=payload["included_project_ids"]; row.portfolio_cursor=payload["portfolio_cursor"]; row.acknowledged_at=_now()
    svc.record_audit(db,action="PORTFOLIO_BRIEFING_REVIEWED",project_id=None,actor_id=actor_id,object_type="PortfolioReviewCheckpoint",object_id=row.id,revision_context=row.portfolio_cursor,metadata={"project_count":len(row.included_project_ids),"project_checkpoints_changed":False,"customer_acceptance":False}); db.commit()
    return {"contract_version":CHECKPOINT,"checkpoint_id":row.id,"portfolio_cursor":row.portfolio_cursor,"idempotent_replay":False,"latency_ms":round((time.monotonic()-started)*1000,2)}

def copilot(packet,query_type="FOCUS_PORTFOLIO_TODAY"):
    focus=packet["focus_projects"][:7]; citations=[e["evidence_id"] for s in focus for e in s["evidence"][:2]]
    base={"contract_version":COPILOT,"query_type":query_type,"answer":f"{len(focus)} authorized project(s) are prioritized by deterministic evidence.","focus_projects":[{"project_id":s["project_id"],"project_name":s["project_name"],"priority_tier":s["priority_tier"],"reason":s["priority_reason"],"evidence_ids":[e["evidence_id"] for e in s["evidence"][:2]]} for s in focus],"evidence_citations":citations,"auto_execution":False,"ai_authority":"NONE"}
    if not reviewer._provider(): return {**base,"status":"NOT_CONFIGURED","operational_status":"AI_NOT_CONFIGURED"}
    return {**base,"status":"DETERMINISTIC_ONLY","operational_status":"AI_DEGRADED","limitations":["Portfolio AI narrative withheld until project-scoped comparison validator is configured."]}
