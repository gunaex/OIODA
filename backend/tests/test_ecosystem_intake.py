"""QA-E2: correlation / idempotency / replay-vs-rerun semantics."""

import pytest

from app import ecosystem_intake, models
from app.database import MasterSessionLocal


@pytest.fixture
def master_db():
    db = MasterSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def ecosystem_project_slug(auth_client):
    r = auth_client.post("/api/projects", json={"name": "Ecosystem Intake Tests"})
    assert r.status_code == 200, r.text
    return r.json()["slug"]


@pytest.fixture
def ecosystem_cycle_id(auth_client, ecosystem_project_slug):
    slug = ecosystem_project_slug
    suite = auth_client.post(f"/api/{slug}/suites", json={"name": "Suite", "suite_type": "REGRESSION"}).json()
    revision = auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions", json={"revision_label": "v1"}).json()
    auth_client.post(
        f"/api/{slug}/revisions/{revision['id']}/cases",
        json={
            "checkpoint_code": "REG-001",
            "title": "case",
            "action_md": "do it",
            "expected_result_md": "it works",
        },
    )
    auth_client.post(f"/api/{slug}/suites/{suite['id']}/revisions/{revision['id']}/publish")
    cycle = auth_client.post(
        f"/api/{slug}/cycles",
        json={"suite_id": suite["id"], "script_revision_id": revision["id"], "name": "cycle", "environment": "test"},
    ).json()
    return cycle["id"]


def _payload(correlation_id="corr-1", commit="abc123"):
    return {
        "qaRequestId": "qar-001",
        "correlationId": correlation_id,
        "workPackageId": "wp-001",
        "releaseCandidate": {"repo": "https://github.com/org/app", "branch": "main", "commit": commit},
        "acceptanceCriteria": {"business": [], "technical": []},
        "createdAt": "2026-08-12T00:00:00Z",
    }


def test_register_creates_new_row(master_db):
    row, created = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-new-1",
        qa_request_id="qar-001",
        correlation_id="corr-1",
        source_system="CONDUCTOR_MAIN",
        payload=_payload(),
    )
    assert created is True
    assert row.status == "RECEIVED"
    assert row.correlation_id == "corr-1"


def test_replay_same_key_same_payload_is_idempotent(master_db):
    payload = _payload(correlation_id="corr-replay")
    row1, created1 = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-replay-1",
        qa_request_id="qar-002",
        correlation_id="corr-replay",
        source_system="CONDUCTOR_MAIN",
        payload=payload,
    )
    row2, created2 = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-replay-1",
        qa_request_id="qar-002",
        correlation_id="corr-replay",
        source_system="CONDUCTOR_MAIN",
        payload=payload,
    )
    assert created1 is True
    assert created2 is False
    assert row1.id == row2.id

    count = (
        master_db.query(models.ExternalQARequest)
        .filter(models.ExternalQARequest.idempotency_key == "idem-replay-1")
        .count()
    )
    assert count == 1


def test_replay_same_key_different_payload_conflicts(master_db):
    ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-conflict-1",
        qa_request_id="qar-003",
        correlation_id="corr-conflict",
        source_system="CONDUCTOR_MAIN",
        payload=_payload(commit="commit-a"),
    )
    with pytest.raises(ecosystem_intake.IdempotencyConflictError):
        ecosystem_intake.register_external_qa_request(
            master_db,
            idempotency_key="idem-conflict-1",
            qa_request_id="qar-003",
            correlation_id="corr-conflict",
            source_system="CONDUCTOR_MAIN",
            payload=_payload(commit="commit-b"),
        )


def test_map_to_cycle_is_idempotent(master_db, ecosystem_project_slug, ecosystem_cycle_id):
    row, _ = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-map-1",
        qa_request_id="qar-map",
        correlation_id="corr-map",
        source_system="CONDUCTOR_MAIN",
        payload=_payload(correlation_id="corr-map"),
    )
    attempt1 = ecosystem_intake.map_to_cycle(
        master_db, row, qa_project_slug=ecosystem_project_slug, cycle_id=ecosystem_cycle_id
    )
    attempt2 = ecosystem_intake.map_to_cycle(
        master_db, row, qa_project_slug=ecosystem_project_slug, cycle_id=ecosystem_cycle_id
    )
    assert attempt1.id == attempt2.id
    assert attempt1.attempt_no == 1
    assert row.status == "MAPPED"
    assert row.test_cycle_id == ecosystem_cycle_id


def test_explicit_rerun_creates_new_attempt_distinct_from_replay(master_db, ecosystem_project_slug, ecosystem_cycle_id):
    row, _ = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-rerun-1",
        qa_request_id="qar-rerun",
        correlation_id="corr-rerun",
        source_system="CONDUCTOR_MAIN",
        payload=_payload(correlation_id="corr-rerun"),
    )
    ecosystem_intake.map_to_cycle(master_db, row, qa_project_slug=ecosystem_project_slug, cycle_id=ecosystem_cycle_id)

    # A plain replay must not add a new attempt.
    ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-rerun-1",
        qa_request_id="qar-rerun",
        correlation_id="corr-rerun",
        source_system="CONDUCTOR_MAIN",
        payload=_payload(correlation_id="corr-rerun"),
    )

    rerun_attempt = ecosystem_intake.explicit_rerun(master_db, row, triggered_by="tester@example.com")
    assert rerun_attempt.attempt_no == 2
    assert rerun_attempt.trigger == "EXPLICIT_RERUN"

    from app.database import open_project_session

    project_db = open_project_session(ecosystem_project_slug)
    try:
        attempts = (
            project_db.query(models.QAExecutionAttempt)
            .filter(models.QAExecutionAttempt.cycle_id == ecosystem_cycle_id)
            .order_by(models.QAExecutionAttempt.attempt_no)
            .all()
        )
    finally:
        project_db.close()

    assert [a.attempt_no for a in attempts] == [1, 2]
    assert [a.trigger for a in attempts] == ["INITIAL", "EXPLICIT_RERUN"]


def test_explicit_rerun_before_mapping_raises(master_db):
    row, _ = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-unmapped-1",
        qa_request_id="qar-unmapped",
        correlation_id="corr-unmapped",
        source_system="CONDUCTOR_MAIN",
        payload=_payload(correlation_id="corr-unmapped"),
    )
    with pytest.raises(ecosystem_intake.NotMappedError):
        ecosystem_intake.explicit_rerun(master_db, row)


def test_end_to_end_correlation_id_traceable(master_db, ecosystem_project_slug, ecosystem_cycle_id):
    """QA_END_TO_END_CORRELATION: the same correlationId must be reachable
    from the ExternalQARequest all the way to its mapped TestCycle."""
    correlation_id = "e2e-corr-trace-1"
    row, _ = ecosystem_intake.register_external_qa_request(
        master_db,
        idempotency_key="idem-corr-trace-1",
        qa_request_id="qar-trace",
        correlation_id=correlation_id,
        source_system="CONDUCTOR_MAIN",
        payload=_payload(correlation_id=correlation_id),
    )
    ecosystem_intake.map_to_cycle(master_db, row, qa_project_slug=ecosystem_project_slug, cycle_id=ecosystem_cycle_id)

    looked_up = (
        master_db.query(models.ExternalQARequest)
        .filter(models.ExternalQARequest.correlation_id == correlation_id)
        .first()
    )
    assert looked_up is not None
    assert looked_up.test_cycle_id == ecosystem_cycle_id
    assert looked_up.qa_project_slug == ecosystem_project_slug
