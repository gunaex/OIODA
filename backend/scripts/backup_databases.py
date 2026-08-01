#!/usr/bin/env python
"""Backs up master.db and every per-project database to a timestamped
directory, using SQLite's online backup API (sqlite3.Connection.backup)
rather than a raw file copy — the backup API produces a transactionally
consistent snapshot even while the app is actively writing, where a raw
`cp` could catch a mid-write/mid-transaction state and copy a corrupt or
inconsistent file.

Usage:
    python scripts/backup_databases.py [backup_root_dir]

Defaults backup_root_dir to $DATA_DIR/backups (excluded from the app's
own served paths — matches backend/.gitignore's backups/ entry).

Only backs up SQLite metadata. Evidence binaries in R2 are NOT included —
see docs/EVIDENCE_STORAGE_LIFECYCLE.md and docs/BACKUP_RESTORE.md for why
that's a separate concern (R2 has its own recommended durability/
versioning story) and is out of scope for this script.
"""
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import DATA_DIR, PROJECTS_DIR  # noqa: E402


def backup_sqlite_file(src_path: str, dest_path: str) -> bool:
    if not os.path.exists(src_path):
        return False
    src = sqlite3.connect(src_path)
    dest = sqlite3.connect(dest_path)
    try:
        with dest:
            src.backup(dest)
    finally:
        src.close()
        dest.close()
    return True


def main():
    backup_root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA_DIR, "backups")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = os.path.join(backup_root, stamp)
    os.makedirs(dest_dir, exist_ok=True)

    backed_up = []

    master_src = os.path.join(DATA_DIR, "master.db")
    if backup_sqlite_file(master_src, os.path.join(dest_dir, "master.db")):
        backed_up.append("master.db")

    if os.path.isdir(PROJECTS_DIR):
        projects_dest = os.path.join(dest_dir, "projects")
        os.makedirs(projects_dest, exist_ok=True)
        for name in sorted(os.listdir(PROJECTS_DIR)):
            if name.endswith(".db"):
                src_path = os.path.join(PROJECTS_DIR, name)
                if backup_sqlite_file(src_path, os.path.join(projects_dest, name)):
                    backed_up.append(f"projects/{name}")

    print(f"Backed up {len(backed_up)} database(s) to {dest_dir}")
    for b in backed_up:
        print(f"  {b}")
    if not backed_up:
        print("Nothing to back up — no master.db found. Has the app started at least once?")
        sys.exit(1)


if __name__ == "__main__":
    main()
