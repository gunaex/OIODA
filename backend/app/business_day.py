from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models

# Per-process cache of the holiday date set — thai_holidays rarely changes
# (a pmo_admin edits it a few times a year at most), so there's no need to
# re-query on every single business-day calculation. Invalidated explicitly
# by the holidays CRUD endpoints whenever they write.
_holiday_cache: set[date] | None = None


def invalidate_holiday_cache() -> None:
    global _holiday_cache
    _holiday_cache = None


def _holiday_set(db: Session) -> set[date]:
    global _holiday_cache
    if _holiday_cache is None:
        _holiday_cache = {row[0] for row in db.query(models.ThaiHoliday.holiday_date).all()}
    return _holiday_cache


def is_business_day(d: date, db: Session) -> bool:
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in _holiday_set(db)


def add_business_days(start: date, n: int, db: Session) -> date:
    """Moves forward n business days from start (n may be negative to move
    backward). start itself is never counted, matching the everyday meaning
    of "3 business days from today"."""
    d = start
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining > 0:
        d += timedelta(days=step)
        if is_business_day(d, db):
            remaining -= 1
    return d


def business_days_between(start: date, end: date, db: Session) -> int:
    """Count of business days strictly after start, up to and including end.
    Negative if end is before start."""
    if start > end:
        return -business_days_between(end, start, db)
    count = 0
    d = start
    while d < end:
        d += timedelta(days=1)
        if is_business_day(d, db):
            count += 1
    return count


def next_business_day(d: date, db: Session) -> date:
    if is_business_day(d, db):
        return d
    return add_business_days(d, 1, db)
