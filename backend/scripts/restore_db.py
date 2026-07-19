"""Restores master.db + per-project .db files from a backup snapshot
created by backup_db.py. Destructive (overwrites live data) — requires
--force and always makes a pre-restore safety copy of whatever's currently
live before overwriting it, so a bad restore is itself recoverable.

Usage:
    python scripts/restore_db.py <snapshot_name|latest> --force
    python scripts/restore_db.py --list
"""

import argparse
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import DATA_DIR, PROJECTS_DIR  # noqa: E402
from scripts.backup_db import BACKUP_DIR  # noqa: E402


def list_snapshots() -> list[str]:
    if not os.path.isdir(BACKUP_DIR):
        return []
    return sorted(
        name for name in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, name))
    )


def resolve_snapshot(name: str) -> str:
    snapshots = list_snapshots()
    if not snapshots:
        raise SystemExit(f"No backup snapshots found in {BACKUP_DIR}")
    if name == "latest":
        return snapshots[-1]
    if name not in snapshots:
        raise SystemExit(f"Snapshot '{name}' not found. Available: {snapshots}")
    return name


def safety_copy_current_state() -> str:
    """Before overwriting anything, snapshot what's currently live — so a
    restore that turns out to be wrong is itself undoable."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    safety_dir = os.path.join(BACKUP_DIR, f"pre-restore-{timestamp}")
    os.makedirs(safety_dir, exist_ok=True)

    master_db = os.path.join(DATA_DIR, "master.db")
    if os.path.exists(master_db):
        shutil.copy2(master_db, os.path.join(safety_dir, "master.db"))

    projects_dir = os.path.join(safety_dir, "projects")
    os.makedirs(projects_dir, exist_ok=True)
    if os.path.isdir(PROJECTS_DIR):
        for name in os.listdir(PROJECTS_DIR):
            if name.endswith(".db"):
                shutil.copy2(os.path.join(PROJECTS_DIR, name), os.path.join(projects_dir, name))

    return safety_dir


def run_restore(snapshot_name: str, force: bool):
    resolved = resolve_snapshot(snapshot_name)
    snapshot_dir = os.path.join(BACKUP_DIR, resolved)

    if not force:
        raise SystemExit(
            f"Refusing to restore from '{resolved}' without --force "
            "(this overwrites the live database files)."
        )

    safety_dir = safety_copy_current_state()
    print(f"[restore] pre-restore safety copy saved to {safety_dir}")

    restored = []
    src_master = os.path.join(snapshot_dir, "master.db")
    if os.path.exists(src_master):
        shutil.copy2(src_master, os.path.join(DATA_DIR, "master.db"))
        restored.append("master.db")

    src_projects = os.path.join(snapshot_dir, "projects")
    if os.path.isdir(src_projects):
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        for name in os.listdir(src_projects):
            shutil.copy2(os.path.join(src_projects, name), os.path.join(PROJECTS_DIR, name))
            restored.append(f"projects/{name}")

    print(f"[restore] restored {len(restored)} file(s) from snapshot '{resolved}':")
    for f in restored:
        print(f"  - {f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", nargs="?", help="Snapshot name (from --list) or 'latest'")
    parser.add_argument("--force", action="store_true", help="Actually perform the restore")
    parser.add_argument("--list", action="store_true", help="List available snapshots and exit")
    args = parser.parse_args()

    if args.list:
        for s in list_snapshots():
            print(s)
        raise SystemExit(0)

    if not args.snapshot:
        parser.error("snapshot name (or 'latest') is required unless --list is given")

    run_restore(args.snapshot, args.force)
