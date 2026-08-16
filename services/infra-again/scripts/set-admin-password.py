#!/usr/bin/env python3
"""Set INFRA-AGAIN admin password for real AWS AIRLOCK.

Uses Argon2id (if available) or PBKDF2-SHA256 for secure hashing.
Password is prompted interactively with hidden input.
Only the hash is stored — NEVER plaintext.

Storage: ~/.config/infra-again/admin-auth.json (0600)
"""
from __future__ import annotations

import getpass
import os
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT, "src"))

from infra_again.execution.admin_auth import AdminAuth


def main():
    print("INFRA-AGAIN Admin Password Setup")
    print("=" * 50)
    print()

    # Check if already configured
    if AdminAuth.is_configured():
        print("Admin password is already configured.")
        choice = input("Overwrite? (y/N): ").strip().lower()
        if choice != "y":
            print("Aborted.")
            return 0

    # Prompt for password
    print("Password requirements: minimum 10 characters")
    pw1 = getpass.getpass("New admin password: ")
    if len(pw1) < 10:
        print("ERROR: Password must be at least 10 characters.")
        return 1

    pw2 = getpass.getpass("Confirm admin password: ")
    if pw1 != pw2:
        print("ERROR: Passwords do not match.")
        return 1

    # Hash and store
    try:
        password_hash = AdminAuth.hash_password(pw1)
        AdminAuth.save_hash(password_hash)
        algorithm = password_hash.split("$")[0]
        print(f"\nAdmin password configured successfully.")
        print(f"Algorithm: {algorithm}")
        print(f"Storage: ~/.config/infra-again/admin-auth.json")
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    # Verify it works
    stored = AdminAuth.load_hash()
    if stored and AdminAuth.verify_password(stored, pw1):
        print("Verification: OK (password verified)")
    else:
        print("Verification: FAILED — something went wrong")
        return 1

    # Clear password from memory (best effort)
    del pw1, pw2
    return 0


if __name__ == "__main__":
    sys.exit(main())
