#!/usr/bin/env python
"""Ops script — finds (and optionally deletes) orphaned evidence objects
across every project. Safe to run repeatedly (idempotent). Defaults to
dry-run; pass --confirm to actually delete.

Usage:
    python scripts/reconcile_evidence.py            # dry run, all projects
    python scripts/reconcile_evidence.py --slug foo # dry run, one project
    python scripts/reconcile_evidence.py --confirm  # actually delete orphans

Run during a low-traffic window — see app/reconciliation.py's docstring
for the narrow in-flight-upload race this doesn't fully close.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import MasterSessionLocal, get_project_db, get_project_engine  # noqa: E402
from app import models  # noqa: E402
from app.reconciliation import find_orphan_keys, delete_orphans  # noqa: E402
from app.storage import get_evidence_storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="Only reconcile this project (default: all projects)")
    parser.add_argument("--confirm", action="store_true", help="Actually delete orphans (default: dry run)")
    args = parser.parse_args()

    with MasterSessionLocal() as master_db:
        if args.slug:
            slugs = [args.slug]
        else:
            slugs = [row[0] for row in master_db.query(models.Project.slug).all()]

    storage = get_evidence_storage()
    results = []
    for slug in slugs:
        get_project_engine(slug)
        project_db = next(get_project_db(slug))
        try:
            orphans = find_orphan_keys(slug, project_db, storage)
            result = delete_orphans(slug, project_db, storage, orphans, dry_run=not args.confirm)
            results.append(result)
        finally:
            project_db.close()

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
