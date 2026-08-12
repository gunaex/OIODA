"""
Conductor Again — Deliberation Router
Multi-agent deliberation with anti-convergence governance.
Independent first-pass → blind critique → revision → judge → decision.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_master_db
from app.integration.lacc_client import LocalAIControlCenterClient
from app.models import (
    AIResource,
    DeliberationCase,
    DissentRecord,
    DiversitySnapshot,
    IndependentSubmission,
    InstalledModel,
    OpinionRevision,
    PanelMember,
    PeerCritique,
    Skill,
    User,
)

router = APIRouter(prefix="/api/deliberation", tags=["deliberation"])

# Local Ollama model families for panel diversity — same rationale as multi_ai.py:
# genuinely different model lineages, not just quantization variants, so "independent
# reasoning from a different model" is still a real property even though every
# execution routes through the same local Ollama executor (LACC's only wired executor
# today, disclosed in docs/architecture/CONDUCTOR_AI_EXECUTION_BOUNDARY.md).
_DELIBERATION_DIVERSITY_MODELS = ["qwen2.5:7b", "llama3.1:8b", "gemma3:4b", "qwen2.5-coder:7b"]

_INDEPENDENT_REASONING_PROMPT = """You are panel member "{label}" in a governed multi-agent deliberation, assigned the role: {role}.

You must reason INDEPENDENTLY — you have not seen and must not assume any other panel member's answer.

TASK:
{task}

DECISION CRITERIA:
{criteria}

Respond with ONLY a valid JSON object (no markdown, no explanation outside the JSON) with these exact keys:
{{
  "conclusion": "your conclusion in 1-3 sentences",
  "recommended_action": "what you recommend doing",
  "key_claims": ["claim 1", "claim 2"],
  "assumptions": ["assumption 1"],
  "uncertainties": ["uncertainty 1"],
  "confidence": 0.0
}}"""

ROLES = [
    "PROPOSER", "ALTERNATIVE_PROPOSER", "DOMAIN_ANALYST",
    "ASSUMPTION_CHALLENGER", "EVIDENCE_CHECKER", "RISK_ANALYST",
    "RED_TEAM", "INDEPENDENT_JUDGE",
]

LABELS = ["A", "B", "C", "D", "E", "F", "G", "H"]

# ═══════════════════════════════════════════════════════════
# Create Deliberation + Build Diverse Panel
# ═══════════════════════════════════════════════════════════

@router.post("/start")
def start_deliberation(
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """Create a deliberation case and auto-build a diverse panel from the AI Resource Pool."""
    title = body.get("title", "Untitled Deliberation")
    trigger = body.get("trigger", "HUMAN_REQUESTED_REVIEW")
    project_slug = body.get("project_slug", "")
    task_description = body.get("task", "")
    decision_criteria = body.get("criteria", "")
    skill_id_str = body.get("skill_id", "")
    min_members = body.get("min_members", 3)

    # Resolve skill if provided
    skill_db_id = None
    if skill_id_str:
        skill = db.query(Skill).filter(Skill.skill_id == skill_id_str).first()
        if skill:
            skill_db_id = skill.id

    # Create case
    case = DeliberationCase(
        project_slug=project_slug,
        title=title,
        trigger=trigger,
        skill_id=skill_db_id,
        source_packet_json={
            "task": task_description,
            "criteria": decision_criteria,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        },
        decision_criteria=decision_criteria,
        status="panel_selected",
        created_by=user.email,
    )
    db.add(case)
    db.flush()

    # Build diverse panel
    resources = db.query(AIResource).filter(
        AIResource.enabled == True,
        AIResource.health_state.in_(["AVAILABLE", "DEGRADED"]),
    ).all()

    if len(resources) < min_members:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {min_members} available resources, found {len(resources)}",
        )

    # Diversity-aware selection
    panel = _build_diverse_panel(resources, min_members, db)

    for i, (resource, role) in enumerate(panel):
        model = db.query(InstalledModel).filter(InstalledModel.id == resource.model_id).first()
        provider_code = resource.account.provider.code if resource.account and resource.account.provider else "unknown"
        member = PanelMember(
            case_id=case.id,
            resource_id=resource.id,
            assigned_role=role,
            provider_code=provider_code,
            model_id=model.model_id if model else "",
            display_label=f"Candidate {LABELS[i]}",
        )
        db.add(member)

    case.status = "panel_selected"
    db.commit()
    db.refresh(case)

    return {
        "case_id": case.id,
        "title": case.title,
        "status": case.status,
        "panel_size": len(panel),
        "members": [
            {
                "id": m.id,
                "label": m.display_label,
                "role": m.assigned_role,
                "provider": m.provider_code,
                "model": m.model_id,
            }
            for m in case.members
        ],
    }


def _build_diverse_panel(resources, min_count: int, db: Session) -> list:
    """Maximize provider/model diversity, assign roles."""
    import random
    random.seed(42)

    # Group by provider
    by_provider = {}
    for r in resources:
        pcode = r.account.provider.code if r.account and r.account.provider else "unknown"
        by_provider.setdefault(pcode, []).append(r)

    # Pick one from each provider first, then fill remaining
    selected = []
    used_providers = set()
    providers = list(by_provider.keys())
    random.shuffle(providers)

    for pcode in providers:
        if len(selected) >= min_count:
            break
        pool = [r for r in by_provider[pcode] if r.id not in {s.id for s, _ in selected}]
        if pool:
            selected.append((random.choice(pool), None))
            used_providers.add(pcode)

    # Fill remaining slots from unused providers first
    remaining = [r for r in resources if r.account.provider.code not in used_providers and r.id not in {s.id for s, _ in selected}]
    random.shuffle(remaining)
    for r in remaining:
        if len(selected) >= min_count:
            break
        selected.append((r, None))

    # If still not enough, use any remaining
    if len(selected) < min_count:
        extra = [r for r in resources if r.id not in {s.id for s, _ in selected}]
        random.shuffle(extra)
        for r in extra:
            if len(selected) >= min_count:
                break
            selected.append((r, None))

    # Assign roles
    roles_pool = list(ROLES)
    random.shuffle(roles_pool)
    return [(r, roles_pool[i % len(roles_pool)]) for i, (r, _) in enumerate(selected[:min_count])]


# ═══════════════════════════════════════════════════════════
# Independent Round — Submit
# ═══════════════════════════════════════════════════════════

@router.post("/{case_id}/submit")
def submit_independent(
    case_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """Panel member submits independent answer WITHOUT seeing peers."""
    case = db.query(DeliberationCase).filter(DeliberationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status not in ("panel_selected", "independent_round"):
        raise HTTPException(status_code=400, detail=f"Case is in '{case.status}', not ready for submissions")

    member_id = body.get("member_id")
    member = db.query(PanelMember).filter(PanelMember.id == member_id, PanelMember.case_id == case_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    sub = IndependentSubmission(
        case_id=case_id,
        member_id=member.id,
        conclusion=body.get("conclusion", ""),
        recommended_action=body.get("recommended_action", ""),
        key_claims=body.get("key_claims", []),
        evidence_references=body.get("evidence_references", []),
        assumptions=body.get("assumptions", []),
        uncertainties=body.get("uncertainties", []),
        limitations=body.get("limitations", []),
        counterarguments=body.get("counterarguments", []),
        failure_conditions=body.get("failure_conditions", []),
        confidence=body.get("confidence"),
        evidence_quality=body.get("evidence_quality"),
        what_would_change_conclusion=body.get("what_would_change_conclusion", ""),
    )
    db.add(sub)
    member.has_submitted = True

    # Check if all members submitted
    all_members = db.query(PanelMember).filter(PanelMember.case_id == case_id).all()
    all_submitted = all(m.has_submitted for m in all_members)

    if all_submitted:
        case.status = "independent_complete"
        # Take initial diversity snapshot
        _take_diversity_snapshot(db, case, "initial")

    db.commit()
    db.refresh(sub)
    return {"submission_id": sub.id, "all_submitted": all_submitted, "case_status": case.status}


@router.post("/{case_id}/members/{member_id}/generate")
async def generate_independent_submission(
    case_id: str,
    member_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """E8.1-D: generates a panel member's independent first-pass submission via the
    AIExecutionGateway (LocalAIControlCenterClient.execute_capability), rather than
    requiring an external caller to POST /submit with pre-written content. This
    completes deliberation's real AI execution wiring — panel selection/role/turn
    logic below is unchanged; only the provider-execution boundary is new. Independent
    reasoning is preserved structurally: the prompt is built solely from
    case.source_packet_json (the frozen input) and never includes any peer's
    submission — this endpoint is only valid while the case is still in
    'panel_selected'/'independent_round'."""
    case = db.query(DeliberationCase).filter(DeliberationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status not in ("panel_selected", "independent_round"):
        raise HTTPException(status_code=400, detail=f"Case is in '{case.status}', not ready for submissions")

    member = db.query(PanelMember).filter(PanelMember.id == member_id, PanelMember.case_id == case_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.has_submitted:
        raise HTTPException(status_code=409, detail="Member has already submitted")

    packet = case.source_packet_json or {}
    label_index = ord((member.display_label.replace("Candidate ", "")[:1] or "A")) - ord("A")
    model = _DELIBERATION_DIVERSITY_MODELS[label_index % len(_DELIBERATION_DIVERSITY_MODELS)]
    prompt = _INDEPENDENT_REASONING_PROMPT.format(
        label=member.display_label, role=member.assigned_role,
        task=packet.get("task", ""), criteria=packet.get("criteria", case.decision_criteria or ""),
    )
    correlation_id = f"corr-delib-{case_id}"
    request_id = f"req-delib-{uuid.uuid4().hex[:8]}"

    result = await asyncio.to_thread(
        LocalAIControlCenterClient.execute_capability,
        capability="GENERAL_REASONING", correlation_id=correlation_id,
        prompt=prompt, model_preference=model, request_id=request_id,
    )
    if result.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=502,
            detail=f"AI execution failed for panel member {member.display_label}: {result.get('outputSummary')}",
        )

    raw_text = result.get("outputSummary") or ""
    parsed = {}
    try:
        start, end = raw_text.find("{"), raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw_text[start:end])
    except Exception:
        parsed = {}

    evidence_refs = [result.get("evidenceRef")] if result.get("evidenceRef") else []
    sub = IndependentSubmission(
        case_id=case_id,
        member_id=member.id,
        conclusion=parsed.get("conclusion", raw_text[:2000]),
        recommended_action=parsed.get("recommended_action", ""),
        key_claims=parsed.get("key_claims", []),
        evidence_references=evidence_refs,
        assumptions=parsed.get("assumptions", []),
        uncertainties=parsed.get("uncertainties", []),
        confidence=parsed.get("confidence"),
        raw_response=raw_text,
    )
    db.add(sub)
    member.has_submitted = True
    member.model_id = result.get("modelUsed", model)
    member.provider_code = result.get("providerUsed", "ollama")

    all_members = db.query(PanelMember).filter(PanelMember.case_id == case_id).all()
    all_submitted = all(m.has_submitted for m in all_members)
    if all_submitted:
        case.status = "independent_complete"
        _take_diversity_snapshot(db, case, "initial")

    db.commit()
    db.refresh(sub)
    return {
        "submission_id": sub.id, "all_submitted": all_submitted, "case_status": case.status,
        "provider": member.provider_code, "model": member.model_id,
        "requestId": request_id, "correlationId": correlation_id, "evidenceRef": result.get("evidenceRef"),
    }


# ═══════════════════════════════════════════════════════════
# Blind Critique Round
# ═══════════════════════════════════════════════════════════

@router.post("/{case_id}/critique")
def submit_critique(
    case_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """Submit anonymized peer critique — reviewer sees label only (Candidate A/B/C)."""
    case = db.query(DeliberationCase).filter(DeliberationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status not in ("independent_complete", "blind_review"):
        case.status = "blind_review"

    critique = PeerCritique(
        case_id=case_id,
        reviewer_member_id=body.get("reviewer_member_id"),
        target_submission_id=body.get("target_submission_id"),
        target_label=body.get("target_label", ""),
        strengths=body.get("strengths", []),
        weaknesses=body.get("weaknesses", []),
        evidence_gaps=body.get("evidence_gaps", []),
        logical_issues=body.get("logical_issues", []),
        overall_assessment=body.get("overall_assessment", ""),
    )
    db.add(critique)
    db.commit()
    db.refresh(critique)
    return {"critique_id": critique.id, "status": "recorded"}


# ═══════════════════════════════════════════════════════════
# Revision Round
# ═══════════════════════════════════════════════════════════

@router.post("/{case_id}/revise")
def submit_revision(
    case_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """Submit revised opinion after seeing anonymized critiques. Must cite reasons."""
    original_sub = db.query(IndependentSubmission).filter(
        IndependentSubmission.id == body.get("original_submission_id")
    ).first()
    if not original_sub:
        raise HTTPException(status_code=404, detail="Original submission not found")

    reason = body.get("reason_for_change", "")
    changed = body.get("changed", False)
    # Flag unsupported conformity
    conformity_flag = False
    if changed and (not reason or reason.strip().lower() in ("i agree with the others.", "the majority is probably right.")):
        conformity_flag = True

    revision = OpinionRevision(
        original_submission_id=original_sub.id,
        member_id=body.get("member_id"),
        previous_conclusion=original_sub.conclusion,
        new_conclusion=body.get("new_conclusion", original_sub.conclusion),
        changed=changed,
        new_evidence_received=body.get("new_evidence_received", []),
        critique_accepted=body.get("critique_accepted", []),
        critique_rejected=body.get("critique_rejected", []),
        assumption_changed=body.get("assumption_changed", ""),
        confidence_before=original_sub.confidence,
        confidence_after=body.get("confidence_after"),
        reason_for_change=reason,
        potential_conformity_flag=conformity_flag,
    )
    db.add(revision)

    # Take post-revision diversity snapshot
    case = db.query(DeliberationCase).filter(DeliberationCase.id == case_id).first()
    if case:
        case.status = "private_revision"
        _take_diversity_snapshot(db, case, "after_revision")

    if conformity_flag:
        _add_conformity_alert(db, case, body.get("member_id"),
            f"Opinion changed without valid evidence or reasoning.")

    db.commit()
    db.refresh(revision)
    return {"revision_id": revision.id, "conformity_flagged": conformity_flag}


# ═══════════════════════════════════════════════════════════
# Dissent Record
# ═══════════════════════════════════════════════════════════

@router.post("/{case_id}/dissent")
def record_dissent(
    case_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """Preserve a minority report — never deleted on majority decision."""
    dissent = DissentRecord(
        case_id=case_id,
        member_id=body.get("member_id"),
        position=body.get("position", ""),
        supporting_evidence=body.get("supporting_evidence", []),
        rejected_majority_assumptions=body.get("rejected_majority_assumptions", []),
        risk_if_minority_correct=body.get("risk_if_minority_correct", ""),
        suggested_verification=body.get("suggested_verification", ""),
    )
    db.add(dissent)
    db.commit()
    db.refresh(dissent)
    return {"dissent_id": dissent.id}


# ═══════════════════════════════════════════════════════════
# Judge Decision
# ═══════════════════════════════════════════════════════════

@router.post("/{case_id}/decide")
def render_decision(
    case_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """Final decision: supported agreement, majority with dissent, or unresolved."""
    case = db.query(DeliberationCase).filter(DeliberationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.outcome = body.get("outcome", "SUPPORTED_AGREEMENT")
    case.final_decision = body.get("final_decision", "")
    case.decided_by = user.email
    case.decided_at = datetime.now(timezone.utc)
    case.human_approved = body.get("human_approved", False)
    case.human_approved_by = body.get("human_approved_by", "")
    case.status = "decided"

    _take_diversity_snapshot(db, case, "final")
    db.commit()

    return {"case_id": case.id, "outcome": case.outcome, "status": case.status}


# ═══════════════════════════════════════════════════════════
# Query Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("")
def list_cases(
    project_slug: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    q = db.query(DeliberationCase).order_by(DeliberationCase.created_at.desc())
    if project_slug:
        q = q.filter(DeliberationCase.project_slug == project_slug)
    if status:
        q = q.filter(DeliberationCase.status == status)
    return [_case_summary(c) for c in q.limit(30).all()]


@router.get("/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    case = db.query(DeliberationCase).filter(DeliberationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return _case_detail(case, db)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _case_summary(case: DeliberationCase) -> dict:
    return {
        "id": case.id,
        "title": case.title,
        "project_slug": case.project_slug,
        "trigger": case.trigger,
        "status": case.status,
        "outcome": case.outcome,
        "member_count": len(case.members),
        "submission_count": len(case.submissions),
        "dissent_count": len(case.dissents),
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


def _case_detail(case: DeliberationCase, db: Session) -> dict:
    d = _case_summary(case)
    d.update({
        "source_packet": case.source_packet_json,
        "decision_criteria": case.decision_criteria,
        "final_decision": case.final_decision,
        "decided_by": case.decided_by,
        "human_approved": case.human_approved,
        "members": [
            {
                "id": m.id, "label": m.display_label, "role": m.assigned_role,
                "provider": m.provider_code, "model": m.model_id, "has_submitted": m.has_submitted,
            }
            for m in case.members
        ],
        "submissions": [
            {
                "id": s.id, "member_id": s.member_id,
                "conclusion": s.conclusion[:300], "confidence": s.confidence,
                "evidence_quality": s.evidence_quality,
            }
            for s in case.submissions
        ],
        "critiques": [
            {"id": c.id, "reviewer": c.reviewer_member_id, "target_label": c.target_label,
             "overall": c.overall_assessment[:200]}
            for c in case.critiques
        ],
        "revisions": [
            {"id": r.id, "member_id": r.member_id, "changed": r.changed,
             "reason": r.reason_for_change[:200], "conformity_flagged": r.potential_conformity_flag}
            for r in db.query(OpinionRevision).filter(
                OpinionRevision.member_id.in_([m.id for m in case.members])
            ).all()
        ] if case.members else [],
        "dissents": [
            {"id": d.id, "position": d.position[:200], "status": d.status}
            for d in case.dissents
        ],
        "diversity_snapshots": [
            {"stage": s.stage, "disagreement_rate": s.disagreement_rate,
             "conformity_alerts": s.conformity_alerts}
            for s in case.snapshots
        ],
    })
    return d


def _take_diversity_snapshot(db: Session, case: DeliberationCase, stage: str):
    """Capture anti-convergence metrics."""
    subs = [s for s in case.submissions]
    members = [m for m in case.members]
    providers = set(m.provider_code for m in members if m.provider_code)
    models = set(m.model_id for m in members if m.model_id)

    # Provider concentration (0 = diverse, 1 = all same)
    provider_conc = 1.0 - (len(providers) / max(len(members), 1)) if members else 0

    # Disagreement rate from submissions
    conclusions = [s.conclusion for s in subs if s.conclusion]
    unique_conclusions = len(set(conclusions))
    disagreement = 1.0 - (unique_conclusions / max(len(conclusions), 1)) if conclusions else 0

    # Check revisions for conformity
    alerts = []
    revisions = db.query(OpinionRevision).filter(
        OpinionRevision.member_id.in_([m.id for m in members]),
        OpinionRevision.potential_conformity_flag == True,
    ).all()
    for r in revisions:
        alerts.append(f"Member {r.member_id}: unsupported opinion change")

    snap = DiversitySnapshot(
        case_id=case.id,
        stage=stage,
        initial_conclusion_diversity=unique_conclusions / max(len(conclusions), 1) if conclusions else 0,
        provider_concentration=round(provider_conc, 2),
        model_family_concentration=round(1.0 - (len(models) / max(len(members), 1)), 2) if members else 0,
        disagreement_rate=round(disagreement, 2),
        opinion_change_rate=round(len(revisions) / max(len(members), 1), 2) if members else 0,
        conformity_alerts=alerts,
    )
    db.add(snap)


def _add_conformity_alert(db: Session, case: DeliberationCase, member_id: str, msg: str):
    """Record a conformity alert."""
    snap = db.query(DiversitySnapshot).filter(
        DiversitySnapshot.case_id == case.id
    ).order_by(DiversitySnapshot.created_at.desc()).first()
    if snap:
        alerts = list(snap.conformity_alerts or [])
        alerts.append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")
        snap.conformity_alerts = alerts
