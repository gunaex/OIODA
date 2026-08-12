"""ECOSYSTEM-H1 — service identity regression tests.

HTTP 200 alone is not proof of service identity: PM Again and QA Again
both defaulted to :8000 locally, so a client that only checked the status
code would treat any service answering on that port as healthy. These
tests pin down the fix: check_service_identity() (and the PM/QA/Account
clients built on it) must fail closed on anything but an exact identity
match, not merely a reachable 200.
"""

import httpx
import pytest

from app.integration.pm_again_client import PMAgainClient
from app.integration.qa_again_client import QAAgainClient
from app.integration.service_health import check_service_identity


class _FakeResponse:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


def test_correct_service_accepted(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok", "service": "PM_AGAIN"}))
    assert check_service_identity("http://x/health", expected_service="PM_AGAIN", timeout=1.0) is True


def test_wrong_service_on_expected_port_rejected(monkeypatch):
    """The critical regression: something answers 200 on the expected port/URL,
    but it identifies as a different service (e.g. QA Again on PM's port)."""
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok", "service": "QA_AGAIN"}))
    assert check_service_identity("http://x/health", expected_service="PM_AGAIN", timeout=1.0) is False


def test_unreachable_service_rejected(monkeypatch):
    def _raise(url, timeout):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "get", _raise)
    assert check_service_identity("http://x/health", expected_service="PM_AGAIN", timeout=1.0) is False


def test_malformed_identity_rejected(monkeypatch):
    """Missing/non-JSON/wrong-shaped body must fail closed, not be treated
    as an implicit match."""
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok"}))
    assert check_service_identity("http://x/health", expected_service="PM_AGAIN", timeout=1.0) is False

    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, None))
    assert check_service_identity("http://x/health", expected_service="PM_AGAIN", timeout=1.0) is False

    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, ["not", "a", "dict"]))
    assert check_service_identity("http://x/health", expected_service="PM_AGAIN", timeout=1.0) is False


def test_pm_adapter_health_rejects_qa_again_masquerading_on_pm_port(monkeypatch):
    """Direct regression for the reported defect: PMAgainClient.health()
    must be False when the responder at PM_AGAIN_URL is actually QA Again."""
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok", "service": "QA_AGAIN"}))
    assert PMAgainClient.health() is False


def test_qa_adapter_health_rejects_pm_again_masquerading_on_qa_port(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok", "service": "PM_AGAIN"}))
    assert QAAgainClient.health() is False


def test_pm_adapter_health_accepts_real_pm_again(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok", "service": "PM_AGAIN"}))
    assert PMAgainClient.health() is True


def test_qa_adapter_health_accepts_real_qa_again(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _FakeResponse(200, {"status": "ok", "service": "QA_AGAIN"}))
    assert QAAgainClient.health() is True
