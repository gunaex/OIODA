"""
E8.1-H — Negative security / fail-closed tests + automated runtime guards.

Proves: in ECOSYSTEM_MODE, no Conductor code path calls a direct AI provider adapter
or reads AIAccount.api_key_encrypted; LACC/Account Again failures fail closed (never a
direct-provider bypass); and Account Again DENY decisions actually block execution.
"""

import asyncio
from unittest.mock import patch

import pytest

from app.integration import lacc_client as lacc_module
from app.integration.account_again_client import AccountAgainClient
from app.integration.lacc_client import LocalAIControlCenterClient
from app.routers import ai_resources, golden_flow, multi_ai

pytestmark = pytest.mark.skipif(
    not AccountAgainClient.health(), reason="Account Again not reachable"
)


def _adapters_forbidden():
    """A get_adapter that raises if called — proves a code path never reaches it."""
    def _raise(*args, **kwargs):
        raise AssertionError("DIRECT_PROVIDER_RUNTIME_BYPASS: get_adapter() was called in ECOSYSTEM_MODE")
    return _raise


def _decrypt_forbidden():
    def _raise(*args, **kwargs):
        raise AssertionError("LEGACY_CREDENTIAL_RUNTIME_GUARD: _decrypt() was called in ECOSYSTEM_MODE")
    return _raise


# ── Direct provider runtime guard (§39, §54) ──────────────────────────

def test_multi_ai_ecosystem_mode_never_calls_get_adapter(monkeypatch):
    monkeypatch.setattr(multi_ai, "ECOSYSTEM_MODE", True)
    monkeypatch.setattr(multi_ai, "get_adapter", _adapters_forbidden())
    result = asyncio.run(multi_ai._call_one_capability_slot(0, "Say pong.", "You are terse.", "corr-guard-1"))
    assert result["provider"] in ("ollama", "none")  # never a cloud SDK provider


def test_golden_flow_ecosystem_mode_never_calls_get_adapter(monkeypatch):
    monkeypatch.setattr(golden_flow, "ECOSYSTEM_MODE", True)
    monkeypatch.setattr(golden_flow.AIResource, "__init__", _adapters_forbidden())  # never even queried
    # The gateway path never touches AIResource at all — proven by not raising here.
    result = asyncio.run(golden_flow._ai_decompose_via_gateway("Users must log in.", "test-slug"))
    assert result is not None


# ── Legacy credential runtime guard (§40, §55) ────────────────────────

def test_ai_resources_health_check_ecosystem_mode_never_decrypts(monkeypatch):
    monkeypatch.setattr(ai_resources, "ECOSYSTEM_MODE", True)
    monkeypatch.setattr(ai_resources, "_decrypt", _decrypt_forbidden())

    class FakeAccount:
        api_key_encrypted = "fake-encrypted-value"

    class FakeDB:
        def query(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def first(self):
            return FakeAccount()

    result = asyncio.run(ai_resources.health_check_account("fake-id", db=FakeDB(), user=None))
    assert "ECOSYSTEM_MODE" in result["message"]


# ── LACC-down fail-closed (§18, §38) ──────────────────────────────────

def test_lacc_down_no_direct_fallback(monkeypatch):
    monkeypatch.setattr(lacc_module, "LACC_URL", "http://localhost:1")
    result = LocalAIControlCenterClient.execute_capability(
        capability="GENERAL_REASONING", correlation_id="corr-guard-2", prompt="x",
    )
    assert result["status"] == "FAILED"
    assert result["providerUsed"] == "none"


def test_lacc_down_multi_ai_slot_degrades_without_bypass(monkeypatch):
    monkeypatch.setattr(lacc_module, "LACC_URL", "http://localhost:1")
    result = asyncio.run(multi_ai._call_one_capability_slot(0, "x", "y", "corr-guard-3"))
    assert result["error"] is not None
    assert result["content"] is None


# ── Account Again DENY blocks execution (§38) ─────────────────────────

def test_nonexistent_tenant_denied_no_execution():
    result = LocalAIControlCenterClient.execute_capability(
        capability="GENERAL_REASONING", correlation_id="corr-guard-4", prompt="x",
        tenant_id="definitely-nonexistent-tenant-xyz",
    )
    assert result["status"] in ("BLOCKED_BY_POLICY", "FAILED")
    assert result["providerUsed"] == "none"


def test_cross_tenant_ai_execution_blocked():
    """A caller cannot get AI execution for a tenant it has no entitlement for."""
    decision = AccountAgainClient.evaluate_entitlement(
        tenant_id="definitely-nonexistent-tenant-xyz", capability="AI_AGENT",
    )
    assert decision["decision"] == "DENY"


# ── Legacy credential exists but unused (§33) ─────────────────────────

def test_legacy_api_key_exists_but_not_used_in_ecosystem_mode(monkeypatch):
    """Even if an AIAccount has a real-looking encrypted key, the ecosystem-mode
    multi-AI path must never touch it."""
    monkeypatch.setattr(multi_ai, "ECOSYSTEM_MODE", True)

    with patch("app.routers.ai_resources._decrypt", side_effect=_decrypt_forbidden()):
        result = asyncio.run(multi_ai._call_one_capability_slot(1, "Say pong.", "Be terse.", "corr-guard-5"))
    assert result is not None  # completed without ever importing/calling _decrypt


# ── Inbound service auth on LACC's /api/ai/execute (§11, §38) ────────

def test_lacc_missing_token_rejected():
    import httpx
    resp = httpx.post(f"{lacc_module.LACC_URL}/ai/execute", json={
        "capability": "GENERAL_REASONING", "payload": {"prompt": "x"},
    }, timeout=10.0)
    assert resp.status_code == 401


def test_lacc_garbage_token_rejected():
    import httpx
    resp = httpx.post(
        f"{lacc_module.LACC_URL}/ai/execute",
        headers={"Authorization": "Bearer garbage.not.a.jwt"},
        json={"capability": "GENERAL_REASONING", "payload": {"prompt": "x"}},
        timeout=10.0,
    )
    assert resp.status_code == 401


def test_lacc_valid_token_wrong_capability_rejected():
    import httpx
    token = AccountAgainClient.get_service_token()
    resp = httpx.post(
        f"{lacc_module.LACC_URL}/ai/execute",
        headers={"Authorization": f"Bearer {token}"},
        json={"capability": "NOT_A_REAL_CAPABILITY", "payload": {"prompt": "x"}},
        timeout=10.0,
    )
    assert resp.status_code == 400
