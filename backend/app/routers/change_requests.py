"""Change Request log, impact analysis, sign-off hand-off and approval.

The anti-scope-creep rule lives here and is enforced server-side: a CR only
reaches Approved once the Impact Analysis document attached to it has been
signed off. The UI never gets to decide that.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import effort_budget, models, schemas
from ..auth import get_current_user, require_internal
from ..database import get_master_db, get_project_db
from ..reports import impact_analysis
from ..reports.style import workbook_response
from ..workflow_definitions import (
    CHANGE_REQUEST_APPROVAL_REQUIRES_DOCUMENT_STATUS,
    CHANGE_REQUEST_APPROVED_STATUS,
    CHANGE_REQUEST_TRANSITIONS,
    is_transition_allowed,
)

router = APIRouter(prefix="/api/{slug}/change-requests", tags=["change-requests"], dependencies=[Depends(get_current_user)])

CR_DOC_TYPE = "Change Request Impact Analysis"


def generate_cr_code(db: Session) -> str:
    existing = db.query(models.ChangeRequest.cr_code).all()
    max_n = 0
    for (code,) in existing:
        if not code:
            continue
        m = re.match(r"^CR-(\d+)$", code)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"CR-{max_n + 1:03d}"


def _get_cr(db: Session, cr_id: int) -> models.ChangeRequest:
    cr = db.query(models.ChangeRequest).filter(models.ChangeRequest.id == cr_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    return cr


# ---------- CRUD ----------


@router.get("", response_model=list[schemas.ChangeRequestOut])
def list_change_requests(slug: str, status: str | None = Query(None), db: Session = Depends(get_project_db)):
    q = db.query(models.ChangeRequest)
    if status:
        q = q.filter(models.ChangeRequest.status == status)
    return q.order_by(models.ChangeRequest.id.desc()).all()


@router.post("", response_model=schemas.ChangeRequestOut)
def create_change_request(
    slug: str,
    payload: schemas.ChangeRequestCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    cr = models.ChangeRequest(
        cr_code=generate_cr_code(db),
        status="Draft",
        **payload.model_dump(),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


@router.get("/{cr_id}", response_model=schemas.ChangeRequestOut)
def get_change_request(slug: str, cr_id: int, db: Session = Depends(get_project_db)):
    return _get_cr(db, cr_id)


@router.put("/{cr_id}", response_model=schemas.ChangeRequestOut)
def update_change_request(
    slug: str,
    cr_id: int,
    payload: schemas.ChangeRequestUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    cr = _get_cr(db, cr_id)
    data = payload.model_dump(exclude_unset=True)

    new_status = data.pop("status", None)
    if new_status and new_status != cr.status:
        _apply_status_change(db, cr, new_status)

    for key, value in data.items():
        setattr(cr, key, value)
    db.commit()
    db.refresh(cr)
    return cr


def _apply_status_change(db: Session, cr: models.ChangeRequest, new_status: str) -> None:
    if not is_transition_allowed(CHANGE_REQUEST_TRANSITIONS, cr.status, new_status):
        allowed = CHANGE_REQUEST_TRANSITIONS.get(cr.status, [])
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move a change request from '{cr.status}' to '{new_status}'. Allowed: {allowed or 'none'}",
        )

    if new_status == CHANGE_REQUEST_APPROVED_STATUS:
        # The gate. Not advisory — a CR without a confirmed impact document
        # simply cannot be approved through this API.
        if not cr.linked_document_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This change request has no Impact Analysis document. Submit it for approval first — "
                    "a CR cannot be approved before the client has signed off its impact."
                ),
            )
        document = db.query(models.Document).filter(models.Document.id == cr.linked_document_id).first()
        if not document:
            raise HTTPException(status_code=400, detail="The linked Impact Analysis document no longer exists.")
        if document.status != CHANGE_REQUEST_APPROVAL_REQUIRES_DOCUMENT_STATUS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The Impact Analysis document '{document.doc_code or document.title}' is "
                    f"'{document.status}', not '{CHANGE_REQUEST_APPROVAL_REQUIRES_DOCUMENT_STATUS}'. "
                    f"A change request can only be approved once its impact has been signed off."
                ),
            )

    cr.status = new_status
    if new_status == CHANGE_REQUEST_APPROVED_STATUS:
        _materialize_approved_impacts(db, cr)


@router.delete("/{cr_id}")
def delete_change_request(
    slug: str,
    cr_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    cr = _get_cr(db, cr_id)
    db.query(models.ChangeRequestImpact).filter(
        models.ChangeRequestImpact.change_request_id == cr.id
    ).delete(synchronize_session=False)
    db.delete(cr)
    db.commit()
    return {"ok": True}


# ---------- impacted functions ----------


@router.get("/{cr_id}/impacts", response_model=list[schemas.ChangeRequestImpactOut])
def list_impacts(slug: str, cr_id: int, db: Session = Depends(get_project_db)):
    _get_cr(db, cr_id)
    return (
        db.query(models.ChangeRequestImpact)
        .filter(models.ChangeRequestImpact.change_request_id == cr_id)
        .order_by(models.ChangeRequestImpact.id)
        .all()
    )


@router.post("/{cr_id}/impacts", response_model=schemas.ChangeRequestImpactOut)
def add_impact(
    slug: str,
    cr_id: int,
    payload: schemas.ChangeRequestImpactCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    _get_cr(db, cr_id)
    impact = models.ChangeRequestImpact(change_request_id=cr_id, **payload.model_dump())
    db.add(impact)
    db.commit()
    db.refresh(impact)
    return impact


@router.delete("/{cr_id}/impacts/{impact_id}")
def delete_impact(
    slug: str,
    cr_id: int,
    impact_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    impact = (
        db.query(models.ChangeRequestImpact)
        .filter(models.ChangeRequestImpact.id == impact_id, models.ChangeRequestImpact.change_request_id == cr_id)
        .first()
    )
    if not impact:
        raise HTTPException(status_code=404, detail="Impact row not found")
    db.delete(impact)
    db.commit()
    return {"ok": True}


# ---------- impact calculation ----------


@router.get("/{cr_id}/impact")
def get_impact(
    slug: str,
    cr_id: int,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    """Effort / budget / schedule / cost. Any section whose inputs are missing
    comes back null with a `missing` list saying what to fill in — never a
    fabricated number."""
    cr = _get_cr(db, cr_id)
    return effort_budget.compute_cr_impact(db, master_db, slug, cr)


@router.get("/{cr_id}/impact-analysis-export")
def export_impact_analysis(
    slug: str,
    cr_id: int,
    db: Session = Depends(get_project_db),
    master_db: Session = Depends(get_master_db),
):
    cr = _get_cr(db, cr_id)
    impact = effort_budget.compute_cr_impact(db, master_db, slug, cr)
    wb = impact_analysis.generate(slug, cr, impact, db, master_db)
    return workbook_response(wb, f"{slug}-{cr.cr_code or cr.id}-impact-analysis.xlsx")


# ---------- sign-off hand-off ----------


@router.post("/{cr_id}/submit-for-approval", response_model=schemas.ChangeRequestOut)
def submit_for_approval(
    slug: str,
    cr_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    """Creates the Impact Analysis `documents` row (if it doesn't exist yet)
    and moves the CR to PendingApproval.

    The document then goes through the existing Document sign-off workflow
    unchanged — Draft -> InReview -> Confirmed. No new workflow was invented
    for change requests.
    """
    cr = _get_cr(db, cr_id)
    if cr.status not in ("Draft", "UnderAnalysis", "PendingApproval"):
        raise HTTPException(
            status_code=400,
            detail=f"A change request in '{cr.status}' cannot be submitted for approval.",
        )

    if not cr.linked_document_id:
        document = models.Document(
            doc_code=f"IA-{cr.cr_code}" if cr.cr_code else None,
            title=f"Impact Analysis — {cr.title}",
            doc_type=CR_DOC_TYPE,
            phase=None,
            owner=cr.requested_by,
            status="Draft",
        )
        db.add(document)
        db.flush()
        cr.linked_document_id = document.id

    if cr.status != "PendingApproval":
        _apply_status_change(db, cr, "PendingApproval")
    db.commit()
    db.refresh(cr)
    return cr


# ---------- auto-create on approval ----------


def _materialize_approved_impacts(db: Session, cr: models.ChangeRequest) -> None:
    """On approval, every `new` impact row that isn't already wired to a
    function becomes a real Function, and any effort estimate recorded
    against the CR is carried over to it rather than recalculated — the
    numbers the client approved are the numbers that get committed."""
    impacts = (
        db.query(models.ChangeRequestImpact)
        .filter(
            models.ChangeRequestImpact.change_request_id == cr.id,
            models.ChangeRequestImpact.impact_type == "new",
            models.ChangeRequestImpact.linked_function_id.is_(None),
        )
        .order_by(models.ChangeRequestImpact.id)
        .all()
    )
    if not impacts:
        return

    cr_estimates = (
        db.query(models.EffortEstimate)
        .filter(
            models.EffortEstimate.linked_entity_type == "change_request",
            models.EffortEstimate.linked_entity_id == cr.id,
        )
        .order_by(models.EffortEstimate.id)
        .all()
    )

    for index, impact in enumerate(impacts):
        function = models.Function(
            name=impact.function_name or f"{cr.cr_code} new function",
            description=impact.note,
            type="Functional",
            status="Draft",
            owner=cr.requested_by,
        )
        db.add(function)
        db.flush()
        impact.linked_function_id = function.id

        # Carry the approved estimate across, one-for-one where the counts
        # line up, otherwise the first one as the basis.
        source = cr_estimates[index] if index < len(cr_estimates) else (cr_estimates[0] if cr_estimates else None)
        if source is None:
            continue
        db.add(
            models.EffortEstimate(
                linked_entity_type="function",
                linked_entity_id=function.id,
                work_type=source.work_type,
                driver_counts_json=source.driver_counts_json,
                reusability_json=source.reusability_json,
                non_similarity_source=source.non_similarity_source,
                priority=source.priority,
                complexity=source.complexity,
                non_similarity=source.non_similarity,
                calculated_fp=source.calculated_fp,
                calculated_final_fp=source.calculated_final_fp,
                calculated_mm=source.calculated_mm,
                calculated_man_days=source.calculated_man_days,
                md_dr=source.md_dr,
                md_dnpu=source.md_dnpu,
                md_iftbct=source.md_iftbct,
            )
        )
