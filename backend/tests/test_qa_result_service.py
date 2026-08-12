"""QA-E3: canonical QAResult aggregation and API tests."""

import pytest

from app import ecosystem_intake, models
from app.contracts.validator import CanonicalContractValidator
from app.database import MasterSessionLocal


@pytest.fixture
def master_db():
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def qa_result_project_slug(auth_client):
    r = auth_client.post("/api/projects", json={"name": "QA Result Tests"})
    assert r.status_code == 200, r.text
    return r.json()["slug"]


def _build_cycle(auth_client, slug, checkpoint="REG-001"):
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={
            "checkpoint_code": checkpoint,
            "title": "case",
            "action_md": "do it",
            "expected_result_md": "it works",
            "priority": "P0",
        },
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    cycle = auth_client.post(
        f"/api/{slug}/cycles",
        json={
            "suite_id": suite["id"],
            "script_revision_id": revision["id"],
            "name": "cycle",
            "environment": "test",
            "require_evidence_for_pass": False,
        },
    ).json()
    return cycle["id"]


def _map_ecosystem_request(master_db, slug, cycle_id, idempotency_key, correlation_id="corr-qa-result"):
    payload = {
        "qaRequestId": f"qar-{idempotency_key}",
        "correlationId": correlation_id,
        "workPackageId": "wp-qa-result-1",
        "releaseCandidate": {"repo": "https://github.com/org/app", "branch": "main", "commit": "abc123"},
        "acceptanceCriteria": {"business": [], "technical": []},
        "createdAt": "2026-08-12T00:00:00Z",
    }
    row, _ = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key=idempotency_key,
        qa_request_id=payload["qaRequestId"],
        correlation_id=correlation_id,
        source_system="CONDUCTOR_MAIN",
        payload=payload,
    )
    ecosystem_intake.map_to_cycle(master_db, row, qa_project_slug=slug, cycle_id=cycle_id)
    return row


def test_qa_result_404_without_ecosystem_mapping(auth_client, qa_result_project_slug):
    cycle_id = _build_cycle(auth_client, qa_result_project_slug, checkpoint="NOMAP-001")
    r = auth_client.get(f"/api/{qa_result_project_slug}/cycles/{cycle_id}/qa-result")
    assert r.status_code == 404


def test_qa_result_pending_before_cycle_completed(auth_client, master_db, qa_result_project_slug):
    cycle_id = _build_cycle(auth_client, qa_result_project_slug, checkpoint="PEND-001")
    _map_ecosystem_request(master_db, qa_result_project_slug, cycle_id, "idem-pending-1", correlation_id="corr-pending")

    r = auth_client.get(f"/api/{qa_result_project_slug}/cycles/{cycle_id}/qa-result")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qualityGate"] == "PENDING"
    assert body["correlationId"] == "corr-pending"
    assert body["workPackageId"] == "wp-qa-result-1"
    CanonicalContractValidator.validate("QAResult", body)


def test_qa_golden_approve_flow(auth_client, master_db, qa_result_project_slug):
    slug = qa_result_project_slug
    cycle_id = _build_cycle(auth_client, slug, checkpoint="APPROVE-001")
    _map_ecosystem_request(master_db, slug, cycle_id, "idem-approve-1", correlation_id="corr-approve")

    results = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results").json()
    result_id = results[0]["id"]
    r = auth_client.put(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}",
        json={"status": "PASS", "actual_result_md": "worked"},
    )
    assert r.status_code == 200, r.text

    r = auth_client.put(f"/api/{slug}/cycles/{cycle_id}", json={"status": "COMPLETED"})
    assert r.status_code == 200, r.text

    r = auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/signoffs",
        json={"cycle_id": cycle_id, "signoff_type": "QA_REVIEW", "decision": "APPROVED"},
    )
    assert r.status_code == 200, r.text

    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/qa-result")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qualityGate"] == "APPROVED"
    assert body["status"] == "COMPLETED"
    assert body["testSummary"]["passed"] == 1
    assert body["testSummary"]["failed"] == 0
    assert body["acceptanceValidation"]["technicalCriteriaMet"] is True
    CanonicalContractValidator.validate("QAResult", body)


def test_qa_golden_reject_flow_blocking_defect(auth_client, master_db, qa_result_project_slug):
    slug = qa_result_project_slug
    cycle_id = _build_cycle(auth_client, slug, checkpoint="REJECT-001")
    _map_ecosystem_request(master_db, slug, cycle_id, "idem-reject-1", correlation_id="corr-reject")

    results = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results").json()
    result_id = results[0]["id"]
    r = auth_client.put(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}",
        json={"status": "FAIL", "actual_result_md": "broke"},
    )
    assert r.status_code == 200, r.text

    r = auth_client.post(
        f"/api/{slug}/defects",
        json={"cycle_id": cycle_id, "cycle_test_result_id": result_id, "title": "Blocking bug", "severity": "P0"},
    )
    assert r.status_code == 200, r.text

    r = auth_client.put(f"/api/{slug}/cycles/{cycle_id}", json={"status": "COMPLETED"})
    assert r.status_code == 200, r.text

    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/qa-result")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["qualityGate"] == "REJECTED"
    assert len(body["defects"]) == 1
    assert body["defects"][0]["severity"] == "CRITICAL"
    CanonicalContractValidator.validate("QAResult", body)


def test_qa_result_forced_rejected_by_signoff_override(auth_client, master_db, qa_result_project_slug):
    """A rejected signoff overrides an otherwise-ready readiness formula
    (QA-E3 §25) — even with all P0 cases passing."""
    slug = qa_result_project_slug
    cycle_id = _build_cycle(auth_client, slug, checkpoint="OVERRIDE-001")
    _map_ecosystem_request(master_db, slug, cycle_id, "idem-override-1", correlation_id="corr-override")

    results = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/results").json()
    result_id = results[0]["id"]
    auth_client.put(
        f"/api/{slug}/cycles/{cycle_id}/results/{result_id}",
        json={"status": "PASS", "actual_result_md": "worked"},
    )
    auth_client.put(f"/api/{slug}/cycles/{cycle_id}", json={"status": "COMPLETED"})
    auth_client.post(
        f"/api/{slug}/cycles/{cycle_id}/signoffs",
        json={"cycle_id": cycle_id, "signoff_type": "GO_LIVE", "decision": "REJECTED"},
    )

    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/qa-result")
    assert r.status_code == 200, r.text
    assert r.json()["qualityGate"] == "REJECTED"


def test_qaresult_evidence_always_present(auth_client, master_db, qa_result_project_slug):
    slug = qa_result_project_slug
    cycle_id = _build_cycle(auth_client, slug, checkpoint="EVID-001")
    _map_ecosystem_request(master_db, slug, cycle_id, "idem-evidence-1", correlation_id="corr-evidence")

    r = auth_client.get(f"/api/{slug}/cycles/{cycle_id}/qa-result")
    assert r.status_code == 200, r.text
    evidence = r.json()["evidence"]
    assert len(evidence) >= 1
    assert evidence[0]["type"] == "QA_TEST_RESULTS"
