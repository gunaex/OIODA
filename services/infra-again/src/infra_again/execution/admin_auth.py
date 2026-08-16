"""Phase 9.1.1 Admin Password Safety Belt.

Argon2id-based admin password verification for real AWS AIRLOCK.
NEVER stores plaintext. NEVER logs password. NEVER includes in evidence.

Usage:
  1. Setup: python scripts/set-admin-password.py
  2. Verify: AdminAuth.verify(password) → bool
  3. Storage: ~/.config/infra-again/admin-auth.json (0600)
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Optional


# ── Storage ──────────────────────────────────────────────
ADMIN_AUTH_DIR = Path.home() / ".config" / "infra-again"
ADMIN_AUTH_FILE = ADMIN_AUTH_DIR / "admin-auth.json"

# ── Fallback env (acceptance only, NOT for production) ──
ACCEPTANCE_HASH_ENV = "INFRA_AGAIN_ADMIN_PASSWORD_HASH"


class AdminAuth:
    """Admin password safety belt for real AWS AIRLOCK."""

    MAX_ATTEMPTS = 3

    def __init__(self):
        self._attempts = 0
        self._locked = False

    # ── Password Hashing ─────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with Argon2id if available, fallback to PBKDF2-SHA256."""
        try:
            from argon2.low_level import hash_secret, Type
            salt = secrets.token_bytes(16)
            encoded = hash_secret(
                secret=password.encode("utf-8"),
                salt=salt,
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                type=Type.ID,
            )
            # hash_secret returns bytes; decode to string for storage
            if isinstance(encoded, bytes):
                return f"argon2id${encoded.decode('utf-8')}"
            return f"argon2id${encoded}"
        except ImportError:
            pass

        # Fallback: PBKDF2-SHA256
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000, dklen=32)
        return f"pbkdf2-sha256$600000${salt.hex()}${dk.hex()}"

    @staticmethod
    def verify_password(stored_hash: str, password: str) -> bool:
        """Verify password against stored hash."""
        parts = stored_hash.split("$", 1)
        algorithm = parts[0]

        if algorithm == "argon2id":
            try:
                from argon2.low_level import verify_secret, Type
                encoded = parts[1].encode("utf-8")
                verify_secret(encoded, password.encode("utf-8"), Type.ID)
                return True
            except Exception:
                return False

        elif algorithm == "pbkdf2-sha256":
            rest = parts[1].split("$")
            iterations = int(rest[0])
            salt = bytes.fromhex(rest[1])
            stored = bytes.fromhex(rest[2])
            computed = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, iterations, dklen=32,
            )
            return secrets.compare_digest(computed, stored)

        return False

    # ── Storage ───────────────────────────────────────────

    @classmethod
    def load_hash(cls) -> Optional[str]:
        """Load stored password hash. Returns None if not configured."""
        # 1. Check env (acceptance only)
        env_hash = os.environ.get(ACCEPTANCE_HASH_ENV)
        if env_hash:
            return env_hash

        # 2. Check file
        if ADMIN_AUTH_FILE.exists():
            try:
                with open(ADMIN_AUTH_FILE, "r") as f:
                    data = json.load(f)
                return data.get("passwordHash")
            except Exception:
                pass

        return None

    @classmethod
    def save_hash(cls, password_hash: str) -> None:
        """Save password hash to storage file."""
        ADMIN_AUTH_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "passwordHash": password_hash,
            "algorithm": password_hash.split("$")[0],
            "createdAt": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
        with open(ADMIN_AUTH_FILE, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(ADMIN_AUTH_FILE, 0o600)

    @classmethod
    def is_configured(cls) -> bool:
        """Check if admin password is configured."""
        return cls.load_hash() is not None

    # ── Verification ─────────────────────────────────────

    def verify(self, password: str) -> tuple[bool, str]:
        """Verify admin password. Returns (success, message)."""
        if self._locked:
            return False, "ADMIN_AIRLOCK_LOCKED"

        stored_hash = self.load_hash()
        if not stored_hash:
            return False, "ADMIN_AUTH_NOT_CONFIGURED"

        self._attempts += 1

        if AdminAuth.verify_password(stored_hash, password):
            self._attempts = 0
            return True, "ADMIN_PASSWORD_VERIFIED=true"

        if self._attempts >= self.MAX_ATTEMPTS:
            self._locked = True
            return False, "ADMIN_AIRLOCK_LOCKED"

        remaining = self.MAX_ATTEMPTS - self._attempts
        return False, f"ADMIN_PASSWORD_INVALID ({remaining} attempts remaining)"

    def is_locked(self) -> bool:
        return self._locked

    def reset_attempts(self) -> None:
        self._attempts = 0
        self._locked = False


# ── Interactive prompt ───────────────────────────────────
def prompt_admin_password() -> Optional[str]:
    """Prompt for admin password interactively. Returns None if non-interactive."""
    import sys
    if not sys.stdin.isatty():
        return None
    import getpass
    return getpass.getpass("Admin password: ")
