"""Requirement 4 — two concurrent uploads must not both independently
pass the quota pre-check and jointly exceed the hard limit undetected."""

import threading

from .conftest import _make_png


def _make_result(auth_client, name):
    r = auth_client.post("/api/projects", json={"name": name})
    slug = r.json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "s", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": "C-1", "title": "t", "action_md": "a", "expected_result_md": "e"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    cycle = auth_client.post(
        f"/api/{slug}/cycles",
        json={"suite_id": suite["id"], "script_revision_id": revision["id"], "name": "c", "environment": "test"},
    ).json()
    result_id = auth_client.get(f"/api/{slug}/cycles/{cycle['id']}/results").json()[0]["id"]
    return slug, cycle["id"], result_id


def test_concurrent_uploads_never_jointly_exceed_quota(auth_client):
    slug, cycle_id, result_id = _make_result(auth_client, "Concurrency Test Project")

    file_a = _make_png(b"\xa1")
    file_b = _make_png(b"\xb2")
    assert len(file_a) == len(file_b), "test assumes equal-sized files for a clean quota math check"

    # Quota fits exactly one file, not both.
    quota = len(file_a) + 5
    auth_client.put(f"/api/projects/{slug}/storage-quota", json={"storage_quota_bytes": quota})

    results = {}

    def do_upload(key, content, filename):
        r = auth_client.post(
            f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence",
            files={"file": (filename, content, "image/png")},
        )
        results[key] = r

    t1 = threading.Thread(target=do_upload, args=("a", file_a, "a.png"))
    t2 = threading.Thread(target=do_upload, args=("b", file_b, "b.png"))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    statuses = {k: r.status_code for k, r in results.items()}
    succeeded = [k for k, code in statuses.items() if code == 200]
    failed = [k for k, code in statuses.items() if code in (400, 409)]

    assert len(succeeded) == 1, f"exactly one upload should win the race, got statuses={statuses}"
    assert len(failed) == 1, f"exactly one upload should be rejected, got statuses={statuses}"

    final = auth_client.get(f"/api/projects/{slug}/storage-quota").json()
    assert final["used_bytes"] <= final["quota_bytes"], "quota must never be exceeded after both requests finish"

    listed = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence").json()
    assert len(listed) == 1, "the losing upload must not leave a DB row behind"
