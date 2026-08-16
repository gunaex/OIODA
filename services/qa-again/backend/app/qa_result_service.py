"""QA-E3: canonical QAResult aggregation.

Builds the canonical AGAIN-ECOSYSTEM QAResult from QA Again's existing
runtime state (TestCycle results, Defects, SignOffs) — it does not
introduce new QA logic. `go_live_readiness()` (app/metrics.py) already
encodes QA Again's blocking-defect / P0-priority policy; this module reuses
it rather than re-deriving acceptance semantics (QA-E3 §21).

A canonical QAResult can only be produced for a cycle that has an
ExternalQARequest mapped to it — correlationId, workPackageId, and
qaRequestId all come from that mapping (from the canonical QARequest
payload QA Again already stored verbatim at intake). A purely local,
non-ecosystem cycle has no canonical identity to report under, so no
QAResult is fabricated for it; use the existing go-live-readiness report
instead (QA-E3 §22, §24 — this stays QA-scoped, distinct from Conductor's
DeliveryReadinessResult).
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from . import models
from .contracts.v1 import QAResult as CanonicalQAResult
from .metrics import go_live_readiness, result_counts

# QA Again's own defect severities (P0..P3, UNSPECIFIED) -> canonical
# severity enum. UNSPECIFIED has no defensible canonical mapping, so it is
# omitted rather than guessed (never fabricate — QA-E3 §22).
_SEVERITY_MAP = {"P0": "CRITICAL", "P1": "HIGH", "P2": "MEDIUM", "P3": "LOW"}

# Only QA_REVIEW is mandatory for APPROVED — BUSINESS_ACCEPTANCE and
# GO_LIVE remain separate acceptance axes per contracts/v1/README.md's
# "Business Acceptance != Technical Acceptance != QA Approval" rule, and
# feed acceptanceValidation / a REJECTED override instead (QA-E3 §25).
_MANDATORY_SIGNOFF_FOR_APPROVAL = "QA_REVIEW"


class QAResultNotAvailableError(Exception):
    """Raised when a cycle has no ExternalQARequest mapped to it — there is
    no canonical correlationId/workPackageId/qaRequestId to report under."""


def _test_summary(counts: dict[str, int]) -> dict[str, int]:
    total = sum(counts.values())
    passed = counts["PASS"]
    failed = counts["FAIL"] + counts["BLOCKED"]
    skipped = counts["NOT_RUN"] + counts["NOT_APPLICABLE"]
    return {"total": total, "passed": passed, "failed": failed, "skipped": skipped}


def _defects(db: Session, cycle_id: int) -> list[dict[str, Any]]:
    rows = db.query(models.Defect).filter(models.Defect.cycle_id == cycle_id).all()
    out = []
    for d in rows:
        entry: dict[str, Any] = {"id": d.defect_key, "title": d.title, "status": d.status}
        mapped_severity = _SEVERITY_MAP.get(d.severity)
        if mapped_severity:
            entry["severity"] = mapped_severity
        out.append(entry)
    return out


def _latest_signoff_decisions(db: Session, cycle_id: int) -> dict[str, str]:
    """Latest decision per signoff_type (SignOff rows are append-only —
    QA-E3 §25 — so "latest" is the one with the greatest acted_at)."""
    rows = (
        db.query(models.SignOff)
        .filter(models.SignOff.cycle_id == cycle_id)
        .order_by(models.SignOff.acted_at.asc())
        .all()
    )
    latest: dict[str, str] = {}
    for row in rows:
        latest[row.signoff_type] = row.decision
    return latest


def _execution_status(cycle: models.TestCycle, counts: dict[str, int]) -> str:
    if cycle.status == "CANCELLED":
        return "FAILED"
    if cycle.status in ("COMPLETED", "LOCKED") and counts["NOT_RUN"] == 0:
        return "COMPLETED"
    return "PARTIAL"


def _quality_gate(
    cycle: models.TestCycle, readiness: dict[str, Any], signoffs: dict[str, str]
) -> str:
    if any(decision == "REJECTED" for decision in signoffs.values()):
        return "REJECTED"
    if cycle.status not in ("COMPLETED", "LOCKED"):
        return "PENDING"
    if not readiness["ready"]:
        return "REJECTED"
    if signoffs.get(_MANDATORY_SIGNOFF_FOR_APPROVAL) == "APPROVED":
        return "APPROVED"
    return "PENDING"


def _acceptance_validation(signoffs: dict[str, str]) -> Optional[dict[str, Any]]:
    if "QA_REVIEW" not in signoffs and "BUSINESS_ACCEPTANCE" not in signoffs:
        return None
    validation: dict[str, Any] = {}
    if "QA_REVIEW" in signoffs:
        validation["technicalCriteriaMet"] = signoffs["QA_REVIEW"] == "APPROVED"
    if "BUSINESS_ACCEPTANCE" in signoffs:
        validation["businessCriteriaMet"] = signoffs["BUSINESS_ACCEPTANCE"] == "APPROVED"
    return validation


def _evidence(slug: str, cycle_id: int, summary: dict[str, int], has_defects: bool, has_signoffs: bool) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    evidence = [
        {
            "type": "QA_TEST_RESULTS",
            "source": "qa-again",
            "reference": f"qa://{slug}/cycles/{cycle_id}/results",
            "summary": f"{summary['passed']}/{summary['total']} passed, {summary['failed']} failed, {summary['skipped']} skipped",
            "timestamp": now,
        }
    ]
    if has_defects:
        evidence.append(
            {
                "type": "DEFECT_REGISTER",
                "source": "qa-again",
                "reference": f"qa://{slug}/cycles/{cycle_id}/defects",
                "timestamp": now,
            }
        )
    if has_signoffs:
        evidence.append(
            {
                "type": "ACCEPTANCE_CHECKLIST",
                "source": "qa-again",
                "reference": f"qa://{slug}/cycles/{cycle_id}/signoffs",
                "timestamp": now,
            }
        )
    return evidence


def build_qa_result(
    project_db: Session,
    master_db: Session,
    *,
    slug: str,
    cycle_id: int,
) -> CanonicalQAResult:
    """Builds and canonically validates a QAResult for `cycle_id`.

    Raises QAResultNotAvailableError if no ExternalQARequest is mapped to
    this cycle (nothing to report a canonical identity under).
    Raises app.contracts.validator.ContractValidationError if the
    aggregated payload somehow fails the vendored canonical schema — a
    signal of a real bug in this aggregator, not something to swallow.
    """
    cycle = project_db.query(models.TestCycle).filter(models.TestCycle.id == cycle_id).first()
    if cycle is None:
        raise QAResultNotAvailableError(f"cycle {cycle_id} not found")

    external_request = (
        master_db.query(models.ExternalQARequest)
        .filter(
            models.ExternalQARequest.qa_project_slug == slug,
            models.ExternalQARequest.test_cycle_id == cycle_id,
        )
        .first()
    )
    if external_request is None:
        raise QAResultNotAvailableError(
            f"cycle {cycle_id} in project {slug!r} has no ExternalQARequest mapped to it "
            "(this cycle was not created via an ecosystem QARequest)"
        )

    qa_request_payload = json.loads(external_request.payload_json)
    work_package_id = qa_request_payload.get("workPackageId")
    if not work_package_id:
        raise QAResultNotAvailableError(
            f"ExternalQARequest {external_request.idempotency_key} has no workPackageId in its stored payload"
        )

    counts = result_counts(project_db, cycle_id)
    summary = _test_summary(counts)
    defects = _defects(project_db, cycle_id)
    signoffs = _latest_signoff_decisions(project_db, cycle_id)
    readiness = go_live_readiness(project_db, cycle_id)

    payload = {
        "qaResultId": f"qr-{slug}-{cycle_id}",
        "correlationId": external_request.correlation_id,
        "workPackageId": work_package_id,
        "qaRequestId": external_request.qa_request_id,
        "status": _execution_status(cycle, counts),
        "testSummary": summary,
        "defects": defects,
        "qualityGate": _quality_gate(cycle, readiness, signoffs),
        "recommendedRegressionAreas": [],
        "evidence": _evidence(slug, cycle_id, summary, bool(defects), bool(signoffs)),
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    acceptance_validation = _acceptance_validation(signoffs)
    if acceptance_validation:
        payload["acceptanceValidation"] = acceptance_validation

    return CanonicalQAResult.validate_canonical(payload)
