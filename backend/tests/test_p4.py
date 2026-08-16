"""P4 tests — production hardening: live identity, tenant isolation, etc."""
from __future__ import annotations

import os
import tempfile
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DA_DB_PATH", tempfile.mkstemp(suffix=".db")[1])

from app import models as m  # noqa: E402
from app import services as svc  # noqa: E402
from app.account_client import (  # noqa: E402
    AccountAgainClient,
    AccountAgainError,
    ValidationCache,
    _fingerprint,
)
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import deps  # noqa: E402
from app.routers.deps import db_session  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("pragma foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db):
    app.dependency_overrides[db_session] = lambda: (yield db)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def project(db):
    return svc.create_project(db, key="P4A", name="P4 Project")


# ---------------------------------------------------------------------------
# P4-A live Account Again validation + auth cache + fail-closed
# ---------------------------------------------------------------------------


def _counting_transport(decision="ALLOW", eval_status=200, account_status=200):
    """MockTransport that records call counts and returns AA-shaped responses."""
    calls = {"evaluate": 0, "account": 0}

    def handler(request: httpx.Request):
        if request.url.path == "/api/v1/entitlements/evaluate":
            calls["evaluate"] += 1
            try:
                body = request.json()
            except Exception:
                body = {}
            return httpx.Response(
                eval_status,
                json={"decision": decision, "accountId": body.get("accountId") or "acc-1",
                      "tenantId": body.get("tenantId") or "t-1"},
            )
        if request.url.path.startswith("/api/v1/accounts/"):
            calls["account"] += 1
            return httpx.Response(account_status, json={
                "accountId": "acc-1", "tenantId": "t-1", "displayName": "Alice",
                "email": "a@x", "status": "ACTIVE",
            })
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler), calls


def test_cache_returns_cached_allow_without_revalidation():
    transport, calls = _counting_transport()
    c = AccountAgainClient("http://aa", transport=transport)
    a1 = c.validate_actor("tok-1", "acc-1", "t-1")
    a2 = c.validate_actor("tok-1", "acc-1", "t-1")
    assert a1["source"] == "ACCOUNT_AGAIN"
    assert a2 == a1
    assert calls["evaluate"] == 1  # second call served from cache


def test_cache_is_tenant_and_account_aware():
    transport, calls = _counting_transport()
    c = AccountAgainClient("http://aa", transport=transport)
    c.validate_actor("tok-1", "acc-1", "t-1")
    c.validate_actor("tok-1", "acc-1", "t-2")  # different tenant -> revalidate
    c.validate_actor("tok-1", "acc-2", "t-1")  # different account -> revalidate
    assert calls["evaluate"] == 3


def test_deny_is_never_cached():
    transport, calls = _counting_transport(decision="DENY")
    c = AccountAgainClient("http://aa", transport=transport)
    with pytest.raises(AccountAgainError):
        c.validate_actor("tok-1", "acc-1", "t-1")
    with pytest.raises(AccountAgainError):
        c.validate_actor("tok-1", "acc-1", "t-1")
    assert calls["evaluate"] == 2  # DENY always re-evaluated live


def test_outage_fails_closed():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("connection refused", request=request)

    c = AccountAgainClient("http://aa", transport=httpx.MockTransport(handler))
    with pytest.raises(AccountAgainError) as exc:
        c.validate_actor("tok-1", "acc-1", "t-1")
    assert exc.value.status_code == 503


def test_missing_token_rejected():
    c = AccountAgainClient("http://aa", transport=_counting_transport()[0])
    with pytest.raises(AccountAgainError) as exc:
        c.validate_actor("", "acc-1", "t-1")
    assert exc.value.status_code == 401


def test_fingerprint_never_stores_raw_token():
    fp = _fingerprint("super-secret-token", "acc-1", "t-1")
    assert "super-secret-token" not in fp
    assert len(fp) == 64  # sha256 hex


def test_cache_corruption_fails_closed_to_miss():
    cache = ValidationCache(ttl=60, max_entries=10)
    cache.put("fp-1", {"account_id": "acc-1", "source": "ACCOUNT_AGAIN"})
    cache._data["fp-1"] = None  # corrupt entry
    assert cache.get("fp-1") is None


def test_actor_dependency_fails_closed_in_account_mode(client, db, monkeypatch):
    # account_again mode: an X-Actor header with no Bearer token must be rejected.
    monkeypatch.setattr(deps, "AUTH_MODE", "account_again")

    def handler(request: httpx.Request):
        raise httpx.ConnectError("down", request=request)

    monkeypatch.setattr(deps, "client", AccountAgainClient("http://aa", transport=httpx.MockTransport(handler)))
    r = client.post("/api/projects", json={"key": "X", "name": "X"}, headers={"X-Actor": "impostor"})
    assert r.status_code == 401  # missing token -> rejected, X-Actor never trusted

    # With a token + account id, an unreachable Account Again yields 503 (outage fail-closed).
    r2 = client.post(
        "/api/projects", json={"key": "Y", "name": "Y"},
        headers={"X-Actor": "impostor", "Authorization": "Bearer tok", "X-Account-Id": "acc-1"},
    )
    assert r2.status_code == 503


# ---------------------------------------------------------------------------
# P4-B tenant isolation hardening
# ---------------------------------------------------------------------------


def test_cross_tenant_read_blocked(client, db):
    pa = client.post("/api/projects", json={"key": "TA", "name": "Tenant A"}, headers={"X-Tenant-Id": "t-a"}).json()
    pb = client.post("/api/projects", json={"key": "TB", "name": "Tenant B"}, headers={"X-Tenant-Id": "t-b"}).json()
    # Tenant A can read its own project
    assert client.get(f"/api/projects/{pa['id']}", headers={"X-Tenant-Id": "t-a"}).status_code == 200
    # Tenant A cannot read Tenant B's project
    r = client.get(f"/api/projects/{pb['id']}", headers={"X-Tenant-Id": "t-a"})
    assert r.status_code == 403
    # list_projects filters by tenant
    listed = client.get("/api/projects", headers={"X-Tenant-Id": "t-a"}).json()
    assert [p["id"] for p in listed] == [pa["id"]]


def test_cross_tenant_write_blocked(client, db):
    pb = client.post("/api/projects", json={"key": "TB2", "name": "Tenant B"}, headers={"X-Tenant-Id": "t-b"}).json()
    r = client.post("/api/artifacts", json={"project_id": pb["id"], "type": "UR", "title": "stolen"},
                    headers={"X-Tenant-Id": "t-a"})
    assert r.status_code == 403


def test_cross_tenant_export_blocked(client, db):
    pb = client.post("/api/projects", json={"key": "TB3", "name": "Tenant B"}, headers={"X-Tenant-Id": "t-b"}).json()
    art = client.post("/api/artifacts", json={"project_id": pb["id"], "type": "UR", "title": "UR"},
                      headers={"X-Tenant-Id": "t-b"}).json()
    rev = art["revisions"][0]
    client.post(f"/api/revisions/{rev['id']}/submit-for-review", headers={"X-Tenant-Id": "t-b"})
    client.post(f"/api/revisions/{rev['id']}/confirm", json={}, headers={"X-Tenant-Id": "t-b"})
    base = client.post("/api/baselines", json={"project_id": pb["id"], "name": "B1",
                                               "artifact_revision_ids": [rev["id"]]},
                       headers={"X-Tenant-Id": "t-b"}).json()
    r = client.get(f"/api/baselines/{base['id']}/package", headers={"X-Tenant-Id": "t-a"})
    assert r.status_code == 403


def test_cross_tenant_trace_blocked(client, db):
    pb = client.post("/api/projects", json={"key": "TB4", "name": "Tenant B"}, headers={"X-Tenant-Id": "t-b"}).json()
    r = client.post("/api/traces", json={"project_id": pb["id"], "source_semantic_id": "REQ-0001",
                                         "target_semantic_id": "REQ-0002", "relation_type": "DERIVED_FROM"},
                    headers={"X-Tenant-Id": "t-a"})
    assert r.status_code == 403


def test_cross_tenant_reference_blocked(client, db):
    pb = client.post("/api/projects", json={"key": "TB5", "name": "Tenant B"}, headers={"X-Tenant-Id": "t-b"}).json()
    r = client.post("/api/external-references", json={"project_id": pb["id"], "semantic_id": "REQ-0001",
                                                      "service": "pm-again", "external_id": "PM-1"},
                    headers={"X-Tenant-Id": "t-a"})
    assert r.status_code == 403


def test_cross_tenant_handoff_read_blocked(client, db):
    pb = client.post("/api/projects", json={"key": "TB6", "name": "Tenant B"}, headers={"X-Tenant-Id": "t-b"}).json()
    client.post("/api/handoffs/execution", json={"project_id": pb["id"]}, headers={"X-Tenant-Id": "t-b"})
    r = client.get(f"/api/projects/{pb['id']}/handoffs/execution", headers={"X-Tenant-Id": "t-a"})
    assert r.status_code == 403
    own = client.get(f"/api/projects/{pb['id']}/handoffs/execution", headers={"X-Tenant-Id": "t-b"})
    assert own.status_code == 200 and len(own.json()) == 1
