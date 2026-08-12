"""E5.1 test helper — NOT a conftest.py (deliberately: a second module doing
`app.dependency_overrides[get_db] = ...` at import time caused a real test-isolation bug
in E4.1, see conftest.py's docstring; this module does no such thing, so a plain
`from tests._auth_helpers import make_service_token` import is safe)."""


def make_service_token(client, system_id: str, tenant_id: str | None = None, secret: str = "test-client-secret-not-real") -> str:
    """Create a ServiceIdentity (or reuse if it already exists), rotate its client
    secret, and exchange it for a real signed JWT via the real /auth/service-token
    endpoint. Returns the bearer token string (no "Bearer " prefix)."""
    resp = client.post("/api/v1/service-identities", json={"systemId": system_id, "tenantId": tenant_id})
    if resp.status_code == 200:
        service_identity_id = resp.json()["serviceIdentityId"]
    else:
        existing = client.get("/api/v1/service-identities").json()
        service_identity_id = next(s["serviceIdentityId"] for s in existing if s["systemId"] == system_id)

    client.post(f"/api/v1/service-identities/{service_identity_id}/rotate-client-secret", json={"clientSecret": secret})
    token_resp = client.post("/api/v1/auth/service-token", json={"systemId": system_id, "clientSecret": secret})
    assert token_resp.status_code == 200, token_resp.text
    return token_resp.json()["accessToken"]
