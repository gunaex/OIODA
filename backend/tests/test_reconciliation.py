"""Requirement 5 — orphan reconciliation must be idempotent and must
never delete an object a committed EvidenceItem row references."""

from app.database import get_project_db
from app.reconciliation import find_orphan_keys, delete_orphans
from app.storage import get_evidence_storage

from .conftest import _make_png


def _project_db_session(slug):
    return next(get_project_db(slug))


def test_no_orphans_when_everything_has_a_row(auth_client, project_slug, result_ref):
    cycle_id, result_id = result_ref
    slug = project_slug
    auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("clean.png", _make_png(b"\xc1"), "image/png")},
    )
    db = _project_db_session(slug)
    try:
        orphans = find_orphan_keys(slug, db, get_evidence_storage())
        assert orphans == []
    finally:
        db.close()


def test_orphan_is_found_and_safely_deleted_idempotently(auth_client, project_slug, result_ref):
    cycle_id, result_id = result_ref
    slug = project_slug
    storage = get_evidence_storage()

    # Simulate a leftover object with no DB row (e.g. a crash between
    # storage.put() and the DB commit) by writing directly to storage,
    # bypassing the API entirely.
    orphan_key = f"evidence/{slug}/{result_id}/orphan-test-object.png"
    storage.put(orphan_key, _make_png(b"\xd2"), "image/png")

    db = _project_db_session(slug)
    try:
        orphans = find_orphan_keys(slug, db, storage)
        assert orphan_key in orphans

        # Dry run must not delete anything.
        dry = delete_orphans(slug, db, storage, orphans, dry_run=True)
        assert dry["dry_run"] is True
        assert dry["deleted"] == []
        assert storage.exists(orphan_key) is True

        # Real run deletes it.
        real = delete_orphans(slug, db, storage, orphans, dry_run=False)
        assert orphan_key in real["deleted"]
        assert storage.exists(orphan_key) is False

        # Idempotent: running again with the same candidate list finds it
        # already gone — a no-op, not an error.
        again = delete_orphans(slug, db, storage, orphans, dry_run=False)
        assert orphan_key in again["skipped_missing"]
        assert again["errors"] == []
    finally:
        db.close()


def test_never_deletes_an_object_a_committed_row_now_references(auth_client, project_slug, result_ref):
    """Simulates the exact race requirement 5 is about: a key appears in
    a stale orphan candidate list (from an earlier listing), but by the
    time delete_orphans actually runs, a real EvidenceItem row now
    references it — it must be skipped, not deleted."""
    cycle_id, result_id = result_ref
    slug = project_slug
    storage = get_evidence_storage()

    uploaded = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("now-referenced.png", _make_png(b"\xe3"), "image/png")},
    ).json()

    db = _project_db_session(slug)
    try:
        from app import models

        real_key = db.query(models.EvidenceItem.object_key).filter(models.EvidenceItem.id == uploaded["id"]).scalar()

        # Stale candidate list — as if it were computed before this
        # evidence item's row was committed.
        stale_candidates = [real_key]

        result = delete_orphans(slug, db, storage, stale_candidates, dry_run=False)
        assert real_key in result["skipped_referenced"]
        assert result["deleted"] == []
        assert storage.exists(real_key) is True, "a referenced object must never be deleted"
    finally:
        db.close()
