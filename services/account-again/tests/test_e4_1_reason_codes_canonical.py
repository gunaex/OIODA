"""Account Again — E4.1 reason-code canonicalization + cloud/local + entitlementDecisionId.

E4.1 §5/§6: every EntitlementDecision must carry an entitlementDecisionId and a
reason_code drawn exclusively from entitlement_engine.REASON_CODES (the single source of
truth this repo maintains — contracts/v2/schemas/EntitlementDecision.json's reasonCode
enum is generated to match it, see scripts/export-reason-codes.py).
"""

import json
from account_again.services.entitlement_engine import REASON_CODES
from account_again.models import Tenant, Account, AIEntitlement, ServiceIdentity


def make_tenant(db, tenant_id="t1", status="ACTIVE"):
    t = Tenant(tenant_id=tenant_id, name="T", status=status)
    db.add(t)
    db.commit()
    return t


class TestEntitlementDecisionIdentity:
    def test_decision_id_present_on_allow(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE"))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE",
        })
        data = resp.json()
        assert data["decision"] == "ALLOW"
        assert data["entitlementDecisionId"]
        assert data["reasonCode"] in REASON_CODES

    def test_decision_id_present_on_deny(self, client, db):
        resp = client.post("/api/v1/entitlements/evaluate", json={"tenantId": "does-not-exist"})
        data = resp.json()
        assert data["decision"] == "DENY"
        assert data["entitlementDecisionId"]
        assert data["reasonCode"] in REASON_CODES

    def test_decision_id_unique_per_call(self, client, db):
        make_tenant(db)
        ids = set()
        for _ in range(5):
            resp = client.post("/api/v1/entitlements/evaluate", json={"tenantId": "t1"})
            ids.add(resp.json()["entitlementDecisionId"])
        assert len(ids) == 5

    def test_decision_id_traceable_in_audit(self, client, db):
        make_tenant(db)
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "correlationId": "CORR-TRACE-001",
        })
        decision_id = resp.json()["entitlementDecisionId"]
        audit = client.get("/api/v1/audit", params={"tenantId": "t1"}).json()
        match = [a for a in audit if a["targetId"] == decision_id]
        assert len(match) == 1
        assert match[0]["correlationId"] == "CORR-TRACE-001"


class TestReasonCodeCanonical:
    """Exercise every real DENY path and confirm the emitted reasonCode is in the
    canonical set — not just plausible-looking, but exactly the one used elsewhere."""

    def test_tenant_not_found(self, client, db):
        resp = client.post("/api/v1/entitlements/evaluate", json={"tenantId": "nope"})
        assert resp.json()["reasonCode"] == "TENANT_NOT_FOUND"

    def test_tenant_suspended(self, client, db):
        make_tenant(db, status="SUSPENDED")
        resp = client.post("/api/v1/entitlements/evaluate", json={"tenantId": "t1"})
        assert resp.json()["reasonCode"] == "TENANT_SUSPENDED"

    def test_capability_not_entitled(self, client, db):
        make_tenant(db)
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE",
        })
        assert resp.json()["reasonCode"] == "CAPABILITY_NOT_ENTITLED"

    def test_all_engine_reason_codes_are_canonical(self):
        """Static sweep: read the engine source and confirm every reason_code string
        literal passed to deny(...) or EntitlementDecision(...) is in REASON_CODES."""
        import inspect
        from account_again.services import entitlement_engine
        source = inspect.getsource(entitlement_engine)
        import re
        # crude but effective: find deny("XXX" and reason_code="XXX"
        found = set(re.findall(r'deny\(\s*"([A-Z_]+)"', source))
        found |= set(re.findall(r'reason_code="([A-Z_]+)"', source))
        assert found, "no reason codes found in engine source — test is broken"
        unknown = found - REASON_CODES
        assert not unknown, f"engine emits reason codes not in canonical REASON_CODES: {unknown}"


class TestCloudLocalPolicy:
    def test_local_only_blocks_cloud_provider(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", local_only=True))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE", "provider": "openai",
        })
        data = resp.json()
        assert data["decision"] == "DENY"
        assert data["reasonCode"] == "CLOUD_NOT_ALLOWED"

    def test_local_only_allows_ollama(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", local_only=True))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE", "provider": "ollama",
        })
        assert resp.json()["decision"] == "ALLOW"

    def test_cloud_allowed_false_blocks_cloud_provider(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", cloud_allowed=False))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE", "provider": "anthropic",
        })
        data = resp.json()
        assert data["decision"] == "DENY"
        assert data["reasonCode"] == "CLOUD_NOT_ALLOWED"

    def test_cloud_allowed_true_allows_cloud_provider(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", cloud_allowed=True))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE", "provider": "anthropic",
        })
        assert resp.json()["decision"] == "ALLOW"

    def test_provider_allowlist_denies_other_provider(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", provider_constraint="ollama"))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE", "provider": "openai",
        })
        assert resp.json()["reasonCode"] == "PROVIDER_NOT_ALLOWED"

    def test_model_allowlist_denies_other_model(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", model_constraint="qwen2.5-coder:7b"))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE", "provider": "ollama", "model": "llama3.1:8b",
        })
        assert resp.json()["reasonCode"] == "MODEL_NOT_ALLOWED"

    def test_response_includes_cloud_allowed_field(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE", cloud_allowed=False))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "t1", "capability": "AI_CODE",
        })
        assert resp.json()["cloudAllowed"] is False


def _direct_service_identity_token(client, db, system_id: str, tenant_id=None, status="ACTIVE") -> str:
    """Like make_service_token, but inserts the ServiceIdentity directly (bypassing the
    API's VALID_SYSTEM_IDS check) so tests can use descriptive fictional system IDs.
    Token issuance itself doesn't check VALID_SYSTEM_IDS — only creation does."""
    sid = f"svc-{system_id.lower()}"
    db.add(ServiceIdentity(service_identity_id=sid, system_id=system_id, tenant_id=tenant_id, status=status))
    db.commit()
    secret = "test-client-secret-not-real"
    client.post(f"/api/v1/service-identities/{sid}/rotate-client-secret", json={"clientSecret": secret})
    resp = client.post("/api/v1/auth/service-token", json={"systemId": system_id, "clientSecret": secret})
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


class TestCrossTenantUsageSubmission:
    """E4.1 §19 / E5.1 §15: tenant enforcement for usage submission, now driven by the
    verified token identity rather than a self-reported body field."""

    def test_unscoped_service_identity_can_submit_any_tenant(self, client, db):
        """No cross-check possible without tenant scoping — documents the real limit of
        domain-only enforcement (see E5_IDENTITY_AND_SERVICE_AUTH.md)."""
        make_tenant(db, tenant_id="tenant-a")
        token = _direct_service_identity_token(client, db, "GLOBAL_SVC")
        resp = client.post("/api/v1/usage", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "tenant-a", "capability": "AI_CODE",
        })
        assert resp.status_code == 200

    def test_tenant_scoped_service_identity_blocked_from_other_tenant(self, client, db):
        make_tenant(db, tenant_id="tenant-a")
        make_tenant(db, tenant_id="tenant-b")
        token = _direct_service_identity_token(client, db, "SCOPED_SVC", tenant_id="tenant-a")
        resp = client.post("/api/v1/usage", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "tenant-b", "capability": "AI_CODE",
        })
        assert resp.status_code == 403

    def test_tenant_scoped_service_identity_allowed_own_tenant(self, client, db):
        make_tenant(db, tenant_id="tenant-a")
        token = _direct_service_identity_token(client, db, "SCOPED_SVC", tenant_id="tenant-a")
        resp = client.post("/api/v1/usage", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "tenant-a", "capability": "AI_CODE",
        })
        assert resp.status_code == 200

    def test_revoked_after_token_issuance_blocked_from_usage_submission(self, client, db):
        make_tenant(db, tenant_id="tenant-a")
        token = _direct_service_identity_token(client, db, "REVOKED_SVC", tenant_id="tenant-a")
        svc = db.query(ServiceIdentity).filter(ServiceIdentity.system_id == "REVOKED_SVC").first()
        client.post(f"/api/v1/service-identities/{svc.service_identity_id}/revoke")
        resp = client.post("/api/v1/usage", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "tenant-a",
        })
        assert resp.status_code == 403

    def test_missing_token_rejected(self, client, db):
        make_tenant(db, tenant_id="tenant-a")
        resp = client.post("/api/v1/usage", json={"tenantId": "tenant-a"})
        assert resp.status_code == 401

    def test_body_serviceSystemId_cannot_masquerade_as_different_token_identity(self, client, db):
        make_tenant(db, tenant_id="tenant-a")
        token = _direct_service_identity_token(client, db, "REAL_CALLER", tenant_id="tenant-a")
        resp = client.post("/api/v1/usage", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "tenant-a", "serviceSystemId": "SOME_OTHER_SYSTEM",
        })
        assert resp.status_code == 403


class TestServiceIdentityTenantScoping:
    def test_tenant_scoped_service_identity_rejects_other_tenant(self, client, db):
        make_tenant(db, tenant_id="tenant-a")
        make_tenant(db, tenant_id="tenant-b")
        db.add(ServiceIdentity(service_identity_id="svc1", system_id="SCOPED_SVC", tenant_id="tenant-a"))
        db.commit()
        resp = client.post("/api/v1/entitlements/evaluate", json={
            "tenantId": "tenant-b", "serviceSystemId": "SCOPED_SVC",
        })
        assert resp.json()["decision"] == "DENY"
        assert resp.json()["reasonCode"] == "TENANT_MISMATCH"
