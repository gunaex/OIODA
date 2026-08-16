"""Effort Calculator + Effort Budget Gauge endpoints.

RBAC: reads are open to any logged-in role (the gauge is something a client
is meant to be shown), writes go through require_internal.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import effort_budget, effort_calculator, models, schemas
from ..auth import get_current_user, require_internal, require_roles
from ..database import get_project_db

router = APIRouter(prefix="/api/{slug}", tags=["effort"], dependencies=[Depends(get_current_user)])

# The contracted total and the productivity figures drive every effort number
# in the project, so editing them is pmo_admin only — narrower than the
# require_internal used for ordinary writes.
require_pmo_admin = require_roles("pmo_admin")


def _guard_delivery_mode(config: models.EffortEstimateConfig, delivery_mode: str | None) -> None:
    """Compliance guard: a project whose contract forbids HUMAN-in-LOOP
    refuses it at the API, not just in the UI. Disabling a button is a
    convenience; this is the control."""
    if delivery_mode == "human_in_loop" and config.hil_restricted:
        raise HTTPException(
            status_code=400,
            detail=(
                "This project is contractually restricted to fully-human delivery. "
                "Check the data-handling clause with the client before changing it."
            ),
        )


def _run(payload, config, delivery_mode: str | None = None) -> dict:
    mode = delivery_mode or getattr(payload, "delivery_mode", None) or effort_calculator.DEFAULT_DELIVERY_MODE
    _guard_delivery_mode(config, mode)
    return effort_calculator.calculate(
        work_type=payload.work_type,
        driver_counts=payload.driver_counts or {},
        complexity=payload.complexity,
        non_similarity=payload.non_similarity,
        reusability=payload.reusability,
        config=effort_budget.config_as_dict(config),
        priority=payload.priority or effort_calculator.COUNTED_PRIORITY,
        delivery_mode=mode,
        hil_leverage=effort_budget.config_hil_leverage(config),
    )


# ---------- config ----------


@router.get("/effort-config", response_model=schemas.EffortConfigOut)
def get_effort_config(slug: str, db: Session = Depends(get_project_db)):
    return effort_budget.config_out(effort_budget.get_config(db))


@router.put("/effort-config", response_model=schemas.EffortConfigOut)
def update_effort_config(
    slug: str,
    payload: schemas.EffortConfigUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_pmo_admin),
):
    config = effort_budget.get_config(db)
    data = payload.model_dump(exclude_unset=True)

    # The phase split has to add up, otherwise the per-phase man-days quietly
    # stop summing to the total.
    ratios = {
        key: data.get(key, getattr(config, key))
        for key in ("phase_ratio_dr", "phase_ratio_dnpu", "phase_ratio_iftbct")
    }
    if any(k in data for k in ratios):
        total = sum(float(v or 0) for v in ratios.values())
        if abs(total - 1.0) > 1e-6:
            raise HTTPException(
                status_code=400,
                detail=f"Phase ratios must add up to 1.0 — they currently total {total:.4f}.",
            )

    if "hil_leverage" in data:
        leverage = data.pop("hil_leverage")
        config.hil_leverage_json = json.dumps(leverage) if leverage else None

    for key, value in data.items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return effort_budget.config_out(config)


@router.get("/effort-drivers")
def get_driver_schema(slug: str):
    """The driver list and coefficients, served from the same table the
    calculation uses so the form can never show a stale coefficient."""
    return effort_calculator.driver_schema()


# ---------- calculate (preview, nothing saved) ----------


@router.post("/effort-estimates/calculate")
def calculate_effort(
    slug: str,
    payload: schemas.EffortCalculateRequest,
    db: Session = Depends(get_project_db),
):
    config = effort_budget.get_config(db)
    return _run(payload, config)


# ---------- estimates CRUD ----------


@router.get("/effort-estimates")
def list_effort_estimates(
    slug: str,
    linked_entity_type: str | None = Query(None),
    linked_entity_id: int | None = Query(None),
    db: Session = Depends(get_project_db),
):
    q = db.query(models.EffortEstimate)
    if linked_entity_type:
        q = q.filter(models.EffortEstimate.linked_entity_type == linked_entity_type)
    if linked_entity_id is not None:
        q = q.filter(models.EffortEstimate.linked_entity_id == linked_entity_id)
    return [effort_budget.estimate_payload(e) for e in q.order_by(models.EffortEstimate.id).all()]


@router.post("/effort-estimates")
def create_effort_estimate(
    slug: str,
    payload: schemas.EffortEstimateCreate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    config = effort_budget.get_config(db)
    result = _run(payload, config)
    estimate = models.EffortEstimate(
        linked_entity_type=payload.linked_entity_type,
        linked_entity_id=payload.linked_entity_id,
        work_type=payload.work_type,
        driver_counts_json=json.dumps(payload.driver_counts or {}),
        reusability_json=json.dumps(payload.reusability) if payload.reusability else None,
        non_similarity_source=result["non_similarity_source"],
        priority=payload.priority or effort_calculator.COUNTED_PRIORITY,
        complexity=result["complexity"],
        non_similarity=result["non_similarity"],
        delivery_mode=result["delivery_mode"],
        effort_multiplier_applied=result["effort_multiplier_applied"],
        man_days_human=result["man_days_human"],
        calculated_fp=result["fp"],
        calculated_final_fp=result["final_fp"],
        calculated_mm=result["mm"],
        calculated_man_days=result["man_days"],
        md_dr=result["md_dr"],
        md_dnpu=result["md_dnpu"],
        md_iftbct=result["md_iftbct"],
    )
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return {**effort_budget.estimate_payload(estimate), "calculation": result}


@router.put("/effort-estimates/{estimate_id}")
def update_effort_estimate(
    slug: str,
    estimate_id: int,
    payload: schemas.EffortEstimateUpdate,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    estimate = db.query(models.EffortEstimate).filter(models.EffortEstimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Effort estimate not found")

    data = payload.model_dump(exclude_unset=True)
    stored = effort_budget.estimate_payload(estimate)
    merged = schemas.EffortCalculateRequest(
        work_type=data.get("work_type", estimate.work_type),
        driver_counts=data.get("driver_counts", stored["driver_counts"]),
        complexity=data.get("complexity", estimate.complexity),
        # An explicit non_similarity always wins; a stored derived value is
        # recomputed from its reusability inputs so editing those actually
        # moves the number.
        non_similarity=data.get("non_similarity")
        if "non_similarity" in data
        else (estimate.non_similarity if estimate.non_similarity_source == "manual" else None),
        reusability=data.get("reusability", stored["reusability"] or None),
        priority=data.get("priority", estimate.priority),
        # Carried over unless the caller is explicitly changing it — a PUT
        # that only edits complexity must not silently flip the mode back.
        delivery_mode=data.get("delivery_mode", estimate.delivery_mode or "human"),
    )
    config = effort_budget.get_config(db)
    result = _run(merged, config)

    estimate.work_type = merged.work_type
    estimate.driver_counts_json = json.dumps(merged.driver_counts or {})
    estimate.reusability_json = json.dumps(merged.reusability) if merged.reusability else None
    estimate.non_similarity_source = result["non_similarity_source"]
    estimate.priority = merged.priority
    estimate.complexity = result["complexity"]
    estimate.non_similarity = result["non_similarity"]
    estimate.delivery_mode = result["delivery_mode"]
    estimate.effort_multiplier_applied = result["effort_multiplier_applied"]
    estimate.man_days_human = result["man_days_human"]
    estimate.calculated_fp = result["fp"]
    estimate.calculated_final_fp = result["final_fp"]
    estimate.calculated_mm = result["mm"]
    estimate.calculated_man_days = result["man_days"]
    estimate.md_dr = result["md_dr"]
    estimate.md_dnpu = result["md_dnpu"]
    estimate.md_iftbct = result["md_iftbct"]
    db.commit()
    db.refresh(estimate)
    return {**effort_budget.estimate_payload(estimate), "calculation": result}


@router.delete("/effort-estimates/{estimate_id}")
def delete_effort_estimate(
    slug: str,
    estimate_id: int,
    db: Session = Depends(get_project_db),
    _user: models.User = Depends(require_internal),
):
    estimate = db.query(models.EffortEstimate).filter(models.EffortEstimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Effort estimate not found")
    db.delete(estimate)
    db.commit()
    return {"ok": True}


@router.get("/effort-estimates/summary")
def effort_summary(slug: str, db: Session = Depends(get_project_db)):
    return effort_budget.effort_summary(db)


# ---------- budget gauge ----------


@router.get("/effort-budget")
def effort_budget_gauge(slug: str, db: Session = Depends(get_project_db)):
    return effort_budget.compute_effort_budget(db)
