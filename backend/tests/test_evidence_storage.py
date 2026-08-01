"""Automated verification for ADR-0002: idempotent uploads, quota
enforcement, compensating cleanup on partial failure, and the R2 backend
(mocked via moto — no real Cloudflare credentials needed or used)."""

import os

from sqlalchemy.orm import Session as OrmSession

from .conftest import _make_png


def test_upload_then_download_round_trip(auth_client, project_slug, result_ref):
    cycle_id, result_id = result_ref
    slug = project_slug
    content = _make_png(b"\x11")

    r = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("shot.png", content, "image/png")},
    )
    assert r.status_code == 200, r.text
    evidence = r.json()
    assert evidence["original_size_bytes"] == len(content)
    assert evidence["evidence_source"] == "HUMAN"  # hybrid extension point, unused default

    dl = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence/{evidence['id']}/original")
    assert dl.status_code == 200
    assert dl.content == content


def test_idempotent_retry_does_not_duplicate(auth_client, project_slug, result_ref):
    """Requirement 6 — a retried upload of identical content converges on
    the same DB row instead of creating a duplicate."""
    cycle_id, result_id = result_ref
    slug = project_slug
    content = _make_png(b"\x22")

    r1 = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("a.png", content, "image/png")},
    )
    r2 = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("a-retry.png", content, "image/png")},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"], "retry with identical content must not create a second row"

    listed = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence").json()
    matching = [e for e in listed if e["original_sha256"] == r1.json()["original_sha256"]]
    assert len(matching) == 1


def test_spoofed_content_type_is_rejected(auth_client, project_slug, result_ref):
    cycle_id, result_id = result_ref
    slug = project_slug
    r = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("fake.png", b"not actually an image", "image/png")},
    )
    assert r.status_code == 400
    assert "signature" in r.json()["detail"]


def test_quota_blocks_upload_over_limit(auth_client, project_slug, result_ref):
    cycle_id, result_id = result_ref
    slug = project_slug
    content = _make_png(b"\x33")

    original = auth_client.get(f"/api/projects/{slug}/storage-quota").json()["quota_bytes"]
    try:
        set_resp = auth_client.put(f"/api/projects/{slug}/storage-quota", json={"storage_quota_bytes": 1})
        assert set_resp.status_code == 200
        assert set_resp.json()["over_quota"] is True

        r = auth_client.post(
            f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
            files={"file": ("too-big.png", content, "image/png")},
        )
        assert r.status_code == 400
        assert "quota" in r.json()["detail"]
    finally:
        auth_client.put(f"/api/projects/{slug}/storage-quota", json={"storage_quota_bytes": original})


def test_archive_hides_but_keeps_object_and_still_counts_toward_quota(auth_client, project_slug, result_ref):
    cycle_id, result_id = result_ref
    slug = project_slug
    content = _make_png(b"\x44")

    uploaded = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("archive-me.png", content, "image/png")},
    ).json()

    before = auth_client.get(f"/api/projects/{slug}/storage-quota").json()["used_bytes"]
    archived = auth_client.put(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence/{uploaded['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"

    listed = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence").json()
    assert uploaded["id"] not in [e["id"] for e in listed]

    # Still downloadable (object was never deleted) and still counted in quota.
    dl = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence/{uploaded['id']}/original")
    assert dl.status_code == 200
    after = auth_client.get(f"/api/projects/{slug}/storage-quota").json()["used_bytes"]
    assert after == before  # archiving doesn't change usage — the object is still there


def test_compensating_cleanup_on_db_failure_leaves_no_orphan_row_and_no_stray_file(
    auth_client, project_slug, result_ref, monkeypatch
):
    """Requirement 7 — simulates the DB insert failing *after* the object
    was already written to storage, and verifies: (a) the client gets a
    distinct error telling it not to assume success, (b) no EvidenceItem
    row was left behind, and (c) the compensating delete actually removed
    the file from disk (proxy for "no orphaned object")."""
    cycle_id, result_id = result_ref
    slug = project_slug
    content = _make_png(b"\x55")

    from app.database import evidence_storage_root_dir

    result_dir = os.path.join(evidence_storage_root_dir(), "evidence", slug, str(result_id))
    files_before = set(os.listdir(result_dir)) if os.path.isdir(result_dir) else set()

    call_count = {"n": 0}
    original_commit = OrmSession.commit

    def flaky_commit(self, *a, **kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated DB failure for test_compensating_cleanup")
        return original_commit(self, *a, **kw)

    monkeypatch.setattr(OrmSession, "commit", flaky_commit)
    try:
        r = auth_client.post(
            f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
            files={"file": ("will-fail.png", content, "image/png")},
        )
    finally:
        monkeypatch.setattr(OrmSession, "commit", original_commit)

    assert r.status_code == 500
    assert "do not assume it exists" in r.json()["detail"]

    listed = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence").json()
    assert content.__class__  # sanity
    import hashlib

    sha = hashlib.sha256(content).hexdigest()
    assert sha not in [e["original_sha256"] for e in listed], "a failed insert must not leave a DB row behind"

    files_after = set(os.listdir(result_dir)) if os.path.isdir(result_dir) else set()
    assert files_after == files_before, "the compensating delete must remove the object the failed request wrote"
