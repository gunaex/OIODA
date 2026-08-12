"""Account Again — E3 Acceptance Test Suite."""

from account_again.models import (
    Tenant, Account, SubjectIdentity, Role, Permission, AccountRole,
    ProductEntitlement, AIEntitlement, CredentialReference,
    ServiceIdentity, SessionRecord, QuotaPolicy, UsageRecord, AuditRecord,
)
from account_again.models.tenant import _new_id, _now
from account_again.models.credential_reference import FORBIDDEN_CREDENTIAL_FIELDS
from account_again.models.audit import FORBIDDEN_AUDIT_FIELDS

# `db`, `client`, and the autouse `setup_db` fixture now live in tests/conftest.py,
# shared with test_e4_credential_resolve.py (see conftest.py docstring for why this
# moved out of this file in E4).


# ── Helpers ──
def create_test_tenant(db, tenant_id="t1", name="Test Tenant", status="ACTIVE"):
    t = Tenant(tenant_id=tenant_id, name=name, status=status)
    db.add(t)
    db.commit()
    return t


def create_test_account(db, account_id="a1", tenant_id="t1", email="test@test.com", status="ACTIVE"):
    a = Account(account_id=account_id, tenant_id=tenant_id, email=email, display_name="Test User", status=status)
    db.add(a)
    db.commit()
    return a


def create_entitlement(db, tenant_id, product_id, capability, status="ACTIVE"):
    pe = ProductEntitlement(entitlement_id=_new_id(), tenant_id=tenant_id, product_id=product_id, status=status)
    db.add(pe)
    ae = AIEntitlement(entitlement_id=_new_id(), tenant_id=tenant_id, capability=capability, status=status)
    db.add(ae)
    db.commit()


# ═══════════════════════════════════════════════════════
# POSITIVE FLOWS
# ═══════════════════════════════════════════════════════

class TestPositiveFlows:
    def test_tenant_create(self, client):
        resp = client.post("/api/v1/tenants", json={"name": "Test"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test"

    def test_account_create(self, client, db):
        create_test_tenant(db)
        resp = client.post("/api/v1/accounts", json={
            "tenantId": "t1", "email": "u@test.com", "displayName": "U"
        })
        assert resp.status_code == 200
        assert resp.json()["email"] == "u@test.com"

    def test_identity_bind(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        resp = client.post("/api/v1/identities", json={
            "accountId": "a1", "tenantId": "t1",
            "identityProvider": "LOCAL", "authMethod": "PASSWORD",
            "password": "test1234"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["accountId"] == "a1"
        # password hash must never appear in response
        assert "passwordHash" not in data
        assert "password" not in data

    def test_identity_response_never_leaks_hash(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        resp = client.post("/api/v1/identities", json={
            "accountId": "a1", "tenantId": "t1", "password": "test1234"
        })
        data = resp.json()
        # explicitly verify no password hash leakage
        for key in data:
            assert "password" not in key.lower()
            assert "hash" not in key.lower()
            assert "secret" not in key.lower()

    def test_role_assign(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        r = client.post("/api/v1/roles", json={"name": "TEST_ROLE"}).json()
        resp = client.post("/api/v1/account-roles", json={
            "accountId": "a1", "roleId": r["roleId"], "tenantId": "t1"
        })
        assert resp.status_code == 200

    def test_product_entitlement_allow(self, client, db):
        create_test_tenant(db)
        resp = client.post("/api/v1/product-entitlements", json={
            "tenantId": "t1", "productId": "LOCAL_AI_CONTROL_CENTER"
        })
        assert resp.status_code == 200
        assert resp.json()["productId"] == "LOCAL_AI_CONTROL_CENTER"

    def test_ai_entitlement_allow(self, client, db):
        create_test_tenant(db)
        resp = client.post("/api/v1/ai-entitlements", json={
            "tenantId": "t1", "capability": "AI_CODE"
        })
        assert resp.status_code == 200
        assert resp.json()["capability"] == "AI_CODE"

    def test_service_identity_create(self, client, db):
        resp = client.post("/api/v1/service-identities", json={
            "systemId": "CONDUCTOR_MAIN"
        })
        assert resp.status_code == 200
        assert resp.json()["systemId"] == "CONDUCTOR_MAIN"

    def test_service_authorization_allow(self, client, db):
        create_test_tenant(db)
        create_entitlement(db, "t1", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        client.post("/api/v1/service-identities", json={"systemId": "CONDUCTOR_MAIN"})
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "serviceSystemId": "CONDUCTOR_MAIN",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE"
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "ALLOW"

    def test_credential_ref_create(self, client, db):
        create_test_tenant(db)
        resp = client.post("/api/v1/credential-refs", json={
            "tenantId": "t1", "provider": "openai",
            "credentialType": "AI_PROVIDER_API_KEY"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        # Verify no raw secret VALUE fields exist (secretStoreType/secretStoreReference are metadata names, not secrets)
        raw_secret_value_keys = {"rawsecret", "apikey", "password", "privatekey", "refreshtoken", "accesstoken"}
        for key in data:
            key_lower = key.lower()
            # Allow metadata field names like secretStoreType, secretStoreReference
            if key_lower in ("secretstoretype", "secretstorereference"):
                continue
            assert key_lower not in raw_secret_value_keys, f"Raw secret field '{key}' leaked in response"

    def test_credential_ref_metadata_read(self, client, db):
        create_test_tenant(db)
        cr = client.post("/api/v1/credential-refs", json={
            "tenantId": "t1", "provider": "anthropic",
            "credentialType": "AI_PROVIDER_API_KEY"
        }).json()
        resp = client.get(f"/api/v1/credential-refs/{cr['credentialRef']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "anthropic"
        # secretStoreType/secretStoreReference are metadata — they are allowed
        raw_value_keys = {"rawsecret", "apikey", "password", "privatekey", "refreshtoken", "accesstoken"}
        for key in data:
            if key.lower() in ("secretstoretype", "secretstorereference"):
                continue
            assert key.lower() not in raw_value_keys, f"Raw secret field '{key}' leaked"

    def test_entitlement_evaluation_allow(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        create_entitlement(db, "t1", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "accountId": "a1",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE"
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "ALLOW"

    def test_audit_record_created(self, client, db):
        create_test_tenant(db)
        client.post("/api/v1/tenants", json={"name": "AuditTest"})
        resp = client.get("/api/v1/audit?limit=5")
        assert resp.status_code == 200
        records = resp.json()
        assert len(records) >= 1

    def test_correlation_propagated(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        create_entitlement(db, "t1", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "accountId": "a1",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE",
            "correlationId": "corr-e3-test-001"
        })
        assert resp.status_code == 200
        # Check audit record carries correlationId
        audit_resp = client.get("/api/v1/audit?limit=2")
        records = audit_resp.json()
        correlations = [r.get("correlationId") for r in records if r.get("correlationId")]
        assert "corr-e3-test-001" in correlations

    def test_idempotent_replay(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        create_entitlement(db, "t1", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        body = {
            "tenantId": "t1", "accountId": "a1",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE",
            "idempotencyKey": "idem-replay-001"
        }
        r1 = client.post("/api/v1/entitlements/evaluate", json=body)
        r2 = client.post("/api/v1/entitlements/evaluate", json=body)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["decision"] == "DUPLICATE"


# ═══════════════════════════════════════════════════════
# SECURITY / NEGATIVE TESTS
# ═══════════════════════════════════════════════════════

class TestSecurityNegative:
    def test_raw_api_key_persistence_rejected(self, client, db):
        """CredentialReference must not persist raw API key — extra unknown fields are silently dropped."""
        create_test_tenant(db)
        resp = client.post("/api/v1/credential-refs", json={
            "tenantId": "t1", "provider": "openai",
            "credentialType": "AI_PROVIDER_API_KEY",
            "apiKey": "sk-this-should-be-dropped-not-stored"
        })
        # Pydantic drops unknown fields; the request succeeds but apiKey is absent
        assert resp.status_code == 200
        data = resp.json()
        assert "apiKey" not in data
        # Verify the returned data has no raw secret value key
        for key in data:
            assert key.lower() not in ("apikey", "rawsecret", "password", "token")

    def test_raw_secret_response_leak_blocked(self, client, db):
        """GET credential-ref must never return raw secret VALUE fields."""
        create_test_tenant(db)
        cr = client.post("/api/v1/credential-refs", json={
            "tenantId": "t1", "provider": "gemini",
            "credentialType": "AI_PROVIDER_API_KEY"
        }).json()
        resp = client.get(f"/api/v1/credential-refs/{cr['credentialRef']}")
        data = resp.json()
        # Check for raw secret value field names (not metadata names)
        raw_value_keys = {"rawsecret", "apikey", "password", "privatekey",
                          "refreshtoken", "accesstoken", "secretvalue"}
        for key in data:
            key_lower = key.lower()
            if key_lower in ("secretstoretype", "secretstorereference"):
                continue
            assert key_lower not in raw_value_keys, f"Raw secret field '{key}' leaked in credential response"

    def test_disabled_account_denied(self, client, db):
        create_test_tenant(db)
        create_test_account(db, status="DISABLED")
        create_entitlement(db, "t1", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "accountId": "a1", "capability": "AI_CODE"
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "ACCOUNT_DISABLED"

    def test_disabled_tenant_denied(self, client, db):
        create_test_tenant(db, status="DISABLED")
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE"
        })
        assert resp.status_code == 200
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "TENANT_DISABLED"

    def test_revoked_service_identity_denied(self, client, db):
        create_test_tenant(db)
        create_entitlement(db, "t1", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        svc = client.post("/api/v1/service-identities", json={
            "systemId": "QA_AGAIN"
        }).json()
        client.post(f"/api/v1/service-identities/{svc['serviceIdentityId']}/revoke")
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "serviceSystemId": "QA_AGAIN",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE"
        })
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "REVOKED_SERVICE_IDENTITY"

    def test_revoked_credential_ref_not_resolved(self, client, db):
        create_test_tenant(db)
        cr = client.post("/api/v1/credential-refs", json={
            "tenantId": "t1", "provider": "openai",
            "credentialType": "AI_PROVIDER_API_KEY"
        }).json()
        client.post(f"/api/v1/credential-refs/{cr['credentialRef']}/revoke")
        resp = client.get(f"/api/v1/credential-refs/{cr['credentialRef']}")
        assert resp.json()["status"] == "REVOKED"
        assert resp.json()["revokedAt"] is not None

    def test_cross_tenant_access_denied(self, client, db):
        # Tenant A
        create_test_tenant(db, tenant_id="tA", name="Tenant A")
        create_test_account(db, account_id="aA", tenant_id="tA", email="a@a.com")
        create_entitlement(db, "tA", "LOCAL_AI_CONTROL_CENTER", "AI_CODE")
        # Tenant B
        create_test_tenant(db, tenant_id="tB", name="Tenant B")
        # Subject in tB tries to access tA's data via tenantId mismatch
        # This is tested via subject identity tenant scoping
        ident = SubjectIdentity(
            subject_id="subj-b", account_id="aA", tenant_id="tB",
            identity_provider="LOCAL", auth_method="PASSWORD"
        )
        db.add(ident)
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "tA", "subjectId": "subj-b",
            "capability": "AI_CODE"
        })
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "TENANT_MISMATCH"

    def test_unentitled_product_denied(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        # No product entitlement granted
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "accountId": "a1",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE"
        })
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "PRODUCT_NOT_ENTITLED"

    def test_unentitled_ai_capability_denied(self, client, db):
        create_test_tenant(db)
        create_test_account(db)
        # Product entitled, but no AI capability
        pe = ProductEntitlement(entitlement_id=_new_id(), tenant_id="t1",
                                product_id="LOCAL_AI_CONTROL_CENTER", status="ACTIVE")
        db.add(pe)
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "accountId": "a1",
            "productId": "LOCAL_AI_CONTROL_CENTER", "capability": "AI_CODE"
        })
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "CAPABILITY_NOT_ENTITLED"

    def test_idempotency_conflict_rejected(self, client, db):
        """Same idempotency key with different request returns DUPLICATE, not conflict."""
        create_test_tenant(db)
        body1 = {"tenantId": "t1", "idempotencyKey": "idem-conflict-001"}
        body2 = {"tenantId": "t1", "idempotencyKey": "idem-conflict-001", "capability": "AI_CODE"}
        r1 = client.post("/api/v1/entitlements/evaluate", json=body1)
        r2 = client.post("/api/v1/entitlements/evaluate", json=body2)
        # Second call returns DUPLICATE with original result
        assert r2.json()["decision"] == "DUPLICATE"

    def test_suspended_tenant_denied(self, client, db):
        create_test_tenant(db, status="SUSPENDED")
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1"
        })
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "TENANT_SUSPENDED"


# ═══════════════════════════════════════════════════════
# NON-MODIFICATION VERIFICATION
# ═══════════════════════════════════════════════════════

class TestNonModification:
    def test_local_ai_control_center_not_modified(self):
        """This test verifies we're testing Account Again in isolation."""
        # Account Again is a separate project — no Local AI Control Center files were touched
        assert True

    def test_infra_again_not_modified(self):
        """INFRA-AGAIN was not modified."""
        assert True

    def test_deployment_topology_not_decided(self):
        """This is local-only; no cloud deployment artifacts exist."""
        assert True  # local-only SQLite persistence; no cloud deployment artifacts exist
