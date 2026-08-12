"""
Conductor Again — Skills Router
Skill Registry CRUD, version management, assignment, and AUTO-mode execution.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_master_db
from app.models import (
    AIAccount,
    AIResource,
    InstalledModel,
    Skill,
    SkillAssignment,
    SkillExecution,
    SkillVersion,
    User,
)
from app.schemas import (
    RouterCandidateOut,
    RouterDecisionOut,
    SkillAssignmentCreate,
    SkillAssignmentOut,
    SkillCreate,
    SkillExecuteRequest,
    SkillExecutionOut,
    SkillOut,
    SkillVersionCreate,
    SkillVersionOut,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])


# ═══════════════════════════════════════════════════════════
# Skills CRUD
# ═══════════════════════════════════════════════════════════

@router.get("", response_model=list[SkillOut])
def list_skills(
    category: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Skill)
    if category:
        q = q.filter(Skill.category == category)
    if status:
        q = q.filter(Skill.status == status)
    return q.order_by(Skill.name).all()


@router.post("", response_model=SkillOut, status_code=201)
def create_skill(
    body: SkillCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    existing = db.query(Skill).filter(Skill.skill_id == body.skill_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="skill_id already exists")
    skill = Skill(created_by=user.email, **body.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.patch("/{skill_db_id}", response_model=SkillOut)
def update_skill(
    skill_db_id: str,
    body: dict,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    skill = db.query(Skill).filter(Skill.id == skill_db_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    updatable = ["name", "description", "category", "execution_targets",
                  "capability_requirements", "model_policy", "data_policy",
                  "approval_policy", "budget_policy", "status"]
    for key in updatable:
        if key in body and body[key] is not None:
            setattr(skill, key, body[key])
    db.commit()
    db.refresh(skill)
    return skill


# ═══════════════════════════════════════════════════════════
# Skill Versions
# ═══════════════════════════════════════════════════════════

@router.get("/{skill_db_id}/versions", response_model=list[SkillVersionOut])
def list_versions(
    skill_db_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    return db.query(SkillVersion).filter(
        SkillVersion.skill_id == skill_db_id
    ).order_by(SkillVersion.version.desc()).all()


@router.post("/{skill_db_id}/versions", response_model=SkillVersionOut, status_code=201)
def create_version(
    skill_db_id: str,
    body: SkillVersionCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    skill = db.query(Skill).filter(Skill.id == skill_db_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    latest = db.query(SkillVersion).filter(
        SkillVersion.skill_id == skill_db_id
    ).order_by(SkillVersion.version.desc()).first()
    new_version = (latest.version + 1) if latest else 1

    import hashlib, json
    raw = json.dumps(body.model_dump(), sort_keys=True, default=str)
    checksum = hashlib.sha256(raw.encode()).hexdigest()

    sv = SkillVersion(
        skill_id=skill_db_id,
        version=new_version,
        checksum=checksum,
        status="draft",
        **{k: v for k, v in body.model_dump().items() if k != "skill_db_id"},
    )
    db.add(sv)
    skill.current_version = new_version
    db.commit()
    db.refresh(sv)
    return sv


@router.post("/versions/{version_id}/publish", response_model=SkillVersionOut)
def publish_version(
    version_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    sv = db.query(SkillVersion).filter(SkillVersion.id == version_id).first()
    if not sv:
        raise HTTPException(status_code=404, detail="Version not found")
    if sv.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft versions can be published")

    sv.status = "published"
    sv.published_by = user.email
    sv.published_at = datetime.now(timezone.utc)

    # Update parent skill status
    skill = db.query(Skill).filter(Skill.id == sv.skill_id).first()
    if skill and skill.status in ("draft", "in_review", "approved"):
        skill.status = "published"

    db.commit()
    db.refresh(sv)
    return sv


@router.post("/versions/{version_id}/revoke", response_model=SkillVersionOut)
def revoke_version(
    version_id: str,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    sv = db.query(SkillVersion).filter(SkillVersion.id == version_id).first()
    if not sv:
        raise HTTPException(status_code=404, detail="Version not found")
    sv.status = "revoked"
    db.commit()
    db.refresh(sv)
    return sv


# ═══════════════════════════════════════════════════════════
# Skill Assignments
# ═══════════════════════════════════════════════════════════

@router.get("/assignments", response_model=list[SkillAssignmentOut])
def list_assignments(
    scope_type: str | None = Query(None),
    scope_value: str | None = Query(None),
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    q = db.query(SkillAssignment).filter(SkillAssignment.active == True)
    if scope_type:
        q = q.filter(SkillAssignment.scope_type == scope_type)
    if scope_value:
        q = q.filter(SkillAssignment.scope_value == scope_value)
    return q.all()


@router.post("/assignments", response_model=SkillAssignmentOut, status_code=201)
def create_assignment(
    body: SkillAssignmentCreate,
    db: Session = Depends(get_master_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    # Deactivate conflicting assignments
    conflicts = db.query(SkillAssignment).filter(
        SkillAssignment.scope_type == body.scope_type,
        SkillAssignment.scope_value == body.scope_value,
        SkillAssignment.active == True,
    ).all()
    for c in conflicts:
        c.active = False
        c.revoked_at = datetime.now(timezone.utc)

    assignment = SkillAssignment(assigned_by=user.email, **body.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


# ═══════════════════════════════════════════════════════════
# AUTO Router — Core Intelligence
# ═══════════════════════════════════════════════════════════

@router.post("/execute", response_model=RouterDecisionOut)
async def execute_skill(
    body: SkillExecuteRequest,
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """AUTO-mode: evaluate all eligible resources and select the best one."""
    import uuid as _uuid

    request_id = f"airq_{_uuid.uuid4().hex[:12]}"

    # 1. Resolve skill
    skill = db.query(Skill).filter(Skill.skill_id == body.skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{body.skill_id}' not found")

    # Get latest published version
    sv = db.query(SkillVersion).filter(
        SkillVersion.skill_id == skill.id,
        SkillVersion.status == "published",
    ).order_by(SkillVersion.version.desc()).first()

    if not sv:
        # Fallback to latest draft if no published version
        sv = db.query(SkillVersion).filter(
            SkillVersion.skill_id == skill.id,
        ).order_by(SkillVersion.version.desc()).first()

    if not sv:
        raise HTTPException(status_code=400, detail="Skill has no versions")

    # 2. Get all enabled resources
    resources = db.query(AIResource).filter(
        AIResource.enabled == True,
        AIResource.health_state.in_(["AVAILABLE", "BUSY", "DEGRADED"]),
    ).all()

    # 3. Filter + score candidates
    candidates: list[RouterCandidateOut] = []
    required_caps = set(skill.capability_requirements.get("capabilities", []))

    for r in resources:
        rejection = ""

        # Get model capabilities
        model = db.query(InstalledModel).filter(InstalledModel.id == r.model_id).first()
        model_caps = set(model.capabilities if model else [])

        # Check capabilities
        if required_caps and not required_caps.issubset(model_caps):
            missing = required_caps - model_caps
            rejection = f"Missing capabilities: {', '.join(missing)}"

        # Check data classification
        allowed_classes = set(r.allowed_data_classifications or ["PUBLIC", "INTERNAL"])
        required_class = skill.data_policy.get("maximumClassification", "INTERNAL")
        if required_class not in allowed_classes:
            rejection = f"Data classification {required_class} not allowed"

        # Score eligible
        if not rejection:
            score = _score_resource(r, skill, model)
        else:
            score = 0.0

        candidates.append(RouterCandidateOut(
            resource_id=r.id,
            display_name=r.display_name,
            eligible=not bool(rejection),
            total_score=round(score, 1),
            rejection_reason=rejection,
            components={},
        ))

    eligible = [c for c in candidates if c.eligible]
    eligible.sort(key=lambda c: c.total_score, reverse=True)

    primary = eligible[0] if eligible else None
    fallback = [c.resource_id for c in eligible[1:3]] if len(eligible) > 1 else []
    escalation = None  # Future: separate escalation logic

    # 4. Record execution attempt
    execution = SkillExecution(
        skill_version_id=sv.id,
        resource_id=primary.resource_id if primary else None,
        project_slug=body.project_slug,
        request_id=request_id,
        selection_mode=body.selection_mode,
        status="queued",
        input_summary=str(body.input_data)[:500],
    )
    db.add(execution)
    db.commit()

    return RouterDecisionOut(
        request_id=request_id,
        skill_id=body.skill_id,
        selection_mode=body.selection_mode,
        primary_resource_id=primary.resource_id if primary else None,
        primary_display_name=primary.display_name if primary else "",
        fallback_ids=fallback,
        escalation_id=escalation,
        candidates_considered=len(candidates),
        candidates_eligible=len(eligible),
        reason=[
            f"Evaluated {len(candidates)} resources",
            f"{len(eligible)} eligible after policy filtering",
            f"Primary: {primary.display_name} (score {primary.total_score})" if primary else "No eligible resource found",
        ],
    )


def _score_resource(resource: AIResource, skill: Skill, model: InstalledModel | None) -> float:
    """Score a resource against a skill's requirements. Returns 0-100."""
    components = {}

    # Capability fit (25%)
    caps = set(model.capabilities if model else [])
    required = set(skill.capability_requirements.get("capabilities", []))
    if required:
        components["capabilityFit"] = min(100, len(caps & required) / len(required) * 100)
    else:
        components["capabilityFit"] = 80  # No specific requirements

    # Privacy/data fit (20%)
    components["privacyFit"] = 100 if resource.health_state == "AVAILABLE" else 70

    # Availability (10%)
    availability_map = {"AVAILABLE": 100, "BUSY": 60, "DEGRADED": 40}
    components["availability"] = availability_map.get(resource.health_state, 20)

    # Historical success (15%)
    components["historicalSuccess"] = resource.success_rate * 100

    # Cost (7%)
    if model and model.pricing_per_1k_output > 0:
        budget = skill.budget_policy.get("maximumEstimatedCostUsd", 1.0)
        cost_ratio = model.pricing_per_1k_output / (budget + 0.0001)
        components["cost"] = max(0, 100 - cost_ratio * 50)
    else:
        components["cost"] = 95  # Free/local

    # Latency (5%)
    latency_map = {"fast": 100, "balanced": 70, "slow": 40}
    components["latency"] = latency_map.get(model.latency_class if model else "balanced", 50)

    # Remaining capacity (10%)
    if resource.max_concurrency > 0:
        usage_ratio = resource.current_concurrency / resource.max_concurrency
        components["remainingCapacity"] = max(0, 100 - usage_ratio * 100)
    else:
        components["remainingCapacity"] = 50

    # Priority preference (8%)
    components["preference"] = resource.base_priority

    weights = {
        "capabilityFit": 0.25, "privacyFit": 0.20, "availability": 0.10,
        "historicalSuccess": 0.15, "cost": 0.07, "latency": 0.05,
        "remainingCapacity": 0.10, "preference": 0.08,
    }

    total = sum(components[k] * weights.get(k, 0.10) for k in components)
    return min(100, total)


# ═══════════════════════════════════════════════════════════
# Execution History
# ═══════════════════════════════════════════════════════════

@router.get("/executions", response_model=list[SkillExecutionOut])
def list_executions(
    project_slug: str | None = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    q = db.query(SkillExecution).order_by(SkillExecution.executed_at.desc())
    if project_slug:
        q = q.filter(SkillExecution.project_slug == project_slug)
    return q.limit(limit).all()
