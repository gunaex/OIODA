"""QA-E6 — live RS256/JWKS round trip against the running Account Again
instance: QA Again obtains its own real service token and verifies it the
same way it would verify an inbound CONDUCTOR_MAIN token. No mocking on
either side of this call. Skipped if Account Again or QA Again's own
client secret isn't configured/reachable."""

from fastapi import Request
from fastapi.testclient import TestClient
import pytest

from app.ecosystem import account_again_client
from app.ecosystem.service_auth import require_conductor_service_identity
from app.main import app


@pytest.fixture(autouse=True)
def _skip_if_not_configured():
    if not account_again_client.is_configured():
        pytest.skip("ACCOUNT_AGAIN_CLIENT_SECRET not configured for QA_AGAIN")
    if not account_again_client.health():
        pytest.skip("Account Again not reachable at ACCOUNT_AGAIN_URL")


def test_qa_again_obtains_and_verifies_its_own_live_service_token():
    token = account_again_client.get_service_token()
    assert token

    claims = account_again_client.verify_service_token(token)
    assert claims["systemId"] == "QA_AGAIN"


def test_garbage_token_fails_live_verification():
    with pytest.raises(account_again_client.ServiceAuthError):
        account_again_client.verify_service_token("not-a-real-jwt")


def test_wrong_system_identity_spoof_blocked_even_with_valid_token():
    """SERVICE_IDENTITY_SPOOF_BLOCKED: a genuinely valid, Account-Again-
    signed token — just for QA_AGAIN itself, not CONDUCTOR_MAIN — must
    still be rejected by the Conductor-only intake boundary. A real
    signature alone is not sufficient authorization."""
    qa_again_token = account_again_client.get_service_token()

    client = TestClient(app)
    resp = client.post(
        "/api/ecosystem/qa-requests",
        json={"qaRequestId": "qar-spoof", "correlationId": "c", "workPackageId": "wp-spoof",
              "releaseCandidate": {"repo": "r", "branch": "b", "commit": "c"},
              "acceptanceCriteria": {}, "createdAt": "2026-08-12T00:00:00Z"},
        headers={"Authorization": f"Bearer {qa_again_token}"},
    )
    assert resp.status_code == 403
    assert "not permitted to dispatch work here" in resp.json()["detail"]
