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
from sqlalchemy.orm import Session

from .. import models as m
from .models import DeliverableSignoff, HumanDeliverableInstance

RELATIONSHIP_VERSION = "impact_relationships/v1"
CHANGE_VERSION = "project_change/v1"
IMPACT_VERSION = "impact_candidates/v1"
RULE_VERSION = "1.0"


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
    unknown = [{"domain": domain, "relationship_class": "UNKNOWN", "impact_type": "UNKNOWN",
                "rationale": f"No stable, authorized {domain} relationship is recorded in this document snapshot."}
               for domain in ("PM", "QA", "INFRA")]
    latency = round((time.monotonic() - started) * 1000, 2)
    attention = [{"id": f"impact-{item['impact_id'].lower()}", "domain": "DOCUMENT",
                  "priority": "ISSUE", "code": item["impact_type"],
                  "title": item["rationale"],
                  "provenance": {"impact_id": item["impact_id"], "rule": item["rule"]}}
                 for item in impacts if item["impact_type"] in {"POTENTIALLY_STALE", "EVIDENCE_REVIEW_RECOMMENDED"}]
    return {"contract_version": IMPACT_VERSION, "relationship_contract": RELATIONSHIP_VERSION,
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
