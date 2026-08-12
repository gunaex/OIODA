"""Account Again — E4 credential-resolution boundary tests.

Covers the new POST /credential-refs/{ref}/resolve endpoint added for
Local AI Control Center integration (E4-C). Reuses the E3 test app/db wiring.
"""

import os
from account_again.models import Tenant, CredentialReference, ServiceIdentity

# `db`, `client`, and the autouse `setup_db` fixture live in tests/conftest.py,
# shared with test_e3_acceptance.py.


def make_tenant(db, tenant_id="t1"):
    t = Tenant(tenant_id=tenant_id, name="Test Tenant")
    db.add(t)
    db.commit()
    return t


def make_credential(db, tenant_id="t1", provider="e4testprovider", status="ACTIVE", expires_at=None):
    cr = CredentialReference(
        credential_ref="cred-e4-001", tenant_id=tenant_id, provider=provider,
        credential_type="AI_PROVIDER_API_KEY", status=status, expires_at=expires_at,
    )
    db.add(cr)
    db.commit()
    return cr


class TestCredentialResolvePositive:
    def test_resolve_success_via_env_var(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "dummy-not-a-real-secret-value")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret"] == "dummy-not-a-real-secret-value"
        assert data["credentialRef"] == "cred-e4-001"

    def test_resolve_audit_never_contains_secret(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "dummy-not-a-real-secret-value")
        client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        audit_resp = client.get("/api/v1/audit", params={"tenantId": "t1"})
        body = audit_resp.text
        assert "dummy-not-a-real-secret-value" not in body

    def test_resolve_with_active_service_identity_allowed(self, client, db):
        make_tenant(db)
        make_credential(db)
        db.add(ServiceIdentity(service_identity_id="svc1", system_id="LOCAL_AI_CONTROL_CENTER"))
        db.commit()
        os.environ["E4TESTPROVIDER_API_KEY"] = "dummy2"
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
            "serviceSystemId": "LOCAL_AI_CONTROL_CENTER",
        })
        del os.environ["E4TESTPROVIDER_API_KEY"]
        assert resp.status_code == 200


class TestCredentialResolveNegative:
    def test_resolve_not_found(self, client, db):
        make_tenant(db)
        resp = client.post("/api/v1/credential-refs/nope/resolve", json={
            "tenantId": "t1", "provider": "openai", "purpose": "x",
        })
        assert resp.status_code == 404

    def test_revoked_credential_blocks_resolution(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db, status="REVOKED")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403
        assert "should-never-be-returned" not in resp.text

    def test_expired_credential_blocks_resolution(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db, expires_at="2000-01-01T00:00:00")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403

    def test_revoked_service_identity_blocks_resolution(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        db.add(ServiceIdentity(service_identity_id="svc1", system_id="LOCAL_AI_CONTROL_CENTER", status="REVOKED"))
        db.commit()
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
            "serviceSystemId": "LOCAL_AI_CONTROL_CENTER",
        })
        assert resp.status_code == 403
        assert "should-never-be-returned" not in resp.text

    def test_unresolvable_credential_returns_no_secret(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        monkeypatch.delenv("E4TESTPROVIDER_API_KEY", raising=False)
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 424
        assert "secret" not in resp.json()

    def test_get_credential_ref_never_returns_secret_field(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-leak-here")
        resp = client.get("/api/v1/credential-refs/cred-e4-001")
        assert resp.status_code == 200
        assert "secret" not in resp.json()
        assert "should-never-leak-here" not in resp.text

    def test_cross_tenant_credential_use_blocked(self, client, db, monkeypatch):
        """E4 §35: tenant A must not be able to resolve tenant B's credentialRef."""
        make_tenant(db, tenant_id="tenant-a")
        make_tenant(db, tenant_id="tenant-b")
        make_credential(db, tenant_id="tenant-b")  # owned by tenant-b
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned-cross-tenant")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "tenant-a", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403
        assert "should-never-be-returned-cross-tenant" not in resp.text
