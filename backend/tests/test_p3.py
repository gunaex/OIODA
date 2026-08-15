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

# ---------------------------------------------------------------------------
# P3-C PM execution handoff
# ---------------------------------------------------------------------------


def test_execution_handoff_snapshots_and_emits(db, project):
    h = svc.create_execution_handoff(
        db, project_id=project.id, source_revision_id="rev-9",
        change_request_id="cr-1", target_service="pm-again", actor="alice", actor_id="acc-1",
    )
    assert h["status"] == "DRAFT" and h["target_service"] == "pm-again"
    assert h["payload_snapshot"]["sourceRevisionId"] == "rev-9"
    assert h["payload_snapshot"]["changeRequestId"] == "cr-1"
    assert h["actor_id"] == "acc-1"

    outbox = db.execute(select(m.OutboxEvent)).scalars().all()
    assert {o.target_service for o in outbox} == {"pm-again"}
    assert all(o.status == "PENDING" for o in outbox)
    ev = db.execute(select(m.EcosystemEvent)).scalars().one()
    assert ev.event_type == "EXECUTION_REQUESTED"
    assert ev.correlation_id == h["correlation_id"]


def test_execution_handoff_status_transitions(db, project):
    h = svc.create_execution_handoff(db, project_id=project.id)
    h2 = svc.mark_handoff_status(db, h["id"], "execution", "SENT", external_reference="pm-task-42")
    assert h2["status"] == "SENT" and h2["external_reference"] == "pm-task-42"
    assert h2["delivered_at"] is not None


def test_execution_handoff_rejects_bad_status(db, project):
    with pytest.raises(ValueError):
        svc.create_execution_handoff(db, project_id=project.id, status="NONSENSE")


# ---------------------------------------------------------------------------
# P3-D QA validation handoff
# ---------------------------------------------------------------------------


def test_qa_handoff_snapshots_and_emits(db, project):
    h = svc.create_qa_validation_handoff(
        db, project_id=project.id, requirement_ids=["REQ-0001"],
        semantic_object_ids=["REQ-0001"], target_release="v1.0", actor="bob", actor_id="acc-2",
    )
    assert h["target_service"] == "qa-again" and h["status"] == "DRAFT"
    assert h["payload_snapshot"]["requirementIds"] == ["REQ-0001"]
    assert h["payload_snapshot"]["targetRelease"] == "v1.0"
    ev = db.execute(select(m.EcosystemEvent)).scalars().one()
    assert ev.event_type == "QA_VALIDATION_REQUESTED"
    outbox = db.execute(select(m.OutboxEvent)).scalars().one()
    assert outbox.target_service == "qa-again"


def test_qa_handoff_rejects_bad_status(db, project):
    with pytest.raises(ValueError):
        svc.create_qa_validation_handoff(db, project_id=project.id, status="BOGUS")


# ---------------------------------------------------------------------------
# P3-E external references (cross-ecosystem trace)
# ---------------------------------------------------------------------------


def test_external_reference_upsert_is_idempotent(db, project):
    svc.ensure_semantic_object(db, project_id=project.id, semantic_id="REQ-0001",
                               object_type=m.SemanticObjectType.REQUIREMENT, display_name="r")
    r1 = svc.create_external_reference(
        db, project_id=project.id, semantic_id="REQ-0001", service="pm-again",
        external_id="PM-42", relation_type="IMPLEMENTED_BY", object_type="task",
    )
    r2 = svc.create_external_reference(
        db, project_id=project.id, semantic_id="REQ-0001", service="pm-again",
        external_id="PM-42", relation_type="TRACKED_BY",
    )
    assert r1["id"] == r2["id"]
    assert r2["relation_type"] == "TRACKED_BY"
    assert len(svc.list_external_references(db, project_id=project.id)) == 1


def test_external_reference_rejects_bad_relation(db, project):
    with pytest.raises(ValueError):
        svc.create_external_reference(
            db, project_id=project.id, semantic_id="REQ-0001", service="pm-again",
            external_id="PM-43", relation_type="NOPE",
        )


def test_external_reference_list_filters_by_semantic(db, project):
    for sem in ["REQ-0001", "REQ-0002"]:
        svc.ensure_semantic_object(db, project_id=project.id, semantic_id=sem,
                                   object_type=m.SemanticObjectType.REQUIREMENT, display_name=sem)
    svc.create_external_reference(db, project_id=project.id, semantic_id="REQ-0001",
                                  service="pm-again", external_id="PM-1")
    svc.create_external_reference(db, project_id=project.id, semantic_id="REQ-0002",
                                  service="qa-again", external_id="QA-1")
    refs = svc.list_external_references(db, project_id=project.id, semantic_id="REQ-0001")
    assert [r["external_id"] for r in refs] == ["PM-1"]


# ---------------------------------------------------------------------------
# P3-J impact analysis v2 (change sets + rule-based severity)
# ---------------------------------------------------------------------------


def test_change_set_create_and_list(db, project):
    cs = svc.create_change_set(
        db, project_id=project.id, name="Breaking API change",
        items=[{"semantic_id": "EP-0001", "change_type": "REMOVED", "rationale": "deprecated"},
               {"semantic_id": "TBL-0001", "change_type": "MODIFIED"}],
    )
    assert cs["name"] == "Breaking API change" and len(cs["items"]) == 2
    listed = svc.list_change_sets(db, project_id=project.id)
    assert listed[0]["id"] == cs["id"]


def test_change_set_rejects_bad_change_type(db, project):
    with pytest.raises(Exception):
        svc.create_change_set(db, project_id=project.id, name="x",
                              items=[{"semantic_id": "EP-0001", "change_type": "NOPE"}])


def test_impact_v2_rule_based_severity(db, project):
    for sid, ot in [("REQ-0001", m.SemanticObjectType.REQUIREMENT),
                    ("EP-0001", m.SemanticObjectType.API_ENDPOINT),
                    ("TBL-0001", m.SemanticObjectType.DB_TABLE),
                    ("FLD-0001", m.SemanticObjectType.DB_FIELD)]:
        svc.ensure_semantic_object(db, project_id=project.id, semantic_id=sid,
                                   object_type=ot, display_name=sid)
    svc.create_trace_link(db, project_id=project.id, source_semantic_id="REQ-0001",
                          target_semantic_id="EP-0001", relation_type=m.TraceRelationType.IMPLEMENTS)
    svc.create_trace_link(db, project_id=project.id, source_semantic_id="EP-0001",
                          target_semantic_id="TBL-0001", relation_type=m.TraceRelationType.AFFECTS)
    svc.create_trace_link(db, project_id=project.id, source_semantic_id="TBL-0001",
                          target_semantic_id="FLD-0001", relation_type=m.TraceRelationType.AFFECTS)

    r = svc.impact_analysis_v2(db, project_id=project.id, semantic_id="REQ-0001", max_depth=4)
    by_sid = {a["semantic_id"]: a for a in r["affected"]}
    assert by_sid["EP-0001"]["severity"] == "DIRECT"
    assert by_sid["TBL-0001"]["severity"] == "DIRECT"  # HIGH bumped by DB_TABLE rule
    assert by_sid["FLD-0001"]["severity"] == "HIGH"    # MEDIUM bumped by DB_FIELD rule
    assert by_sid["EP-0001"]["path"][0]["relation"] == "IMPLEMENTS"


# ---------------------------------------------------------------------------
# P3-G OpenAPI import/export
# ---------------------------------------------------------------------------

OPENAPI_SPEC = """
openapi: 3.0.0
info: {title: Petstore, version: "1.0"}
paths:
  /pets:
    get:
      summary: List pets
      parameters:
        - {name: limit, in: query, required: false, schema: {type: integer}}
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  id: {type: string}
    post:
      summary: Create pet
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [name]
              properties:
                name: {type: string}
      responses:
        "201": {description: Created}
        "400": {description: Bad request}
"""


def test_openapi_to_endpoints_parses_yaml(db, project):
    eps = svc.openapi_to_endpoints(svc._parse_openapi(OPENAPI_SPEC))
    assert {e["method"] for e in eps} == {"GET", "POST"}
    get_ep = next(e for e in eps if e["method"] == "GET")
    assert get_ep["parameters"][0]["name"] == "limit"
    assert get_ep["response_fields"][0]["name"] == "id"


def test_openapi_import_creates_endpoints_and_children(db, project):
    report = svc.import_openapi(db, project.id, OPENAPI_SPEC)
    assert len(report["applied"]) == 2
    eps = svc.list_api_endpoints(db, project_id=project.id)
    assert len(eps) == 2
    get_ep = next(e for e in eps if e["method"] == "GET")
    assert get_ep["parameters"][0]["name"] == "limit"
    assert get_ep["response_fields"][0]["name"] == "id"
    post_ep = next(e for e in eps if e["method"] == "POST")
    assert post_ep["request_fields"][0]["name"] == "name"


def test_openapi_preview_diff(db, project):
    svc.import_openapi(db, project.id, OPENAPI_SPEC)
    preview = svc.preview_openapi_import(db, project.id, OPENAPI_SPEC)
    assert preview["added"] == [] and preview["unchanged"] == ["api_get_pets", "api_post_pets"]


def test_openapi_export_from_revision_snapshot(db, project):
    artifact = m.Artifact(project_id=project.id, type=m.ArtifactType.API_DESIGN, title="API")
    db.add(artifact)
    db.flush()
    rev = m.ArtifactRevision(
        artifact_id=artifact.id, revision_number=1, status=m.RevisionStatus.CONFIRMED,
        title="API v1", snapshot={"technical_design": {"api_endpoints": {
            "api_get_pets": {
                "method": "GET", "path": "/pets", "summary": "List pets",
                "description": None, "authentication": "NONE",
                "parameters": [{"name": "limit", "location": "query", "data_type": "integer",
                                "required": False, "description": None}],
                "request_fields": [], "response_fields": [],
                "error_responses": [], "request_spec": None, "response_spec": None,
            }
        }}},
    )
    db.add(rev)
    db.commit()
    out = svc.export_openapi(db, rev.id)
    assert out["openapi"] == "3.0.0"
    assert "/pets" in out["paths"]
    assert out["paths"]["/pets"]["get"]["parameters"][0]["name"] == "limit"
