"""QA-E7: runner identity, execution/snapshot/browser provenance, and
trust negative tests for the HYB-0 hybrid runner endpoints."""

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import MasterSessionLocal
from app.main import app


@pytest.fixture
def hybrid_project_slug(auth_client):
    return auth_client.post("/api/projects", json={"name": "Hybrid Provenance Tests"}).json()["slug"]


@pytest.fixture
def hybrid_other_project_slug(auth_client):
    return auth_client.post("/api/projects", json={"name": "Hybrid Provenance Other Project"}).json()["slug"]


@pytest.fixture
def hybrid_result_ref(auth_client, hybrid_project_slug):
    slug = hybrid_project_slug
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": "HYB-001", "title": "case", "action_md": "do it", "expected_result_md": "works"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    cycle = auth_client.post(
        f"/api/{slug}/cycles",
        json={"suite_id": suite["id"], "script_revision_id": revision["id"], "name": "cycle", "environment": "test"},
    ).json()
    results = auth_client.get(f"/api/{slug}/cycles/{cycle['id']}/results").json()
    return cycle["id"], results[0]["id"]


def _mint_runner_token(auth_client, label, project_slug=None):
    body = {"label": label}
    if project_slug is not None:
        body["project_slug"] = project_slug
    resp = auth_client.post("/api/runner-tokens", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


# ── E7.9 trust negatives ──────────────────────────────────────────


def test_missing_runner_token_rejected(client, hybrid_project_slug):
    resp = client.post(f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "no-auth"})
    assert resp.status_code == 401


def test_invalid_runner_token_rejected(client, hybrid_project_slug):
    resp = client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "bad-token"},
        headers={"X-Runner-Token": "not-a-real-token"},
    )
    assert resp.status_code == 401


def test_scoped_token_rejected_for_other_project(auth_client, hybrid_project_slug, hybrid_other_project_slug):
    token = _mint_runner_token(auth_client, "scoped-to-project-a", project_slug=hybrid_project_slug)

    resp = auth_client.post(
        f"/api/{hybrid_other_project_slug}/hybrid/runs",
        json={"label": "cross-project-attempt"},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 403

    # Same token against its own project still works — proves the 403 is
    # scoping, not a broken token.
    resp_ok = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "same-project"},
        headers={"X-Runner-Token": token},
    )
    assert resp_ok.status_code == 200, resp_ok.text


def test_unscoped_token_works_for_any_project(auth_client, hybrid_project_slug, hybrid_other_project_slug):
    token = _mint_runner_token(auth_client, "global-legacy-token")
    for slug in (hybrid_project_slug, hybrid_other_project_slug):
        resp = auth_client.post(f"/api/{slug}/hybrid/runs", json={"label": "global"}, headers={"X-Runner-Token": token})
        assert resp.status_code == 200, resp.text


def test_run_id_namespace_isolated_across_projects(auth_client, hybrid_project_slug, hybrid_other_project_slug):
    """QA_RUN_PROVENANCE / cross-tenant isolation: a run_id from one
    project's SQLite file cannot resolve to a run in another project."""
    token = _mint_runner_token(auth_client, "isolation-check")
    run_a = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "a"}, headers={"X-Runner-Token": token}
    ).json()

    resp = auth_client.get(f"/api/{hybrid_other_project_slug}/hybrid/runs/{run_a['id']}")
    assert resp.status_code == 404


# ── E7.1 runner identity ──────────────────────────────────────────


def test_run_records_runner_identity(auth_client, hybrid_project_slug):
    token_value = _mint_runner_token(auth_client, "identity-check-runner")
    with MasterSessionLocal() as db:
        token_row = db.query(models.RunnerToken).filter(models.RunnerToken.label == "identity-check-runner").first()

    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "run", "runner_instance_id": "inst-abc123", "runner_version": "0.0.1-hyb0-spike"},
        headers={"X-Runner-Token": token_value},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["runner_token_id"] == token_row.id
    assert body["runner_label"] == "identity-check-runner"
    assert body["runner_instance_id"] == "inst-abc123"
    assert body["runner_version"] == "0.0.1-hyb0-spike"


# ── E7.2/E7.3 execution + snapshot provenance ─────────────────────


def test_run_records_execution_provenance(auth_client, hybrid_project_slug):
    token = _mint_runner_token(auth_client, "exec-provenance-runner")
    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={
            "label": "run",
            "external_qa_request_id": "qar-e7-1",
            "correlation_id": "corr-e7-1",
            "environment": "ecosystem",
            "target_base_url": "https://example.test",
            "artifact_ref": "abc123def",
        },
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["external_qa_request_id"] == "qar-e7-1"
    assert body["correlation_id"] == "corr-e7-1"
    assert body["environment"] == "ecosystem"
    assert body["target_base_url"] == "https://example.test"
    assert body["artifact_ref"] == "abc123def"


def test_run_snapshot_linkage_when_valid(auth_client, hybrid_project_slug, hybrid_result_ref):
    cycle_id, result_id = hybrid_result_ref
    token = _mint_runner_token(auth_client, "snapshot-linkage-runner")
    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "run", "test_cycle_id": cycle_id, "cycle_test_result_id": result_id},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["test_cycle_id"] == cycle_id
    assert body["cycle_test_result_id"] == result_id


def test_run_snapshot_linkage_rejects_nonexistent_result(auth_client, hybrid_project_slug):
    token = _mint_runner_token(auth_client, "bad-snapshot-runner")
    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "run", "cycle_test_result_id": 999999},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 400


def test_run_snapshot_linkage_rejects_mismatch(auth_client, hybrid_project_slug, hybrid_result_ref):
    """QA_TEST_REVISION_PROVENANCE / provenance mismatch: a result that
    doesn't belong to the given cycle must be rejected, not silently
    stored as if it did."""
    cycle_id, result_id = hybrid_result_ref
    token = _mint_runner_token(auth_client, "mismatch-runner")
    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "run", "test_cycle_id": cycle_id + 999, "cycle_test_result_id": result_id},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 400


def test_run_without_snapshot_linkage_stays_unknown(auth_client, hybrid_project_slug):
    """Unknown provenance (no TestCycle context) is honestly represented
    as null, never fabricated — matches HYB-0's own spike scenario."""
    token = _mint_runner_token(auth_client, "no-linkage-runner")
    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "run"}, headers={"X-Runner-Token": token}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["test_cycle_id"] is None
    assert body["cycle_test_result_id"] is None


# ── E7.4 browser provenance ────────────────────────────────────────


def test_provenance_patch_sets_browser_fields(auth_client, hybrid_project_slug):
    token = _mint_runner_token(auth_client, "browser-provenance-runner")
    run = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "run"}, headers={"X-Runner-Token": token}
    ).json()

    resp = auth_client.patch(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/provenance",
        json={"browser_name": "chromium", "browser_version": "120.0.0.0", "os_platform": "darwin"},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["browser_name"] == "chromium"
    assert body["browser_version"] == "120.0.0.0"
    assert body["os_platform"] == "darwin"


def test_provenance_patch_requires_runner_token(client, auth_client, hybrid_project_slug):
    token = _mint_runner_token(auth_client, "provenance-auth-check-runner")
    run = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "run"}, headers={"X-Runner-Token": token}
    ).json()

    resp = client.patch(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/provenance",
        json={"browser_name": "chromium"},
    )
    assert resp.status_code == 401


def test_provenance_patch_rejected_after_terminal(auth_client, hybrid_project_slug):
    token = _mint_runner_token(auth_client, "terminal-provenance-runner")
    run = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "run"}, headers={"X-Runner-Token": token}
    ).json()

    auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/events",
        json={"event_type": "CHECKPOINT_WAITING", "actor_type": "RUNNER"},
        headers={"X-Runner-Token": token},
    )
    decision = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/checkpoint-decision",
        json={"decision": "FAIL", "reason": "deliberate test failure"},
    )
    assert decision.status_code == 200, decision.text

    resp = auth_client.patch(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/provenance",
        json={"browser_name": "chromium"},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 400


# ── E7.6 evidence chain ────────────────────────────────────────────


def test_evidence_traceable_to_execution_and_snapshot(auth_client, hybrid_project_slug, hybrid_result_ref):
    cycle_id, result_id = hybrid_result_ref
    token = _mint_runner_token(auth_client, "evidence-chain-runner")
    run = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={
            "label": "run", "test_cycle_id": cycle_id, "cycle_test_result_id": result_id,
            "correlation_id": "corr-evidence-chain",
        },
        headers={"X-Runner-Token": token},
    ).json()

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/evidence",
        files={"file": ("evidence.png", png_bytes, "image/png")},
        headers={"X-Runner-Token": token},
    )
    assert resp.status_code == 200, resp.text

    detail = auth_client.get(f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}").json()
    assert detail["test_cycle_id"] == cycle_id
    assert detail["cycle_test_result_id"] == result_id
    assert detail["correlation_id"] == "corr-evidence-chain"
    assert any(e["event_type"] == "EVIDENCE_UPLOADED" for e in detail["events"])
    assert len(detail["evidence"]) == 1
    assert detail["evidence"][0]["original_filename"] == "evidence.png"

    # QA-E8.4/E8.5: the UI looks up runs for a result via this filter to
    # decide whether to show an "Automation" / evidence-navigation block.
    listed = auth_client.get(
        f"/api/{hybrid_project_slug}/hybrid/runs", params={"cycle_test_result_id": result_id}
    ).json()
    assert [r["id"] for r in listed] == [run["id"]]


def test_list_runs_unfiltered_and_by_test_cycle_id(auth_client, hybrid_project_slug, hybrid_result_ref):
    cycle_id, result_id = hybrid_result_ref
    token = _mint_runner_token(auth_client, "list-runs-runner")
    run = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs",
        json={"label": "run", "test_cycle_id": cycle_id},
        headers={"X-Runner-Token": token},
    ).json()

    all_runs = auth_client.get(f"/api/{hybrid_project_slug}/hybrid/runs").json()
    assert any(r["id"] == run["id"] for r in all_runs)

    by_cycle = auth_client.get(f"/api/{hybrid_project_slug}/hybrid/runs", params={"test_cycle_id": cycle_id}).json()
    assert [r["id"] for r in by_cycle] == [run["id"]]

    by_other_result = auth_client.get(
        f"/api/{hybrid_project_slug}/hybrid/runs", params={"cycle_test_result_id": result_id + 999}
    ).json()
    assert by_other_result == []


def test_list_runs_requires_human_auth(hybrid_project_slug):
    # A fresh, cookie-less TestClient — the shared `client`/`auth_client`
    # session fixtures carry auth cookies from earlier tests in the same
    # session (see conftest.py), so they can't demonstrate "unauthenticated".
    unauthenticated_client = TestClient(app)
    resp = unauthenticated_client.get(f"/api/{hybrid_project_slug}/hybrid/runs")
    assert resp.status_code == 401


# ── E7.7 manual checkpoint auditability (already-real behavior) ────


def test_checkpoint_decision_is_auditable(auth_client, hybrid_project_slug):
    token = _mint_runner_token(auth_client, "checkpoint-audit-runner")
    run = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs", json={"label": "run"}, headers={"X-Runner-Token": token}
    ).json()
    auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/events",
        json={"event_type": "CHECKPOINT_WAITING", "actor_type": "RUNNER"},
        headers={"X-Runner-Token": token},
    )

    resp = auth_client.post(
        f"/api/{hybrid_project_slug}/hybrid/runs/{run['id']}/checkpoint-decision",
        json={"decision": "PASS"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "PASS"
    assert body["decided_by"]  # real user identity, not a placeholder
    assert body["decided_at"]
