"""E8-E — Specialist dispatch adapter tests."""

import pytest

from app.database import MasterSessionLocal
from app.integration.lacc_client import LocalAIControlCenterClient
from app.orchestration.dispatch import FROZEN_RUNTIME, HARNESS, REAL_RUNTIME
from app.orchestration.dispatch import idea_to_code_adapter, infra_adapter, pm_adapter, qa_adapter
from app.orchestration.service import OrchestrationService


@pytest.fixture
def run():
    db = MasterSessionLocal()
    svc = OrchestrationService(db)
    intent = svc.create_business_intent(
        tenant_id="local-tenant", project_slug="e8-adapters", title="Adapter test",
        description="d", priority="MEDIUM",
    )
    r = svc.create_delivery_run(intent=intent, assignments={"engineering": True, "infrastructure": True, "qa": True})
    yield r
    db.close()


def test_adapter_status_classifications_are_disclosed():
    assert idea_to_code_adapter.STATUS == REAL_RUNTIME
    assert infra_adapter.STATUS == FROZEN_RUNTIME
    assert qa_adapter.STATUS == HARNESS
    assert pm_adapter.STATUS == REAL_RUNTIME


def test_pm_adapter_never_fabricates_a_status_when_unreachable(run):
    """No live PM Again in this test environment — fetch_status must return
    None (fail closed), never a synthetic/fabricated PMStatus."""
    assert pm_adapter.fetch_status(run=run) is None


def test_infra_adapter_produces_valid_canonical_request_and_result(run):
    req = infra_adapter.build_infrastructure_request(run=run, engineering_result_id="er-1", requirements={})
    assert req["engineeringResultId"] == "er-1"
    result = infra_adapter.simulate_result(run=run, infrastructure_request=req)
    assert result["status"] == "SUCCESS"
    assert "FROZEN_RUNTIME_REFERENCE" in result["evidence"][0]["summary"]


def _fake_engineering_result(run, verify_ok=True, tests_failed=0):
    return {
        "engineeringResultId": "er-1", "repo": "r", "branch": "b", "commit": "c",
        "pipeline": {"verify": {"status": "PASS" if verify_ok else "FAIL"},
                     "test": {"testsPassed": 3, "testsFailed": tests_failed}},
    }


def test_qa_adapter_approves_when_upstream_verified(run):
    eng = _fake_engineering_result(run, verify_ok=True, tests_failed=0)
    qar = qa_adapter.build_qa_request(run=run, engineering_result=eng, acceptance_criteria={})
    result = qa_adapter.run_harness(run=run, qa_request=qar, engineering_result=eng)
    assert result["qualityGate"] == "APPROVED"


def test_qa_adapter_rejects_when_upstream_failed_verify(run):
    eng = _fake_engineering_result(run, verify_ok=False, tests_failed=1)
    qar = qa_adapter.build_qa_request(run=run, engineering_result=eng, acceptance_criteria={})
    result = qa_adapter.run_harness(run=run, qa_request=qar, engineering_result=eng)
    assert result["qualityGate"] == "REJECTED"


@pytest.mark.skipif(not LocalAIControlCenterClient.health(), reason="Local AI Control Center not reachable")
def test_idea_to_code_adapter_real_dispatch(run):
    ewp = idea_to_code_adapter.build_engineering_work_package(run=run, requirements="Add a GET /ping endpoint")
    response = idea_to_code_adapter.dispatch(run=run, engineering_work_package=ewp, project_name="e8-adapter-test")
    assert response["status"] in ("RECEIVED", "DUPLICATE")
    assert response["run"]["correlationId"] == run.correlation_id


@pytest.mark.skipif(not pm_adapter.health(), reason="PM Again not reachable")
def test_pm_adapter_real_dispatch_and_status_fetch(run):
    dwp = run.work_package_payload
    response = pm_adapter.dispatch(run=run, delivery_work_package=dwp)
    assert response["created"] in (True, False)

    status = pm_adapter.fetch_status(run=run)
    assert status is not None
    assert status["workPackageId"] == run.work_package_id
