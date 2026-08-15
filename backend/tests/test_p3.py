"""P3 tests — ecosystem integration, trust, resilience, impact v2, export v2."""
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


# ---------------------------------------------------------------------------
# P3-B ecosystem outbox
# ---------------------------------------------------------------------------


def test_outbox_atomic_write(db, project):
    event = svc.emit_event(
        db, event_type="DESIGN_BASELINED", project_id=project.id,
        payload={"baseline": "1.0"}, target_services=["pm-again", "qa-again"],
        correlation_id="corr-1", actor_id="acc-1",
    )
    outbox = db.execute(select(m.OutboxEvent).where(m.OutboxEvent.event_id == event.id)).scalars().all()
    assert {o.target_service for o in outbox} == {"pm-again", "qa-again"}
    assert all(o.status == "PENDING" for o in outbox)
    assert all(o.correlation_id == "corr-1" for o in outbox)


def test_delivery_retry_and_backoff(db, project):
    svc.emit_event(db, event_type="DESIGN_BASELINED", project_id=project.id,
                   target_services=["pm-again"], correlation_id="corr-2")

    def fail(o):
        raise RuntimeError("pm down")

    r = svc.deliver_due_events(db, fail)
    assert r["failed"] == 1 and r["delivered"] == 0
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    assert out.status == "FAILED" and out.attempt_count == 1 and out.last_error == "pm down"
    assert out.next_attempt_at is not None

    # force due
    out.next_attempt_at = m.utcnow() - timedelta(seconds=10)
    db.commit()
    delivered = []
    svc.deliver_due_events(db, lambda o: delivered.append(o.id) or "pm-ref-1")
    assert len(delivered) == 1
    db.expire_all()
    out2 = db.execute(select(m.OutboxEvent)).scalars().one()
    assert out2.status == "SENT" and out2.external_reference == "pm-ref-1"


def test_delivery_idempotent_and_duplicate_safe(db, project):
    svc.emit_event(db, event_type="DESIGN_BASELINED", project_id=project.id,
                   target_services=["pm-again"], correlation_id="corr-3")
    delivered = []
    svc.deliver_due_events(db, lambda o: delivered.append(o.id))
    svc.deliver_due_events(db, lambda o: delivered.append(o.id))
    assert len(delivered) == 1  # second pass: already SENT, not re-delivered
    assert len(db.execute(select(m.OutboxEvent)).scalars().all()) == 1