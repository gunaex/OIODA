import os
import logging
import secrets

from sqlalchemy.orm import Session

from . import models
from .auth import hash_password

logger = logging.getLogger("seed")


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
        role="ADMIN",
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
