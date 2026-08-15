"""P3 tests — ecosystem integration, trust, resilience, impact v2, export v2."""
from __future__ import annotations

import os
import tempfile

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DA_DB_PATH", tempfile.mkstemp(suffix=".db")[1])

from app import models as m  # noqa: E402
from app import services as svc  # noqa: E402
from app.account_client import AccountAgainClient  # noqa: E402
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
    return svc.create_project(db, key="DA3", name="P3 Project")


@pytest.fixture()
def requirement(db, project):
    return svc.create_requirement(db, project_id=project.id, title="2-level approval required")


# ---------------------------------------------------------------------------
# P3-A Account Again token validation
# ---------------------------------------------------------------------------


def _aa_transport(decision="ALLOW", eval_status=200, account_status=200):
    def handler(request: httpx.Request):
        if request.url.path == "/entitlements/evaluate":
            return httpx.Response(eval_status, json={"decision": decision, "accountId": "acc-1", "tenantId": "t-1"})
        if request.url.path == "/accounts/acc-1":
            return httpx.Response(account_status, json={"accountId": "acc-1", "tenantId": "t-1", "displayName": "Alice", "email": "a@x", "status": "ACTIVE"})
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def test_account_again_mode_validates_token(client, db, project, monkeypatch):
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="REQ-0001",
                               object_type=m.SemanticObjectType.REQUIREMENT, display_name="r")
    monkeypatch.setattr(deps, "AUTH_MODE", "account_again")
    monkeypatch.setattr(deps, "client", AccountAgainClient("http://aa", transport=_aa_transport()))

    r = client.post("/api/annotations", json={
        "project_id": project.id, "anchor_object_type": "REQUIREMENT",
        "anchor_semantic_id": "REQ-0001", "content": "hi",
    }, headers={"Authorization": "Bearer s3cret", "X-Account-Id": "acc-1", "X-Tenant-Id": "t-1"})
    assert r.status_code == 201, r.text
    ann = db.execute(select(m.Annotation)).scalars().one()
    assert ann.actor_id == "acc-1"
    assert ann.created_by == "Alice"


def test_invalid_token_rejected(client, db, project, monkeypatch):
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="REQ-0001",
                               object_type=m.SemanticObjectType.REQUIREMENT, display_name="r")
    monkeypatch.setattr(deps, "AUTH_MODE", "account_again")
    monkeypatch.setattr(deps, "client", AccountAgainClient("http://aa", transport=_aa_transport(eval_status=401)))

    r = client.post("/api/annotations", json={
        "project_id": project.id, "anchor_object_type": "REQUIREMENT",
        "anchor_semantic_id": "REQ-0001", "content": "hi",
    }, headers={"Authorization": "Bearer bad", "X-Account-Id": "acc-1"})
    assert r.status_code == 401


def test_deny_decision_rejected(client, db, project, monkeypatch):
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="REQ-0001",
                               object_type=m.SemanticObjectType.REQUIREMENT, display_name="r")
    monkeypatch.setattr(deps, "AUTH_MODE", "account_again")
    monkeypatch.setattr(deps, "client", AccountAgainClient("http://aa", transport=_aa_transport(decision="DENY")))

    r = client.post("/api/annotations", json={
        "project_id": project.id, "anchor_object_type": "REQUIREMENT",
        "anchor_semantic_id": "REQ-0001", "content": "hi",
    }, headers={"Authorization": "Bearer tok", "X-Account-Id": "acc-1"})
    assert r.status_code == 403


def test_missing_token_rejected_in_account_mode(client, db, project, monkeypatch):
    monkeypatch.setattr(deps, "AUTH_MODE", "account_again")
    monkeypatch.setattr(deps, "client", AccountAgainClient("http://aa", transport=_aa_transport()))
    r = client.post("/api/annotations", json={
        "project_id": project.id, "anchor_object_type": "REQUIREMENT",
        "anchor_semantic_id": "REQ-0001", "content": "hi",
    }, headers={"X-Account-Id": "acc-1"})
    assert r.status_code == 401


def test_local_mode_isolated(client, db, project, monkeypatch):
    monkeypatch.setattr(deps, "AUTH_MODE", "local")
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="REQ-0001",
                               object_type=m.SemanticObjectType.REQUIREMENT, display_name="r")
    r = client.post("/api/annotations", json={
        "project_id": project.id, "anchor_object_type": "REQUIREMENT",
        "anchor_semantic_id": "REQ-0001", "content": "hi",
    }, headers={"X-Actor": "dev"})
    assert r.status_code == 201
    ann = db.execute(select(m.Annotation)).scalars().one()
    assert ann.actor_id == "local:dev"