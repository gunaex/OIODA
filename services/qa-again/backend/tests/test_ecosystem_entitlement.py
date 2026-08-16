"""QA-E6 — live product entitlement enforcement against the running
Account Again instance (no dependency override — this exercises the real
HTTP round trip). Skipped if Account Again isn't reachable locally."""

import pytest

from app.ecosystem import account_again_client, ecosystem_auth
from app.ecosystem.ecosystem_auth import require_ecosystem_identity
from app.main import app
from fastapi import HTTPException, Request


@pytest.fixture(autouse=True)
def _skip_if_account_again_down():
    if not account_again_client.health():
        pytest.skip("Account Again not reachable at ACCOUNT_AGAIN_URL")


@pytest.fixture(autouse=True)
def _ecosystem_mode_on(monkeypatch):
    monkeypatch.setattr(ecosystem_auth, "ECOSYSTEM_MODE", True)


def teardown_function(_fn):
    app.dependency_overrides.pop(require_ecosystem_identity, None)


def _fake_request(headers: dict) -> Request:
    scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope)


class _StubUser:
    tenant_id = None


def test_bootstrapped_local_tenant_is_entitled_for_qa_again():
    """local-tenant was seeded with an ACTIVE QA_AGAIN product entitlement
    by Account Again's own bootstrap script — a live ALLOW is expected."""
    request = _fake_request({"X-Tenant-Id": "local-tenant"})
    identity = require_ecosystem_identity(request=request, user=_StubUser())
    assert identity.tenant_id == "local-tenant"
    assert identity.entitlement_decision["decision"] == "ALLOW"


def test_unentitled_tenant_is_denied_live():
    """QA_PRODUCT_ENTITLEMENT_DENY: a tenant with no QA_AGAIN
    ProductEntitlement row gets a real, live DENY — not a fabricated one."""
    request = _fake_request({"X-Tenant-Id": "tenant-with-no-qa-entitlement"})
    with pytest.raises(HTTPException) as exc_info:
        require_ecosystem_identity(request=request, user=_StubUser())
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"] == "QA_AGAIN_ENTITLEMENT_DENIED"
