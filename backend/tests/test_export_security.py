"""Phase 7 requirement 5 — export security: ZIP path traversal, filename
injection, large exports, temp-file cleanup, authorization leakage."""

import io
import os
import zipfile

from app.database import DATA_DIR

from .conftest import _make_png


def _full_cycle_with_evil_checkpoint(auth_client, name, checkpoint_code):
    r = auth_client.post("/api/projects", json={"name": name})
    slug = r.json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "s", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": checkpoint_code, "title": "t", "action_md": "a", "expected_result_md": "e"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    cycle = auth_client.post(
        f"/api/{slug}/cycles",
        json={"suite_id": suite["id"], "script_revision_id": revision["id"], "name": "c", "environment": "test"},
    ).json()
    result_id = auth_client.get(f"/api/{slug}/cycles/{cycle['id']}/results").json()[0]["id"]
    auth_client.post(
        f"/api/{slug}/cycles/{cycle['id']}/results/{result_id}/evidence",
        files={"file": ("shot.png", _make_png(b"\xe1"), "image/png")},
    )
    return slug, cycle["id"]


def test_zip_entries_never_escape_the_evidence_directory_via_checkpoint_code(auth_client):
    """A checkpoint code crafted to look like a path-traversal payload
    must not produce a ZIP entry outside evidence/ — report_zip.py's
    _safe_slug() must fully neutralize path separators and ".." runs."""
    slug, cycle_id = _full_cycle_with_evil_checkpoint(auth_client, "Zip Traversal Test", "../../../../etc/passwd")

    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/export/zip")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    for name in zf.namelist():
        assert not name.startswith("/"), f"absolute path entry: {name}"
        assert ".." not in name, f"path-traversal entry: {name}"
        if name.startswith("evidence/"):
            # Must resolve to strictly inside evidence/, one path segment.
            rest = name[len("evidence/") :]
            assert "/" not in rest, f"evidence entry escaped its directory: {name}"


def test_zip_entries_handle_special_characters_without_corrupting_archive_structure(auth_client):
    """Filename-injection-style checkpoint codes (quotes, null-ish
    separators, unicode) must not break the archive or produce a
    malformed entry name — they should simply be slugified."""
    slug, cycle_id = _full_cycle_with_evil_checkpoint(
        auth_client, "Zip Injection Test", 'REG"; rm -rf /; --\x00<script>'
    )
    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/export/zip")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert zf.testzip() is None, "archive failed its own integrity check"
    for name in zf.namelist():
        assert '"' not in name and ";" not in name and "\x00" not in name and "<" not in name


def test_export_of_a_larger_cycle_completes_and_produces_a_consistent_manifest(auth_client):
    """Not a true load/stress test (see docs/CAPACITY.md for the
    documented in-memory-generation limitation at real scale) — a sanity
    check that a many-case cycle doesn't crash or silently drop rows."""
    r = auth_client.post("/api/projects", json={"name": "Larger Export Test"})
    slug = r.json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "s", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    n = 25
    for i in range(n):
        auth_client.post(
            f"/api/{slug}/revisions/{revision['id']}/cases",
            json={"checkpoint_code": f"CASE-{i:03d}", "title": f"case {i}", "action_md": "a", "expected_result_md": "e"},
        )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    cycle = auth_client.post(
        f"/api/{slug}/cycles",
        json={"suite_id": suite["id"], "script_revision_id": revision["id"], "name": "big", "environment": "test"},
    ).json()

    r = auth_client.get(f"/api/{slug}/cycles/{cycle['id']}/export/excel")
    assert r.status_code == 200
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    rows = list(wb["02_Test_Results"].iter_rows(min_row=2, values_only=True))
    assert len(rows) == n


def test_export_leaves_no_temp_files_behind(auth_client, project_slug, result_ref):
    """Requirement: temp-file/cleanup strategy is in-memory generation
    with nothing written to disk — verify DATA_DIR's contents are
    unchanged by an export (proxy for "nothing was left behind")."""
    cycle_id, result_id = result_ref
    slug = project_slug
    auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
        files={"file": ("t.png", _make_png(b"\xf1"), "image/png")},
    )

    def snapshot():
        files = set()
        for dirpath, _dirs, filenames in os.walk(DATA_DIR):
            for f in filenames:
                files.add(os.path.relpath(os.path.join(dirpath, f), DATA_DIR))
        return files

    before = snapshot()
    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/export/zip")
    assert r.status_code == 200
    after = snapshot()
    assert after == before, f"export left files behind: {after - before}"


def test_export_requires_authentication(project_slug):
    from fastapi.testclient import TestClient
    from app.main import app

    anon = TestClient(app)
    r = anon.get(f"/api/{project_slug}/cycles/1/export/excel")
    assert r.status_code == 401


def test_export_for_nonexistent_cycle_in_a_different_project_404s_not_leaks(auth_client, project_slug):
    other_slug = auth_client.post("/api/projects", json={"name": "Export Isolation B"}).json()["slug"]
    r = auth_client.get(f"/api/{other_slug}/cycles/999999/export/excel")
    assert r.status_code == 404
