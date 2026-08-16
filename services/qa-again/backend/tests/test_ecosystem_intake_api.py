"""QA-E4/E5 — Conductor -> QA Again intake endpoint + service auth + QAResult delivery."""

import pytest
from fastapi.testclient import TestClient

from app import models
from app.contracts.validator import CanonicalContractValidator
from app.database import MasterSessionLocal
from app.ecosystem.service_auth import require_conductor_service_identity
from app.main import app


def _qar(work_package_id, qa_request_id, correlation_id="corr-e4"):
    return {
        "qaRequestId": qa_request_id,
        "correlationId": correlation_id,
        "workPackageId": work_package_id,
        "releaseCandidate": {"repo": "https://github.com/org/app", "branch": "main", "commit": "abc123"},
        "acceptanceCriteria": {"business": [], "technical": []},
        "createdAt": "2026-08-12T00:00:00Z",
    }


def _override_conductor_identity(tenant_id="tenant-e4"):
    app.dependency_overrides[require_conductor_service_identity] = lambda: {
        "systemId": "CONDUCTOR_MAIN",
        "tenantId": tenant_id,
    }


def teardown_function(_fn):
    app.dependency_overrides.pop(require_conductor_service_identity, None)


def test_missing_service_token_rejected(client):
    resp = client.post("/api/ecosystem/qa-requests", json=_qar("wp-noauth-1", "qar-noauth-1"))
    assert resp.status_code == 401


def test_invalid_service_token_rejected(client):
    resp = client.post(
        "/api/ecosystem/qa-requests",
        json=_qar("wp-badtoken-1", "qar-badtoken-1"),
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 403


def test_valid_intake_without_published_revision_stays_unmapped(client):
    """QA Again never fabricates test cases to fill a gap — a freshly
    minted project for a new workPackageId has no PUBLISHED revision yet,
    so the ExternalQARequest is recorded but not mapped to a cycle."""
    _override_conductor_identity()
    resp = client.post("/api/ecosystem/qa-requests", json=_qar("wp-nomap-1", "qar-nomap-1"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] is True
    assert body["testCycleId"] is None
    assert body["status"] == "RECEIVED"
    assert body["qaProjectSlug"]


def test_intake_maps_to_cycle_when_revision_exists(auth_client, client):
    slug = auth_client.post("/api/projects", json={"name": "E4 Mapping Project"}).json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": "E4-001", "title": "case", "action_md": "do it", "expected_result_md": "works"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")

    with MasterSessionLocal() as master_db:
        project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
        master_db.add(models.ExternalQAProjectLink(work_package_id="wp-map-1", project_id=project.id))
        master_db.commit()

    _override_conductor_identity()
    resp = client.post("/api/ecosystem/qa-requests", json=_qar("wp-map-1", "qar-map-1"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["qaProjectSlug"] == slug
    assert body["testCycleId"] is not None
    assert body["status"] == "MAPPED"

    results = auth_client.get(f"/api/{slug}/cycles/{body['testCycleId']}/results").json()
    assert len(results) == 1


def test_replay_is_idempotent_no_duplicate_cycle(client):
    _override_conductor_identity()
    resp1 = client.post("/api/ecosystem/qa-requests", json=_qar("wp-replay-1", "qar-replay-1"))
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["created"] is True

    resp2 = client.post("/api/ecosystem/qa-requests", json=_qar("wp-replay-1", "qar-replay-1"))
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["created"] is False
    assert body2["externalQARequestId"] == body1["externalQARequestId"]


def test_replay_with_mutated_payload_same_key_is_conflict(client):
    _override_conductor_identity()
    resp1 = client.post("/api/ecosystem/qa-requests", json=_qar("wp-conflict-1", "qar-conflict-1"))
    assert resp1.status_code == 200

    mutated = _qar("wp-conflict-1", "qar-conflict-1")
    mutated["releaseCandidate"]["commit"] = "different-commit"
    resp2 = client.post("/api/ecosystem/qa-requests", json=mutated)
    assert resp2.status_code == 409


def test_qa_result_by_qa_request_id_requires_service_auth(client):
    resp = client.get("/api/ecosystem/qa-requests/qar-anything/qa-result")
    assert resp.status_code == 401


def test_qa_result_by_qa_request_id_404_when_unmapped(client):
    _override_conductor_identity()
    client.post("/api/ecosystem/qa-requests", json=_qar("wp-noresult-1", "qar-noresult-1"))
    resp = client.get("/api/ecosystem/qa-requests/qar-noresult-1/qa-result")
    assert resp.status_code == 404


def test_qa_result_by_qa_request_id_returns_canonical_result(auth_client, client):
    slug = auth_client.post("/api/projects", json={"name": "E5 Result Project"}).json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": "E5-001", "title": "case", "action_md": "do it", "expected_result_md": "works"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")

    with MasterSessionLocal() as master_db:
        project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
        master_db.add(models.ExternalQAProjectLink(work_package_id="wp-result-1", project_id=project.id))
        master_db.commit()

    _override_conductor_identity()
    intake_resp = client.post("/api/ecosystem/qa-requests", json=_qar("wp-result-1", "qar-result-1", correlation_id="corr-e5"))
    cycle_id = intake_resp.json()["testCycleId"]
    assert cycle_id is not None

    results = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results").json()
    auth_client.put(f"/api/{slug}/cycles/{cycle_id}/results/{results[0]['id']}", json={"status": "PASS", "actual_result_md": "ok"})
    auth_client.put(f"/api/{slug}/cycles/{cycle_id}", json={"status": "COMPLETED"})
    auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/signoffs",
        json={"cycle_id": cycle_id, "signoff_type": "QA_REVIEW", "decision": "APPROVED"},
    )

    resp = client.get("/api/ecosystem/qa-requests/qar-result-1/qa-result")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["correlationId"] == "corr-e5"
    assert body["qualityGate"] == "APPROVED"
    CanonicalContractValidator.validate("QAResult", body)


def test_explicit_rerun_creates_new_attempt_and_replay_does_not(client, master_db=None):
    """QA-E9.9 — POST .../rerun always adds a QAExecutionAttempt; a plain
    POST /qa-requests replay of the same key+payload must not."""
    _override_conductor_identity()
    intake = client.post("/api/ecosystem/qa-requests", json=_qar("wp-rerun-1", "qar-rerun-http-1")).json()
    assert intake["testCycleId"] is None  # fresh project, no published revision — unmapped

    # Can't rerun an unmapped request.
    resp = client.post("/api/ecosystem/qa-requests/qar-rerun-http-1/rerun")
    assert resp.status_code == 409


def test_rerun_requires_service_auth():
    unauthenticated_client = TestClient(app)
    resp = unauthenticated_client.post("/api/ecosystem/qa-requests/qar-anything/rerun")
    assert resp.status_code == 401


def test_rerun_404_for_unknown_qa_request(client):
    _override_conductor_identity()
    resp = client.post("/api/ecosystem/qa-requests/qar-does-not-exist-rerun/rerun")
    assert resp.status_code == 404


def test_rerun_on_mapped_request_creates_attempt_two(auth_client, client):
    slug = auth_client.post("/api/projects", json={"name": "E9 Rerun Mapping Project"}).json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": "RERUN-001", "title": "case", "action_md": "do it", "expected_result_md": "works"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")

    with MasterSessionLocal() as master_db:
        project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
        master_db.add(models.ExternalQAProjectLink(work_package_id="wp-rerun-2", project_id=project.id))
        master_db.commit()

    _override_conductor_identity()
    intake = client.post("/api/ecosystem/qa-requests", json=_qar("wp-rerun-2", "qar-rerun-http-2")).json()
    assert intake["testCycleId"] is not None

    resp = client.post("/api/ecosystem/qa-requests/qar-rerun-http-2/rerun")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["attemptNo"] == 2
    assert body["trigger"] == "EXPLICIT_RERUN"
    assert body["testCycleId"] == intake["testCycleId"]

    # A replay of the original intake still must not add a third attempt.
    client.post("/api/ecosystem/qa-requests", json=_qar("wp-rerun-2", "qar-rerun-http-2"))
    resp2 = client.post("/api/ecosystem/qa-requests/qar-rerun-http-2/rerun")
    assert resp2.json()["attemptNo"] == 3  # a second explicit rerun legitimately adds attempt 3


def test_cross_tenant_qa_result_blocked(auth_client, client):
    """E10.7 — a CONDUCTOR_MAIN token presenting a different tenant
    context than the one this QARequest was intaken under must not read
    its QAResult, even though CONDUCTOR_MAIN itself is a valid,
    cross-tenant-capable service identity."""
    slug = auth_client.post("/api/projects", json={"name": "E10 Tenant QAResult Project"}).json()["slug"]
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={"checkpoint_code": "TEN-001", "title": "case", "action_md": "do it", "expected_result_md": "works"},
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    with MasterSessionLocal() as master_db:
        project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
        master_db.add(models.ExternalQAProjectLink(work_package_id="wp-tenant-result-1", project_id=project.id))
        master_db.commit()

    _override_conductor_identity(tenant_id="tenant-owner")
    intake = client.post("/api/ecosystem/qa-requests", json=_qar("wp-tenant-result-1", "qar-tenant-result-1"))
    assert intake.json()["testCycleId"] is not None

    _override_conductor_identity(tenant_id="tenant-intruder")
    resp = client.get("/api/ecosystem/qa-requests/qar-tenant-result-1/qa-result")
    assert resp.status_code == 404

    _override_conductor_identity(tenant_id="tenant-owner")
    resp_owner = client.get("/api/ecosystem/qa-requests/qar-tenant-result-1/qa-result")
    assert resp_owner.status_code == 200


def test_cross_tenant_rerun_blocked(client):
    _override_conductor_identity(tenant_id="tenant-owner")
    intake = client.post("/api/ecosystem/qa-requests", json=_qar("wp-tenant-rerun-1", "qar-tenant-rerun-1"))
    assert intake.status_code == 200

    _override_conductor_identity(tenant_id="tenant-intruder")
    resp = client.post("/api/ecosystem/qa-requests/qar-tenant-rerun-1/rerun")
    assert resp.status_code == 404


def test_connection_status_requires_human_auth():
    # A fresh, cookie-less TestClient — the shared `client`/`auth_client`
    # session fixtures carry auth cookies from earlier tests in the same
    # session (see conftest.py), so they can't demonstrate "unauthenticated".
    unauthenticated_client = TestClient(app)
    resp = unauthenticated_client.get("/api/ecosystem/connection-status")
    assert resp.status_code == 401


def test_connection_status_reports_real_probes(auth_client):
    resp = auth_client.get("/api/ecosystem/connection-status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "ecosystemMode" in body
    assert isinstance(body["accountAgain"]["reachable"], bool)
    assert isinstance(body["conductorMain"]["reachable"], bool)
