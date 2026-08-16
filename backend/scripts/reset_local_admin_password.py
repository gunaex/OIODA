#!/usr/bin/env python3
"""Local-only password recovery utility for PM-Again.

This is a RECOVERY tool for LOCAL DEVELOPMENT ONLY. It updates the password
hash of a single local user directly in the local SQLite master database,
using PM-Again's own bcrypt hashing implementation (app.auth.hash_password).
It is NOT production authentication and must never be run against a deployed
instance.

Refuses to run unless:
  - OIDA_LOCAL_RESET=1 is set in the environment (explicit opt-in), AND
  - no deployment environment markers are present (FLY_APP_NAME, RENDER,
    VERCEL, RAILWAY, HEROKU_APP_NAME).

The new password is read interactively (getpass) or from the ephemeral
OIDA_LOCAL_RESET_PASSWORD environment variable. It is never printed, never
written to any file, and never stored in plaintext. The resulting password
hash is also never printed.

Usage:
  OIDA_LOCAL_RESET=1 python scripts/reset_local_admin_password.py --email you@example.com
"""

import argparse
import getpass
import os
import sys

DEPLOY_MARKERS = ("FLY_APP_NAME", "RENDER", "VERCEL", "RAILWAY", "HEROKU_APP_NAME")
MIN_PASSWORD_LENGTH = 8


def _refuse(reason: str) -> None:
    print(f"REFUSED: {reason}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    if os.environ.get("OIDA_LOCAL_RESET") != "1":
        _refuse(
            "OIDA_LOCAL_RESET=1 not set — this utility only runs in an "
            "explicitly local/development context."
        )
    for marker in DEPLOY_MARKERS:
        if os.environ.get(marker):
            _refuse(
                f"deployment marker {marker} is set — refusing to touch a "
                "deployed database."
            )

    parser = argparse.ArgumentParser(
        description="Local-only admin password recovery (development only)."
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the single local user whose password to reset.",
    )
    args = parser.parse_args()

    password = os.environ.get("OIDA_LOCAL_RESET_PASSWORD")
    password_source = "ephemeral environment variable"
    if not password:
        password = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm new password: ")
        if password != confirm:
            _refuse("passwords do not match")
        password_source = "interactive prompt"
    if not password:
        _refuse("no password supplied")
    if len(password) < MIN_PASSWORD_LENGTH:
        _refuse(f"password too short (minimum {MIN_PASSWORD_LENGTH} characters)")

    # Import app modules AFTER the guards so this script cannot even touch
    # the database unless the local-only conditions above pass.
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, backend_dir)

    from app import models
    from app.auth import hash_password
    from app.database import MasterSessionLocal

    with MasterSessionLocal() as db:
        user = db.query(models.User).filter(models.User.email == args.email).first()
        if user is None:
            _refuse(f"no local user with email {args.email!r} — nothing changed")
        user.password_hash = hash_password(password)
        db.commit()
        print(
            f"OK: updated password hash for local user {user.email!r} "
            f"(role {user.role!r})."
        )
        print(
            f"Password was supplied via {password_source}; it was not printed, "
            "logged, or stored."
        )
        print(
            "This is a LOCAL DEVELOPMENT recovery action — production "
            "authentication is untouched."
        )


if __name__ == "__main__":
    main()
