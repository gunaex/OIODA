"""Copies master.db + every per-project .db file into a timestamped
snapshot folder, then prunes snapshots older than BACKUP_RETENTION_DAYS.

Local-filesystem backup is the testable MVP here — no S3/Google Drive
credentials exist yet to wire up real off-machine upload (the spec offers
those as examples, "เช่น", not a hard requirement). BACKUP_DIR defaults to
a sibling folder next to DATA_DIR so it's not itself inside the live data
tree; point it at a different disk/mount once one is available. Uploading
these snapshots to S3-compatible storage is a natural next step — add it as
a step at the end of main() once credentials exist, everything up to the
snapshot folder stays the same.

Usage:
    python scripts/backup_db.py

Intended to run on a schedule (cron locally, or a Fly.io scheduled machine
once deployed — see the fly.toml deployment prep notes).
"""

import os
import shutil
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import DATA_DIR, PROJECTS_DIR  # noqa: E402

BACKUP_DIR = os.environ.get("BACKUP_DIR") or os.path.join(os.path.dirname(DATA_DIR), "backups")
RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "7"))


def run_backup() -> str:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    snapshot_dir = os.path.join(BACKUP_DIR, timestamp)
    os.makedirs(snapshot_dir, exist_ok=True)

    master_db = os.path.join(DATA_DIR, "master.db")
    copied = []
    if os.path.exists(master_db):
        shutil.copy2(master_db, os.path.join(snapshot_dir, "master.db"))
        copied.append("master.db")

    projects_backup_dir = os.path.join(snapshot_dir, "projects")
    os.makedirs(projects_backup_dir, exist_ok=True)
    if os.path.isdir(PROJECTS_DIR):
        for name in os.listdir(PROJECTS_DIR):
            if not name.endswith(".db"):
                continue
            src = os.path.join(PROJECTS_DIR, name)
            shutil.copy2(src, os.path.join(projects_backup_dir, name))
            copied.append(f"projects/{name}")

    print(f"[backup] {timestamp}: copied {len(copied)} file(s) -> {snapshot_dir}")
    for f in copied:
        print(f"  - {f}")

    prune_old_backups()
    return snapshot_dir


def prune_old_backups():
    if not os.path.isdir(BACKUP_DIR):
        return
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    for name in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, name)
        if not os.path.isdir(path):
            continue
        try:
            snapshot_time = datetime.strptime(name, "%Y-%m-%d_%H%M%S")
        except ValueError:
            continue
        if snapshot_time < cutoff:
            shutil.rmtree(path)
            print(f"[backup] pruned old snapshot: {name}")


if __name__ == "__main__":
    run_backup()
