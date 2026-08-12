"""PM-E4 — Conductor -> PM Again intake endpoint + service auth."""

from app.main import app
from app.ecosystem.service_auth import require_conductor_service_identity

VALID_DWP = {
    "workPackageId": "wp-e4-001",
    "correlationId": "corr-e4-001",
    "businessIntentId": "bi-e4-001",
    "title": "E4 Golden Service",
    "priority": "HIGH",
    "state": "PLANNED",
    "assignments": {"pm": True, "engineering": True},
    "createdAt": "2026-08-12T00:00:00Z",
}


def _override_conductor_identity(tenant_id="tenant-a"):
    app.dependency_overrides[require_conductor_service_identity] = lambda: {
        "systemId": "CONDUCTOR_MAIN",
        "tenantId": tenant_id,
    }


def teardown_function(_fn):
    app.dependency_overrides.pop(require_conductor_service_identity, None)


def test_missing_service_token_rejected(client):
    resp = client.post("/api/ecosystem/delivery-work-packages", json=VALID_DWP)
    assert resp.status_code == 401


def test_invalid_service_token_rejected(client):
    resp = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=VALID_DWP,
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 403


def test_valid_intake_creates_project_and_mapping(client):
    _override_conductor_identity()
    resp = client.post("/api/ecosystem/delivery-work-packages", json=VALID_DWP)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] is True
    assert body["correlationId"] == "corr-e4-001"
    assert body["projectSlug"]

    project_resp = client.get(f"/api/projects/{body['projectSlug']}")
    assert project_resp.status_code == 401  # human auth dependency still applies here — separate concern


def test_replay_is_idempotent_no_duplicate_project(client):
    _override_conductor_identity()
    resp1 = client.post("/api/ecosystem/delivery-work-packages", json=dict(VALID_DWP, workPackageId="wp-e4-002"))
    assert resp1.status_code == 200
    body1 = resp1.json()
    assert body1["created"] is True

    resp2 = client.post("/api/ecosystem/delivery-work-packages", json=dict(VALID_DWP, workPackageId="wp-e4-002"))
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["created"] is False
    assert body2["projectSlug"] == body1["projectSlug"]
    assert body2["externalWorkReferenceId"] == body1["externalWorkReferenceId"]


def test_replay_with_mutated_payload_same_key_is_conflict(client):
    _override_conductor_identity()
    resp1 = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=dict(VALID_DWP, workPackageId="wp-e4-003"),
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=dict(VALID_DWP, workPackageId="wp-e4-003", state="CANCELLED"),
    )
    assert resp2.status_code == 409


def test_invalid_schema_rejected(client):
    _override_conductor_identity()
    broken = dict(VALID_DWP)
    del broken["businessIntentId"]
    resp = client.post("/api/ecosystem/delivery-work-packages", json=broken)
    assert resp.status_code == 422


def test_two_work_packages_same_business_intent_share_one_project(client):
    _override_conductor_identity()
    resp1 = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=dict(VALID_DWP, workPackageId="wp-e4-shared-1", businessIntentId="bi-e4-shared"),
    )
    resp2 = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=dict(VALID_DWP, workPackageId="wp-e4-shared-2", businessIntentId="bi-e4-shared"),
    )
    assert resp1.json()["projectSlug"] == resp2.json()["projectSlug"]
