"""
Conductor Again — Integration Router
Cross-app traceability, service health, and orchestration commands.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_master_db, get_project_db
from app.integration import (
    SERVICES,
    check_service_health,
    pm_create_delivery_plan,
    pm_get_artifact_references,
    pm_get_plan_status,
    qa_create_quality_design,
    qa_get_coverage_summary,
    qa_request_retest,
)
from app.models import (
    ActivityLog,
    ArtifactReference,
    IntegrationService,
    Requirement,
    TraceLink,
    User,
    Vision,
)

router = APIRouter(prefix="/api", tags=["integration"])

# ═══════════════════════════════════════════════════════════
# Service Registry
# ═══════════════════════════════════════════════════════════

@router.get("/integration/services")
def list_services(
    db: Session = Depends(get_master_db),
    user: User = Depends(get_current_user),
):
    """List all registered sibling services and their status."""
    result = []
    for code, svc in SERVICES.items():
        db_svc = db.query(IntegrationService).filter(IntegrationService.code == code).first()
        result.append({
            "code": code,
            "name": svc["name"],
            "status": db_svc.status if db_svc else svc["status"],
            "base_url": svc["base_url"],
            "description": svc["description"],
        })
    return result


@router.post("/integration/services/{code}/health")
async def check_service(code: str, user: User = Depends(require_roles("admin", "conductor"))):
    """Check health of a sibling service."""
    result = await check_service_health(code)
    return result


# ═══════════════════════════════════════════════════════════
# PM Again — Delivery Planning
# ═══════════════════════════════════════════════════════════

@router.post("/{slug}/integration/pm/delivery-plan")
async def send_delivery_plan(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(require_roles("admin", "conductor", "approver")),
):
    """Send approved requirements to PM Again for delivery planning."""
    # Get vision
    vision = db.query(Vision).order_by(Vision.revision.desc()).first()
    vision_title = vision.content[:80] if vision else slug

    # Get approved requirements
    reqs = db.query(Requirement).filter(Requirement.baseline_approved == True).all()
    if not reqs:
        raise HTTPException(status_code=400, detail="No approved requirements to send")

    req_data = [
        {
            "id": r.id,
            "code": r.code,
            "title": r.title,
            "description": r.description or "",
            "priority": 0,
        }
        for r in reqs
    ]

    result = await pm_create_delivery_plan(slug, req_data, vision_title)

    # Log activity
    db.add(ActivityLog(
        actor=user.email,
        actor_type="human",
        action="send_delivery_plan",
        entity_type="integration",
        entity_id=slug,
        details=f"Sent {len(reqs)} requirements to PM Again",
    ))
    db.commit()

    return result


@router.get("/{slug}/integration/pm/status")
async def get_pm_status(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    """Get PM Again delivery plan status for this project."""
    return await pm_get_plan_status(slug)


# ═══════════════════════════════════════════════════════════
# QA Again — Quality Design
# ═══════════════════════════════════════════════════════════

@router.post("/{slug}/integration/qa/quality-design")
async def send_quality_design(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(require_roles("admin", "conductor", "approver")),
):
    """Send requirements to QA Again for test design."""
    reqs = db.query(Requirement).filter(Requirement.baseline_approved == True).all()
    if not reqs:
        raise HTTPException(status_code=400, detail="No approved requirements to send")

    req_data = [
        {"id": r.id, "code": r.code, "title": r.title, "description": r.description or ""}
        for r in reqs
    ]

    result = await qa_create_quality_design(slug, req_data)

    db.add(ActivityLog(
        actor=user.email,
        actor_type="human",
        action="send_quality_design",
        entity_type="integration",
        entity_id=slug,
        details=f"Sent {len(reqs)} requirements to QA Again",
    ))
    db.commit()

    return result


@router.get("/{slug}/integration/qa/coverage")
async def get_qa_coverage(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    """Get QA Again test coverage for this project."""
    return await qa_get_coverage_summary(slug)


@router.post("/{slug}/integration/qa/retest")
async def request_retest(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    user: User = Depends(require_roles("admin", "conductor", "approver")),
):
    """Request QA Again retest after fix."""
    defect_id = body.get("defect_id", "")
    if not defect_id:
        raise HTTPException(status_code=400, detail="defect_id required")
    result = await qa_request_retest(slug, defect_id)

    db.add(ActivityLog(
        actor=user.email,
        actor_type="human",
        action="request_retest",
        entity_type="integration",
        entity_id=defect_id,
        details=f"Retest requested for defect {defect_id}",
    ))
    db.commit()

    return result


# ═══════════════════════════════════════════════════════════
# Traceability — Artifact References & Trace Links
# ═══════════════════════════════════════════════════════════

@router.post("/{slug}/trace/artifact-refs")
def create_artifact_ref(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    """Register an artifact reference from a sibling system."""
    ref = ArtifactReference(
        owner_system=body.get("owner_system", ""),
        artifact_type=body.get("artifact_type", ""),
        external_id=body.get("external_id", ""),
        external_url=body.get("external_url", ""),
        display_key=body.get("display_key", ""),
        status=body.get("status", ""),
        metadata_json=body.get("metadata_json", {}),
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return {"id": ref.id, "owner_system": ref.owner_system, "external_id": ref.external_id}


@router.get("/{slug}/trace/artifact-refs")
def list_artifact_refs(
    slug: str,
    owner_system: str | None = Query(None),
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    """List artifact references for this project."""
    q = db.query(ArtifactReference)
    if owner_system:
        q = q.filter(ArtifactReference.owner_system == owner_system)
    return q.order_by(ArtifactReference.created_at.desc()).all()


@router.post("/{slug}/trace/links")
def create_trace_link(
    slug: str,
    body: dict,
    db: Session = Depends(get_project_db),
    user: User = Depends(require_roles("admin", "conductor")),
):
    """Create a traceability link between a requirement and an artifact."""
    link = TraceLink(
        source_type=body.get("source_type", ""),
        source_id=body.get("source_id", ""),
        target_type=body.get("target_type", ""),
        target_ref_id=body.get("target_ref_id", ""),
        link_type=body.get("link_type", "traces_to"),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return {"id": link.id, "source_type": link.source_type, "target_type": link.target_type}


@router.get("/{slug}/trace/links")
def list_trace_links(
    slug: str,
    source_type: str | None = Query(None),
    source_id: str | None = Query(None),
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    """List traceability links for this project."""
    q = db.query(TraceLink)
    if source_type:
        q = q.filter(TraceLink.source_type == source_type)
    if source_id:
        q = q.filter(TraceLink.source_id == source_id)
    links = q.order_by(TraceLink.created_at.desc()).all()

    # Enrich with artifact ref data
    result = []
    for link in links:
        ref = db.query(ArtifactReference).filter(ArtifactReference.id == link.target_ref_id).first()
        result.append({
            "id": link.id,
            "source_type": link.source_type,
            "source_id": link.source_id,
            "target_type": link.target_type,
            "link_type": link.link_type,
            "target_ref": {
                "id": ref.id,
                "owner_system": ref.owner_system,
                "external_id": ref.external_id,
                "display_key": ref.display_key,
                "status": ref.status,
            } if ref else None,
            "created_at": link.created_at.isoformat() if link.created_at else None,
        })
    return result


@router.get("/{slug}/trace/matrix")
def get_trace_matrix(
    slug: str,
    db: Session = Depends(get_project_db),
    user: User = Depends(get_current_user),
):
    """Get full traceability matrix: Vision → Requirements → PM Artifacts → QA Artifacts."""
    requirements = db.query(Requirement).order_by(Requirement.code).all()
    vision = db.query(Vision).order_by(Vision.revision.desc()).first()

    rows = []
    for req in requirements:
        # Find trace links from this requirement
        links = db.query(TraceLink).filter(
            TraceLink.source_type == "REQUIREMENT",
            TraceLink.source_id == req.id,
        ).all()

        pm_refs = []
        qa_refs = []
        for link in links:
            ref = db.query(ArtifactReference).filter(ArtifactReference.id == link.target_ref_id).first()
            if ref:
                entry = {"id": ref.external_id, "type": ref.artifact_type, "status": ref.status, "url": ref.external_url}
                if ref.owner_system == "PM_AGAIN":
                    pm_refs.append(entry)
                elif ref.owner_system == "QA_AGAIN":
                    qa_refs.append(entry)

        rows.append({
            "requirement_code": req.code,
            "requirement_title": req.title,
            "requirement_status": req.status,
            "pm_artifacts": pm_refs,
            "qa_artifacts": qa_refs,
        })

    return {
        "vision": vision.content[:200] if vision else "",
        "requirements_count": len(requirements),
        "traced_count": sum(1 for r in rows if r["pm_artifacts"] or r["qa_artifacts"]),
        "rows": rows,
    }
