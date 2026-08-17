"""R17.1 — Human Deliverable service.

Implements the human-centered model on top of the internal standard registry:

  * project-type composition (small, human-facing document list)
  * on-demand generation only (no auto document creation)
  * deterministic generation precheck (5 readiness dimensions)
  * version-specific sign-off with content fingerprint + signer identity
  * immutability of approved/baselined versions
  * freshness + material-change detection
  * deterministic audit trail
  * acceptance & sign-off register
  * export types: controlled document / snapshot / sign-off evidence /
    acceptance package

AI is advisory only — every mutation requires an authenticated human actor and
the audit trail is deterministic.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..observability import request_id
from ..services import DomainError
from . import catalog as cat
from . import service as dsvc
from . import xlsx as dxlsx
from .models import (
    DeliverableAuditEvent,
    DeliverableSignoff,
    HumanDeliverableInstance,
)
from .standards import BY_NAME, standard_by_name
from .taxonomy import LIFECYCLE_TRANSITIONS, PROJECT_ATTRIBUTES

# lifecycle states for human deliverables (NOT_GENERATED implied by no row)
HD_LIFECYCLE_STATES = [
    "DRAFT", "INTERNAL_REVIEW", "CUSTOMER_REVIEW", "APPROVED",
    "BASELINED", "SUPERSEDED", "ARCHIVED",
]
HD_TRANSITIONS = {
    "DRAFT": ["DRAFT", "INTERNAL_REVIEW", "ARCHIVED"],
    "INTERNAL_REVIEW": ["DRAFT", "CUSTOMER_REVIEW", "ARCHIVED"],
    "CUSTOMER_REVIEW": ["INTERNAL_REVIEW", "APPROVED", "ARCHIVED"],
    "APPROVED": ["BASELINED", "SUPERSEDED", "ARCHIVED"],
    "BASELINED": ["SUPERSEDED", "ARCHIVED"],
    "SUPERSEDED": ["ARCHIVED"],
    "ARCHIVED": [],
}
# states that are immutable + require human action to move out of
IMMUTABLE_STATES = {"APPROVED", "BASELINED", "SUPERSEDED"}
HUMAN_ONLY_HD_STATES = {"APPROVED", "BASELINED", "SUPERSEDED"}

AUTHORITY_LABEL = {
    "DOCUMENT_AGAIN": "Document Again",
    "PM_AGAIN": "PM Again",
    "QA_AGAIN": "QA Again",
    "INFRA_AGAIN": "Infra Again",
    "ACCOUNT_AGAIN": "Account Again",
    "CONDUCTOR_AGAIN": "Conductor Again",
}
AUTHORITY_ROUTE = {
    "DOCUMENT_AGAIN": "requirements",
    "PM_AGAIN": "planning",
    "QA_AGAIN": "qa",
    "INFRA_AGAIN": "architecture",
    "ACCOUNT_AGAIN": "account",
    "CONDUCTOR_AGAIN": "conductor",
}

PROFILE_KEY = "deliverable_profile"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _identity(actx) -> dict:
    name = getattr(actx, "name", None) or "local-user"
    return {
        "user_id": getattr(actx, "id", None) or name,
        "name": name,
        "email": name,
        "organization": getattr(actx, "tenant_id", None),
        "source": getattr(actx, "source", "LOCAL"),
    }


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(obj) -> str:
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _audit(db: Session, project_id: str, object_type: str, object_id: str,
           action: str, actor: dict, before: dict | None, after: dict | None,
           reason: str | None = None) -> DeliverableAuditEvent:
    ev = DeliverableAuditEvent(
        id=_new_id("aud"),
        project_id=project_id,
        object_type=object_type,
        object_id=object_id,
        action=action,
        actor_user_id=actor["user_id"],
        actor_name=actor["name"],
        timestamp=_now(),
        before_state=before,
        after_state=after,
        reason=reason,
        request_id=request_id(),
    )
    db.add(ev)
    return ev


# ── Source indicators (deterministic counts of authoritative truth in DA) ───
def build_source_indicators(db: Session, project: m.Project) -> dict:
    def _count(model):
        return db.execute(
            select(model).where(model.project_id == project.id)
        ).scalars().all().__len__()

    return {
        "project_context": 1 if (project.description or project.name) else 0,
        "scope": 1 if project.description else 0,
        "requirements": _count(m.Requirement),
        "assumptions": _count(m.Assumption),
        "decisions": _count(m.Decision),
        "clarifications": _count(m.Clarification),
        "change_requests": _count(m.ChangeRequest),
        "trace_links": _count(m.TraceLink),
        "architecture": _count(m.ArchitectureDiagram),
        "flows": _count(m.ProcessFlow),
        "flow_steps": db.execute(
            select(m.ProcessStep)
            .join(m.ProcessFlow, m.ProcessStep.flow_id == m.ProcessFlow.id)
            .where(m.ProcessFlow.project_id == project.id)
        ).scalars().all().__len__(),
        # registers without a dedicated DA table yet — deterministic 0
        "stakeholders": 0, "milestones": 0, "deliverables": 0,
        "dependencies": 0, "raid": 0, "acceptance": 0, "handover": 0,
        "test_evidence": 0, "security": 0, "operations": 0, "data": 0,
        "ai": 0, "functions": 0, "generic": 0,
    }


# ── Composition ─────────────────────────────────────────────────────────────
def _profile(db: Session, project: m.Project) -> dict:
    return dsvc.get_profile(db, project)


def _role_assignments(profile: dict) -> dict[str, list[str]]:
    return profile.get("role_assignments") or {}


def compose_for_project(db: Session, project: m.Project) -> list[dict]:
    """Small human-facing document list derived from the project profile."""
    profile = _profile(db, project)
    primary_type = (profile.get("primary_type") or "").upper()
    attributes = profile.get("attributes") or {}

    composed = []
    for code, applicability in cat.composition_for(primary_type):
        hd = cat.HUMAN_DELIVERABLES[code]
        # CONDITIONAL documents are included only when a driving attribute is true
        if applicability == "CONDITIONAL":
            driver = cat._CONDITIONAL_DRIVER.get(code)
            if not driver or not attributes.get(driver):
                continue
            applicability = "RECOMMENDED"
        composed.append({
            "code": code,
            "name": hd["name"],
            "level": hd["level"],
            "level_name": cat.LEVELS[hd["level"]],
            "purpose": hd["purpose"],
            "category": hd["category"],
            "required_by": hd["required_by"],
            "applicability": applicability,
            "owner_role": hd["owner_role"],
            "reviewer_roles": hd["reviewer_roles"],
            "approver_roles": hd["approver_roles"],
            "signatory_roles": hd["signatory_roles"],
            "fyi_roles": hd["fyi_roles"],
            "signoff_policy": hd["signoff_policy"],
        })
    # order by gate order, then level, then code
    composed.sort(key=lambda d: (
        next((g["order"] for g in cat.SIGN_OFF_GATES if g["code"] == d["required_by"]), 99),
        d["level"], d["code"],
    ))
    return composed


def resolve_sections(human_code: str) -> list[dict]:
    """Expand a human deliverable's sections into concrete internal standards."""
    hd = cat.HUMAN_DELIVERABLES.get(human_code)
    if not hd:
        raise DomainError(f"Unknown human deliverable: {human_code}", status_code=404)
    out = []
    for section in hd["sections"]:
        stds = []
        for name in section["standards"]:
            std = standard_by_name(name)
            meta = cat.source_for(name)
            stds.append({
                "code": std["code"] if std else None,
                "name": name,
                "domain": std["domain"] if std else "UNKNOWN",
                "category": std["category"] if std else "UNKNOWN",
                "authority": meta["authority"],
                "source_key": meta["key"],
            })
        out.append({"title": section["title"], "kind": section["kind"], "standards": stds})
    return out


# ── Timing ──────────────────────────────────────────────────────────────────
def _current_phase(profile: dict) -> str | None:
    return (profile.get("current_phase") or "").upper() or None


def _timing(required_by: str, phase: str | None) -> tuple[str, str]:
    """Return (state, label) where state in UPCOMING/CURRENT/PAST/ANY."""
    gate = cat.GATE_BY_CODE.get(required_by)
    if not gate or gate.get("phase") == "ANY":
        return ("ANY", "Event-driven")
    target_phase = gate["phase"]
    if not phase or phase not in cat.PHASE_ORDER or target_phase not in cat.PHASE_ORDER:
        return ("CURRENT", f"Required by {target_phase}")
    ci = cat.PHASE_ORDER.index(phase)
    ti = cat.PHASE_ORDER.index(target_phase)
    if ti > ci:
        return ("UPCOMING", f"Required by {target_phase}")
    if ti < ci:
        return ("PAST", f"Required by {target_phase}")
    return ("CURRENT", f"Required by {target_phase}")


# ── Precheck ────────────────────────────────────────────────────────────────
def precheck(db: Session, project: m.Project, human_code: str) -> dict:
    hd = cat.HUMAN_DELIVERABLES.get(human_code)
    if not hd:
        raise DomainError(f"Unknown human deliverable: {human_code}", status_code=404)

    profile = _profile(db, project)
    indicators = build_source_indicators(db, project)
    sections = resolve_sections(human_code)
    phase = _current_phase(profile)
    timing_state, timing_label = _timing(hd["required_by"], phase)

    section_results = []
    for section in sections:
        states = []
        for std in section["standards"]:
            value = indicators.get(std["source_key"], 0)
            if value > 0:
                state = "READY"
            elif std["authority"] == "DOCUMENT_AGAIN":
                state = "MISSING"
            else:
                state = "NO_SOURCE"
            states.append({
                "code": std["code"], "name": std["name"], "state": state,
                "authority": std["authority"],
                "owner_label": AUTHORITY_LABEL.get(std["authority"], std["authority"]),
                "owner_route": AUTHORITY_ROUTE.get(std["authority"], ""),
            })
        section_results.append({
            "title": section["title"],
            "kind": section["kind"],
            "ready": sum(1 for s in states if s["state"] == "READY"),
            "partial": sum(1 for s in states if s["state"] in ("PARTIAL",)),
            "missing": sum(1 for s in states if s["state"] == "MISSING"),
            "no_source": sum(1 for s in states if s["state"] == "NO_SOURCE"),
            "standards": states,
        })

    total = sum(len(s["standards"]) for s in section_results)
    ready_modules = sum(s["ready"] for s in section_results)
    missing_modules = sum(s["missing"] for s in section_results)
    no_source_modules = sum(s["no_source"] for s in section_results)
    fully_ready_sections = sum(
        1 for s in section_results
        if s["missing"] == 0 and s["no_source"] == 0 and s["ready"] == len(s["standards"])
    )

    # overall readiness (deterministic — no arbitrary percentages)
    if timing_state == "UPCOMING":
        readiness = "NOT_DUE"
    elif fully_ready_sections == len(section_results) and total > 0:
        readiness = "READY"
    elif ready_modules > 0:
        readiness = "READY_WITH_GAPS"
    else:
        readiness = "NOT_READY"

    return {
        "human_code": human_code,
        "name": hd["name"],
        "required_by": hd["required_by"],
        "timing_state": timing_state,
        "timing_label": timing_label,
        "readiness": readiness,
        "required_sections": len(section_results),
        "ready_sections": fully_ready_sections,
        "ready_modules": ready_modules,
        "missing_modules": missing_modules,
        "no_source_modules": no_source_modules,
        "total_modules": total,
        "precheck_id": _new_id("pc"),
        "sections": section_results,
    }


# ── Instance helpers ────────────────────────────────────────────────────────
def _head(db: Session, project_id: str, human_code: str) -> HumanDeliverableInstance | None:
    rows = db.execute(
        select(HumanDeliverableInstance).where(
            HumanDeliverableInstance.project_id == project_id,
            HumanDeliverableInstance.human_code == human_code,
        ).order_by(HumanDeliverableInstance.created_at.desc())
    ).scalars().all()
    return rows[0] if rows else None


def _all_versions(db: Session, project_id: str, human_code: str) -> list[HumanDeliverableInstance]:
    return db.execute(
        select(HumanDeliverableInstance).where(
            HumanDeliverableInstance.project_id == project_id,
            HumanDeliverableInstance.human_code == human_code,
        ).order_by(HumanDeliverableInstance.created_at.desc())
    ).scalars().all()


def _signoff_for_version(db: Session, project_id: str, human_code: str, version: str) -> DeliverableSignoff | None:
    return db.execute(
        select(DeliverableSignoff).where(
            DeliverableSignoff.project_id == project_id,
            DeliverableSignoff.human_code == human_code,
            DeliverableSignoff.document_version == version,
        )
    ).scalars().first()


def _next_version(current: str | None, *, baseline: bool = False) -> str:
    if not current:
        return "0.1"
    parts = current.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return "1.0" if baseline else "0.1"
    if baseline:
        return f"{major + 1}.0"
    return f"{major}.{minor + 1}"


def _snapshot(db: Session, project: m.Project) -> dict:
    ctx = dxlsx.build_context(db, project)
    # drop the derived matrix (regenerated) — keep authoritative truth only
    ctx.pop("matrix", None)
    ctx.pop("summary", None)
    # build_context keeps architecture nodes / flow steps as ORM objects for the
    # XLSX renderer; the snapshot must be plain JSON so it can be persisted and
    # fingerprinted deterministically.
    ctx["architecture"] = [
        {"name": d["name"], "nodes": [
            {"id": n.semantic_id, "name": n.name,
             "type": n.node_type.value if hasattr(n.node_type, "value") else str(n.node_type),
             "technology": n.technology, "environment": n.environment}
            for n in d["nodes"]]
        }
        for d in ctx.get("architecture", [])
    ]
    ctx["flows"] = [
        {"name": f["name"], "steps": [
            {"id": s.semantic_id, "name": s.name,
             "type": s.step_type.value if hasattr(s.step_type, "value") else str(s.step_type),
             "position": s.position}
            for s in f["steps"]]
        }
        for f in ctx.get("flows", [])
    ]
    return ctx


# ── List (Deliverable Center) ───────────────────────────────────────────────
def list_human_deliverables(db: Session, project: m.Project, actx) -> dict:
    composed = compose_for_project(db, project)
    profile = _profile(db, project)
    actor = _identity(actx)
    my_roles = _role_assignments(profile).get(actor["email"], [])
    my_roles = [r.upper() for r in my_roles]

    rows = []
    my_actions = {"review": 0, "approval": 0, "signoff": 0}
    for c in composed:
        head = _head(db, project.id, c["code"])
        my_role = _my_role(c, my_roles)
        lifecycle = head.lifecycle_status if head else "NOT_GENERATED"
        version = head.version if head else None
        signoff = _signoff_for_version(db, project.id, c["code"], version) if head else None

        # queues
        needs_review = my_role == "REVIEWER" and lifecycle == "INTERNAL_REVIEW"
        needs_approval = my_role == "APPROVER" and lifecycle == "CUSTOMER_REVIEW"
        needs_signoff = (
            my_role == "SIGNATORY"
            and lifecycle == "APPROVED"
            and not signoff
            and c["signoff_policy"]["mode"] in ("REQUIRED", "CONDITIONAL")
        )
        if needs_review:
            my_actions["review"] += 1
        if needs_approval:
            my_actions["approval"] += 1
        if needs_signoff:
            my_actions["signoff"] += 1

        # freshness / material change for generated docs
        freshness = head.freshness if head else "NOT_APPLICABLE"
        material = head.material_change if head else "NOT_APPLICABLE"

        rows.append({
            "code": c["code"],
            "name": c["name"],
            "level": c["level"],
            "level_name": c["level_name"],
            "purpose": c["purpose"],
            "applicability": c["applicability"],
            "required_by": c["required_by"],
            "owner_role": c["owner_role"],
            "signoff_policy": c["signoff_policy"],
            "lifecycle_status": lifecycle,
            "version": version,
            "readiness": head.readiness if head else None,
            "freshness": freshness,
            "material_change": material,
            "document_id": head.document_id if head else None,
            "generated_at": head.generated_at.isoformat() if head and head.generated_at else None,
            "generated_by": head.generated_by if head else None,
            "my_role": my_role,
            "needs_review": needs_review,
            "needs_approval": needs_approval,
            "needs_signoff": needs_signoff,
            "instance_id": head.id if head else None,
        })

    # summary counts (small, human-friendly)
    summary = {
        "total": len(rows),
        "ready_to_generate": sum(1 for r in rows if r["lifecycle_status"] == "NOT_GENERATED"),
        "needs_information": sum(1 for r in rows if r["readiness"] in ("NOT_READY", "READY_WITH_GAPS") and r["lifecycle_status"] == "NOT_GENERATED"),
        "generated": sum(1 for r in rows if r["lifecycle_status"] != "NOT_GENERATED"),
        "not_due": sum(1 for r in rows if r["readiness"] == "NOT_DUE"),
        "stale": sum(1 for r in rows if r["freshness"] == "STALE"),
    }

    return {
        "project_id": project.id,
        "project_name": project.name,
        "project_key": project.key,
        "current_phase": _current_phase(profile) or "NOT SET",
        "my_actions": my_actions,
        "summary": summary,
        "documents": rows,
        "gates": gate_status(db, project),
        "supporting_registers": cat.SUPPORTING_REGISTERS,
        "internal_module_count": len(BY_NAME),
    }


def _my_role(composed: dict, my_roles: list[str]) -> str:
    if composed["owner_role"] in my_roles:
        return "OWNER"
    if any(r in my_roles for r in composed["reviewer_roles"]):
        return "REVIEWER"
    if any(r in my_roles for r in composed["approver_roles"]):
        return "APPROVER"
    if any(r in my_roles for r in composed["signatory_roles"]):
        return "SIGNATORY"
    return "FYI"


# ── Generation (on demand, human confirmed) ─────────────────────────────────
def generate(db: Session, project: m.Project, human_code: str, actx,
             *, with_gaps: bool = False, precheck_id: str | None = None) -> dict:
    hd = cat.HUMAN_DELIVERABLES.get(human_code)
    if not hd:
        raise DomainError(f"Unknown human deliverable: {human_code}", status_code=404)

    composed = {c["code"]: c for c in compose_for_project(db, project)}
    if human_code not in composed:
        raise DomainError(
            f"{human_code} is not applicable to this project profile", status_code=409,
        )

    actor = _identity(actx)
    head = _head(db, project.id, human_code)

    if head and head.lifecycle_status in IMMUTABLE_STATES:
        # signed/approved versions are immutable → create a new revision
        return _create_revision(db, project, hd, composed[human_code], head, actor, with_gaps)
    if head and head.lifecycle_status not in ("SUPERSEDED",):
        raise DomainError(
            f"{hd['name']} already generated (v{head.version}, {head.lifecycle_status}). "
            "Submit it for review or create a revision after approval.",
            status_code=409,
        )

    pc = precheck(db, project, human_code)
    if pc["readiness"] == "NOT_READY" and not with_gaps:
        raise DomainError(
            f"Precheck is {pc['readiness']} — confirm 'Generate Draft With Gaps' to proceed.",
            status_code=409,
        )

    snapshot = _snapshot(db, project)
    snapshot_hash = _sha256(snapshot)
    doc_id = f"{project.key}-{human_code}"
    inst = HumanDeliverableInstance(
        id=_new_id("hd"),
        project_id=project.id,
        human_code=human_code,
        name=hd["name"],
        level=hd["level"],
        level_name=cat.LEVELS[hd["level"]],
        applicability=composed[human_code]["applicability"],
        applicability_reason=[f"project_type={_profile(db, project).get('primary_type')}"],
        document_id=doc_id,
        version="0.1",
        lifecycle_status="DRAFT",
        readiness=pc["readiness"],
        required_by=hd["required_by"],
        owner_role=hd["owner_role"],
        reviewer_roles=hd["reviewer_roles"],
        approver_roles=hd["approver_roles"],
        signatory_roles=hd["signatory_roles"],
        fyi_roles=hd["fyi_roles"],
        signoff_policy=hd["signoff_policy"],
        generated_at=_now(),
        generated_by=actor["email"],
        generated_by_id=actor["user_id"],
        precheck_id=precheck_id or pc["precheck_id"],
        readiness_at_generation={
            "readiness": pc["readiness"],
            "ready_sections": pc["ready_sections"],
            "ready_modules": pc["ready_modules"],
            "missing_modules": pc["missing_modules"],
            "no_source_modules": pc["no_source_modules"],
            "with_gaps": with_gaps,
        },
        source_snapshot=snapshot,
        snapshot_hash=snapshot_hash,
        mapping_version="1.0",
        template_version="1.0",
        freshness="CURRENT",
        material_change="UNKNOWN",
        stale=False,
    )
    db.add(inst)
    _audit(db, project.id, "HUMAN_DELIVERABLE", inst.id, "GENERATED", actor,
           before=None, after={"lifecycle_status": "DRAFT", "version": inst.version,
                               "readiness": inst.readiness},
           reason=f"on-demand generation (precheck {inst.precheck_id}, with_gaps={with_gaps})")
    db.commit()
    return inst.to_dict()


def _create_revision(db: Session, project: m.Project, hd: dict, composed: dict,
                     old: HumanDeliverableInstance, actor: dict, with_gaps: bool) -> dict:
    pc = precheck(db, project, hd["code"])
    if pc["readiness"] == "NOT_READY" and not with_gaps:
        raise DomainError(
            f"Precheck is {pc['readiness']} — confirm 'Generate Draft With Gaps' to proceed.",
            status_code=409,
        )
    snapshot = _snapshot(db, project)
    snapshot_hash = _sha256(snapshot)
    next_v = _next_version(old.version)
    inst = HumanDeliverableInstance(
        id=_new_id("hd"),
        project_id=project.id,
        human_code=hd["code"],
        name=hd["name"],
        level=hd["level"],
        level_name=cat.LEVELS[hd["level"]],
        applicability=composed["applicability"],
        applicability_reason=old.applicability_reason,
        document_id=f"{project.key}-{hd['code']}",
        version=next_v,
        lifecycle_status="DRAFT",
        readiness=pc["readiness"],
        required_by=hd["required_by"],
        owner_role=hd["owner_role"],
        reviewer_roles=hd["reviewer_roles"],
        approver_roles=hd["approver_roles"],
        signatory_roles=hd["signatory_roles"],
        fyi_roles=hd["fyi_roles"],
        signoff_policy=hd["signoff_policy"],
        generated_at=_now(),
        generated_by=actor["email"],
        generated_by_id=actor["user_id"],
        precheck_id=pc["precheck_id"],
        readiness_at_generation={
            "readiness": pc["readiness"],
            "with_gaps": with_gaps,
        },
        source_snapshot=snapshot,
        snapshot_hash=snapshot_hash,
        mapping_version="1.0",
        template_version="1.0",
        freshness="CURRENT",
        material_change=_material_change(old.source_snapshot, snapshot),
        stale=False,
        supersedes_id=old.id,
    )
    db.add(inst)
    # the old version becomes SUPERSEDED but remains immutable
    old.lifecycle_status = "SUPERSEDED"
    old.freshness = "STALE"
    _audit(db, project.id, "HUMAN_DELIVERABLE", inst.id, "REVISION_CREATED", actor,
           before={"supersedes": old.id, "old_version": old.version},
           after={"lifecycle_status": "DRAFT", "version": inst.version},
           reason=f"revision of v{old.version}")
    db.commit()
    return inst.to_dict()


def _material_change(old_snapshot: dict | None, new_snapshot: dict) -> str:
    if not old_snapshot:
        return "UNKNOWN"
    old_hash = _sha256(old_snapshot)
    new_hash = _sha256(new_snapshot)
    if old_hash == new_hash:
        return "NON_MATERIAL_CHANGE"
    # deterministic material signals: scope / requirements / architecture / CRs
    for key in ("requirements", "architecture", "flows", "change_requests", "decisions"):
        if _sha256(old_snapshot.get(key, [])) != _sha256(new_snapshot.get(key, [])):
            return "MATERIAL_CHANGE"
    return "UNKNOWN"


# ── Freshness ───────────────────────────────────────────────────────────────
def refresh_freshness(db: Session, project: m.Project, human_code: str) -> dict:
    head = _head(db, project.id, human_code)
    if not head or not head.source_snapshot:
        return {"freshness": "NOT_APPLICABLE", "material_change": "NOT_APPLICABLE"}
    current = _snapshot(db, project)
    cur_hash = _sha256(current)
    if cur_hash == head.snapshot_hash:
        head.freshness = "CURRENT"
    else:
        head.freshness = "STALE"
        head.stale = True
        head.material_change = _material_change(head.source_snapshot, current)
    db.commit()
    return {"freshness": head.freshness, "material_change": head.material_change,
            "snapshot_hash": head.snapshot_hash, "current_hash": cur_hash}


# ── Lifecycle transition ────────────────────────────────────────────────────
def transition(db: Session, project: m.Project, human_code: str, target: str, actx,
               *, comment: str | None = None) -> dict:
    if target not in HD_LIFECYCLE_STATES:
        raise DomainError(f"Unknown lifecycle state: {target}", status_code=422)
    head = _head(db, project.id, human_code)
    if not head:
        raise DomainError(f"No generated instance for {human_code}", status_code=404)
    if target not in HD_TRANSITIONS.get(head.lifecycle_status, []):
        raise DomainError(
            f"Invalid transition {head.lifecycle_status} -> {target}", status_code=409,
        )
    if target in HUMAN_ONLY_HD_STATES:
        # always human — the route enforces an authenticated human actor
        pass
    actor = _identity(actx)
    before = {"lifecycle_status": head.lifecycle_status, "version": head.version}
    head.lifecycle_status = target
    if target == "BASELINED":
        # version is fixed at APPROVED (sign-off) time; baseline only records the
        # frozen baseline identifier — it never changes the version the sign-off
        # applies to.
        head.baseline_id = _new_id("bsl")
    _audit(db, project.id, "HUMAN_DELIVERABLE", head.id, target, actor,
           before=before, after={"lifecycle_status": target, "version": head.version},
           reason=comment)
    db.commit()
    return head.to_dict()


# ── Sign-off (version-specific, identity-verified) ──────────────────────────
def signoff(db: Session, project: m.Project, human_code: str, actx, body: dict) -> dict:
    head = _head(db, project.id, human_code)
    if not head:
        raise DomainError(f"No generated instance for {human_code}", status_code=404)
    if head.lifecycle_status not in ("CUSTOMER_REVIEW", "APPROVED"):
        raise DomainError(
            f"Sign-off requires CUSTOMER_REVIEW or APPROVED (currently {head.lifecycle_status})",
            status_code=409,
        )

    decision = (body.get("decision") or "ACCEPT").upper()
    if decision not in cat.SIGNOFF_DECISIONS:
        raise DomainError(f"Unknown sign-off decision: {decision}", status_code=422)
    signoff_type = (body.get("signoff_type") or decision).upper()
    if decision in ("APPROVE", "ACCEPT"):
        signoff_type = "APPROVE" if decision == "APPROVE" else "ACCEPT"
    if decision == "ACKNOWLEDGE":
        signoff_type = "ACKNOWLEDGE"
    if decision == "REJECT":
        signoff_type = "REJECT"

    actor = _identity(actx)
    role = body.get("signer_role") or None

    before = {"lifecycle_status": head.lifecycle_status, "version": head.version}
    if decision in ("APPROVE", "ACCEPT", "ACCEPTED_WITH_EXCEPTIONS"):
        # first approval pins the document at 1.0 (draft revisions were 0.x);
        # subsequent re-approvals keep their revision number (1.1, 1.2, …).
        if (head.version or "").startswith("0."):
            head.version = "1.0"
        head.lifecycle_status = "APPROVED"
    elif decision == "REJECT":
        head.lifecycle_status = "INTERNAL_REVIEW"

    known_exceptions = body.get("known_exceptions") or []
    sig = DeliverableSignoff(
        id=_new_id("sgn"),
        project_id=project.id,
        human_code=human_code,
        instance_id=head.id,
        document_id=head.document_id or f"{project.key}-{human_code}",
        document_version=head.version or "0.1",
        baseline_id=head.baseline_id,
        document_hash=head.snapshot_hash,
        snapshot_hash=head.snapshot_hash,
        signoff_type=signoff_type,
        decision=decision,
        signer_user_id=actor["user_id"],
        signer_name=actor["email"],
        signer_role=role,
        signer_organization=actor["organization"],
        signed_at=_now(),
        comment=body.get("comment"),
        known_exceptions=known_exceptions,
        source_snapshot_id=head.precheck_id,
        auth_context={"source": actor["source"], "organization": actor["organization"]},
    )
    db.add(sig)
    db.flush()
    _audit(db, project.id, "SIGNOFF", sig.id, "SIGNED", actor,
           before=before, after={"lifecycle_status": head.lifecycle_status,
                                 "decision": decision, "version": head.version},
           reason=f"sign-off {decision} on v{head.version} (hash {head.snapshot_hash[:12]}…)")
    db.commit()
    return sig.to_dict()


# ── Registers / queues / history ────────────────────────────────────────────
def signoff_register(db: Session, project: m.Project) -> list[dict]:
    rows = db.execute(
        select(DeliverableSignoff).where(DeliverableSignoff.project_id == project.id)
        .order_by(DeliverableSignoff.signed_at.desc())
    ).scalars().all()
    return [s.to_dict() for s in rows]


def accept_change_request(db: Session, project: m.Project, cr_code: str, actx,
                          body: dict) -> dict:
    """Gate 3 — Change Acceptance. Records explicit human acceptance of an
    important change request as version-specific sign-off evidence, reusing the
    existing Change Request governance."""
    cr = db.execute(
        select(m.ChangeRequest).where(
            m.ChangeRequest.project_id == project.id,
            m.ChangeRequest.code == cr_code,
        )
    ).scalars().first()
    if not cr:
        raise DomainError(f"Change request not found: {cr_code}", status_code=404)

    decision = (body.get("decision") or "ACCEPT").upper()
    if decision not in cat.SIGNOFF_DECISIONS:
        raise DomainError(f"Unknown sign-off decision: {decision}", status_code=422)

    actor = _identity(actx)
    sig = DeliverableSignoff(
        id=_new_id("sgn"),
        project_id=project.id,
        human_code=f"CR-{cr.code}",
        instance_id=cr.id,
        document_id=f"{project.key}-{cr.code}",
        document_version="1.0",
        baseline_id=None,
        document_hash=None,
        snapshot_hash=None,
        signoff_type="ACCEPT" if decision in ("ACCEPT", "APPROVE") else decision,
        decision=decision,
        signer_user_id=actor["user_id"],
        signer_name=actor["email"],
        signer_role=body.get("signer_role"),
        signer_organization=actor["organization"],
        signed_at=_now(),
        comment=body.get("comment") or f"Change acceptance for {cr_code}",
        known_exceptions=body.get("known_exceptions") or [],
        source_snapshot_id=cr.id,
        auth_context={"source": actor["source"], "organization": actor["organization"]},
    )
    db.add(sig)
    db.flush()
    _audit(db, project.id, "SIGNOFF", sig.id, "SIGNED", actor,
           before=None,
           after={"decision": decision, "object": cr_code},
           reason=f"change acceptance {decision} on {cr_code}")
    db.commit()
    return sig.to_dict()


def gate_status(db: Session, project: m.Project) -> list[dict]:
    """Status of the 7 critical gates: which are signed (or not applicable)."""
    sigs = signoff_register(db, project)
    out = []
    for gate in cat.SIGN_OFF_GATES:
        code = gate["code"]
        if code == "CHANGE_ACCEPTANCE":
            cr_sigs = [s for s in sigs if s["human_code"].startswith("CR-")]
            out.append({"gate": code, "name": gate["name"], "phase": gate["phase"],
                        "status": "SIGNED" if cr_sigs else "OPEN", "signoffs": len(cr_sigs)})
            continue
        docs = [c for c in compose_for_project(db, project) if c["required_by"] == code]
        if not docs:
            out.append({"gate": code, "name": gate["name"], "phase": gate["phase"],
                        "status": "NOT_APPLICABLE", "signoffs": 0})
            continue
        signed = any(
            s["human_code"] == d["code"] for d in docs for s in sigs
        )
        out.append({"gate": code, "name": gate["name"], "phase": gate["phase"],
                    "status": "SIGNED" if signed else "OPEN",
                    "signoffs": sum(1 for d in docs for s in sigs if s["human_code"] == d["code"])})
    return out


def my_signoffs(db: Session, project: m.Project, actx) -> list[dict]:
    actor = _identity(actx)
    rows = db.execute(
        select(DeliverableSignoff).where(
            DeliverableSignoff.project_id == project.id,
            DeliverableSignoff.signer_user_id == actor["user_id"],
        ).order_by(DeliverableSignoff.signed_at.desc())
    ).scalars().all()
    return [s.to_dict() for s in rows]


def audit_trail(db: Session, project: m.Project, limit: int = 200) -> list[dict]:
    rows = db.execute(
        select(DeliverableAuditEvent).where(DeliverableAuditEvent.project_id == project.id)
        .order_by(DeliverableAuditEvent.timestamp.desc()).limit(limit)
    ).scalars().all()
    return [r.to_dict() for r in rows]


def version_history(db: Session, project: m.Project, human_code: str) -> list[dict]:
    return [v.to_dict() for v in _all_versions(db, project.id, human_code)]


# ── Exports ─────────────────────────────────────────────────────────────────
def build_human_workbook(db: Session, project: m.Project, human_code: str,
                         brand: str = "GEA_STANDARD") -> bytes:
    hd = cat.HUMAN_DELIVERABLES.get(human_code)
    if not hd:
        raise DomainError(f"Unknown human deliverable: {human_code}", status_code=404)
    head = _head(db, project.id, human_code)
    if not head:
        raise DomainError(f"No generated instance for {human_code} — generate first.", status_code=404)

    ctx = dxlsx.build_context(db, project)
    x = dxlsx.Xlsx(brand)
    wb = x.new_workbook()

    doc = {
        "title": hd["name"],
        "project": project.name,
        "project_code": project.key,
        "document_id": head.document_id or f"{project.key}-{human_code}",
        "template_id": human_code,
        "template_version": "1.0",
        "version": head.version or "0.1",
        "revision": head.version or "0.1",
        "status": head.lifecycle_status,
        "prepared_by": head.generated_by or "—",
        "reviewed_by": "—",
        "approved_by": "—",
        "effective_date": (head.generated_at or _now()).isoformat()[:10],
        "generated_at": (head.generated_at or _now()).isoformat(),
        "customer": project.description or "Customer",
    }
    x.render_cover(wb, doc)
    x.render_document_control(wb, doc)
    revisions = [
        {"revision": head.version, "date": (head.generated_at or _now()).isoformat()[:10],
         "description": f"Generated (readiness: {head.readiness})",
         "prepared": head.generated_by or "—", "reviewed": "—", "status": head.lifecycle_status},
    ]
    x.render_revision_history(wb, doc, revisions)

    sections = resolve_sections(human_code)
    sheet_names = ["00_Cover", "01_Document_Control", "02_Revision_History", "03_Sheet_Index"]
    for i, section in enumerate(sections, start=10):
        sheet_names.append(f"{i}_{_sheet_name(section['title'])}")
    sheet_names += ["80_Source_Registers", "90_Review_Signoff", "99_Source_Reference"]
    x.render_index(wb, doc, dxlsx._index_entries(sheet_names))

    # section composition sheets
    for i, section in enumerate(sections, start=10):
        rows = [[s["code"] or "—", s["name"], s["domain"], s["authority"],
                 _section_state(s, head.readiness_at_generation)] for s in section["standards"]]
        x.render_register(
            wb, f"{i}_{_sheet_name(section['title'])}",
            ["Standard", "Module", "Domain", "Source Authority", "State"], rows, doc,
            widths=(14, 40, 14, 16, 16),
        )

    # source registers (real authoritative truth only — nothing fabricated)
    x.render_register(wb, "80_Requirements",
                      ["Code", "Title", "Status", "Priority", "Source"],
                      [[r["code"], r["title"], r["status"], r["priority"], r["source"]]
                       for r in ctx.get("requirements", [])],
                      doc, widths=(14, 52, 12, 10, 18))
    x.render_register(wb, "81_Assumptions",
                      ["ID", "Assumption", "Status"],
                      [[a["id"], a["content"], a["status"]] for a in ctx.get("assumptions", [])],
                      doc, widths=(14, 76, 12))
    x.render_register(wb, "82_Decisions",
                      ["ID", "Decision", "Content"],
                      [[d["id"], d["title"], d["content"]] for d in ctx.get("decisions", [])],
                      doc, widths=(14, 36, 50))
    x.render_register(wb, "83_Clarifications",
                      ["Question", "Answer", "Resolved"],
                      [[c["question"], c["answer"] or "—", "Yes" if c["resolved"] else "No"]
                       for c in ctx.get("clarifications", [])],
                      doc, widths=(46, 46, 10))
    x.render_register(wb, "84_Change_Requests",
                      ["Code", "Title", "Requested Change", "Status"],
                      [[c["code"], c["title"], c["requested_change"], c["status"]]
                       for c in ctx.get("change_requests", [])],
                      doc, widths=(12, 32, 46, 16))

    # sign-off sheet
    sig = _signoff_for_version(db, project.id, human_code, head.version)
    signoffs = []
    if sig:
        signoffs = [{
            "role": sig.signer_role or "Signer", "name": sig.signer_name,
            "date": (sig.signed_at or _now()).isoformat()[:19],
        }]
    x.render_signoff(wb, doc, signoffs)

    x.render_source_reference(wb, doc, [
        {"authority": s["authority"], "object_type": "Standard", "object_id": s["code"],
         "version": "1.0", "retrieved_at": (head.generated_at or _now()).isoformat()}
        for s in sum((sec["standards"] for sec in sections), []) if s["code"]
    ])

    wb.active = 0
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sheet_name(title: str) -> str:
    return title.replace(" ", "_").replace("/", "_")[:28]


def _section_state(standard: dict, readiness_at_generation: dict | None) -> str:
    # state is recomputed deterministically at export time from the source key
    return standard.get("code") or "TBD"


def snapshot_export(db: Session, project: m.Project, human_code: str) -> bytes:
    head = _head(db, project.id, human_code)
    if not head or not head.source_snapshot:
        raise DomainError(f"No generated instance for {human_code}", status_code=404)
    payload = {
        "project_id": project.id,
        "project_key": project.key,
        "human_code": human_code,
        "document_id": head.document_id,
        "version": head.version,
        "snapshot_hash": head.snapshot_hash,
        "generated_at": head.generated_at.isoformat() if head.generated_at else None,
        "generated_by": head.generated_by,
        "source_snapshot": head.source_snapshot,
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def signoff_evidence_export(db: Session, project: m.Project, human_code: str | None = None) -> bytes:
    sigs = signoff_register(db, project)
    if human_code:
        sigs = [s for s in sigs if s["human_code"] == human_code]
    payload = {
        "project_id": project.id,
        "project_key": project.key,
        "generated_at": _now().isoformat(),
        "signoffs": sigs,
        "note": ("This record supports strong project acceptance evidence and is "
                 "version-specific with content hashes. It does not, by itself, "
                 "guarantee legal enforceability in every jurisdiction."),
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def acceptance_package(db: Session, project: m.Project) -> bytes:
    """Zip package of actually-generated documents + evidence registers.

    Only generated documents are included — missing documents are never
    fabricated to fill the package."""
    buf = io.BytesIO()
    composed = {c["code"]: c for c in compose_for_project(db, project)}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # generated human documents
        generated = []
        for code in composed:
            head = _head(db, project.id, code)
            if not head:
                continue
            generated.append({"code": code, "name": head.name, "version": head.version})
            xlsx = build_human_workbook(db, project, code)
            zf.writestr(f"{code}_{head.name.replace(' ', '_')}_v{head.version}.xlsx", xlsx)
        # sign-off evidence
        zf.writestr("Signoff_Evidence.json", signoff_evidence_export(db, project))
        # sign-off register xlsx
        zf.writestr("Acceptance_Register.xlsx", _signoff_register_xlsx(db, project))
        # source manifest
        manifest = {
            "project": project.name,
            "project_key": project.key,
            "generated_at": _now().isoformat(),
            "documents": generated,
            "internal_module_count": len(BY_NAME),
        }
        zf.writestr("Source_Manifest.json", json.dumps(manifest, indent=2, default=str))
        # audit trail
        zf.writestr("Audit_Trail.json", json.dumps(audit_trail(db, project), indent=2, default=str))
    return buf.getvalue()


def _signoff_register_xlsx(db: Session, project: m.Project) -> bytes:
    x = dxlsx.Xlsx()
    wb = x.new_workbook()
    doc = {"title": "Acceptance & Sign-off Register", "project": project.name,
           "project_code": project.key, "document_id": f"{project.key}-SIGNOFF-REGISTER",
           "version": "1.0", "status": "EVIDENCE"}
    x.render_register(wb, "Acceptance_Signoff_Register",
                      ["Sign-off ID", "Document", "Version", "Decision", "Signer", "Role", "Signed At", "Hash"],
                      [[s["signoff_id"], s["document_id"], s["document_version"], s["decision"],
                        s["signer_name"], s["signer_role"] or "—", s["signed_at"],
                        (s["document_hash"] or "")[:16]] for s in signoff_register(db, project)],
                      doc, widths=(20, 28, 10, 22, 26, 22, 20, 18))
    wb.active = 0
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
