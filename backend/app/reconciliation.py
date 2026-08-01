"""Evidence storage reconciliation — see docs/EVIDENCE_STORAGE_LIFECYCLE.md.

Read-only listing/comparison is separated from the delete step
deliberately, and the delete step re-verifies each candidate immediately
before acting on it (requirement 5: never delete an object a committed
DB row references, even if it raced with the initial listing).

Known limitation, documented rather than silently ignored: there is a
narrow window where an in-flight upload has written its object to
storage but not yet committed its DB row (see routers/evidence.py's
upload ordering) — if reconciliation's delete happens to land in that
exact window, it could delete a legitimately-in-flight object. The
mitigation is operational (run reconciliation during low-traffic
windows), not a code-level lock, since EvidenceStorage doesn't expose
object age/metadata to filter on. This is called out explicitly rather
than claimed to be impossible.
"""

import logging

from sqlalchemy.orm import Session

from . import models
from .storage import EvidenceStorage

logger = logging.getLogger("reconciliation")


def find_orphan_keys(project_slug: str, project_db: Session, storage: EvidenceStorage) -> list[str]:
    """Read-only. Lists objects under evidence/{slug}/ and returns every
    key with no matching EvidenceItem.object_key row."""
    prefix = f"evidence/{project_slug}/"
    listed_keys = set(storage.list_keys(prefix))
    known_keys = {row[0] for row in project_db.query(models.EvidenceItem.object_key).all()}
    return sorted(listed_keys - known_keys)


def delete_orphans(
    project_slug: str,
    project_db: Session,
    storage: EvidenceStorage,
    orphan_keys: list[str],
    dry_run: bool = True,
) -> dict:
    """Idempotent: a key that's already gone (this run or a prior one)
    is a no-op, not an error. `dry_run=True` (the default) never deletes
    anything — always report before acting."""
    deleted, skipped_referenced, skipped_missing, errors = [], [], [], []

    for key in orphan_keys:
        # Re-verify immediately before acting — the whole point of
        # requirement 5. A row may have been committed between the
        # earlier find_orphan_keys() listing and this call.
        still_referenced = project_db.query(models.EvidenceItem.id).filter(models.EvidenceItem.object_key == key).first()
        if still_referenced:
            skipped_referenced.append(key)
            continue
        if not storage.exists(key):
            skipped_missing.append(key)  # already deleted by an earlier run — fine, not an error
            continue
        if dry_run:
            continue
        try:
            storage.delete(key)
            deleted.append(key)
        except Exception as exc:
            logger.error("Reconciliation: failed to delete orphan %s/%s: %s", project_slug, key, exc)
            errors.append(key)

    return {
        "project_slug": project_slug,
        "candidates": len(orphan_keys),
        "deleted": deleted,
        "skipped_referenced": skipped_referenced,
        "skipped_missing": skipped_missing,
        "errors": errors,
        "dry_run": dry_run,
    }
