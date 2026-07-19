import os
import secrets
import logging

import openpyxl
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password

logger = logging.getLogger("seed")

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
    """Idempotent: only runs if the users table is completely empty, so
    there's always at least one account able to log in and create others.
    Set ADMIN_EMAIL/ADMIN_PASSWORD to control the bootstrap credentials
    (required for a real deploy); without them, a random password is
    generated and logged once — change it immediately after first login."""
    if db.query(models.User).first() is not None:
        return

    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD")
    generated = password is None
    if generated:
        password = secrets.token_urlsafe(12)

    user = models.User(
        email=email,
        password_hash=hash_password(password),
        role="pmo_admin",
        active=True,
        must_change_password=True,
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
