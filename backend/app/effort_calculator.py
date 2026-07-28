"""Function Point effort model — transcribed from the customer's own
spreadsheets and verified against them cell for cell.

Source of truth (variant A), confirmed by reading the formulas with
openpyxl(data_only=False) and checking our arithmetic against the values
Excel had cached:

  reference/SATL_Function_List.xlsx :: SATL_FunctionList_BeforeDR
  reference/Impact_Analysis_TBOS_*.xlsx :: FunctionList

The workbook also carries a second, newer model on its `ref_Function List`
sheet (Kaizen function types, productivity 4.7/5.4/5.4 + 5.4/5.9/5.9, ODB as
a single x0.2 column, 21 batch drivers). That one is deliberately NOT
implemented here — the two are not compatible variants of one formula, and
variant A is what produced the Impact Analysis document the client signed.

Everything below is arithmetic and table lookup. No ML, no external calls.
"""

import math
from typing import Optional

# --------------------------------------------------------------------------
# Driver tables
# --------------------------------------------------------------------------
# Each entry: (key, label, coefficient, divisor)
# divisor None  -> contributes count * coefficient
# divisor n     -> contributes ROUNDUP(count / n, 0) * coefficient
#
# Excel's ROUNDUP(x, 0) rounds away from zero; for these non-negative counts
# that is math.ceil.

SCREEN_DRIVERS = [
    ("basic_retrieve", "Basic for Retrieve (always 1)", 1.0, None),
    ("basic_update", "Basic for Update (always 1)", 1.0, None),
    ("incr_target_tables_retrieve", "Incremental Target Tables (retrieve)", 0.2, None),
    ("incr_target_tables_update", "Incremental Target Tables (update)", 0.3, None),
    ("combobox_accessing_table", "Combobox accessing Table", 0.1, None),
    ("display_sub_screen", "Display Sub-Screen", 0.5, None),
    ("refer_check_master", "Refer/Check Master", 0.1, None),
    ("check_input_items", "Check Input Items", 0.1, 5),
    ("additional_func_client", "Additional Functions (On Client)", 0.5, None),
    ("additional_func_server", "Additional Functions (Server Access)", 1.0, None),
    ("odb_basic", "ODB — Basic", 1.0, None),
    ("odb_additional_func_client", "ODB — Additional Functions (On Client)", 0.5, None),
]

REPORT_DRIVERS = [
    ("report_basic", "Basic", 1.0, None),
    ("report_incr_target_tables", "Incremental Target Tables", 0.2, None),
    ("report_incr_forms", "Incremental Forms", 1.0, None),
    ("report_special_edit", "Special Edit", 0.1, 3),
    ("report_special_layout", "Special Layout", 0.5, None),
]

BATCH_DRIVERS = [
    ("upload_basic", "Upload — Basic", 1.0, None),
    ("upload_incr_target_tables", "Upload — Incremental target tables", 0.3, None),
    ("upload_refer_check_master", "Upload — Refer/Check Master", 0.1, None),
    ("upload_data_convert_edit", "Upload — Data convert and edit", 0.1, 3),
    ("upload_communicate_other_system", "Upload — Communicate with other system", 1.0, None),
    ("upload_additional_func", "Upload — Additional function", 1.0, None),
    ("download_basic", "Download — Basic", 1.0, None),
    ("download_incr_target_tables", "Download — Incremental target tables", 0.2, None),
    ("download_refer_check_master", "Download — Refer/Check Master", 0.1, None),
    ("download_data_convert_edit", "Download — Data convert and edit", 0.1, 3),
    ("download_communicate_other_system", "Download — Communicate with other system", 1.0, None),
    ("download_additional_func", "Download — Additional function", 1.0, None),
    ("calculation_data_edit", "Calculation / Data Edit", 1.0, None),
]

DRIVERS_BY_WORK_TYPE = {
    "screen": SCREEN_DRIVERS,
    "report": REPORT_DRIVERS,
    "batch": BATCH_DRIVERS,
}

WORK_TYPES = tuple(DRIVERS_BY_WORK_TYPE.keys())

# The workbook gates every formula on Priority: IF(Priority<>"M", 0, ...).
# A non-"M" row contributes nothing at all — not its computed value. Missing
# from the kickoff spec, present in every formula in both workbooks.
COUNTED_PRIORITY = "M"

# --------------------------------------------------------------------------
# Non-similarity model (ref_Non-similarity sheet)
# --------------------------------------------------------------------------
# non_similarity is not a number somebody types — it's derived from how much
# of each development activity can be reused. Per activity:
#     non_reusable = weight * (1 - reusability)
# summed within its phase group, then weighted by the group's share.
#
# Each group's weights sum to 1.0 and the group shares sum to 1.0, so a
# wholly new function scores 1.0 and a wholly reusable one scores 0.
#
# (key, label, group, weight)
NON_SIMILARITY_ACTIVITIES = [
    ("discussion", "Discussion", "dr", 0.2),
    ("document", "Document", "dr", 0.5),
    ("is_review", "IS Review", "dr", 0.1),
    ("user_review", "User Review", "dr", 0.1),
    ("finalize", "Finalize", "dr", 0.1),
    ("ps", "PS", "pu", 0.2),
    ("coding", "Coding", "pu", 0.35),
    ("pt_script", "PT Script", "pu", 0.15),
    ("pt", "PT", "pu", 0.2),
    ("pu_bug_fix", "Bug Fix (PU)", "pu", 0.1),
    ("ift_script", "IFT Script", "st", 0.2),
    ("ift", "IFT", "st", 0.2),
    ("ift_bug_fix", "Bug Fix (IFT)", "st", 0.1),
    ("bct_script", "BCT Script", "st", 0.2),
    ("bct", "BCT", "st", 0.2),
    ("bct_bug_fix", "Bug Fix (BCT)", "st", 0.1),
]

# Group shares live on the ref_Non-similarity sheet (F8/K8/P8), separate cells
# from the man-day phase split on the FunctionList sheet — they happen to hold
# the same numbers, but they are not the same setting and are not configurable
# together.
NON_SIMILARITY_GROUP_WEIGHTS = {"dr": 0.3, "pu": 0.4, "st": 0.3}


# --------------------------------------------------------------------------
# Delivery mode (HUMAN / HUMAN-in-LOOP)
# --------------------------------------------------------------------------
# HUMAN-in-LOOP means tooling assists parts of the work. The saving is NOT a
# flat percentage across the board, because the activities benefit very
# unevenly — writing a script or a program spec gains a lot, sitting in a user
# review or running UAT gains almost nothing. Modelling it per activity (the
# same 16 as the non-similarity model) is what lets an estimate be explained
# line by line rather than asserted.
#
#     phase_leverage    = Σ_activity ( activity_weight × leverage_activity )
#     total_leverage    = Σ_phase   ( phase_weight × phase_leverage )
#     effort_multiplier = 1 − total_leverage
#
# !! THESE DEFAULTS ARE A STARTING POINT, NOT CALIBRATED FIGURES !!
# They are a considered first guess and have not yet been checked against
# measured delivery data from real projects. Revise them once there are
# actual before/after numbers to compare. Do not present them to a client as
# though they were empirically derived.
DELIVERY_MODES = ("human", "human_in_loop")
DEFAULT_DELIVERY_MODE = "human"

DEFAULT_HIL_LEVERAGE = {
    "discussion": 0.10,
    "document": 0.60,
    "is_review": 0.30,
    "user_review": 0.00,
    "finalize": 0.30,
    "ps": 0.50,
    "coding": 0.70,
    "pt_script": 0.60,
    "pt": 0.30,
    "pu_bug_fix": 0.40,
    "ift_script": 0.60,
    "ift": 0.25,
    "ift_bug_fix": 0.40,
    "bct_script": 0.50,
    "bct": 0.10,
    "bct_bug_fix": 0.40,
}


def compute_delivery_leverage(leverage: Optional[dict] = None) -> dict:
    """Effort multiplier for HUMAN-in-LOOP, with the per-activity and
    per-phase breakdown that the UI shows. Activities absent from `leverage`
    fall back to the default; an activity with no default gains nothing."""
    table = {**DEFAULT_HIL_LEVERAGE, **(leverage or {})}

    activities = []
    phase_raw = {"dr": 0.0, "pu": 0.0, "st": 0.0}
    for key, label, group, weight in NON_SIMILARITY_ACTIVITIES:
        try:
            factor = float(table.get(key, 0.0))
        except (TypeError, ValueError):
            factor = 0.0
        factor = min(max(factor, 0.0), 1.0)
        contribution = weight * factor
        phase_raw[group] += contribution
        activities.append(
            {
                "key": key,
                "label": label,
                "group": group,
                "weight": weight,
                "leverage": factor,
                "contribution": contribution,
            }
        )

    phases = [
        {
            "group": group,
            "phase_leverage": raw,
            "phase_weight": NON_SIMILARITY_GROUP_WEIGHTS[group],
            "weighted": raw * NON_SIMILARITY_GROUP_WEIGHTS[group],
        }
        for group, raw in phase_raw.items()
    ]
    total_leverage = sum(p["weighted"] for p in phases)
    return {
        "total_leverage": total_leverage,
        "effort_multiplier": 1.0 - total_leverage,
        "phases": phases,
        "activities": activities,
        "calibration_note": (
            "Leverage factors are an uncalibrated starting point, not measured figures. "
            "Revise them against real delivery data before treating them as evidence."
        ),
    }


def roundup(value: float, digits: int = 0) -> float:
    """Excel ROUNDUP — away from zero, unlike Python's round()."""
    factor = 10 ** digits
    if value >= 0:
        return math.ceil(value * factor) / factor
    return -math.ceil(-value * factor) / factor


def _count(driver_counts: dict, key: str) -> float:
    raw = driver_counts.get(key)
    if raw in (None, ""):
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def compute_non_similarity(reusability: dict) -> dict:
    """Derives the non-similarity factor from per-activity reusability ratios
    (0 = nothing reusable, 1 = fully reusable). Anything not supplied counts
    as 0 reusable, i.e. fully new — the conservative direction."""
    per_activity = []
    group_totals = {"dr": 0.0, "pu": 0.0, "st": 0.0}
    for key, label, group, weight in NON_SIMILARITY_ACTIVITIES:
        raw = reusability.get(key)
        try:
            ratio = 0.0 if raw in (None, "") else float(raw)
        except (TypeError, ValueError):
            ratio = 0.0
        ratio = min(max(ratio, 0.0), 1.0)
        contribution = weight - (ratio * weight)
        group_totals[group] += contribution
        per_activity.append(
            {
                "key": key,
                "label": label,
                "group": group,
                "weight": weight,
                "reusability": ratio,
                "contribution": contribution,
            }
        )

    group_breakdown = [
        {
            "group": group,
            "raw_total": total,
            "group_weight": NON_SIMILARITY_GROUP_WEIGHTS[group],
            "weighted": total * NON_SIMILARITY_GROUP_WEIGHTS[group],
        }
        for group, total in group_totals.items()
    ]
    non_similarity = sum(g["weighted"] for g in group_breakdown)
    return {
        "non_similarity": non_similarity,
        "activities": per_activity,
        "groups": group_breakdown,
    }


def compute_fp(work_type: str, driver_counts: dict) -> dict:
    """Stage 1 — raw Function Points, with the per-driver breakdown that the
    UI shows so an estimate can be defended line by line."""
    drivers = DRIVERS_BY_WORK_TYPE.get(work_type)
    if drivers is None:
        raise ValueError(f"work_type must be one of {WORK_TYPES}")

    breakdown = []
    total = 0.0
    for key, label, coefficient, divisor in drivers:
        count = _count(driver_counts, key)
        if divisor:
            units = roundup(count / divisor)
            contribution = units * coefficient
            rule = f"ROUNDUP({count:g}/{divisor}) x {coefficient:g}"
        else:
            units = count
            contribution = count * coefficient
            rule = f"{count:g} x {coefficient:g}"
        total += contribution
        breakdown.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "coefficient": coefficient,
                "divisor": divisor,
                "units": units,
                "contribution": contribution,
                "rule": rule,
            }
        )
    return {"fp": total, "breakdown": breakdown}


def calculate(
    work_type: str,
    driver_counts: dict,
    complexity: Optional[float] = None,
    non_similarity: Optional[float] = None,
    reusability: Optional[dict] = None,
    config: Optional[dict] = None,
    priority: str = COUNTED_PRIORITY,
    delivery_mode: str = DEFAULT_DELIVERY_MODE,
    hil_leverage: Optional[dict] = None,
) -> dict:
    """The whole model, stages 1-3, with everything it used shown alongside.

    `non_similarity` wins if given; otherwise it is derived from
    `reusability`; otherwise it defaults to 1 (fully new), matching Excel's
    IF(S<>"",S,1).

    `delivery_mode` is applied strictly *after* the Function Point model has
    produced its man-days, and "human" applies a multiplier of exactly 1.0.
    That is what guarantees an existing estimate — which has no delivery mode
    — still computes bit-for-bit what it always did.
    """
    config = config or {}
    productivity = {
        "screen": float(config.get("productivity_screen") or 4.2),
        "batch": float(config.get("productivity_batch") or 4.6),
        "report": float(config.get("productivity_report") or 4.6),
    }
    working_days = float(config.get("working_days_per_month") or 20)
    ratios = {
        "dr": float(config.get("phase_ratio_dr") if config.get("phase_ratio_dr") is not None else 0.30),
        "dnpu": float(config.get("phase_ratio_dnpu") if config.get("phase_ratio_dnpu") is not None else 0.40),
        "iftbct": float(config.get("phase_ratio_iftbct") if config.get("phase_ratio_iftbct") is not None else 0.30),
    }

    fp_result = compute_fp(work_type, driver_counts)

    non_similarity_detail = None
    if non_similarity is not None:
        effective_non_similarity = float(non_similarity)
        non_similarity_source = "manual"
    elif reusability:
        non_similarity_detail = compute_non_similarity(reusability)
        effective_non_similarity = non_similarity_detail["non_similarity"]
        non_similarity_source = "derived"
    else:
        effective_non_similarity = 1.0
        non_similarity_source = "default"

    effective_complexity = 1.0 if complexity in (None, "") else float(complexity)

    # The Priority gate: a row that isn't "M" contributes nothing anywhere.
    counted = priority == COUNTED_PRIORITY

    fp = fp_result["fp"]
    final_fp = fp * effective_complexity
    if counted:
        mm = effective_non_similarity * (final_fp / productivity[work_type])
    else:
        fp = 0.0
        final_fp = 0.0
        mm = 0.0

    # The HUMAN baseline — always computed and always stored, whichever mode
    # is selected, so switching modes is reversible and re-costing after a
    # leverage change never needs the drivers re-entered.
    man_days_human = mm * working_days

    mode = delivery_mode if delivery_mode in DELIVERY_MODES else DEFAULT_DELIVERY_MODE
    if mode == "human_in_loop":
        leverage_detail = compute_delivery_leverage(hil_leverage)
        multiplier = leverage_detail["effort_multiplier"]
    else:
        # Exactly 1.0, not "about 1" — this is the no-regression guarantee.
        leverage_detail = None
        multiplier = 1.0

    mm = mm * multiplier
    man_days = mm * working_days

    return {
        "work_type": work_type,
        "priority": priority,
        "counted": counted,
        "fp": fp,
        "final_fp": final_fp,
        "mm": mm,
        "man_days": man_days,
        "delivery_mode": mode,
        "effort_multiplier_applied": multiplier,
        "man_days_human": man_days_human,
        "man_days_saved": man_days_human - man_days,
        "leverage_detail": leverage_detail,
        "md_dr": mm * ratios["dr"] * working_days,
        "md_dnpu": mm * ratios["dnpu"] * working_days,
        "md_iftbct": mm * ratios["iftbct"] * working_days,
        "complexity": effective_complexity,
        "non_similarity": effective_non_similarity,
        "non_similarity_source": non_similarity_source,
        "non_similarity_detail": non_similarity_detail,
        "productivity_used": productivity[work_type],
        "working_days_per_month": working_days,
        "phase_ratios": ratios,
        # Kept raw (never pre-rounded) so callers decide their own display
        # rounding — see reports/impact_analysis.py for the workbook's own
        # double-rounding behaviour.
        "breakdown": fp_result["breakdown"],
        "not_counted_reason": None if counted else f"Priority is '{priority}', not '{COUNTED_PRIORITY}'",
    }


def driver_schema() -> dict:
    """Field definitions for the calculator form, served from the backend so
    the UI can't drift from the coefficients actually used."""
    return {
        "work_types": [
            {
                "key": work_type,
                "drivers": [
                    {"key": k, "label": label, "coefficient": c, "divisor": d}
                    for k, label, c, d in drivers
                ],
            }
            for work_type, drivers in DRIVERS_BY_WORK_TYPE.items()
        ],
        "non_similarity_activities": [
            {"key": k, "label": label, "group": g, "weight": w}
            for k, label, g, w in NON_SIMILARITY_ACTIVITIES
        ],
        "non_similarity_group_weights": NON_SIMILARITY_GROUP_WEIGHTS,
        "counted_priority": COUNTED_PRIORITY,
        "delivery_modes": list(DELIVERY_MODES),
        "default_delivery_mode": DEFAULT_DELIVERY_MODE,
        "default_hil_leverage": DEFAULT_HIL_LEVERAGE,
    }
