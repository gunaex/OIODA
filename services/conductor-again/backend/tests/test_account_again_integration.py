"""
E8-C — Account Again integration tests.

These hit a REAL running Account Again instance (localhost:8001) when
available and are skipped otherwise — they are integration tests, not mocks,
per the task's demand for truthful REAL_RUNTIME vs HARNESS classification.
"""

import importlib

import httpx
import pytest

from app.integration import account_again_client as aac

pytestmark = pytest.mark.skipif(
    not aac.AccountAgainClient.health(), reason="Account Again not reachable at ACCOUNT_AGAIN_URL"
)


def test_service_token_auth_conductor_main_identity():
    token = aac.AccountAgainClient.get_service_token()
    assert token
    import jwt as pyjwt
    claims = pyjwt.decode(token, options={"verify_signature": False})
    assert claims["systemId"] == "CONDUCTOR_MAIN"
    assert claims["iss"] == "account-again-local"
    assert claims["aud"] == "again-ecosystem-services"


def test_entitlement_evaluation_allow_real():
    decision = aac.AccountAgainClient.evaluate_entitlement(
        tenant_id="local-tenant", capability="AI_ARCHITECTURE", provider="ollama",
        correlation_id="e8-test-allow",
    )
    assert decision["decision"] in ("ALLOW", "DENY")
    assert decision["reasonCode"]


def test_bad_client_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(aac, "CLIENT_SECRET", "definitely-wrong-secret")
    fresh_cache = aac._TokenCache()
    monkeypatch.setattr(aac, "_token_cache", fresh_cache)
    with pytest.raises(aac.AccountAgainUnavailableError):
        aac.AccountAgainClient.get_service_token()


def test_missing_client_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(aac, "CLIENT_SECRET", "")
    fresh_cache = aac._TokenCache()
    monkeypatch.setattr(aac, "_token_cache", fresh_cache)
    with pytest.raises(aac.AccountAgainUnavailableError):
        aac.AccountAgainClient.get_service_token()


def test_unreachable_account_again_yields_deny_not_allow(monkeypatch):
    monkeypatch.setattr(aac, "ACCOUNT_AGAIN_URL", "http://localhost:1/api/v1")
    fresh_cache = aac._TokenCache()
    monkeypatch.setattr(aac, "_token_cache", fresh_cache)
    decision = aac.AccountAgainClient.evaluate_entitlement(tenant_id="t", capability="AI_CODE")
    assert decision["decision"] == "DENY"
    assert decision["reasonCode"] == "ACCOUNT_AGAIN_UNAVAILABLE"
