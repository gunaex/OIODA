"""One-time, idempotent materialization of the TRUE CLOUD MIGRATION execution
model into PM Again (R3 — PM execution materialization).

Why this exists:
  The Full Loop trial ingested DeliveryWorkPackage payloads that predate the
  structured requirement refs. PM Again therefore holds only 4 flat seed tasks
  ("Design baseline bsl_…", "True Cloud Migration") and no Functions — the
  exact gap OIDA OS R3 closes.

What it does:
  1. Reads the *verified* requirement list + track names from Document Again's
     database (the design authority) — read-only, never writes it.
  2. Locates the PM project created for that Document project.
  3. Records the superseded seed tasks in a PM note (historical trace), then
     removes them.
  4. Materializes one Function per track and one requirement-backed Task per
     requirement, with NO invented owner/date/priority.

Idempotent: if Functions already exist for the project it exits without
changing anything.

Run:  cd /Users/kanphong/PM-AGAIN && .venv/bin/python backend/scripts/materialize_true_cloud.py
"""

import sqlite3
import sys
from datetime import datetime, timezone

DOC_DB = "/Users/kanphong/DOCUMENT-AGAIN/backend/data/document-again.db"
PM_MASTER = "/Users/kanphong/PM-AGAIN/backend/data/master.db"
PM_PROJECTS_DIR = "/Users/kanphong/PM-AGAIN/backend/data/projects"

DOC_PROJECT_ID = "prj_02884ef10cdc459889f1"

# Track names come from Document Again's own architecture diagrams
# (arch_track1 / arch_track2) — not invented here.
TRACK_FALLBACK = {
    "T1": "Track 1 — Landing Zone",
    "T2": "Track 2 — Migration Factory",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


def read_document_truth() -> tuple[list[dict], dict[str, str]]:
    con = sqlite3.connect(f"file:{DOC_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        reqs = [
            dict(r)
            for r in con.execute(
                "SELECT id, code, title FROM requirements WHERE project_id = ? ORDER BY code",
                (DOC_PROJECT_ID,),
            )
        ]
        track_names = {
            row["semantic_id"].replace("arch_track", "T"): row["name"]
            for row in con.execute(
                "SELECT semantic_id, name FROM architecture_diagrams WHERE project_id = ?",
                (DOC_PROJECT_ID,),
            )
            if row["name"]
        }
    finally:
        con.close()
    return reqs, track_names


def track_key(code: str) -> str:
    # REQ-T1-004 -> T1
    import re

    m = re.match(r"^REQ-(T\d+)-", code or "")
    return m.group(1) if m else "UNSCOPED"


def main() -> int:
    reqs, track_names = read_document_truth()
    if not reqs:
        print("No requirements found for the Document project — aborting.")
        return 1

    master = sqlite3.connect(PM_MASTER)
    master.row_factory = sqlite3.Row
    project = master.execute(
        "SELECT id, name, slug FROM projects WHERE name = 'True Cloud Migration' ORDER BY id LIMIT 1"
    ).fetchone()
    if not project:
        print("PM project 'True Cloud Migration' not found — aborting.")
        return 1
    slug = project["slug"]
    master.close()

    db_path = f"{PM_PROJECTS_DIR}/{slug}.db"
    pdb = sqlite3.connect(db_path)
    pdb.row_factory = sqlite3.Row

    existing_functions = pdb.execute("SELECT COUNT(*) AS n FROM functions").fetchone()["n"]
    if existing_functions:
        print(f"Functions already exist ({existing_functions}) — idempotent exit.")
        pdb.close()
        return 0

    seed_tasks = pdb.execute("SELECT id, title FROM tasks ORDER BY id").fetchall()
    if seed_tasks:
        # Preserve a historical trace of the superseded flat seed tasks.
        titles = "; ".join(f"#{t['id']} {t['title']}" for t in seed_tasks)
        pdb.execute(
            "INSERT INTO notes (content, status, created_at) VALUES (?, 'Open', ?)",
            (
                "OIDA R3 materialization: superseded flat Conductor seed tasks -> "
                f"replaced by requirement-backed Functions/Tasks. Removed: {titles}",
                _now(),
            ),
        )
        pdb.execute("DELETE FROM tasks")
        pdb.commit()
        print(f"Removed {len(seed_tasks)} flat seed tasks (trace recorded in notes).")

    function_ids: dict[str, int] = {}
    grouped: dict[str, list[dict]] = {}
    for r in reqs:
        grouped.setdefault(track_key(r["code"]), []).append(r)

    for key, group in grouped.items():
        name = track_names.get(key, TRACK_FALLBACK.get(key, f"Track {key[1:]}"))
        cur = pdb.execute(
            "INSERT INTO functions (name, description, type, phase, status, created_at, updated_at) "
            "VALUES (?, ?, 'Functional', 'UR', 'Confirmed', ?, ?)",
            (
                name,
                "Execution workstream materialized from the confirmed True Cloud Migration design baseline.",
                _now(),
                _now(),
            ),
        )
        function_ids[key] = cur.lastrowid
        print(f"Function: {name}")

    for key, group in grouped.items():
        for r in group:
            code, title = r["code"], r["title"]
            pdb.execute(
                "INSERT INTO tasks (title, description, phase, status, linked_function_id, created_at) "
                "VALUES (?, ?, 'UR', 'Todo', ?, ?)",
                (
                    f"{code} — {title}",
                    "Requirement-backed execution item. Baseline prj_02884ef10cdc459889f1 (True Cloud Migration).",
                    function_ids[key],
                    _now(),
                ),
            )
            print(f"Task: {code} — {title}")

    pdb.commit()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
