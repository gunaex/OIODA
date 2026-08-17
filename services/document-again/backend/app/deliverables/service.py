"""R17 — Deliverable framework service: profile, matrix, gaps, instances,
lifecycle and completeness."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..services import DomainError
from . import rules
from .models import DeliverableInstance
from .standards import STANDARDS, get_standard
from .taxonomy import (
    HUMAN_ONLY_STATES,
    LIFECYCLE_STATES,
    LIFECYCLE_TRANSITIONS,
    PROJECT_ATTRIBUTES,
    PROJECT_TYPES,
    WORKSTREAMS,
)

DOMAIN_ABBREV = {
    "CORE": "CTL", "APPLICATION": "APP", "INFRASTRUCTURE": "INF", "CLOUD": "CLD",
    "NETWORK": "NET", "MIGRATION": "MIG", "SECURITY": "SEC", "DATA": "DAT",
    "AI_RAG": "AIR", "INTEGRATION": "INT", "TEST": "TST", "OPERATIONS": "OPS",
    "COMMERCIAL": "COM",
}

PROFILE_KEY = "deliverable_profile"

DEFAULT_PROFILE = {
    "primary_type": None,
    "workstreams": [],
    "attributes": {a: False for a in PROJECT_ATTRIBUTES},
    "ai_recommendation": None,
    "confirmed_at": None,
    "confirmed_by": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Project profile ─────────────────────────────────────────────────────────
def get_profile(db: Session, project: m.Project) -> dict:
    stored = (project.project_meta or {}).get(PROFILE_KEY) or {}
    profile = dict(DEFAULT_PROFILE)
    profile.update(stored)
    profile["attributes"] = {**DEFAULT_PROFILE["attributes"], **(stored.get("attributes") or {})}
    return profile


def set_profile(db: Session, project: m.Project, profile: dict, *, actor: str = "local-user",
                confirmed: bool = False) -> dict:
    meta = dict(project.project_meta or {})
    current = get_profile(db, project)

    primary_type = (profile.get("primary_type") or None)
    if primary_type is not None and primary_type.upper() not in PROJECT_TYPES:
        raise DomainError(f"Unknown primary project type: {primary_type}", status_code=422)

    workstreams = list(dict.fromkeys([w.upper() for w in (profile.get("workstreams") or [])]))
    for w in workstreams:
        if w not in WORKSTREAMS:
            raise DomainError(f"Unknown workstream: {w}", status_code=422)

    attributes = current["attributes"]
    for k, v in (profile.get("attributes") or {}).items():
        if k not in PROJECT_ATTRIBUTES:
            raise DomainError(f"Unknown project attribute: {k}", status_code=422)
        attributes[k] = bool(v)

    next_profile = {
        "primary_type": primary_type.upper() if primary_type else current.get("primary_type"),
        "workstreams": workstreams,
        "attributes": attributes,
        "ai_recommendation": profile.get("ai_recommendation") or current.get("ai_recommendation"),
        "confirmed_at": _now_iso() if confirmed else current.get("confirmed_at"),
        "confirmed_by": actor if confirmed else current.get("confirmed_by"),
        # R17.1 — delivery phase + role→person assignments for the "My Documents" UX
        "current_phase": profile.get("current_phase") or current.get("current_phase"),
        "role_assignments": profile.get("role_assignments") or current.get("role_assignments") or {},
    }
    meta[PROFILE_KEY] = next_profile
    project.project_meta = meta
    db.commit()
    return next_profile


# ── Matrix ──────────────────────────────────────────────────────────────────
def _instance_map(db: Session, project_id: str) -> dict[str, DeliverableInstance]:
    rows = db.execute(
        select(DeliverableInstance).where(DeliverableInstance.project_id == project_id)
    ).scalars().all()
    return {r.standard_code: r for r in rows}


def generate_matrix(db: Session, project: m.Project, *, actor: str = "local-user",
                    persist: bool = True) -> dict:
    """Evaluate applicability for every standard and merge instance state.
    When persist=True, creates a MISSING instance for every applicable standard
    that has no instance yet (idempotent)."""
    profile = get_profile(db, project)
    evaluated = rules.evaluate_profile(profile)
    instances = _instance_map(db, project.id)

    matrix = []
    for row in evaluated:
        inst = instances.get(row["code"])
        matrix.append(_compose_row(project, row, inst, profile))
    matrix.sort(key=lambda r: (r["domain"] != "CORE", r["domain"], r["code"]))

    if persist:
        for row in evaluated:
            if row["code"] in instances:
                continue
            if row["applicability"] == "NOT_APPLICABLE":
                continue
            db.add(DeliverableInstance(
                project_id=project.id,
                standard_code=row["code"],
                standard_version=row["template_version"],
                document_id=make_document_id(project.key, row["code"]),
                applicability=row["applicability"],
                applicability_reason=row["reason"],
                lifecycle_status="MISSING",
                source_authorities=row["source_authorities"],
            ))
        db.commit()

    return {
        "project_id": project.id,
        "profile": profile,
        "summary": completeness(matrix),
        "rows": matrix,
    }


def _compose_row(project: m.Project, row: dict, inst: DeliverableInstance | None, profile: dict) -> dict:
    applicability = row["applicability"]
    reason = list(row["reason"])
    if inst:
        applicability = inst.applicability
        if inst.applicability_reason:
            reason = list(inst.applicability_reason)
    return {
        "code": row["code"],
        "name": row["name"],
        "domain": row["domain"],
        "category": row["category"],
        "applicability": applicability,
        "reason": reason,
        "lifecycle_status": inst.lifecycle_status if inst else ("N/A" if applicability == "NOT_APPLICABLE" else "MISSING"),
        "owner": inst.owner if inst else None,
        "reviewers": inst.reviewers if inst else [],
        "approvers": inst.approvers if inst else [],
        "version": inst.version if inst else None,
        "baseline_id": inst.baseline_id if inst else None,
        "document_id": inst.document_id if inst else make_document_id(project.key, row["code"]),
        "stale": inst.stale if inst else False,
        "source_authorities": inst.source_authorities if inst else row["source_authorities"],
        "layout_template": row["layout_template"],
        "template_version": row["template_version"],
        "instance_id": inst.id if inst else None,
    }


def get_matrix(db: Session, project: m.Project) -> dict:
    return generate_matrix(db, project, persist=False)


def completeness(matrix_rows: list[dict]) -> dict:
    required = [r for r in matrix_rows if r["applicability"] in ("MANDATORY",)]
    approved = [r for r in required if r["lifecycle_status"] in ("APPROVED", "BASELINED")]
    draft = [r for r in required if r["lifecycle_status"] in ("DRAFT", "INTERNAL_REVIEW", "CUSTOMER_REVIEW")]
    missing = [r for r in required if r["lifecycle_status"] == "MISSING"]
    na = [r for r in matrix_rows if r["applicability"] == "NOT_APPLICABLE"]
    return {
        "required": len(required),
        "approved_baselined": len(approved),
        "draft_review": len(draft),
        "missing": len(missing),
        "not_applicable": len(na),
        "by_applicability": {a: len([r for r in matrix_rows if r["applicability"] == a])
                             for a in ("MANDATORY", "RECOMMENDED", "CONDITIONAL", "OPTIONAL", "NOT_APPLICABLE")},
    }


# ── Gap detection (deterministic, no AI required) ───────────────────────────
def detect_gaps(db: Session, project: m.Project) -> dict:
    matrix = get_matrix(db, project)["rows"]
    gaps = {
        "mandatory_missing": [],
        "mandatory_no_owner": [],
        "mandatory_no_content": [],
        "awaiting_review": [],
        "missing_signoff": [],
        "stale_authority_data": [],
        "missing_source_authority": [],
    }
    for r in matrix:
        if r["applicability"] != "MANDATORY":
            continue
        if r["lifecycle_status"] == "MISSING":
            gaps["mandatory_missing"].append({"code": r["code"], "name": r["name"]})
        if r["lifecycle_status"] in ("DRAFT", "INTERNAL_REVIEW", "CUSTOMER_REVIEW", "APPROVED", "BASELINED") and not r["owner"]:
            gaps["mandatory_no_owner"].append({"code": r["code"], "name": r["name"]})
        if r["lifecycle_status"] in ("INTERNAL_REVIEW", "CUSTOMER_REVIEW"):
            gaps["awaiting_review"].append({"code": r["code"], "name": r["name"]})
        if r["lifecycle_status"] == "APPROVED" and not r["approvers"]:
            gaps["missing_signoff"].append({"code": r["code"], "name": r["name"]})
        if r["stale"]:
            gaps["stale_authority_data"].append({"code": r["code"], "name": r["name"]})
        if r["applicability"] != "NOT_APPLICABLE" and not r["source_authorities"]:
            gaps["missing_source_authority"].append({"code": r["code"], "name": r["name"]})
    return {"project_id": project.id, "gaps": gaps, "summary": {k: len(v) for k, v in gaps.items()}}


# ── Instances ───────────────────────────────────────────────────────────────
def make_document_id(project_key: str, standard_code: str) -> str:
    std = get_standard(standard_code)
    domain = std["domain"] if std else standard_code.split("-")[1]
    abbrev = DOMAIN_ABBREV.get(domain, domain[:3])
    seq = standard_code.rsplit("-", 1)[-1] if std else "000"
    return f"{project_key}-{abbrev}-{seq}"


def get_instance(db: Session, project_id: str, standard_code: str) -> DeliverableInstance | None:
    return db.execute(
        select(DeliverableInstance).where(
            DeliverableInstance.project_id == project_id,
            DeliverableInstance.standard_code == standard_code,
        )
    ).scalars().first()


def _require_instance(db: Session, project_id: str, standard_code: str) -> DeliverableInstance:
    inst = get_instance(db, project_id, standard_code)
    if not inst:
        raise DomainError(f"No deliverable instance for standard {standard_code}", status_code=404)
    return inst


def transition_instance(db: Session, project_id: str, standard_code: str, target: str,
                        *, actor: str = "local-user", human: bool = False,
                        version: str | None = None, owner: str | None = None) -> dict:
    if target not in LIFECYCLE_STATES:
        raise DomainError(f"Unknown lifecycle state: {target}", status_code=422)
    inst = _require_instance(db, project_id, standard_code)
    if target not in LIFECYCLE_TRANSITIONS.get(inst.lifecycle_status, []):
        raise DomainError(
            f"Invalid transition {inst.lifecycle_status} -> {target}", status_code=409,
        )
    if target in HUMAN_ONLY_STATES and not human:
        raise DomainError(f"Transition to {target} requires a human action", status_code=403)
    if version is not None:
        inst.version = version
    if owner is not None:
        inst.owner = owner
    inst.lifecycle_status = target
    if target == "BASELINED":
        inst.version = inst.version or "1.0"
    db.commit()
    return inst.to_dict()


def override_applicability(db: Session, project_id: str, standard_code: str, applicability: str,
                           *, actor: str = "local-user") -> dict:
    from .taxonomy import APPLICABILITY_STATES as STATES
    if applicability not in STATES:
        raise DomainError(f"Unknown applicability state: {applicability}", status_code=422)
    inst = _require_instance(db, project_id, standard_code)
    inst.applicability = applicability
    inst.applicability_override = True
    inst.override_by = actor
    inst.override_at = datetime.now(timezone.utc)
    db.commit()
    return inst.to_dict()
