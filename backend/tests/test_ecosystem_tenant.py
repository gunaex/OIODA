"""PM-E6 — tenant isolation. require_ecosystem_identity is overridden per
test to control the caller's tenant directly, without needing a live
Account Again for the entitlement round-trip — the mechanism under test is
tenant *enforcement* (require_project_tenant_match), not the entitlement
call itself."""

import pytest

from app.main import app
from app.database import MasterSessionLocal
from app import models
from app.ecosystem import ecosystem_auth
from app.ecosystem.ecosystem_auth import require_ecosystem_identity, EcosystemIdentity
from app.ecosystem.service_auth import require_conductor_service_identity


@pytest.fixture(autouse=True)
def _ecosystem_mode_on(monkeypatch):
    # require_project_tenant_match only actually enforces when
    # ECOSYSTEM_MODE=true (see ecosystem_auth.py) — these tests are
    # specifically exercising that live enforcement path.
    monkeypatch.setattr(ecosystem_auth, "ECOSYSTEM_MODE", True)


def _identity_for(tenant_id):
    def _dep():
        return EcosystemIdentity(tenant_id=tenant_id, user=None, entitlement_decision={"decision": "ALLOW"})

    return _dep


def teardown_function(_fn):
    app.dependency_overrides.pop(require_ecosystem_identity, None)
    app.dependency_overrides.pop(require_conductor_service_identity, None)


def _make_project_for_tenant(auth_client, tenant_id, name):
    project = auth_client.post("/api/projects", json={"name": name}).json()
    with MasterSessionLocal() as db:
        row = db.query(models.Project).filter(models.Project.slug == project["slug"]).first()
        row.tenant_id = tenant_id
        db.commit()
    return project


def test_cross_tenant_project_access_blocked(auth_client):
    project = _make_project_for_tenant(auth_client, "tenant-a", "Tenant A Project")

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-b")
    resp = auth_client.get(f"/api/projects/{project['slug']}")
    assert resp.status_code == 404

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-a")
    resp = auth_client.get(f"/api/projects/{project['slug']}")
    assert resp.status_code == 200


def test_cross_tenant_task_access_blocked(auth_client):
    project = _make_project_for_tenant(auth_client, "tenant-a", "Tenant A Tasks Project")

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-a")
    create_resp = auth_client.post(f"/api/{project['slug']}/tasks", json={"title": "In tenant A"})
    assert create_resp.status_code == 200

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-b")
    resp = auth_client.get(f"/api/{project['slug']}/tasks")
    assert resp.status_code == 404


def test_cross_tenant_pmstatus_access_blocked(auth_client):
    project = _make_project_for_tenant(auth_client, "tenant-a", "Tenant A PMStatus Project")

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-b")
    resp = auth_client.get(f"/api/{project['slug']}/pm-status")
    assert resp.status_code == 404

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-a")
    resp = auth_client.get(f"/api/{project['slug']}/pm-status")
    assert resp.status_code == 200


def test_project_with_no_tenant_is_exempt(auth_client):
    """A project created before ecosystem mode existed (tenant_id is NULL)
    stays reachable — tenant enforcement only applies once a project is
    actually tenant-owned."""
    project = auth_client.post("/api/projects", json={"name": "No Tenant Project"}).json()

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-anything")
    resp = auth_client.get(f"/api/projects/{project['slug']}")
    assert resp.status_code == 200


VALID_DWP = {
    "workPackageId": "wp-e6-tenant",
    "correlationId": "corr-e6-tenant",
    "businessIntentId": "bi-e6-tenant",
    "title": "E6 Tenant Service",
    "priority": "HIGH",
    "state": "PLANNED",
    "assignments": {"pm": True},
    "createdAt": "2026-08-12T00:00:00Z",
}


def test_cross_tenant_delivery_work_package_rejected(client):
    app.dependency_overrides[require_conductor_service_identity] = lambda: {
        "systemId": "CONDUCTOR_MAIN",
        "tenantId": "tenant-a",
    }
    resp1 = client.post("/api/ecosystem/delivery-work-packages", json=VALID_DWP)
    assert resp1.status_code == 200

    app.dependency_overrides[require_conductor_service_identity] = lambda: {
        "systemId": "CONDUCTOR_MAIN",
        "tenantId": "tenant-b",
    }
    resp2 = client.post(
        "/api/ecosystem/delivery-work-packages",
        json=dict(VALID_DWP, workPackageId="wp-e6-tenant-2"),
    )
    assert resp2.status_code == 403
    app.dependency_overrides.pop(require_conductor_service_identity, None)


def test_local_auth_alone_does_not_override_tenant_mismatch(auth_client):
    """LOCAL_AUTH_NOT_AUTHORITATIVE_IN_ECOSYSTEM_MODE: a valid pmo_admin
    session (the highest local role) is not, by itself, sufficient to reach
    a project owned by a different tenant."""
    project = _make_project_for_tenant(auth_client, "tenant-a", "Local Auth Not Authoritative")

    app.dependency_overrides[require_ecosystem_identity] = _identity_for("tenant-b")
    resp = auth_client.get(f"/api/projects/{project['slug']}")
    assert resp.status_code == 404, "pmo_admin role alone must not bypass tenant enforcement"
