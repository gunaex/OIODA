"""R17.3 typed, read-only cross-service impact projection.

The resolver deliberately stays one hop.  It consumes stable identifiers and
recorded owner evidence; missing linkage is an UNKNOWN result, never a fuzzy
match.  Nothing in this module persists relationships or impact candidates.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from ..services import DomainError, record_audit
from .models import DeliverableSignoff, HumanDeliverableInstance, ImpactConfirmation

RELATIONSHIP_VERSION = "impact_relationships/v1"
CHANGE_VERSION = "project_change/v1"
IMPACT_VERSION = "impact_candidates/v1"
RULE_VERSION = "1.0"
CONFIRMATION_VERSION = "impact_confirmation/v1"
ACTIONS_VERSION = "impact_actions/v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def relationship(*, project_id: str, source_type: str, source_id: str,
                 target_type: str, target_id: str, relationship_type: str,
                 relationship_class: str, source_authority: str,
                 provenance: dict, observed_at: str | None = None,
                 status: str = "ACTIVE", advisory: dict | None = None) -> dict:
    if relationship_class not in {"EXPLICIT", "DETERMINISTIC", "AI_SUGGESTED", "UNKNOWN"}:
        raise ValueError("Unsupported relationship class")
    if relationship_class in {"EXPLICIT", "DETERMINISTIC"} and (not source_id or not target_id or not provenance):
        raise ValueError("Authoritative relationships require stable IDs and provenance")
    if relationship_class == "AI_SUGGESTED" and not advisory:
        raise ValueError("AI suggestions require advisory metadata")
    core = {"project_id": project_id, "source_type": source_type, "source_id": source_id,
            "target_type": target_type, "target_id": target_id,
            "relationship_type": relationship_type, "relationship_class": relationship_class,
            "source_authority": source_authority, "provenance": provenance,
            "created_or_observed_at": observed_at or _now(), "status": status}
    core["relationship_id"] = f"REL-{_hash(core)[:16]}"
    if advisory:
        core["advisory"] = advisory
    return core


def change_event(*, change_id: str, project_id: str, entity_type: str, entity_id: str,
                 change_type: str, source_service: str, timestamp: str,
                 provenance: dict, before: Any = "NOT_RECORDED", after: Any = "NOT_RECORDED",
                 source_revision: str | int | None = None, actor: str | None = None) -> dict:
    return {"contract_version": CHANGE_VERSION, "change_id": change_id, "project_id": project_id,
            "entity_type": entity_type, "entity_id": entity_id, "change_type": change_type,
            "before": before, "after": after, "source_service": source_service,
            "source_revision": source_revision, "timestamp": timestamp, "actor": actor,
            "provenance": provenance}


def _candidate(change: dict, target: dict, rel: dict | None, impact_type: str,
               rationale: str, evidence_ids: list[str], rule_id: str,
               status: str = "REVIEW_RECOMMENDED") -> dict:
    core = {"source_change": change, "target_entity": target, "relationship": rel,
            "relationship_class": rel["relationship_class"] if rel else "UNKNOWN",
            "impact_type": impact_type, "rationale": rationale,
            "evidence_ids": list(dict.fromkeys(evidence_ids)), "status": status,
            "rule": {"rule_id": rule_id, "rule_version": RULE_VERSION}}
    core["impact_id"] = f"IMP-{_hash(core)[:16]}"
    return core


def project_impacts(change: dict, relationships: list[dict], *,
                    visible: Callable[[dict], bool] | None = None,
                    coverage: list[str] | None = None) -> dict:
    """Project a bounded one-hop graph, deduplicating stable targets.

    `visible` is an authorization seam: rejected targets and their labels are
    omitted completely. API callers must resolve relationships only from data
    already authorized for the current request.
    """
    started = time.monotonic()
    visible = visible or (lambda _rel: True)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for rel in relationships:
        if rel.get("source_id") != change["entity_id"] or not visible(rel):
            continue
        grouped.setdefault((rel["target_type"], rel["target_id"]), []).append(rel)
    candidates = []
    for (target_type, target_id), reasons in grouped.items():
        rel = reasons[0]
        candidates.append(_candidate(
            change, {"entity_type": target_type, "entity_id": target_id}, rel,
            "ATTENTION_REQUIRED", "A recorded one-hop relationship links this target to the changed entity.",
            [r["relationship_id"] for r in reasons], "R17.3-KNOWN-LINK",
        ) | {"relationship_reasons": reasons})
    unknown = []
    for domain in coverage or []:
        if not any(r["target_type"].startswith(domain) for rs in grouped.values() for r in rs):
            unknown.append({"domain": domain, "relationship_class": "UNKNOWN", "impact_type": "UNKNOWN",
                            "rationale": f"No stable, visible {domain} relationship evidence is recorded."})
    return {"contract_version": IMPACT_VERSION, "source_change": change,
            "known_impacts": candidates, "ai_suggested_impacts": [], "unknown": unknown,
            "traversal": {"depth": 1, "cycle_protection": True, "deduplication": "TARGET_STABLE_ID"},
            "metrics": {"relationship_resolution_ms": round((time.monotonic() - started) * 1000, 2),
                        "downstream_calls": 0}}


def validate_ai_suggestions(items: list[dict], evidence_ids: set[str], *,
                            provider: str, model: str, prompt_version: str) -> tuple[list[dict], list[dict]]:
    """Fail closed and force every model-created relationship to stay advisory."""
    accepted, rejected = [], []
    forbidden = ("will delay", "will fail", "must rerun", "acceptance is invalid", "definitely")
    for item in items[:20]:
        ids = list(dict.fromkeys(item.get("evidence_ids") or []))
        reason = str(item.get("reason") or "")[:600]
        if not item.get("source_id") or not item.get("target_id") or not ids:
            rejected.append({"reason": "MISSING_STABLE_ID_OR_CITATION"}); continue
        if any(i not in evidence_ids for i in ids):
            rejected.append({"reason": "UNKNOWN_CITATION"}); continue
        if any(phrase in reason.lower() for phrase in forbidden):
            rejected.append({"reason": "UNSUPPORTED_IMPACT", "statement": reason}); continue
        advisory = {"reason": reason, "evidence_ids": ids,
                    "confidence": item.get("confidence"), "generated_at": _now(),
                    "provider": provider, "model": model, "prompt_version": prompt_version,
                    "confirmation_status": "UNCONFIRMED"}
        accepted.append(relationship(
            project_id=item["project_id"], source_type=item["source_type"], source_id=item["source_id"],
            target_type=item["target_type"], target_id=item["target_id"],
            relationship_type=item.get("relationship_type") or "AFFECTS",
            relationship_class="AI_SUGGESTED", source_authority="AI_ADVISORY",
            provenance={"evidence_ids": ids}, advisory=advisory,
        ))
    return accepted, rejected


def action_recommendations(project_id: str, projection: dict) -> dict:
    """Conservative navigation/review suggestions; never executable writes."""
    rows: list[dict] = []
    def add(candidate_id: str | None, action_type: str, label: str, mode: str,
            reason: str, *, service="DOCUMENT_AGAIN", target_id=None, route=None,
            priority="RECOMMENDED", evidence=None):
        core = {"impact_candidate_id": candidate_id, "action_type": action_type,
                "target_service": service, "target_entity_id": target_id,
                "execution_mode": mode, "route": route}
        rows.append({"action_id": f"ACT-{_hash(core)[:16]}", **core, "label": label,
                     "action_class": priority, "reason": reason,
                     "evidence_ids": evidence or [], "executable": mode in {"LOCAL_VIEW", "DEEP_LINK"}})
    for item in projection.get("known_impacts") or []:
        kind, iid = item.get("impact_type"), item.get("impact_id")
        target = item.get("target_entity") or {}
        evidence = item.get("evidence_ids") or []
        if kind == "POTENTIALLY_STALE":
            add(iid, "REVIEW_DOCUMENT", "Review Document", "LOCAL_VIEW",
                "Inspect the stale-source evidence before deciding whether content should change.",
                target_id=target.get("entity_id"), priority="REQUIRED_ATTENTION", evidence=evidence)
            add(iid, "CONSIDER_DOCUMENT_REVISION", "Consider New Revision", "HUMAN_CONFIRMATION",
                "A revision may be appropriate, but generation remains a separate human action.",
                target_id=target.get("entity_id"), evidence=evidence)
        elif kind == "EVIDENCE_REVIEW_RECOMMENDED":
            add(iid, "REVIEW_ACCEPTANCE_VERSION", "Review Acceptance Applicability", "LOCAL_VIEW",
                "Compare the accepted and current versions without invalidating historical acceptance.",
                target_id=target.get("entity_id"), priority="REQUIRED_ATTENTION", evidence=evidence)
        target_type = str(target.get("entity_type") or "")
        for prefix, action_type, label, service, route in (
            ("QA", "OPEN_QA", "Review QA Context", "QA_AGAIN", f"/projects/{project_id}/qa"),
            ("PM", "OPEN_PM", "Review PM Context", "PM_AGAIN", f"/projects/{project_id}/planning"),
            ("INFRA", "OPEN_INFRA", "Review Infra Context", "INFRA_AGAIN", f"/projects/{project_id}/architecture"),
        ):
            if target_type.startswith(prefix):
                add(iid, action_type, label, "LOCAL_VIEW", "Open the existing OIDA owner-context view; no owner record will change.",
                    service=service, target_id=target.get("entity_id"), route=route, evidence=evidence)
    if projection.get("unknown"):
        add(None, "REVIEW_EVIDENCE", "Review Source Evidence", "LOCAL_VIEW",
            "Impact cannot be determined from current stable relationship evidence.", priority="UNVERIFIED")
    return {"contract_version": ACTIONS_VERSION, "actions": rows,
            "authority_note": "Recommendations require a human choice and perform no owner-domain mutation.",
            "cross_service_domain_writes": 0}


def _relationship_identity(snapshot: dict) -> str:
    core = {key: snapshot.get(key) for key in (
        "project_id", "source_type", "source_id", "target_type", "target_id",
        "relationship_type", "relationship_class", "source_authority", "provenance",
        "created_or_observed_at", "status")}
    return f"REL-{_hash(core)[:16]}"


def review_relationship(db: Session, project, *, relationship_snapshot: dict,
                        evidence_hash: str, current_evidence_hash: str,
                        impact_candidate_id: str | None, decision: str, reason: str | None,
                        actor, actor_role: str | None = None, actor_org: str | None = None,
                        evidence_refs: list[str] | None = None, change_id: str | None = None,
                        allowed_evidence: dict[str, dict] | None = None) -> dict:
    started = time.monotonic()
    decision = decision.upper()
    if decision not in {"CONFIRMED", "REJECTED", "UNRESOLVED"}:
        raise DomainError("Decision must be CONFIRMED, REJECTED, or UNRESOLVED", status_code=422)
    if decision == "REJECTED" and not (reason or "").strip():
        raise DomainError("A reason is required to reject a relationship", status_code=422)
    if evidence_hash != current_evidence_hash:
        raise DomainError("Impact evidence changed; refresh before reviewing this relationship", status_code=409)
    if relationship_snapshot.get("project_id") != project.id:
        raise DomainError("Relationship does not belong to this project", status_code=403)
    origin = relationship_snapshot.get("relationship_class")
    if origin not in {"AI_SUGGESTED", "UNKNOWN"}:
        raise DomainError("Known owner/structural relationships do not require confirmation", status_code=422)
    relationship_id = relationship_snapshot.get("relationship_id")
    if not relationship_id or relationship_id != _relationship_identity(relationship_snapshot):
        raise DomainError("Relationship identity or provenance is invalid", status_code=422)
    refs = list(dict.fromkeys(evidence_refs or []))[:40]
    allowed_evidence = allowed_evidence or {}
    if origin == "AI_SUGGESTED":
        if not refs or any(ref not in allowed_evidence for ref in refs):
            raise DomainError("AI suggestions require known evidence citations", status_code=422)
        corpus = json.dumps([allowed_evidence[ref] for ref in refs], default=str)
        if str(relationship_snapshot.get("target_id")) not in corpus:
            raise DomainError("Suggested target is not grounded in cited evidence", status_code=422)
    elif not str(relationship_snapshot.get("target_id") or "").startswith("UNRESOLVED:"):
        raise DomainError("Unknown relationships may only review an unresolved domain placeholder", status_code=422)
    idem = _hash({"project": project.id, "relationship": relationship_id, "candidate": impact_candidate_id,
                  "evidence": evidence_hash, "decision": decision, "reason": (reason or "").strip(),
                  "actor": actor.id})
    existing = db.execute(select(ImpactConfirmation).where(ImpactConfirmation.idempotency_key == idem)).scalar_one_or_none()
    if existing:
        return {**existing.to_dict(current_evidence_hash=current_evidence_hash), "idempotent_replay": True,
                "mutation_latency_ms": round((time.monotonic() - started) * 1000, 2)}
    previous = db.execute(select(ImpactConfirmation).where(
        ImpactConfirmation.project_id == project.id,
        ImpactConfirmation.relationship_id == relationship_id,
        ImpactConfirmation.evidence_hash == evidence_hash,
    ).order_by(ImpactConfirmation.reviewed_at.desc(), ImpactConfirmation.id.desc())).scalars().first()
    row = ImpactConfirmation(
        project_id=project.id, relationship_id=relationship_id, impact_candidate_id=impact_candidate_id,
        relationship_class_at_review=origin, relationship_snapshot=relationship_snapshot,
        decision=decision, reason=(reason or "").strip() or None, actor_user_id=actor.id,
        actor_name=actor.name, actor_role=actor_role, actor_org=actor_org,
        evidence_hash=evidence_hash, change_id=change_id, evidence_refs=refs, idempotency_key=idem,
    )
    try:
        db.add(row); db.flush()
        action = ("IMPACT_RELATIONSHIP_REOPENED" if decision == "UNRESOLVED" and previous and previous.decision != "UNRESOLVED"
                  else f"IMPACT_RELATIONSHIP_{decision}")
        record_audit(db, action=action, project_id=project.id, actor_id=actor.id,
                     object_type="IMPACT_RELATIONSHIP", object_id=relationship_id,
                     revision_context=evidence_hash,
                     metadata={"confirmation_id": row.id, "origin_class": origin,
                               "decision": decision, "previous_decision": previous.decision if previous else None,
                               "evidence_refs": refs, "customer_acceptance": False,
                               "cross_service_domain_write": False})
    except IntegrityError:
        db.rollback()
        row = db.execute(select(ImpactConfirmation).where(ImpactConfirmation.idempotency_key == idem)).scalar_one()
        return {**row.to_dict(current_evidence_hash=current_evidence_hash), "idempotent_replay": True,
                "mutation_latency_ms": round((time.monotonic() - started) * 1000, 2)}
    return {**row.to_dict(current_evidence_hash=current_evidence_hash), "idempotent_replay": False,
            "mutation_latency_ms": round((time.monotonic() - started) * 1000, 2)}


def confirmation_history(db: Session, project_id: str, *, current_evidence_hash: str,
                         relationship_id: str | None = None) -> dict:
    q = select(ImpactConfirmation).where(ImpactConfirmation.project_id == project_id)
    if relationship_id:
        q = q.where(ImpactConfirmation.relationship_id == relationship_id)
    rows = db.execute(q.order_by(ImpactConfirmation.reviewed_at.desc(), ImpactConfirmation.id.desc())).scalars().all()
    history = [row.to_dict(current_evidence_hash=current_evidence_hash) for row in rows]
    effective = {}
    for row in history:
        effective.setdefault(row["relationship_id"], row)
    return {"contract_version": CONFIRMATION_VERSION, "history": history,
            "effective": list(effective.values()), "current_evidence_hash": current_evidence_hash}


def suppress_reviewed_suggestions(suggestions: list[dict], history: dict) -> list[dict]:
    rejected = {(row["relationship_id"], row["evidence_hash"]) for row in history.get("effective", [])
                if row["decision"] == "REJECTED" and not row["stale"]}
    return [item for item in suggestions
            if (item.get("relationship_id"), history.get("current_evidence_hash")) not in rejected]


def document_impact(db: Session, project, current: HumanDeliverableInstance,
                    previous: HumanDeliverableInstance | None,
                    signoffs: list[DeliverableSignoff]) -> dict:
    """Smallest useful R17.3 slice over controlled-document truth."""
    started = time.monotonic()
    observed = (current.generated_at or current.created_at).isoformat()
    doc_change = change_event(
        change_id=f"DOC-{current.id}", project_id=project.id, entity_type="DOCUMENT_VERSION",
        entity_id=current.id, change_type="VERSION_CHANGED" if previous else "CREATED",
        before=previous.version if previous else "NOT_RECORDED", after=current.version,
        source_service="DOCUMENT_AGAIN", source_revision=current.version, timestamp=observed,
        actor=current.generated_by, provenance={"instance_id": current.id, "snapshot_hash": current.snapshot_hash},
    )
    rels = [relationship(
        project_id=project.id, source_type="DOCUMENT_VERSION", source_id=current.id,
        target_type="DOCUMENT", target_id=current.document_id or current.human_code,
        relationship_type="BELONGS_TO", relationship_class="DETERMINISTIC",
        source_authority="DOCUMENT_AGAIN", observed_at=observed,
        provenance={"instance_id": current.id, "document_id": current.document_id,
                    "rule_id": "R17.3-DOCUMENT-OWNERSHIP", "rule_version": RULE_VERSION},
    )]
    impacts = []
    snapshot = current.source_snapshot or {}
    requirements = snapshot.get("requirements") if isinstance(snapshot.get("requirements"), list) else []
    for ref in requirements:
        stable = ref.get("id") or ref.get("code") if isinstance(ref, dict) else None
        if not stable:
            continue
        rel = relationship(
            project_id=project.id, source_type="REQUIREMENT", source_id=str(stable),
            target_type="DOCUMENT_VERSION", target_id=current.id, relationship_type="DERIVED_FROM",
            relationship_class="EXPLICIT", source_authority="DOCUMENT_SOURCE_SNAPSHOT", observed_at=observed,
            provenance={"instance_id": current.id, "snapshot_hash": current.snapshot_hash,
                        "source_path": f"requirements[{stable}]"},
        )
        rels.append(rel)
        req = db.get(m.Requirement, stable)
        if not req:
            req = db.execute(select(m.Requirement).where(m.Requirement.project_id == project.id,
                                                        m.Requirement.code == str(stable))).scalar_one_or_none()
        recorded_revision = ref.get("revision_number", ref.get("revision"))
        if req and recorded_revision is not None:
            latest = db.execute(select(m.RequirementRevision).where(
                m.RequirementRevision.requirement_id == req.id,
                m.RequirementRevision.status == m.RequirementStatus.CONFIRMED,
            ).order_by(m.RequirementRevision.revision_number.desc())).scalars().first()
            if latest and str(latest.revision_number) != str(recorded_revision):
                req_change = change_event(
                    change_id=f"REQREV-{latest.id}", project_id=project.id, entity_type="REQUIREMENT",
                    entity_id=str(stable), change_type="VERSION_CHANGED", before=recorded_revision,
                    after=latest.revision_number, source_service="DOCUMENT_AGAIN",
                    source_revision=latest.revision_number, timestamp=latest.confirmed_at.isoformat() if latest.confirmed_at else observed,
                    provenance={"requirement_id": req.id, "revision_id": latest.id},
                )
                impacts.append(_candidate(
                    req_change, {"entity_type": "DOCUMENT_VERSION", "entity_id": current.id,
                                 "label": current.name, "version": current.version}, rel,
                    "POTENTIALLY_STALE", "The document snapshot records an older requirement revision than current confirmed truth.",
                    [rel["relationship_id"], latest.id], "R17.3-SOURCE-REVISION-STALE", "POTENTIALLY_STALE"))
        # Exact semantic trace links are authoritative owner records.  Keep
        # their original semantics and stable IDs; never derive links from the
        # display label. Direction follows the stored trace edge.
        trace_sources = {str(stable)}
        if req:
            trace_sources.add(req.code)
        links = db.execute(select(m.TraceLink).where(
            m.TraceLink.project_id == project.id,
            m.TraceLink.source_semantic_id.in_(trace_sources),
        )).scalars().all()
        target_ids = {link.target_semantic_id for link in links}
        nodes = {node.semantic_id: node for node in db.execute(select(m.SemanticObject).where(
            m.SemanticObject.project_id == project.id,
            m.SemanticObject.semantic_id.in_(target_ids),
        )).scalars().all()} if target_ids else {}
        for link in links:
            node = nodes.get(link.target_semantic_id)
            rels.append(relationship(
                project_id=project.id, source_type="REQUIREMENT", source_id=str(stable),
                target_type=node.object_type.value if node else "UNKNOWN_ENTITY",
                target_id=link.target_semantic_id, relationship_type=link.relation_type.value,
                relationship_class="EXPLICIT", source_authority="DOCUMENT_AGAIN_TRACE_REGISTER",
                observed_at=link.created_at.isoformat(),
                provenance={"trace_link_id": link.id, "revision_context": link.revision_context,
                            "entity_ref": node.entity_ref if node else None},
            ))
    qualifying = [s for s in signoffs if s.evidence_class in {"CUSTOMER", "FORMAL_EXTERNAL"}
                  and s.purpose in {"ACCEPTANCE", "SIGN_OFF"}
                  and s.decision in {"ACCEPT", "ACCEPTED_WITH_EXCEPTIONS", "APPROVE"}]
    old = next((s for s in qualifying if s.document_version != current.version), None)
    if old:
        rel = relationship(
            project_id=project.id, source_type="ACCEPTANCE_EVIDENCE", source_id=old.id,
            target_type="DOCUMENT_VERSION", target_id=old.instance_id or f"{old.document_id}@{old.document_version}",
            relationship_type="ACCEPTS", relationship_class="EXPLICIT", source_authority="DOCUMENT_AGAIN_SIGNOFF",
            provenance={"signoff_id": old.id, "document_version": old.document_version,
                        "snapshot_hash": old.snapshot_hash, "evidence_class": old.evidence_class,
                        "purpose": old.purpose}, observed_at=old.signed_at.isoformat(),
        )
        rels.append(rel)
        impacts.append(_candidate(
            doc_change, {"entity_type": "DOCUMENT_VERSION", "entity_id": current.id,
                         "label": current.name, "current_version": current.version,
                         "accepted_version": old.document_version}, rel,
            "EVIDENCE_REVIEW_RECOMMENDED",
            f"Customer acceptance is recorded for version {old.document_version}; current version is {current.version}. Previous acceptance is preserved and does not automatically apply.",
            [rel["relationship_id"], old.id], "R17.3-ACCEPTED-VERSION-AWARENESS"))
    unknown = []
    for domain in ("PM", "QA", "INFRA"):
        unresolved = relationship(
            project_id=project.id, source_type="DOCUMENT_VERSION", source_id=current.id,
            target_type=f"{domain}_CONTEXT", target_id=f"UNRESOLVED:{domain}",
            relationship_type="AFFECTS", relationship_class="UNKNOWN",
            source_authority="NO_RELIABLE_RELATIONSHIP_RECORDED", observed_at=observed,
            provenance={"instance_id": current.id, "snapshot_hash": current.snapshot_hash,
                        "coverage_domain": domain}, status="UNRESOLVED")
        unknown.append({"domain": domain, "relationship_class": "UNKNOWN", "impact_type": "UNKNOWN",
                        "rationale": f"No stable, authorized {domain} relationship is recorded in this document snapshot.",
                        "relationship": unresolved})
    latency = round((time.monotonic() - started) * 1000, 2)
    attention = [{"id": f"impact-{item['impact_id'].lower()}", "domain": "DOCUMENT",
                  "priority": "ISSUE", "code": item["impact_type"],
                  "title": item["rationale"],
                  "provenance": {"impact_id": item["impact_id"], "rule": item["rule"]}}
                 for item in impacts if item["impact_type"] in {"POTENTIALLY_STALE", "EVIDENCE_REVIEW_RECOMMENDED"}]
    result = {"contract_version": IMPACT_VERSION, "relationship_contract": RELATIONSHIP_VERSION,
            "source_change": doc_change, "relationships": rels, "known_impacts": impacts,
            "ai_suggested_impacts": [], "unknown": unknown,
            "authority_order": ["EXPLICIT", "DETERMINISTIC", "AI_SUGGESTED", "UNKNOWN"],
            "traversal": {"depth": 1, "cycle_protection": True, "deduplication": "TARGET_STABLE_ID"},
            "project_attention_contribution": {"contract_version": "project_attention/v1",
                                               "items": attention, "actionable_only": True},
            "provider_status": "NOT_REQUESTED", "write_actions": 0,
            "metrics": {"relationship_resolution_ms": latency,
                        "impact_projection_ms": latency, "downstream_calls": 0},
            "provenance": {"derived": True, "read_only": True, "authoritative": False,
                           "generated_at": observed}}
    result["suggested_actions"] = action_recommendations(project.id, result)
    return result
