"""P5-A Conductor relay tests — Document Again handoff acceptance.

Authority boundary: only DOCUMENT_AGAIN may submit design handoffs; only
CONDUCTOR_MAIN may dispatch into PM/QA (enforced downstream). Idempotency:
repeated handoff_id returns the same acknowledgement and never dispatches
twice.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.integration import service_auth
from app.integration import pm_again_client, qa_again_client
from app.database import MasterSessionLocal


def _doc_handoff(handoff_id="dh-1", handoff_type="EXECUTION", tenant_id="t-main"):
    return {
        "contract": {"name": "document-again-handoff", "version": 1},
        "handoff_id": handoff_id,
        "handoff_type": handoff_type,
        "tenant_id": tenant_id,
        "project_id": "prj-1",
        "baseline_id": "bsl-1",
        "requirement_ids": ["REQ-0001"],
        "artifact_revision_ids": ["rev-1"],
        "semantic_object_ids": ["REQ-0001"],
        "correlation_id": f"corr-{handoff_id}",
        "source_service": "DOCUMENT_AGAIN",
    }


def test_document_again_identity_required(monkeypatch):
    with TestClient(app) as c:
        # no Authorization header -> 401 (fail closed)
        r = c.post("/api/ecosystem/document-handoffs", json=_doc_handoff())
        assert r.status_code == 401


def test_wrong_service_identity_rejected(monkeypatch):
    monkeypatch.setattr(service_auth, "verify_service_token", lambda token: {"systemId": "PM_AGAIN"})
    with TestClient(app) as c:
        r = c.post("/api/ecosystem/document-handoffs", json=_doc_handoff(), headers={"Authorization": "Bearer x"})
        assert r.status_code == 403


def test_unsupported_contract_rejected(monkeypatch):
    monkeypatch.setattr(service_auth, "verify_service_token", lambda token: {"systemId": "DOCUMENT_AGAIN"})
    with TestClient(app) as c:
        body = _doc_handoff()
        body["contract"] = {"name": "document-again-handoff", "version": 99}
        r = c.post("/api/ecosystem/document-handoffs", json=body, headers={"Authorization": "Bearer x"})
        assert r.status_code == 422


def test_relay_idempotent_pm_dispatch(monkeypatch):
    monkeypatch.setattr(service_auth, "verify_service_token", lambda token: {"systemId": "DOCUMENT_AGAIN"})
    calls = {"n": 0}

    def fake_dispatch(**kwargs):
        calls["n"] += 1
        return {"externalWorkReferenceId": "pm-ref-1", "correlationId": "corr-dh-1"}

    monkeypatch.setattr(pm_again_client.PMAgainClient, "dispatch_delivery_work_package", staticmethod(fake_dispatch))
    with TestClient(app) as c:
        h = {"Authorization": "Bearer x"}
        r1 = c.post("/api/ecosystem/document-handoffs", json=_doc_handoff(), headers=h)
        r2 = c.post("/api/ecosystem/document-handoffs", json=_doc_handoff(), headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["externalReferenceId"] == "pm-ref-1"
    assert r2.json()["duplicate"] is True
    assert calls["n"] == 1  # no duplicate dispatch


def test_relay_idempotent_qa_dispatch(monkeypatch):
    monkeypatch.setattr(service_auth, "verify_service_token", lambda token: {"systemId": "DOCUMENT_AGAIN"})
    calls = {"n": 0}

    def fake_qa(**kwargs):
        calls["n"] += 1
        return {"externalReferenceId": "qa-ref-1"}

    monkeypatch.setattr(qa_again_client.QAAgainClient, "dispatch_qa_request", staticmethod(fake_qa))
    with TestClient(app) as c:
        h = {"Authorization": "Bearer x"}
        body = _doc_handoff(handoff_id="dh-2", handoff_type="QA_VALIDATION")
        r1 = c.post("/api/ecosystem/document-handoffs", json=body, headers=h)
        r2 = c.post("/api/ecosystem/document-handoffs", json=body, headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["externalReferenceId"] == "qa-ref-1"
    assert r2.json()["duplicate"] is True
    assert calls["n"] == 1


def test_relay_pm_outage_marks_failed_and_retries(monkeypatch):
    monkeypatch.setattr(service_auth, "verify_service_token", lambda token: {"systemId": "DOCUMENT_AGAIN"})
    calls = {"n": 0}

    def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise pm_again_client.PMAgainUnavailableError("down")
        return {"externalWorkReferenceId": "pm-ref-2"}

    monkeypatch.setattr(pm_again_client.PMAgainClient, "dispatch_delivery_work_package", staticmethod(flaky))
    with TestClient(app) as c:
        h = {"Authorization": "Bearer x"}
        r1 = c.post("/api/ecosystem/document-handoffs", json=_doc_handoff("dh-3"), headers=h)
        r2 = c.post("/api/ecosystem/document-handoffs", json=_doc_handoff("dh-3"), headers=h)
    assert r1.status_code == 502
    assert r2.status_code == 200 and r2.json()["externalReferenceId"] == "pm-ref-2"
    assert calls["n"] == 2
