import os
import secrets
import logging
from datetime import date

import openpyxl
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password

logger = logging.getLogger("seed")

# 2026 (B.E. 2569) Thai official holidays, cross-checked against three
# independent sources (Secretariat of the Cabinet's own site returned 403 to
# automated fetches, so this is triangulated from the Cabinet-sourced
# calendars that were reachable — see report to user for exactly which ones
# were excluded pending manual confirmation, e.g. Labor Day, Royal Ploughing
# Ceremony Day). Deliberately NOT guessed — lunar-calendar dates (Makha/
# Visakha/Asalha Bucha) are exactly the ones easiest to get wrong from
# memory alone. pmo_admin can correct/extend this via the holidays UI
# without needing a code change, which is the whole point of this table.
THAI_HOLIDAYS_2026 = [
    (date(2026, 1, 1), "วันขึ้นปีใหม่", "New Year's Day", False),
    (date(2026, 1, 2), "วันหยุดพิเศษ (มติ ครม.)", "Special Holiday (Cabinet Resolution)", True),
    (date(2026, 3, 3), "วันมาฆบูชา", "Makha Bucha Day", False),
    (date(2026, 4, 6), "วันจักรี", "Chakri Memorial Day", False),
    (date(2026, 4, 13), "วันสงกรานต์", "Songkran Festival", False),
    (date(2026, 4, 14), "วันสงกรานต์", "Songkran Festival", False),
    (date(2026, 4, 15), "วันสงกรานต์", "Songkran Festival", False),
    (date(2026, 5, 4), "วันฉัตรมงคล", "Coronation Day", False),
    (date(2026, 5, 31), "วันวิสาขบูชา", "Visakha Bucha Day", False),
    (date(2026, 6, 1), "วันหยุดชดเชยวันวิสาขบูชา", "Substitute for Visakha Bucha Day", False),
    (date(2026, 6, 3), "วันเฉลิมพระชนมพรรษาสมเด็จพระนางเจ้าสุทิดาฯ", "HM Queen Suthida's Birthday", False),
    (date(2026, 7, 28), "วันเฉลิมพระชนมพรรษาพระบาทสมเด็จพระวชิรเกล้าเจ้าอยู่หัว", "HM King Vajiralongkorn's Birthday", False),
    (date(2026, 7, 29), "วันอาสาฬหบูชา", "Asalha Bucha Day", False),
    (date(2026, 8, 12), "วันเฉลิมพระชนมพรรษาสมเด็จพระนางเจ้าสิริกิติ์ฯ (วันแม่แห่งชาติ)", "Queen Mother's Birthday / Mother's Day", False),
    (date(2026, 10, 13), "วันนวมินทรมหาราช", "HM King Bhumibol Memorial Day", False),
    (date(2026, 10, 23), "วันปิยมหาราช", "Chulalongkorn Memorial Day", False),
    (date(2026, 12, 5), "วันคล้ายวันพระบรมราชสมภพ ร.9 (วันพ่อแห่งชาติ)", "King Bhumibol's Birthday / Father's Day", False),
    (date(2026, 12, 7), "วันหยุดชดเชยวันพ่อแห่งชาติ", "Substitute for Father's Day", False),
    (date(2026, 12, 10), "วันรัฐธรรมนูญ", "Constitution Day", False),
    (date(2026, 12, 31), "วันสิ้นปี", "New Year's Eve", False),
]

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_data")
DOCUMENT_TEMPLATE_SEED_PATH = os.path.join(SEED_DIR, "DocumentTemplateMaster_Seed.xlsx")

EXPECTED_COLUMNS = [
    "doc_code",
    "doc_name",
    "phase_code",
    "phase_name",
    "doc_set_no",
    "doc_set_name",
    "mandatory_critical",
    "mandatory_non_critical",
    "mandatory_ma",
    "mandatory_rollout",
    "defined_by",
    "documented_by",
    "approved_by",
]


def seed_document_templates(db: Session):
    """Idempotent: only imports if the table is empty, so this is safe to
    call on every app startup."""
    if db.query(models.DocumentTemplate).first() is not None:
        return

    if not os.path.exists(DOCUMENT_TEMPLATE_SEED_PATH):
        return

    wb = openpyxl.load_workbook(DOCUMENT_TEMPLATE_SEED_PATH)
    ws = wb["document_templates_seed"]
    rows = list(ws.iter_rows(values_only=True))
    header, data_rows = rows[0], rows[1:]

    header = [str(h).strip() for h in header]
    if header != EXPECTED_COLUMNS:
        raise ValueError(
            f"document_templates_seed sheet header does not match expected columns.\n"
            f"Expected: {EXPECTED_COLUMNS}\nFound:    {header}"
        )

    for row in data_rows:
        record = dict(zip(EXPECTED_COLUMNS, row))
        if record["doc_code"] is None:
            continue
        db.add(models.DocumentTemplate(**record))

    db.commit()


def seed_bootstrap_admin(db: Session):
    """Idempotent: ensures at least one account able to log in and create
    others. Set ADMIN_EMAIL/ADMIN_PASSWORD to control the bootstrap
    credentials (required for a real deploy); without them, a random password
    is generated and logged once — change it immediately after first login.
    The configured ADMIN_EMAIL account is created if missing so ecosystem SSO
    can map the Account Again human identity to it by email."""
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD")

    if db.query(models.User).filter(models.User.email == email).first() is not None:
        return

    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)

    user = models.User(
        email=email,
        password_hash=hash_password(password),
        role="pmo_admin",
        active=True,
        must_change_password=generated,
    )
    db.add(user)
    db.commit()

    if generated:
        logger.warning(
            "No users existed — bootstrapped an admin account.\n"
            "  email:    %s\n"
            "  password: %s\n"
            "This password was randomly generated and is only shown here, once. "
            "Log in and consider rotating it (or set ADMIN_EMAIL/ADMIN_PASSWORD "
            "before first startup next time to control it directly).",
            email,
            password,
        )
    else:
        logger.info("Bootstrapped admin account %s from ADMIN_EMAIL/ADMIN_PASSWORD.", email)


def seed_thai_holidays(db: Session):
    """Idempotent: only inserts holidays not already present (matched by
    date), so re-running after a pmo_admin has edited/added entries via the
    holidays UI never overwrites their changes or duplicates rows."""
    existing_dates = {d for (d,) in db.query(models.ThaiHoliday.holiday_date).all()}
    added = 0
    for holiday_date, name_th, name_en, is_special in THAI_HOLIDAYS_2026:
        if holiday_date in existing_dates:
            continue
        db.add(
            models.ThaiHoliday(
                holiday_date=holiday_date,
                name_th=name_th,
                name_en=name_en,
                year=holiday_date.year,
                is_special=is_special,
            )
        )
        added += 1
    if added:
        db.commit()
