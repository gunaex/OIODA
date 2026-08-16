"""Progress Matrix (予定実績表 / Yotei-Jisseki) engine.

Plan dates come from gantt_items.baseline_start / baseline_end, reached via
the generalised linked_entity_type / linked_entity_id link.

Actual dates are never entered by hand — they are derived from activity_log
status changes using workflow_definitions.PROGRESS_TRIGGER_STATUS.

The analysis layer (status/delay, cross-check, forecast, recovery) only ever
states things it can point at a row of data for. Every suggestion carries the
`data_points` it was computed from; nothing generic is emitted.
"""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .business_day import business_days_between
from .slippage import _historical_avg_delay_by_phase
from .workflow_definitions import PROGRESS_TRIGGER_STATUS

# How far behind plan before the matrix calls a row "late" rather than
# "slightly off". Business days, consistent with the Thai Business-day Engine
# used everywhere else.
LATE_THRESHOLD_DAYS = 1

ENTITY_MODELS = {
    "task": models.Task,
    "function": models.Function,
    "board_item": models.BoardItem,
}


# ---------- entity field access ----------


def entity_code(obj, entity_type: str) -> Optional[str]:
    return {
        "task": lambda: obj.task_code,
        "function": lambda: obj.function_code,
        "board_item": lambda: obj.item_code,
    }[entity_type]()


def entity_title(obj, entity_type: str) -> str:
    return obj.name if entity_type == "function" else obj.title


# ---------- actual dates, derived from activity_log ----------


def compute_actual_dates(db: Session, entity_type: str, entity_id: int) -> dict:
    """Actual dates for one entity, in three layers rather than one number.

    Returns derived (from activity_log), override (hand-entered), and the
    effective value each consumer should use, plus which layer it came from
    and whether the two disagree.

    Never guesses: no matching status change and no override means no date.
    """
    return _bulk_actual_dates_detail(db, entity_type, [entity_id]).get(
        entity_id, _actual_dates_detail(None, None, None)
    )


def _actual_dates_detail(derived: Optional[tuple], override_row, _unused=None) -> dict:
    """Combines the derived pair and the override row into the shape every
    consumer reads. `override ?? derived`, field by field — an override that
    only fills in the start date leaves the derived end date in place."""
    derived_start, derived_end = derived or (None, None)
    override_start = override_row.actual_start_override if override_row else None
    override_end = override_row.actual_end_override if override_row else None

    effective_start = override_start if override_start is not None else derived_start
    effective_end = override_end if override_end is not None else derived_end

    def source(override_value, derived_value):
        if override_value is not None:
            return "override"
        return "derived" if derived_value is not None else None

    # A conflict is only meaningful where BOTH layers have an opinion and
    # they differ. An override filling a gap the log never recorded is the
    # normal case, not a conflict.
    conflict_start = (
        derived_start is not None and override_start is not None and derived_start != override_start
    )
    conflict_end = derived_end is not None and override_end is not None and derived_end != override_end

    return {
        "actual_start_derived": derived_start,
        "actual_start_override": override_start,
        "actual_start": effective_start,
        "actual_start_source": source(override_start, derived_start),
        "actual_end_derived": derived_end,
        "actual_end_override": override_end,
        "actual_end": effective_end,
        "actual_end_source": source(override_end, derived_end),
        "has_override": override_row is not None and (override_start is not None or override_end is not None),
        "has_conflict": conflict_start or conflict_end,
        "conflict_fields": [
            f for f, c in (("actual_start", conflict_start), ("actual_end", conflict_end)) if c
        ],
        "override_reason": override_row.reason if override_row else None,
        "override_by": override_row.created_by if override_row else None,
    }


def _override_rows(db: Session, entity_type: str, entity_ids: list[int]) -> dict:
    if not entity_ids:
        return {}
    rows = (
        db.query(models.ProgressActualOverride)
        .filter(
            models.ProgressActualOverride.entity_type == entity_type,
            models.ProgressActualOverride.entity_id.in_(entity_ids),
        )
        .all()
    )
    return {r.entity_id: r for r in rows}


def _bulk_actual_dates_detail(db: Session, entity_type: str, entity_ids: list[int]) -> dict:
    """The three-layer view for a whole entity type in two queries."""
    derived = _bulk_actual_dates(db, entity_type, entity_ids)
    overrides = _override_rows(db, entity_type, entity_ids)
    return {
        entity_id: _actual_dates_detail(derived.get(entity_id), overrides.get(entity_id))
        for entity_id in entity_ids
    }


def _bulk_actual_dates(db: Session, entity_type: str, entity_ids: list[int]) -> dict[int, tuple]:
    """Same derivation as compute_actual_dates but for a whole entity type in
    one query — the matrix would otherwise issue two queries per row."""
    config = PROGRESS_TRIGGER_STATUS.get(entity_type)
    if not config or not entity_ids:
        return {}

    rows = (
        db.query(models.ActivityLog)
        .filter(
            models.ActivityLog.entity_type == entity_type,
            # Only status changes count. The spec spells this out for the
            # start trigger; applying it to the end trigger too stops an
            # unrelated field that happens to hold the text "Done" from
            # inventing a completion date.
            models.ActivityLog.field_changed == "status",
            models.ActivityLog.entity_id.in_(entity_ids),
        )
        .order_by(models.ActivityLog.changed_at, models.ActivityLog.id)
        .all()
    )

    start_value = config["start"]
    end_values = set(config["end"])
    result: dict[int, tuple] = {}
    for log in rows:
        if log.changed_at is None:
            continue
        changed_on = log.changed_at.date()
        actual_start, actual_end = result.get(log.entity_id, (None, None))
        # Rows arrive oldest-first, so the first match wins for each side.
        if log.new_value == start_value and actual_start is None:
            actual_start = changed_on
        if log.new_value in end_values and actual_end is None:
            actual_end = changed_on
        result[log.entity_id] = (actual_start, actual_end)
    return result


# ---------- plan dates, from gantt_items ----------


def _plan_dates_by_entity(db: Session, entity_type: str) -> dict[int, tuple]:
    """gantt_items rows owned by this entity type, keyed by entity id.

    Reads linked_entity_type/linked_entity_id (which the migration backfilled
    for every pre-existing task-linked row), never linked_task_id — that
    column stays exclusively the Gantt bar chart's."""
    rows = (
        db.query(models.GanttItem)
        .filter(models.GanttItem.linked_entity_type == entity_type, models.GanttItem.linked_entity_id.isnot(None))
        .order_by(models.GanttItem.id)
        .all()
    )
    plan: dict[int, tuple] = {}
    for g in rows:
        # An entity could in principle own more than one gantt row (a task
        # with several bars). Take the widest span so the plan window covers
        # everything scheduled for it.
        existing = plan.get(g.linked_entity_id)
        start, end = g.baseline_start, g.baseline_end
        if existing:
            prev_start, prev_end, prev_id = existing
            start = min([d for d in (start, prev_start) if d], default=None)
            end = max([d for d in (end, prev_end) if d], default=None)
            plan[g.linked_entity_id] = (start, end, prev_id)
        else:
            plan[g.linked_entity_id] = (start, end, g.id)
    return plan


# ---------- symbols ----------


def _symbols_by_date(row: dict) -> dict[str, str]:
    """Maps each date that carries a marker to the symbol shown in that cell.

    PS = Plan Start, PR = Plan Result (plan end), RS = Result Start,
    R = Result (actual end). When a plan marker and an actual marker land on
    the same date they are merged into one cell rather than fighting over it:
    PSR (plan start + plan end same day), RSR (actual start + end same day),
    and combined forms like "PS/RS" when a plan and an actual coincide.
    """
    markers: dict[str, list[str]] = {}

    def add(d, symbol):
        if d:
            markers.setdefault(d.isoformat(), []).append(symbol)

    add(row["plan_start"], "PS")
    add(row["plan_end"], "PR")
    add(row["actual_start"], "RS")
    add(row["actual_end"], "R")

    # Which days carry a marker that came from a hand-entered date. The UI
    # draws those with a dashed border so a typed-in actual is never mistaken
    # for one the log can prove.
    overridden_days = {
        d.isoformat()
        for d in (row.get("actual_start_override"), row.get("actual_end_override"))
        if d
    }

    cells: dict[str, str] = {}
    for day, syms in markers.items():
        plan_part = None
        if "PS" in syms and "PR" in syms:
            plan_part = "PSR"  # planned to start and finish on the same day
        elif "PS" in syms:
            plan_part = "PS"
        elif "PR" in syms:
            plan_part = "PR"

        actual_part = None
        if "RS" in syms and "R" in syms:
            actual_part = "RSR"  # actually started and finished on the same day
        elif "RS" in syms:
            actual_part = "RS"
        elif "R" in syms:
            actual_part = "R"

        # A plan marker and an actual marker on the same date share the cell.
        cells[day] = "/".join(p for p in (plan_part, actual_part) if p)
    return cells, overridden_days


# ---------- analysis: status / delay ----------


def _analyse_row(row: dict, master_db: Session, today: date) -> dict:
    """Status + delay, measured in business days against the plan. Returns
    None-valued fields wherever the underlying date is missing — an unknown
    delay is reported as unknown, never as zero."""
    plan_start, plan_end = row["plan_start"], row["plan_end"]
    actual_start, actual_end = row["actual_start"], row["actual_end"]

    if actual_end:
        status = "done"
    elif actual_start:
        status = "in_progress"
    else:
        status = "not_started"

    # Start delay: against the actual start if it happened, otherwise against
    # today for something that was due to start and hasn't.
    start_delay = None
    if plan_start:
        if actual_start:
            start_delay = business_days_between(plan_start, actual_start, master_db)
        elif today > plan_start:
            start_delay = business_days_between(plan_start, today, master_db)

    end_delay = None
    if plan_end:
        if actual_end:
            end_delay = business_days_between(plan_end, actual_end, master_db)
        elif today > plan_end:
            end_delay = business_days_between(plan_end, today, master_db)

    if status == "done":
        health = "late" if (end_delay or 0) > LATE_THRESHOLD_DAYS else "on_track"
    elif plan_end and today > plan_end:
        health = "overdue"
    elif status == "not_started" and plan_start and today > plan_start:
        health = "not_started_late"
    elif (start_delay or 0) > LATE_THRESHOLD_DAYS:
        health = "late"
    elif plan_start or plan_end:
        health = "on_track"
    else:
        health = "unplanned"  # no baseline dates set at all

    return {
        "status": status,
        "health": health,
        "start_delay_days": start_delay,
        "end_delay_days": end_delay,
    }


# ---------- analysis: cross-check ----------

# Which entity statuses mean "this thing is finished", per entity type — the
# same table the actual-date derivation uses, so the two can't disagree.
def _is_end_status(entity_type: str, status: Optional[str]) -> bool:
    return status in set(PROGRESS_TRIGGER_STATUS[entity_type]["end"])


def _is_start_status(entity_type: str, status: Optional[str]) -> bool:
    return status == PROGRESS_TRIGGER_STATUS[entity_type]["start"]


def _cross_check(row: dict, entity_type: str, current_status: Optional[str]) -> list[dict]:
    """Contradictions between what the entity's own status field says and what
    its activity_log / plan dates say. Each finding names the two data points
    that disagree, so it can be verified rather than taken on trust."""
    findings = []
    actual_start, actual_end = row["actual_start"], row["actual_end"]
    plan_start, plan_end = row["plan_start"], row["plan_end"]

    # Spec 5.3 — an informational flag, not an error. Someone reading the
    # matrix alongside a client should be able to tell at a glance which
    # figures the log can prove and which were typed in.
    if row.get("has_override"):
        parts = []
        if row.get("actual_start_override"):
            parts.append(f"start={row['actual_start_override'].isoformat()}")
        if row.get("actual_end_override"):
            parts.append(f"end={row['actual_end_override'].isoformat()}")
        findings.append(
            {
                "code": "manual_actual_override",
                "severity": "info",
                "message": (
                    "Actual date entered by hand rather than derived from the activity log ("
                    + ", ".join(parts)
                    + ")"
                    + (f" — reason: {row['override_reason']}" if row.get("override_reason") else "")
                ),
                "data_points": parts + ([f"by={row['override_by']}"] if row.get("override_by") else []),
            }
        )

    if row.get("has_conflict"):
        detail = []
        for field in row.get("conflict_fields") or []:
            derived_value = row.get(f"{field}_derived")
            override_value = row.get(f"{field}_override")
            detail.append(
                f"{field}: log says {derived_value.isoformat()}, override says {override_value.isoformat()}"
            )
        findings.append(
            {
                "code": "override_conflicts_with_log",
                "severity": "warning",
                "message": (
                    "A hand-entered actual date disagrees with what the activity log recorded. "
                    "The entered value is the one being used for delays and forecasts. — "
                    + "; ".join(detail)
                ),
                "data_points": detail,
            }
        )

    if _is_end_status(entity_type, current_status) and actual_end is None:
        findings.append(
            {
                "code": "done_without_log",
                "message": (
                    f"Status is '{current_status}' but activity_log has no status change to "
                    f"{'/'.join(PROGRESS_TRIGGER_STATUS[entity_type]['end'])} — the matrix cannot show a "
                    f"completion marker for it."
                ),
                "data_points": [f"{entity_type}.status={current_status}", "activity_log: no matching end transition"],
            }
        )

    # This finding's claim is specifically about what the LOG recorded, so it
    # reads the derived layer. Using the effective value here would have it
    # announce "activity_log records completion" about a date somebody typed.
    derived_end = row.get("actual_end_derived")
    if derived_end is not None and not _is_end_status(entity_type, current_status):
        findings.append(
            {
                "code": "log_done_status_not",
                "message": (
                    f"activity_log records completion on {derived_end.isoformat()} but the status has since "
                    f"moved back to '{current_status}'."
                ),
                "data_points": [f"activity_log.changed_at={derived_end.isoformat()}", f"{entity_type}.status={current_status}"],
            }
        )

    if actual_start is None and _is_start_status(entity_type, current_status):
        findings.append(
            {
                "code": "in_progress_without_log",
                "message": (
                    f"Status is '{current_status}' but no start transition was logged, so the matrix has no "
                    f"RS marker to place."
                ),
                "data_points": [f"{entity_type}.status={current_status}", "activity_log: no matching start transition"],
            }
        )

    if actual_start and actual_end and actual_end < actual_start:
        findings.append(
            {
                "code": "end_before_start",
                "message": f"Logged completion ({actual_end.isoformat()}) precedes the logged start ({actual_start.isoformat()}).",
                "data_points": [f"actual_start={actual_start.isoformat()}", f"actual_end={actual_end.isoformat()}"],
            }
        )

    if plan_start and plan_end and plan_end < plan_start:
        findings.append(
            {
                "code": "plan_end_before_start",
                "message": f"Planned end ({plan_end.isoformat()}) is before the planned start ({plan_start.isoformat()}).",
                "data_points": [f"baseline_start={plan_start.isoformat()}", f"baseline_end={plan_end.isoformat()}"],
            }
        )

    if (plan_start is None) != (plan_end is None):
        present = "baseline_start" if plan_start else "baseline_end"
        missing = "baseline_end" if plan_start else "baseline_start"
        findings.append(
            {
                "code": "half_planned",
                "message": f"Only {present} is set — {missing} is empty, so the plan bar has no end.",
                "data_points": [f"{present}={(plan_start or plan_end).isoformat()}", f"{missing}=null"],
            }
        )

    return findings


# ---------- analysis: forecast ----------


def _forecast(row: dict, analysis: dict, phase: Optional[str], avg_delay_by_phase: dict, master_db: Session) -> Optional[dict]:
    """Expected completion for a row that isn't finished yet.

    Reuses the Slippage Predictor's own historical average delay per phase
    (`slippage._historical_avg_delay_by_phase`) rather than inventing a second
    forecasting rule — and inherits its refusal to predict from fewer than
    MIN_HISTORY_SAMPLES completed items, so a phase with thin history simply
    gets no forecast."""
    if analysis["status"] == "done" or not row["plan_end"]:
        return None
    avg_delay = avg_delay_by_phase.get(phase) if phase else None
    if avg_delay is None:
        return None
    forecast_date = row["plan_end"] + timedelta(days=round(avg_delay))
    return {
        "forecast_end": forecast_date.isoformat(),
        "basis": (
            f"plan end {row['plan_end'].isoformat()} + average delay of {round(avg_delay, 1)} days "
            f"observed on completed {phase} items"
        ),
        "data_points": [f"baseline_end={row['plan_end'].isoformat()}", f"avg_delay_{phase}={round(avg_delay, 1)}d"],
        "source": "slippage_predictor.historical_avg_delay_by_phase",
    }


# ---------- analysis: recovery suggestions ----------


def _recovery_suggestions(row: dict, analysis: dict, entity_type: str, obj, allocation_index: dict) -> list[dict]:
    """Concrete next actions, each tied to the data that triggered it.

    Deliberately narrow: a suggestion is only produced when a specific
    condition in this project's own data fires. There is no catch-all advice
    for rows that look fine, and no suggestion is emitted without the
    `data_points` that justify it.
    """
    out = []
    plan_start, plan_end = row["plan_start"], row["plan_end"]
    owner = getattr(obj, "owner", None)

    if analysis["health"] == "unplanned":
        out.append(
            {
                "code": "set_plan_dates",
                "action": "Set plan dates so this item can be tracked against a baseline.",
                "data_points": ["baseline_start=null", "baseline_end=null"],
            }
        )
        return out  # nothing else can be said without a baseline

    if analysis["health"] == "not_started_late" and plan_start:
        out.append(
            {
                "code": "start_overdue",
                "action": (
                    f"Should have started on {plan_start.isoformat()} — "
                    f"{analysis['start_delay_days']} business days ago and still not started"
                    + (f". Owner on record: {owner}." if owner else " and has no owner assigned.")
                ),
                "data_points": [
                    f"baseline_start={plan_start.isoformat()}",
                    f"start_delay={analysis['start_delay_days']}d",
                    f"owner={owner or 'unassigned'}",
                ],
            }
        )

    if analysis["health"] == "overdue" and plan_end:
        out.append(
            {
                "code": "end_overdue",
                "action": (
                    f"Past its planned end of {plan_end.isoformat()} by {analysis['end_delay_days']} business days "
                    f"with no completion logged — re-baseline it or escalate."
                ),
                "data_points": [
                    f"baseline_end={plan_end.isoformat()}",
                    f"end_delay={analysis['end_delay_days']}d",
                    f"status={getattr(obj, 'status', None)}",
                ],
            }
        )

    # Owner load is only mentioned when this project's own allocation rows say
    # the owner is committed elsewhere over the same window.
    if owner and analysis["health"] in ("overdue", "not_started_late", "late"):
        load = allocation_index.get(owner)
        if load:
            out.append(
                {
                    "code": "owner_committed_elsewhere",
                    "action": (
                        f"{owner} is allocated {load['percent']}% across {load['count']} "
                        f"allocation row(s) overlapping this window — rebalancing or reassigning is likely "
                        f"needed before the date can be recovered."
                    ),
                    "data_points": [
                        f"owner={owner}",
                        f"allocation_percent_total={load['percent']}",
                        f"allocation_rows={load['count']}",
                    ],
                }
            )

    if not owner and analysis["health"] in ("overdue", "not_started_late"):
        out.append(
            {
                "code": "no_owner",
                "action": "No owner is set, so there is nobody to chase — assign one.",
                "data_points": [f"{entity_type}.owner=null"],
            }
        )

    return out


def _allocation_index(master_db: Session, slug: str, window_start: Optional[date], window_end: Optional[date]) -> dict:
    """Resource commitments per person over the matrix window, from the
    existing resource_allocations data. Used only to back up a recovery
    suggestion with a real number — never to generate one on its own."""
    if not window_start or not window_end:
        return {}
    rows = (
        master_db.query(models.ResourceAllocation, models.Resource)
        .join(models.Resource, models.Resource.id == models.ResourceAllocation.resource_id)
        .filter(
            models.ResourceAllocation.project_slug == slug,
            models.ResourceAllocation.start_date <= window_end,
            models.ResourceAllocation.end_date >= window_start,
        )
        .all()
    )
    index: dict[str, dict] = {}
    for allocation, resource in rows:
        entry = index.setdefault(resource.name, {"percent": 0, "count": 0})
        entry["percent"] += allocation.allocation_percent
        entry["count"] += 1
    return index


# ---------- the matrix itself ----------


def build_progress_matrix(
    slug: str,
    db: Session,
    master_db: Session,
    entity_types: list[str],
    phase: Optional[str] = None,
    owner: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    board_flavours: Optional[set] = None,
) -> dict:
    today = date.today()
    avg_delay_by_phase = _historical_avg_delay_by_phase(db)
    allocation_index = _allocation_index(master_db, slug, date_from, date_to)

    rows = []
    for entity_type in entity_types:
        model = ENTITY_MODELS[entity_type]
        query = db.query(model)
        if phase:
            query = query.filter(model.phase == phase)
        if owner:
            query = query.filter(model.owner == owner)
        if entity_type == "board_item" and board_flavours:
            # "Issue / Incident / Backlog" are one table; the UI filters them
            # as if they were separate entity types.
            query = query.filter(model.item_type.in_(list(board_flavours)))
        entities = query.order_by(model.id).all()
        if not entities:
            continue

        plan_index = _plan_dates_by_entity(db, entity_type)
        actual_index = _bulk_actual_dates_detail(db, entity_type, [e.id for e in entities])

        for obj in entities:
            plan_start, plan_end, gantt_item_id = plan_index.get(obj.id, (None, None, None))
            actuals = actual_index.get(obj.id) or _actual_dates_detail(None, None)
            row = {
                "entity_type": entity_type,
                "entity_id": obj.id,
                "entity_code": entity_code(obj, entity_type),
                "entity_title": entity_title(obj, entity_type),
                "phase": obj.phase,
                "owner": obj.owner,
                "current_status": obj.status,
                "gantt_item_id": gantt_item_id,
                "plan_start": plan_start,
                "plan_end": plan_end,
                # row["actual_start"] / ["actual_end"] hold the EFFECTIVE
                # values. Everything downstream — symbols, delay, cross-check,
                # forecast, recovery — reads those keys and therefore gets the
                # override automatically. The derived and override layers ride
                # along under their own keys for display, and nothing computes
                # from them directly.
                **actuals,
            }
            if entity_type == "board_item":
                row["item_type"] = obj.item_type

            analysis = _analyse_row(row, master_db, today)
            row.update(analysis)
            row["symbols"], row["overridden_days"] = _symbols_by_date(row)
            row["cross_check"] = _cross_check(row, entity_type, obj.status)
            row["forecast"] = _forecast(row, analysis, obj.phase, avg_delay_by_phase, master_db)
            row["recovery"] = _recovery_suggestions(row, analysis, entity_type, obj, allocation_index)
            rows.append(row)

    rows = [r for r in rows if _in_window(r, date_from, date_to)]
    rows.sort(key=_sort_key)

    return {
        "from": date_from.isoformat() if date_from else None,
        "to": date_to.isoformat() if date_to else None,
        "rows": [_serialize(r) for r in rows],
        "summary": _summarize(rows),
    }


def _in_window(row: dict, date_from: Optional[date], date_to: Optional[date]) -> bool:
    """A row is in scope when its plan/actual span overlaps the window.

    Rows with no dates at all are always kept: an item with no baseline is
    precisely what the matrix exists to surface, and hiding it behind a date
    filter would make the gap invisible."""
    if not date_from and not date_to:
        return True
    dates = [d for d in (row["plan_start"], row["plan_end"], row["actual_start"], row["actual_end"]) if d]
    if not dates:
        return True
    if date_from and max(dates) < date_from:
        return False
    if date_to and min(dates) > date_to:
        return False
    return True


_HEALTH_ORDER = {"overdue": 0, "not_started_late": 1, "late": 2, "unplanned": 3, "on_track": 4}


def _sort_key(row: dict):
    # Worst first, then by plan start so the eye can follow the schedule.
    return (
        _HEALTH_ORDER.get(row["health"], 9),
        row["plan_start"] or date.max,
        row["entity_type"],
        row["entity_id"],
    )


DATE_KEYS = (
    "plan_start",
    "plan_end",
    "actual_start",
    "actual_end",
    "actual_start_derived",
    "actual_start_override",
    "actual_end_derived",
    "actual_end_override",
)


def _serialize(row: dict) -> dict:
    out = dict(row)
    for key in DATE_KEYS:
        value = row.get(key)
        out[key] = value.isoformat() if value else None
    out["overridden_days"] = sorted(row.get("overridden_days") or [])
    return out


def _summarize(rows: list[dict]) -> dict:
    by_health: dict[str, int] = {}
    for row in rows:
        by_health[row["health"]] = by_health.get(row["health"], 0) + 1
    delays = [r["end_delay_days"] for r in rows if r["end_delay_days"] is not None and r["end_delay_days"] > 0]
    return {
        "total": len(rows),
        "by_health": by_health,
        "cross_check_count": sum(len(r["cross_check"]) for r in rows),
        "recovery_count": sum(len(r["recovery"]) for r in rows),
        "worst_end_delay_days": max(delays) if delays else None,
        "average_end_delay_days": round(sum(delays) / len(delays), 1) if delays else None,
    }


# ---------- plan-date upsert ----------


def upsert_actual_override(
    db: Session,
    entity_type: str,
    entity_id: int,
    actual_start_override: Optional[date],
    actual_end_override: Optional[date],
    reason: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Optional[models.ProgressActualOverride]:
    """Writes (or clears) the hand-entered actual dates for one entity.

    Touches only the override table. The derived value is read-only for the
    whole of this module and nothing here writes to activity_log's status
    records — see log_override_change for what does get recorded.
    """
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return None
    if db.query(model).filter(model.id == entity_id).first() is None:
        return None

    row = (
        db.query(models.ProgressActualOverride)
        .filter(
            models.ProgressActualOverride.entity_type == entity_type,
            models.ProgressActualOverride.entity_id == entity_id,
        )
        .first()
    )
    if row is None:
        row = models.ProgressActualOverride(entity_type=entity_type, entity_id=entity_id)
        db.add(row)

    row.actual_start_override = actual_start_override
    row.actual_end_override = actual_end_override
    row.reason = reason
    row.created_by = created_by
    db.commit()
    db.refresh(row)
    return row


def delete_actual_override(db: Session, entity_type: str, entity_id: int) -> bool:
    """Removes the override so the entity falls straight back to whatever the
    activity log derives — no residue, no remembered value."""
    row = (
        db.query(models.ProgressActualOverride)
        .filter(
            models.ProgressActualOverride.entity_type == entity_type,
            models.ProgressActualOverride.entity_id == entity_id,
        )
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def upsert_plan_dates(
    db: Session,
    entity_type: str,
    entity_id: int,
    baseline_start: Optional[date],
    baseline_end: Optional[date],
) -> models.GanttItem:
    """Writes plan dates for any entity into gantt_items.

    For a Function / Board Item with no Gantt row yet this creates one purely
    to hold the baseline: no dependencies, not a milestone. For a Task it
    updates the row the Gantt bar chart already owns rather than making a
    second one, so the two views stay in agreement."""
    model = ENTITY_MODELS[entity_type]
    obj = db.query(model).filter(model.id == entity_id).first()
    if obj is None:
        return None

    item = (
        db.query(models.GanttItem)
        .filter(
            models.GanttItem.linked_entity_type == entity_type,
            models.GanttItem.linked_entity_id == entity_id,
        )
        .order_by(models.GanttItem.id)
        .first()
    )
    # A pre-existing task row might predate the backfill in an edge case
    # (created while this request was in flight); fall back to the original
    # column so a task never ends up with two rows.
    if item is None and entity_type == "task":
        item = (
            db.query(models.GanttItem)
            .filter(models.GanttItem.linked_task_id == entity_id)
            .order_by(models.GanttItem.id)
            .first()
        )

    if item is None:
        # start_date/end_date are NOT NULL on gantt_items, so a brand new row
        # mirrors the baseline until someone moves the actual bar.
        fallback_start = baseline_start or baseline_end
        fallback_end = baseline_end or baseline_start
        if fallback_start is None:
            return None
        code = entity_code(obj, entity_type)
        item = models.GanttItem(
            name=f"{code} {entity_title(obj, entity_type)}".strip() if code else entity_title(obj, entity_type),
            phase=obj.phase,
            start_date=fallback_start,
            end_date=fallback_end,
            progress=0,
            dependencies=None,
            linked_entity_type=entity_type,
            linked_entity_id=entity_id,
            is_milestone=False,
        )
        db.add(item)

    item.baseline_start = baseline_start
    item.baseline_end = baseline_end
    # Keep the generalised link populated even when an old row was found via
    # linked_task_id.
    item.linked_entity_type = entity_type
    item.linked_entity_id = entity_id
    db.commit()
    db.refresh(item)
    return item
