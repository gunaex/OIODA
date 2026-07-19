from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def iter_weeks(from_date: date, to_date: date):
    """Yields the Monday of every ISO week overlapping [from_date, to_date]."""
    cur = _monday_of(from_date)
    end = _monday_of(to_date)
    while cur <= end:
        yield cur
        cur += timedelta(days=7)


def compute_utilization(master_db: Session, from_date: date, to_date: date) -> list[dict]:
    """Per resource, per week: allocation_percent summed across every
    project that resource is allocated to (an allocation counts for a week
    if its [start_date, end_date] range overlaps that week at all)."""
    resources = master_db.query(models.Resource).order_by(models.Resource.name).all()
    allocations = (
        master_db.query(models.ResourceAllocation)
        .filter(models.ResourceAllocation.start_date <= to_date, models.ResourceAllocation.end_date >= from_date)
        .all()
    )
    allocations_by_resource: dict[int, list] = {}
    for a in allocations:
        allocations_by_resource.setdefault(a.resource_id, []).append(a)

    weeks = list(iter_weeks(from_date, to_date))
    result = []
    for r in resources:
        resource_allocs = allocations_by_resource.get(r.id, [])
        week_rows = []
        for week_start in weeks:
            week_end = week_start + timedelta(days=6)
            total = sum(
                a.allocation_percent
                for a in resource_allocs
                if a.start_date <= week_end and a.end_date >= week_start
            )
            week_rows.append({"week": week_start.isoformat(), "total_percent": total})
        result.append({"resource_id": r.id, "resource_name": r.name, "weeks": week_rows})
    return result
