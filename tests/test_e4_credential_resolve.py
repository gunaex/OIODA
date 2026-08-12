"""Account Again — E4/E5.1 credential-resolution boundary tests.

Covers POST /credential-refs/{ref}/resolve, added in E4-C and hardened in E5.1 to
require a real signed service token (LOCAL_OIDC_COMPATIBLE_SERVICE_AUTH) rather than a
self-declared serviceSystemId body field. Reuses the E3 test app/db wiring.
"""

import os
from account_again.models import Tenant, CredentialReference, ServiceIdentity
from tests._auth_helpers import make_service_token

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


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestCredentialResolvePositive:
    def test_resolve_success_via_env_var(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "dummy-not-a-real-secret-value")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["secret"] == "dummy-not-a-real-secret-value"
        assert data["credentialRef"] == "cred-e4-001"

    def test_resolve_audit_never_contains_secret(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "dummy-not-a-real-secret-value")
        client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        audit_resp = client.get("/api/v1/audit", params={"tenantId": "t1"})
        body = audit_resp.text
        assert "dummy-not-a-real-secret-value" not in body

    def test_resolve_with_matching_declared_service_system_id_allowed(self, client, db):
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        os.environ["E4TESTPROVIDER_API_KEY"] = "dummy2"
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
            "serviceSystemId": "LOCAL_AI_CONTROL_CENTER",
        })
        del os.environ["E4TESTPROVIDER_API_KEY"]
        assert resp.status_code == 200


class TestCredentialResolveNegative:
    def test_resolve_not_found(self, client, db):
        make_tenant(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        resp = client.post("/api/v1/credential-refs/nope/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "openai", "purpose": "x",
        })
        assert resp.status_code == 404

    def test_revoked_credential_blocks_resolution(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db, status="REVOKED")
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403
        assert "should-never-be-returned" not in resp.text

    def test_expired_credential_blocks_resolution(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db, expires_at="2000-01-01T00:00:00")
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403

    def test_revoked_after_token_issuance_blocks_resolution(self, client, db, monkeypatch):
        """E5.1 §10: a valid, unexpired, correctly-signed token is NOT sufficient once
        the underlying ServiceIdentity has been revoked — the DB is re-checked live."""
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        svc = db.query(ServiceIdentity).filter(ServiceIdentity.system_id == "LOCAL_AI_CONTROL_CENTER").first()
        client.post(f"/api/v1/service-identities/{svc.service_identity_id}/revoke")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403
        assert "should-never-be-returned" not in resp.text

    def test_unresolvable_credential_returns_no_secret(self, client, db, monkeypatch):
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.delenv("E4TESTPROVIDER_API_KEY", raising=False)
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
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
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "should-never-be-returned-cross-tenant")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "tenant-a", "provider": "e4testprovider", "purpose": "AI_CODE_GENERATION",
        })
        assert resp.status_code == 403
        assert "should-never-be-returned-cross-tenant" not in resp.text


class TestE51TokenEnforcement:
    """New E5.1 tests: the token requirement itself, not just what it protects."""

    def test_missing_token_rejected(self, client, db):
        make_tenant(db)
        make_credential(db)
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "x",
        })
        assert resp.status_code == 401

    def test_malformed_authorization_header_rejected(self, client, db):
        make_tenant(db)
        make_credential(db)
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve",
                            headers={"Authorization": "NotBearer something"}, json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "x",
        })
        assert resp.status_code == 401

    def test_garbage_token_rejected(self, client, db):
        make_tenant(db)
        make_credential(db)
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve",
                            headers=auth("this.is.not.a.valid.jwt"), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "x",
        })
        assert resp.status_code == 401

    def test_expired_token_rejected(self, client, db, monkeypatch):
        import time
        from account_again.services import service_auth
        make_tenant(db)
        make_credential(db)
        monkeypatch.setattr(service_auth, "TOKEN_TTL_SECONDS", -10)  # issue already-expired
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "x",
        })
        assert resp.status_code == 401

    def test_wrong_service_identity_cannot_masquerade(self, client, db):
        """token = IDEA_TO_CODE, request declares serviceSystemId = LOCAL_AI_CONTROL_CENTER"""
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "IDEA_TO_CODE")
        resp = client.post("/api/v1/credential-refs/cred-e4-001/resolve", headers=auth(token), json={
            "tenantId": "t1", "provider": "e4testprovider", "purpose": "x",
            "serviceSystemId": "LOCAL_AI_CONTROL_CENTER",
        })
        assert resp.status_code == 403

    def test_legacy_header_does_not_override_token_identity(self, client, db, monkeypatch):
        """E5.1 §6: X-AGAIN-Service-Context header claiming a different identity than
        the verified token must have zero effect — the token wins, always."""
        make_tenant(db)
        make_credential(db)
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        monkeypatch.setenv("E4TESTPROVIDER_API_KEY", "dummy-header-test")
        resp = client.post(
            "/api/v1/credential-refs/cred-e4-001/resolve",
            headers={**auth(token), "X-AGAIN-Service-Context": '{"mode":"LOCAL_TRUSTED_SERVICE_CONTEXT","systemId":"ACCOUNT_AGAIN"}'},
            json={"tenantId": "t1", "provider": "e4testprovider", "purpose": "x"},
        )
        # Succeeds using the TOKEN's identity (LOCAL_AI_CONTROL_CENTER), proving the
        # header (claiming ACCOUNT_AGAIN) had no effect on the outcome.
        assert resp.status_code == 200
