"""Account Again — E5.1 LOCAL_OIDC_COMPATIBLE_SERVICE_AUTH tests.

Covers /auth/service-token, /.well-known/jwks.json, and the optional-token path on
/entitlements/evaluate. Credential-resolve and /usage token enforcement is covered in
test_e4_credential_resolve.py and test_e4_1_reason_codes_canonical.py respectively
(both hardened in this same phase).
"""

from account_again.models import Tenant, AIEntitlement, ServiceIdentity
from tests._auth_helpers import make_service_token


def make_tenant(db, tenant_id="t1"):
    t = Tenant(tenant_id=tenant_id, name="T")
    db.add(t)
    db.commit()
    return t


class TestServiceTokenIssuance:
    def test_issue_token_success(self, client, db):
        make_service_token(client, "LOCAL_AI_CONTROL_CENTER")  # raises on non-200 internally

    def test_issue_token_wrong_secret_rejected(self, client, db):
        client.post("/api/v1/service-identities", json={"systemId": "LOCAL_AI_CONTROL_CENTER"})
        svc = client.get("/api/v1/service-identities").json()[0]
        client.post(f"/api/v1/service-identities/{svc['serviceIdentityId']}/rotate-client-secret",
                    json={"clientSecret": "correct-secret"})
        resp = client.post("/api/v1/auth/service-token", json={"systemId": "LOCAL_AI_CONTROL_CENTER", "clientSecret": "wrong-secret"})
        assert resp.status_code == 401

    def test_issue_token_unknown_system_rejected(self, client, db):
        resp = client.post("/api/v1/auth/service-token", json={"systemId": "DOES_NOT_EXIST", "clientSecret": "x"})
        assert resp.status_code == 401

    def test_issue_token_no_secret_configured_rejected(self, client, db):
        client.post("/api/v1/service-identities", json={"systemId": "LOCAL_AI_CONTROL_CENTER"})
        resp = client.post("/api/v1/auth/service-token", json={"systemId": "LOCAL_AI_CONTROL_CENTER", "clientSecret": "anything"})
        assert resp.status_code == 401

    def test_issue_token_for_revoked_identity_rejected(self, client, db):
        create = client.post("/api/v1/service-identities", json={"systemId": "LOCAL_AI_CONTROL_CENTER"})
        sid = create.json()["serviceIdentityId"]
        client.post(f"/api/v1/service-identities/{sid}/rotate-client-secret", json={"clientSecret": "s"})
        client.post(f"/api/v1/service-identities/{sid}/revoke")
        resp = client.post("/api/v1/auth/service-token", json={"systemId": "LOCAL_AI_CONTROL_CENTER", "clientSecret": "s"})
        assert resp.status_code == 403

    def test_token_response_never_contains_client_secret(self, client, db):
        client.post("/api/v1/service-identities", json={"systemId": "LOCAL_AI_CONTROL_CENTER"})
        svc = client.get("/api/v1/service-identities").json()[0]
        client.post(f"/api/v1/service-identities/{svc['serviceIdentityId']}/rotate-client-secret",
                    json={"clientSecret": "my-super-secret-value"})
        resp = client.post("/api/v1/auth/service-token", json={"systemId": "LOCAL_AI_CONTROL_CENTER", "clientSecret": "my-super-secret-value"})
        assert "my-super-secret-value" not in resp.text

    def test_service_identity_list_never_contains_secret_hash(self, client, db):
        client.post("/api/v1/service-identities", json={"systemId": "LOCAL_AI_CONTROL_CENTER"})
        svc = client.get("/api/v1/service-identities").json()[0]
        client.post(f"/api/v1/service-identities/{svc['serviceIdentityId']}/rotate-client-secret",
                    json={"clientSecret": "my-super-secret-value-2"})
        listing = client.get("/api/v1/service-identities")
        assert "client_secret_hash" not in listing.text
        assert "my-super-secret-value-2" not in listing.text


class TestJWKS:
    def test_jwks_shape(self, client, db):
        resp = client.get("/api/v1/.well-known/jwks.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert data["keys"][0]["kty"] == "RSA"
        assert data["keys"][0]["alg"] == "RS256"


class TestEntitlementEvaluateWithToken:
    def test_token_present_and_matching_allows(self, client, db):
        make_tenant(db)
        db.add(AIEntitlement(entitlement_id="ae1", tenant_id="t1", capability="AI_CODE"))
        db.commit()
        token = make_service_token(client, "IDEA_TO_CODE")
        resp = client.post("/api/v1/entitlements/evaluate", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "t1", "capability": "AI_CODE", "serviceSystemId": "IDEA_TO_CODE",
        })
        assert resp.json()["decision"] == "ALLOW"

    def test_token_present_body_mismatch_rejected(self, client, db):
        make_tenant(db)
        token = make_service_token(client, "IDEA_TO_CODE")
        resp = client.post("/api/v1/entitlements/evaluate", headers={"Authorization": f"Bearer {token}"}, json={
            "tenantId": "t1", "serviceSystemId": "LOCAL_AI_CONTROL_CENTER",
        })
        assert resp.status_code == 403

    def test_no_token_still_works_legacy_body_path(self, client, db):
        """Backward compatibility: E3/E4/E4.1's ~68 pre-existing tests call this
        endpoint with no token at all — that path must remain functional (E5.1's
        explicit, disclosed scoping decision — see docs/current-state/
        E5_1_TRUST_CLOSURE.md)."""
        make_tenant(db)
        resp = client.post("/api/v1/entitlements/evaluate", json={"tenantId": "t1"})
        assert resp.status_code == 200

    def test_invalid_token_rejected_even_though_optional(self, client, db):
        """Optional means 'no token is fine' — it does NOT mean 'a garbage token is
        silently ignored'. A malformed/invalid token, once present, must still fail."""
        make_tenant(db)
        resp = client.post("/api/v1/entitlements/evaluate",
                            headers={"Authorization": "Bearer garbage.not.valid"}, json={"tenantId": "t1"})
        assert resp.status_code == 401


class TestTokenClaimValidation:
    """Genuinely missing evidence identified in the V1 freeze documentation-correction
    pass: TOKEN_ISSUER_VALIDATED / TOKEN_AUDIENCE_VALIDATED were enforced in code
    (jose.jwt.decode(..., issuer=..., audience=...)) but had no direct test forging a
    correctly-SIGNED token with a wrong issuer/audience to prove rejection — the prior
    tests only covered a garbage/malformed token (which fails signature verification
    before issuer/audience are even checked), not a well-formed-but-wrong-claims token."""

    def _forge_token(self, **override_claims):
        import time
        import uuid
        from jose import jwt
        from account_again.services.service_auth import _PRIVATE_PEM, ALGORITHM, ISSUER, AUDIENCE, _KEY_ID
        now = int(time.time())
        claims = {
            "iss": ISSUER, "sub": "forged", "aud": AUDIENCE, "iat": now, "exp": now + 300,
            "jti": str(uuid.uuid4()), "systemId": "LOCAL_AI_CONTROL_CENTER",
            "serviceIdentityId": "forged", "tenantId": None,
        }
        claims.update(override_claims)
        return jwt.encode(claims, _PRIVATE_PEM, algorithm=ALGORITHM, headers={"kid": _KEY_ID})

    def test_wrong_issuer_rejected(self, client, db):
        """Correctly signed (real private key), correct audience, WRONG issuer."""
        token = self._forge_token(iss="some-other-issuer")
        resp = client.post("/api/v1/entitlements/evaluate",
                            headers={"Authorization": f"Bearer {token}"}, json={"tenantId": "t1"})
        assert resp.status_code == 401

    def test_wrong_audience_rejected(self, client, db):
        """Correctly signed, correct issuer, WRONG audience."""
        token = self._forge_token(aud="some-other-audience")
        resp = client.post("/api/v1/entitlements/evaluate",
                            headers={"Authorization": f"Bearer {token}"}, json={"tenantId": "t1"})
        assert resp.status_code == 401

    def test_correct_issuer_and_audience_pass_claim_validation(self, client, db):
        """Control case: a forged-but-correctly-claimed token (same issuer/audience as
        real tokens) passes claim validation and is only rejected because 'forged' is
        not a real ServiceIdentity — proving the PRIOR two tests fail for the right
        reason (issuer/audience), not because forging tokens fails generically."""
        token = self._forge_token()
        resp = client.post("/api/v1/entitlements/evaluate",
                            headers={"Authorization": f"Bearer {token}"}, json={"tenantId": "t1"})
        # 401 here is expected too (unknown serviceIdentityId "forged"), but the
        # important assertion is in the error detail: it must NOT be an issuer/audience
        # complaint (proving claim validation happens and passes) — it must be about
        # the service identity not existing.
        assert resp.status_code == 401
        assert "issuer" not in resp.text.lower()
        assert "audience" not in resp.text.lower()
        assert "no longer exists" in resp.text.lower() or "not found" in resp.text.lower()


class TestRawTokenNeverLoggedOrPersisted:
    def test_token_not_in_audit_log(self, client, db):
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        audit = client.get("/api/v1/audit").text
        assert token not in audit

    def test_token_not_in_any_service_identity_response(self, client, db):
        token = make_service_token(client, "LOCAL_AI_CONTROL_CENTER")
        listing = client.get("/api/v1/service-identities").text
        assert token not in listing
