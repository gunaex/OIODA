"""Change Request impact analysis and the Effort Budget Gauge.

Both are pure aggregation over data that already exists elsewhere in the app —
effort estimates, the contracted total, resource utilization, function
pricing. Nothing here invents a number.

The rule that matters most: when an input is missing, the corresponding
section comes back as null WITH an explanation of what is missing. It never
guesses, and it never quietly reports 0 as though it were a real answer.
"""

import json
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .resource_utils import compute_utilization
from .workflow_definitions import (
    CHANGE_REQUEST_COMMITTED_STATUSES,
    EFFORT_USED_STATUSES,
)

# Budget health thresholds, on remaining as a share of contracted.
HEALTHY_THRESHOLD = 0.25
WARNING_THRESHOLD = 0.10


def get_config(db: Session) -> models.EffortEstimateConfig:
    """One config row per project, created on first read."""
    config = db.query(models.EffortEstimateConfig).order_by(models.EffortEstimateConfig.id).first()
    if config is None:
        config = models.EffortEstimateConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def config_as_dict(config: models.EffortEstimateConfig) -> dict:
    return {
        "productivity_screen": config.productivity_screen,
        "productivity_batch": config.productivity_batch,
        "productivity_report": config.productivity_report,
        "working_days_per_month": config.working_days_per_month,
        "phase_ratio_dr": config.phase_ratio_dr,
        "phase_ratio_dnpu": config.phase_ratio_dnpu,
        "phase_ratio_iftbct": config.phase_ratio_iftbct,
        "contracted_total_md": config.contracted_total_md,
        "rate_thb_per_md": config.rate_thb_per_md,
    }


def config_hil_leverage(config: models.EffortEstimateConfig) -> Optional[dict]:
    """The project's own leverage overrides, or None to use the defaults."""
    if not config.hil_leverage_json:
        return None
    try:
        value = json.loads(config.hil_leverage_json)
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        return None


def config_out(config: models.EffortEstimateConfig) -> dict:
    """API shape — the JSON blob decoded, everything else as-is."""
    return {
        "id": config.id,
        **config_as_dict(config),
        "hil_leverage": config_hil_leverage(config),
        "hil_price_discount_percent": config.hil_price_discount_percent,
        "show_delivery_mode_in_client_docs": bool(config.show_delivery_mode_in_client_docs),
        "hil_restricted": bool(config.hil_restricted),
    }


def _estimates_for(db: Session, entity_type: str, entity_ids: Optional[list[int]] = None):
    q = db.query(models.EffortEstimate).filter(models.EffortEstimate.linked_entity_type == entity_type)
    if entity_ids is not None:
        if not entity_ids:
            return []
        q = q.filter(models.EffortEstimate.linked_entity_id.in_(entity_ids))
    return q.all()


def _sum_md(estimates) -> dict:
    return {
        "total_md": sum(e.calculated_man_days or 0 for e in estimates),
        "dr": sum(e.md_dr or 0 for e in estimates),
        "dnpu": sum(e.md_dnpu or 0 for e in estimates),
        "iftbct": sum(e.md_iftbct or 0 for e in estimates),
    }


# --------------------------------------------------------------------------
# Effort Budget Gauge
# --------------------------------------------------------------------------


def compute_effort_budget(db: Session) -> dict:
    """contracted / used / committed / remaining, in man-days.

    used      = estimates on functions and tasks that have actually reached a
                done state (Done / Confirmed, per EFFORT_USED_STATUSES)
    committed = estimates on approved change requests, plus estimates on
                functions/tasks that exist but aren't finished — work already
                promised and not yet delivered
    """
    config = get_config(db)
    contracted = config.contracted_total_md

    used_md = 0.0
    committed_md = 0.0
    breakdown = {"function": {"used": 0.0, "committed": 0.0}, "task": {"used": 0.0, "committed": 0.0},
                 "change_request": {"used": 0.0, "committed": 0.0}}

    # Same de-duplication as effort_summary: a task under an already-estimated
    # function would otherwise be counted against the budget twice.
    excluded_task_ids = _double_counted_task_ids(db)

    for entity_type, model in (("function", models.Function), ("task", models.Task)):
        estimates = _estimates_for(db, entity_type)
        if entity_type == "task" and excluded_task_ids:
            estimates = [e for e in estimates if e.linked_entity_id not in excluded_task_ids]
        if not estimates:
            continue
        ids = {e.linked_entity_id for e in estimates}
        statuses = {
            row.id: row.status
            for row in db.query(model).filter(model.id.in_(ids)).all()
        }
        done_statuses = EFFORT_USED_STATUSES[entity_type]
        for e in estimates:
            md = e.calculated_man_days or 0
            if statuses.get(e.linked_entity_id) in done_statuses:
                used_md += md
                breakdown[entity_type]["used"] += md
            else:
                committed_md += md
                breakdown[entity_type]["committed"] += md

    cr_estimates = _estimates_for(db, "change_request")
    if cr_estimates:
        cr_ids = {e.linked_entity_id for e in cr_estimates}
        cr_status = {
            row.id: row.status
            for row in db.query(models.ChangeRequest).filter(models.ChangeRequest.id.in_(cr_ids)).all()
        }
        for e in cr_estimates:
            if cr_status.get(e.linked_entity_id) in CHANGE_REQUEST_COMMITTED_STATUSES:
                md = e.calculated_man_days or 0
                committed_md += md
                breakdown["change_request"]["committed"] += md

    if contracted is None:
        # No contracted figure means there is no budget to report against.
        # Saying "0 remaining" here would be a lie, so the gauge stays null
        # and says why.
        return {
            "contracted_md": None,
            "used_md": used_md,
            "committed_md": committed_md,
            "remaining_md": None,
            "remaining_percent": None,
            "status": None,
            "breakdown": breakdown,
            "missing": ["effort_estimate_config.contracted_total_md"],
            "note": "Set the contracted man-days in Effort Config to enable the budget gauge.",
        }

    remaining = contracted - used_md - committed_md
    percent = (remaining / contracted * 100) if contracted else None
    if remaining < 0:
        status = "over_budget"
    elif percent is not None and percent / 100 > HEALTHY_THRESHOLD:
        status = "healthy"
    elif percent is not None and percent / 100 >= WARNING_THRESHOLD:
        status = "warning"
    else:
        status = "critical"

    return {
        "contracted_md": contracted,
        "used_md": used_md,
        "committed_md": committed_md,
        "remaining_md": remaining,
        "remaining_percent": percent,
        "status": status,
        "breakdown": breakdown,
        "missing": [],
        "note": None,
    }


# --------------------------------------------------------------------------
# Change Request impact
# --------------------------------------------------------------------------


def _cost_section(db: Session, cr: models.ChangeRequest, effort: dict, config) -> dict:
    """Cost from the impacted functions' own price_thb where the project
    prices its function list; otherwise from the configured day rate. If
    neither exists, null plus the reason."""
    impacts = (
        db.query(models.ChangeRequestImpact)
        .filter(models.ChangeRequestImpact.change_request_id == cr.id)
        .all()
    )
    function_ids = [i.linked_function_id for i in impacts if i.linked_function_id]
    priced = []
    if function_ids:
        priced = [
            f
            for f in db.query(models.Function).filter(models.Function.id.in_(function_ids)).all()
            if f.price_thb
        ]

    if priced:
        total = sum(f.price_thb for f in priced)
        return {
            "estimated_thb": total,
            "basis": (
                f"Sum of price_thb on {len(priced)} impacted function(s) already priced in the Function List"
            ),
            "data_points": [f"function#{f.id} price_thb={f.price_thb}" for f in priced],
            "missing": [],
        }

    if config.rate_thb_per_md and effort["total_md"] is not None:
        total = effort["total_md"] * config.rate_thb_per_md
        return {
            "estimated_thb": total,
            "basis": f"{effort['total_md']:.2f} MD x {config.rate_thb_per_md:,.0f} THB/MD from Effort Config",
            "data_points": [
                f"total_md={effort['total_md']}",
                f"rate_thb_per_md={config.rate_thb_per_md}",
            ],
            "missing": [],
        }

    return {
        "estimated_thb": None,
        "basis": None,
        "data_points": [],
        "missing": ["functions.price_thb on the impacted functions", "effort_estimate_config.rate_thb_per_md"],
    }


def _schedule_section(
    cr: models.ChangeRequest, effort: dict, project_slug: str, master_db: Session
) -> dict:
    """Delay estimated from the team's genuinely free capacity over the CR's
    own window, taken from the existing Resource Utilization data."""
    if not effort["total_md"]:
        return {
            "affected_phases": [],
            "estimated_delay_days": None,
            "basis": None,
            "data_points": [],
            "missing": ["effort estimate on this change request"],
        }

    today = date.today()
    window_start = cr.requested_date or today
    window_end = cr.target_date or (window_start + timedelta(days=90))
    if window_end < window_start:
        window_end = window_start + timedelta(days=90)

    # compute_utilization gives, per resource, that resource's committed
    # percentage for each week in the window. Free capacity is whatever is
    # left of 100% once every project's claim on them is counted — averaged
    # across the weeks, since a person free for half the window is half a
    # person for this purpose.
    utilization = compute_utilization(master_db, window_start, window_end)
    free_percent = 0.0
    contributors = []
    for row in utilization:
        weeks = row.get("weeks") or []
        if not weeks:
            continue
        free_by_week = [max(0.0, 100.0 - float(w.get("total_percent") or 0)) for w in weeks]
        average_free = sum(free_by_week) / len(free_by_week)
        if average_free > 0:
            free_percent += average_free
            contributors.append(f"{row.get('resource_name')}: {average_free:.0f}% free on average")

    if free_percent <= 0:
        return {
            "affected_phases": _affected_phases(effort),
            "estimated_delay_days": None,
            "basis": None,
            "data_points": [
                f"resources checked: {len(utilization)}",
                f"window: {window_start.isoformat()}..{window_end.isoformat()}",
                "free capacity: 0%",
            ],
            "missing": ["free capacity in resource_allocations over this window"],
        }

    # free_percent is a sum of percentages; /100 turns it into whole people.
    people_equivalent = free_percent / 100.0
    delay_days = effort["total_md"] / people_equivalent
    return {
        "affected_phases": _affected_phases(effort),
        "estimated_delay_days": round(delay_days, 1),
        "basis": (
            f"{effort['total_md']:.2f} MD / {people_equivalent:.2f} person-equivalents free between "
            f"{window_start.isoformat()} and {window_end.isoformat()} (from Resource Allocation)"
        ),
        "data_points": [f"total_md={effort['total_md']}", f"free_capacity={people_equivalent:.2f} people"]
        + contributors[:5],
        "missing": [],
    }


def _affected_phases(effort: dict) -> list[str]:
    phases = []
    if effort.get("dr"):
        phases.append("DR")
    if effort.get("dnpu"):
        phases.append("DN&PU")
    if effort.get("iftbct"):
        phases.append("IFT/BCT")
    return phases


def compute_cr_impact(db: Session, master_db: Session, project_slug: str, cr: models.ChangeRequest) -> dict:
    """The four-part impact answer: effort / budget / schedule / cost."""
    config = get_config(db)
    estimates = _estimates_for(db, "change_request", [cr.id])
    effort = _sum_md(estimates)
    effort["estimate_count"] = len(estimates)
    if not estimates:
        effort = {"total_md": None, "dr": None, "dnpu": None, "iftbct": None, "estimate_count": 0,
                  "missing": ["effort estimate linked to this change request"]}
    else:
        effort["missing"] = []

    budget = compute_effort_budget(db)
    cr_md = effort.get("total_md")
    if budget["contracted_md"] is None or cr_md is None:
        budget_section = {
            "contracted_md": budget["contracted_md"],
            "used_md": budget["used_md"],
            "remaining_before": budget["remaining_md"],
            "remaining_after": None,
            "remaining_percent_after": None,
            "warning": None,
            "missing": (budget["missing"] or []) + ([] if cr_md is not None else ["effort estimate on this CR"]),
        }
    else:
        # This CR's own effort is already in committed_md once it's approved;
        # for a not-yet-approved CR it is the thing being asked about.
        already_counted = cr.status in CHANGE_REQUEST_COMMITTED_STATUSES
        remaining_before = budget["remaining_md"] + (cr_md if already_counted else 0)
        remaining_after = remaining_before - cr_md
        percent_after = (remaining_after / budget["contracted_md"] * 100) if budget["contracted_md"] else None
        warning = None
        if percent_after is not None and percent_after < 0:
            warning = (
                f"Accepting this CR puts the project {abs(remaining_after):.1f} MD over the contracted "
                f"{budget['contracted_md']:.0f} MD."
            )
        elif percent_after is not None and percent_after < WARNING_THRESHOLD * 100:
            warning = (
                f"Accepting this CR leaves {remaining_after:.1f} MD ({percent_after:.1f}%) — below the "
                f"{WARNING_THRESHOLD * 100:.0f}% safety buffer."
            )
        elif percent_after is not None and percent_after < HEALTHY_THRESHOLD * 100:
            warning = (
                f"Accepting this CR leaves {remaining_after:.1f} MD ({percent_after:.1f}%) — inside the "
                f"warning band."
            )
        budget_section = {
            "contracted_md": budget["contracted_md"],
            "used_md": budget["used_md"],
            "remaining_before": remaining_before,
            "remaining_after": remaining_after,
            "remaining_percent_after": percent_after,
            "warning": warning,
            "missing": [],
        }

    return {
        "change_request_id": cr.id,
        "cr_code": cr.cr_code,
        "status": cr.status,
        "effort": effort,
        "budget": budget_section,
        "schedule": _schedule_section(cr, effort, project_slug, master_db),
        "cost": _cost_section(db, cr, effort, config),
    }


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


def _double_counted_task_ids(db: Session) -> set[int]:
    """Tasks whose parent Function already carries an effort estimate.

    Function is the unit the Function Point model actually sizes (it is the
    thing the customer's Function List enumerates); a Task is a slice of
    delivering one. So when both are estimated, the Function is authoritative
    and the Task's estimate is excluded from the total rather than added on
    top of it — otherwise the same work is billed twice.
    """
    task_estimates = _estimates_for(db, "task")
    if not task_estimates:
        return set()
    estimated_function_ids = {e.linked_entity_id for e in _estimates_for(db, "function")}
    if not estimated_function_ids:
        return set()

    task_ids = {e.linked_entity_id for e in task_estimates}
    parents = (
        db.query(models.Task.id, models.Task.linked_function_id)
        .filter(models.Task.id.in_(task_ids), models.Task.linked_function_id.isnot(None))
        .all()
    )
    return {task_id for task_id, function_id in parents if function_id in estimated_function_ids}


def effort_summary(db: Session) -> dict:
    """Total man-days across the project, split by phase and by entity type.

    The total deliberately does not equal the sum of the three entity-type
    rows when a task sits under an already-estimated function — see
    `_double_counted_task_ids`. The excluded amount is reported explicitly so
    the difference is visible rather than mysterious.
    """
    excluded_task_ids = _double_counted_task_ids(db)
    out = {"by_entity_type": {}, "total": {"total_md": 0.0, "dr": 0.0, "dnpu": 0.0, "iftbct": 0.0}}
    excluded = {"total_md": 0.0, "dr": 0.0, "dnpu": 0.0, "iftbct": 0.0, "task_count": 0}

    for entity_type in ("function", "task", "change_request"):
        estimates = _estimates_for(db, entity_type)
        totals = _sum_md(estimates)
        totals["estimate_count"] = len(estimates)

        if entity_type == "task" and excluded_task_ids:
            counted = [e for e in estimates if e.linked_entity_id not in excluded_task_ids]
            skipped = [e for e in estimates if e.linked_entity_id in excluded_task_ids]
            skipped_totals = _sum_md(skipped)
            for key in ("total_md", "dr", "dnpu", "iftbct"):
                excluded[key] += skipped_totals[key]
            excluded["task_count"] = len({e.linked_entity_id for e in skipped})
            totals["excluded_from_total_md"] = skipped_totals["total_md"]
            contributing = _sum_md(counted)
        else:
            totals["excluded_from_total_md"] = 0.0
            contributing = totals

        out["by_entity_type"][entity_type] = totals
        for key in ("total_md", "dr", "dnpu", "iftbct"):
            out["total"][key] += contributing[key]

    out["excluded_double_counted"] = excluded
    out["note"] = (
        f"{excluded['task_count']} task estimate(s) are excluded from the total because their function is "
        f"already estimated — Function is the sized unit, a Task is a slice of one."
        if excluded["task_count"]
        else None
    )
    return out


def estimate_payload(estimate: models.EffortEstimate) -> dict:
    """DB row -> API shape, with the JSON blobs decoded."""
    def _load(raw):
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}

    return {
        "id": estimate.id,
        "linked_entity_type": estimate.linked_entity_type,
        "linked_entity_id": estimate.linked_entity_id,
        "work_type": estimate.work_type,
        "driver_counts": _load(estimate.driver_counts_json),
        "reusability": _load(estimate.reusability_json),
        "non_similarity_source": estimate.non_similarity_source,
        "priority": estimate.priority,
        "complexity": estimate.complexity,
        "non_similarity": estimate.non_similarity,
        "delivery_mode": estimate.delivery_mode or "human",
        "effort_multiplier_applied": estimate.effort_multiplier_applied,
        "man_days_human": estimate.man_days_human,
        "calculated_fp": estimate.calculated_fp,
        "calculated_final_fp": estimate.calculated_final_fp,
        "calculated_mm": estimate.calculated_mm,
        "calculated_man_days": estimate.calculated_man_days,
        "md_dr": estimate.md_dr,
        "md_dnpu": estimate.md_dnpu,
        "md_iftbct": estimate.md_iftbct,
        "created_at": estimate.created_at,
        "updated_at": estimate.updated_at,
    }
