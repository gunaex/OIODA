from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_master_db
from ..auth import get_current_user, require_roles
from ..business_day import invalidate_holiday_cache, add_business_days

# Holidays are shared reference data (like document_templates) — every
# authenticated role can read them (needed anywhere a due date is shown),
# but only pmo_admin can edit, per the spec: "วันหยุดเป็นข้อมูล reference
# กลาง ไม่ควรให้ role อื่นแก้".
router = APIRouter(prefix="/api/holidays", tags=["holidays"], dependencies=[Depends(get_current_user)])

require_pmo_admin = require_roles("pmo_admin")


@router.get("", response_model=list[schemas.HolidayOut])
def list_holidays(year: int = Query(...), db: Session = Depends(get_master_db)):
    return (
        db.query(models.ThaiHoliday)
        .filter(models.ThaiHoliday.year == year)
        .order_by(models.ThaiHoliday.holiday_date)
        .all()
    )


@router.post("", response_model=schemas.HolidayOut)
def create_holiday(
    payload: schemas.HolidayCreate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_pmo_admin),
):
    if db.query(models.ThaiHoliday).filter(models.ThaiHoliday.holiday_date == payload.holiday_date).first():
        raise HTTPException(status_code=400, detail="A holiday already exists on that date")
    obj = models.ThaiHoliday(
        holiday_date=payload.holiday_date,
        name_th=payload.name_th,
        name_en=payload.name_en,
        year=payload.holiday_date.year,
        is_special=payload.is_special,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    invalidate_holiday_cache()
    return obj


@router.put("/{holiday_id}", response_model=schemas.HolidayOut)
def update_holiday(
    holiday_id: int,
    payload: schemas.HolidayUpdate,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_pmo_admin),
):
    obj = db.query(models.ThaiHoliday).filter(models.ThaiHoliday.id == holiday_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Holiday not found")
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(obj, key, value)
    if "holiday_date" in updates:
        obj.year = obj.holiday_date.year
    db.commit()
    db.refresh(obj)
    invalidate_holiday_cache()
    return obj


@router.delete("/{holiday_id}")
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_master_db),
    _user: models.User = Depends(require_pmo_admin),
):
    obj = db.query(models.ThaiHoliday).filter(models.ThaiHoliday.id == holiday_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(obj)
    db.commit()
    invalidate_holiday_cache()
    return {"ok": True}


# Small standalone utility (spec 3.3) — lets the frontend offer "due in N
# business days" as a quick-pick when creating a Task, instead of the user
# having to work out and type an exact date. Not tied to /api/holidays'
# prefix since it's a general-purpose date calculation, not a holiday
# record lookup.
business_days_router = APIRouter(prefix="/api/business-days", tags=["holidays"], dependencies=[Depends(get_current_user)])


@business_days_router.get("/add")
def add_days(
    start: date = Query(...),
    days: int = Query(...),
    db: Session = Depends(get_master_db),
):
    return {"result_date": add_business_days(start, days, db).isoformat()}
