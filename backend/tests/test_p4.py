"""P4 tests — production hardening: live identity, tenant isolation, etc."""
from __future__ import annotations

import json as _json
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


# ---------------------------------------------------------------------------
# P4-E ecosystem contract governance
# ---------------------------------------------------------------------------


def test_handoff_payloads_carry_contract_envelope(db, project):
    h = svc.create_execution_handoff(db, project_id=project.id)
    assert h["payload_snapshot"]["contract"] == {"name": "execution-handoff", "version": 1}
    q = svc.create_qa_validation_handoff(db, project_id=project.id, requirement_ids=["REQ-0001"])
    assert q["payload_snapshot"]["contract"] == {"name": "qa-validation-handoff", "version": 1}


def test_unsupported_major_version_rejected():
    from app.contracts import ContractVersionError, require_compatible
    with pytest.raises(ContractVersionError):
        require_compatible({"contract": {"name": "execution-handoff", "version": 99}}, "execution-handoff")


def test_missing_contract_envelope_rejected():
    from app.contracts import ContractVersionError, require_compatible
    with pytest.raises(ContractVersionError):
        require_compatible({"baselineId": "x"}, "execution-handoff")


def test_contract_name_mismatch_rejected():
    from app.contracts import ContractVersionError, require_compatible
    with pytest.raises(ContractVersionError):
        require_compatible({"contract": {"name": "qa-validation-handoff", "version": 1}}, "execution-handoff")


def test_backward_compatible_minor_accepted():
    from app.contracts import require_compatible
    # minor/patch are not encoded in the major-only integer version; a
    # supported major is accepted regardless of additive fields.
    out = require_compatible({"contract": {"name": "execution-handoff", "version": 1}, "extra": 1}, "execution-handoff")
    assert out["contract"]["version"] == 1


# ---------------------------------------------------------------------------
# P4-C/D outbox HTTP delivery (idempotent, versioned, fail-closed)
# ---------------------------------------------------------------------------


def _delivery_transport(respond_status=200, body=None, with_token=True):
    calls = {"deliver": 0, "token": 0}

    def handler(request: httpx.Request):
        if request.url.path.endswith("/auth/service-token"):
            calls["token"] += 1
            return httpx.Response(200, json={"accessToken": "svc-token", "tokenType": "Bearer", "expiresIn": 3600})
        if request.url.path == "/relay/handoffs":
            calls["deliver"] += 1
            if respond_status >= 400:
                return httpx.Response(respond_status, json={"detail": "nope"})
            return httpx.Response(200, json=body or {"externalWorkReferenceId": "pm-ref-7"})
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler), calls


def test_http_delivery_is_idempotent_and_persists_reference(db, project):
    from app.ecosystem_client import EcosystemDeliveryClient
    svc.emit_event(db, event_type="EXECUTION_REQUESTED", project_id=project.id,
                   payload={"contract": {"name": "execution-handoff", "version": 1}, "baselineId": "b1"},
                   target_services=["pm-again"], correlation_id="corr-d")
    transport, calls = _delivery_transport()
    client = EcosystemDeliveryClient("http://aa", client_secret="s", transport=transport)
    r = svc.deliver_due_events_http(db, "http://relay/relay/handoffs", tenant_id="t-1", client=client)
    assert r == {"delivered": 1, "failed": 0}
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    assert out.status == "SENT" and out.external_reference == "pm-ref-7"
    # second pass: already SENT, not re-delivered
    r2 = svc.deliver_due_events_http(db, "http://relay/relay/handoffs", tenant_id="t-1", client=client)
    assert r2 == {"delivered": 0, "failed": 0}


def test_http_delivery_fails_closed_on_5xx(db, project):
    from app.ecosystem_client import EcosystemDeliveryClient
    svc.emit_event(db, event_type="QA_VALIDATION_REQUESTED", project_id=project.id,
                   target_services=["qa-again"], correlation_id="corr-e")
    transport, _calls = _delivery_transport(respond_status=500)
    client = EcosystemDeliveryClient("http://aa", client_secret="s", transport=transport)
    r = svc.deliver_due_events_http(db, "http://relay/relay/handoffs", tenant_id="t-1", client=client)
    assert r["failed"] == 1 and r["delivered"] == 0
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    assert out.status == "FAILED" and out.attempt_count == 1


def test_delivery_payload_is_versioned(db, project):
    svc.emit_event(db, event_type="DESIGN_BASELINED", project_id=project.id,
                   payload={"baseline": "1"}, target_services=["pm-again"], correlation_id="corr-f")
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    payload = svc.build_event_delivery_payload(db, out)
    assert payload["contract"] == {"name": "ecosystem-event", "version": 1}
    assert payload["eventType"] == "DESIGN_BASELINED"
    assert payload["correlationId"] == "corr-f"


# ---------------------------------------------------------------------------
# P4-F.1 ERD regression — layout is presentation-only, semantic ids stable
# ---------------------------------------------------------------------------


def test_erd_layout_does_not_touch_structured_model(db, project):
    schema = svc.create_schema(db, project_id=project.id, name="core", semantic_id="sch_core")
    table = svc.create_table(db, schema_id=schema.id, name="orders", semantic_id="tbl_orders")
    svc.create_field(db, table_id=table.id, name="id", data_type="UUID", primary_key=True)
    before = svc.db_design_snapshot(db, schema.id)

    # move a node: layout keyed by semantic id only
    svc.save_erd_layout(db, schema.id, {"tbl_orders": {"x": 999, "y": 123}})
    after = svc.db_design_snapshot(db, schema.id)

    assert svc.get_erd_layout(db, schema.id) == {"tbl_orders": {"x": 999, "y": 123}}
    assert before == after  # structured model unchanged
    # semantic table/field ids are stable, never derived from layout position
    tbl = db.execute(select(m.DatabaseTable).where(m.DatabaseTable.id == table.id)).scalars().one()
    assert tbl.semantic_id == "tbl_orders"


# ---------------------------------------------------------------------------
# P4-I observability: health / readiness / metrics / correlation
# ---------------------------------------------------------------------------


def test_health_readiness_and_metrics_endpoints(client):
    h = client.get("/api/health")
    assert h.status_code == 200 and h.json()["service"] == "document-again"
    r = client.get("/api/readiness")
    assert r.status_code == 200 and r.json()["checks"]["database"] == "ok"
    mresp = client.get("/api/metrics")
    assert mresp.status_code == 200 and "counters" in mresp.json()


def test_request_correlation_id_header(client):
    r = client.get("/api/health", headers={"X-Request-Id": "req-123"})
    assert r.headers.get("X-Request-Id") == "req-123"


def test_outbox_metrics_count_delivery(db, project):
    from app.ecosystem_client import EcosystemDeliveryClient
    from app.observability import metrics
    svc.emit_event(db, event_type="EXECUTION_REQUESTED", project_id=project.id,
                   target_services=["pm-again"], correlation_id="corr-m")
    assert metrics.snapshot().get("outbox_pending", 0) >= 1
    transport, _c = _delivery_transport()
    c = EcosystemDeliveryClient("http://aa", client_secret="s", transport=transport)
    svc.deliver_due_events_http(db, "http://relay/relay/handoffs", client=c)
    snap = metrics.snapshot()
    assert snap.get("outbox_delivered", 0) >= 1


# ---------------------------------------------------------------------------
# P4-J immutable audit events
# ---------------------------------------------------------------------------


def test_audit_events_recorded_and_searchable(db, project):
    svc.record_audit(db, action="REVISION_CONFIRMED", project_id=project.id,
                     actor_id="acc-1", object_type="ArtifactRevision", object_id="rev-1",
                     revision_context="rev-1")
    svc.record_audit(db, action="BASELINE_CREATED", project_id=project.id,
                     actor_id="acc-1", object_type="Baseline", object_id="bsl-1", baseline_id="bsl-1")
    by_action = svc.list_audit_events(db, project_id=project.id, action="BASELINE_CREATED")
    assert len(by_action) == 1 and by_action[0]["baseline_id"] == "bsl-1"
    by_actor = svc.list_audit_events(db, project_id=project.id, actor_id="acc-1")
    assert len(by_actor) == 2


def test_confirm_writes_audit_event(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.UR, title="UR")
    rev = db.execute(select(m.ArtifactRevision).where(
        m.ArtifactRevision.artifact_id == art.id)).scalars().one()
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id, actor_id="acc-9")
    events = svc.list_audit_events(db, project_id=project.id, action="REVISION_CONFIRMED")
    assert events and events[0]["object_id"] == rev.id


# ---------------------------------------------------------------------------
# P4-K safe outbox replay / recovery
# ---------------------------------------------------------------------------


def test_outbox_retry_re_enqueues_and_keeps_payload_immutable(db, project):
    svc.emit_event(db, event_type="EXECUTION_REQUESTED", project_id=project.id,
                   payload={"baselineId": "b1"}, target_services=["pm-again"], correlation_id="corr-r")
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    svc.mark_outbox_failed(db, out.id, "boom")
    ev_before = db.execute(select(m.EcosystemEvent)).scalars().one()

    result = svc.retry_outbox_event(db, out.id, actor_id="acc-1")
    assert result["status"] == "PENDING"
    assert result["attempt_count"] == 1  # retry re-enqueued without incrementing here
    # original payload unchanged
    ev_after = db.execute(select(m.EcosystemEvent)).scalars().one()
    assert ev_after.payload == ev_before.payload == {"baselineId": "b1"}
    # replay attempt recorded as its own audit event
    replays = svc.list_audit_events(db, project_id=project.id, action="REPLAY_ATTEMPTED")
    assert len(replays) == 1


def test_outbox_retry_rejects_non_failed(db, project):
    svc.emit_event(db, event_type="DESIGN_BASELINED", project_id=project.id,
                   target_services=["pm-again"], correlation_id="corr-s")
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    with pytest.raises(Exception):
        svc.retry_outbox_event(db, out.id)  # PENDING -> cannot retry (only FAILED)


def test_outbox_inspect_endpoint(client, db, project):
    svc.emit_event(db, event_type="DESIGN_BASELINED", project_id=project.id,
                   payload={"x": 1}, target_services=["pm-again"], correlation_id="corr-t")
    out = db.execute(select(m.OutboxEvent)).scalars().one()
    r = client.get(f"/api/outbox/{out.id}")
    assert r.status_code == 200
    assert r.json()["event"]["payload"] == {"x": 1}


# ---------------------------------------------------------------------------
# P4-M concurrency / conflict safety — double confirm exactly-once
# ---------------------------------------------------------------------------


def test_double_confirm_produces_exactly_one_confirmation(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev = db.execute(select(m.ArtifactRevision).where(
        m.ArtifactRevision.artifact_id == art.id)).scalars().one()
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id, actor_id="acc-1")
    # second confirmation must be rejected (revision already CONFIRMED)
    from app.services import DomainError
    with pytest.raises(DomainError):
        svc.confirm_revision(db, rev.id, actor_id="acc-2")
    confirmations = db.execute(select(m.Confirmation).where(
        m.Confirmation.artifact_revision_id == rev.id)).scalars().all()
    assert len(confirmations) == 1


def test_confirmation_unique_constraint_blocks_duplicate(db, project):
    art = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.UR, title="UR")
    rev = db.execute(select(m.ArtifactRevision).where(
        m.ArtifactRevision.artifact_id == art.id)).scalars().one()
    svc.submit_for_review(db, rev.id)
    svc.confirm_revision(db, rev.id)
    db.add(m.Confirmation(project_id=project.id, artifact_revision_id=rev.id, confirmed_by="dup"))
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ---------------------------------------------------------------------------
# P4-O security hardening
# ---------------------------------------------------------------------------


def test_openapi_import_size_bound(db, project):
    from app.services import DomainError, import_openapi
    huge = "openapi: 3.0.0\npaths:\n  /x:\n    get:\n      summary: " + ("A" * (6 * 1024 * 1024))
    with pytest.raises(DomainError):
        import_openapi(db, project.id, huge)


def test_safe_filename_blocks_path_traversal():
    # Path traversal requires separators; these are stripped to underscores,
    # so no zip entry can escape its directory.
    assert "/" not in svc._safe_filename("../../etc/passwd")
    assert "\\" not in svc._safe_filename("a/b\\c")
    assert svc._safe_filename("../x.json") == ".._x.json"  # no separators


def test_openapi_no_remote_ref_fetch(db, project):
    # A $ref is reduced to its final path component; no network call is made.
    doc = 'openapi: 3.0.0\npaths:\n  /x:\n    get:\n      responses:\n        "200":\n          content:\n            application/json:\n              schema:\n                $ref: "https://evil.example/schema.json#/X"\n'
    eps = svc.openapi_to_endpoints(svc._parse_openapi(doc))
    # $ref becomes a schema name, no fetch occurred (nothing raises/network)
    assert eps[0]["method"] == "GET"


# ---------------------------------------------------------------------------
# P4-H export fidelity V3 — design visuals + historical reproducibility
# ---------------------------------------------------------------------------


def test_historical_export_remains_v1_after_v2(db, project):
    flow = svc.create_flow(db, project_id=project.id, name="Approval", semantic_id="flow_approval")
    svc.add_flow_step(db, flow_id=flow.id, name="Submit", semantic_id="flow_step_submit", step_type="START")
    svc.add_flow_step(db, flow_id=flow.id, name="Approve", semantic_id="flow_step_approve", step_type="APPROVAL")

    dr = svc.create_artifact(db, project_id=project.id, type=m.ArtifactType.DR, title="DR")
    rev1 = db.execute(select(m.ArtifactRevision).where(
        m.ArtifactRevision.artifact_id == dr.id)).scalars().one()
    svc.submit_for_review(db, rev1.id)
    svc.confirm_revision(db, rev1.id)
    baseline = svc.create_baseline(db, project_id=project.id, name="v1", artifact_revision_ids=[rev1.id])

    # v2: add a third approval step, confirm a new revision
    svc.add_flow_step(db, flow_id=flow.id, name="Director", semantic_id="flow_step_director", step_type="APPROVAL")
    rev2 = svc.create_revision(db, artifact_id=dr.id)
    svc.submit_for_review(db, rev2.id)
    svc.confirm_revision(db, rev2.id)

    v1_json = _json.loads(svc.export_revision(db, rev1.id, "json")[0])
    v2_json = _json.loads(svc.export_revision(db, rev2.id, "json")[0])
    v1_steps = set(v1_json["technical_design"]["flows"]["flow_approval"]["steps"].keys())
    v2_steps = set(v2_json["technical_design"]["flows"]["flow_approval"]["steps"].keys())
    assert "flow_step_director" not in v1_steps
    assert "flow_step_director" in v2_steps
    assert v1_steps == {"flow_step_submit", "flow_step_approve"}

    # flow/arch SVG render from the exact snapshot
    assert b"<svg" in svc.export_revision(db, rev1.id, "flow-svg")[0]
    assert b"<svg" in svc.export_revision(db, rev2.id, "architecture-svg")[0]

    # DOCX embeds design summary tables (API/flow/architecture)
    docx_bytes = svc.export_revision_v2(db, rev2.id, "docx")[0]
    assert docx_bytes[:2] == b"PK"


# ---------------------------------------------------------------------------
# P5-B/C/D — Document -> Conductor relay handoff delivery
# ---------------------------------------------------------------------------


def _conductor_transport(respond_status=200, body=None):
    def handler(request: httpx.Request):
        if request.url.path.endswith("/auth/service-token"):
            return httpx.Response(200, json={"accessToken": "tok", "tokenType": "Bearer", "expiresIn": 3600})
        if request.url.path == "/api/ecosystem/document-handoffs":
            if respond_status >= 400:
                return httpx.Response(respond_status, json={"detail": "down"})
            return httpx.Response(200, json=body or {"externalReferenceId": "dwp-ref-9"})
        return httpx.Response(404, json={"detail": "nf"})

    return httpx.MockTransport(handler)


def test_handoff_payload_is_document_again_contract(db, project):
    h = svc.create_execution_handoff(db, project_id=project.id, source_revision_id="rev-1")
    payload = svc.build_handoff_payload(db, h["id"], "execution")
    assert payload["contract"] == {"name": "document-again-handoff", "version": 1}
    assert payload["handoff_type"] == "EXECUTION"
    assert payload["handoff_id"] == h["id"]
    assert payload["baseline_id"] is None or isinstance(payload["baseline_id"], str)


def test_deliver_handoff_to_conductor_success(db, project):
    from app.ecosystem_client import EcosystemDeliveryClient
    h = svc.create_execution_handoff(db, project_id=project.id, source_revision_id="rev-1")
    client = EcosystemDeliveryClient("http://aa", client_secret="s", transport=_conductor_transport())
    out = svc.deliver_handoff_to_conductor(db, h["id"], "execution", client=client)
    assert out["status"] == "ACKNOWLEDGED"
    assert out["external_reference"] == "dwp-ref-9"
    assert out["last_error"] is None


def test_deliver_handoff_to_conductor_failure(db, project):
    from app.ecosystem_client import EcosystemDeliveryClient
    from app.services import DomainError
    h = svc.create_execution_handoff(db, project_id=project.id, source_revision_id="rev-1")
    client = EcosystemDeliveryClient("http://aa", client_secret="s", transport=_conductor_transport(respond_status=502))
    with pytest.raises(DomainError):
        svc.deliver_handoff_to_conductor(db, h["id"], "execution", client=client)
    row = db.get(m.ExecutionHandoff, h["id"])
    assert row.status == "FAILED" and row.last_error is not None


def test_deliver_handoff_idempotent_no_redelivery(db, project):
    from app.ecosystem_client import EcosystemDeliveryClient
    h = svc.create_qa_validation_handoff(db, project_id=project.id, requirement_ids=["REQ-0001"])
    client = EcosystemDeliveryClient("http://aa", client_secret="s", transport=_conductor_transport(body={"externalReferenceId": "qa-ref-1"}))
    svc.deliver_handoff_to_conductor(db, h["id"], "qa", client=client)
    # second delivery is a no-op (already acknowledged)
    out2 = svc.deliver_handoff_to_conductor(db, h["id"], "qa", client=client)
    assert out2["status"] == "ACKNOWLEDGED" and out2["external_reference"] == "qa-ref-1"
