"""
E8-B / E8-F — Core orchestration domain + readiness policy tests.
Exercises the domain service directly (no HTTP) against a throwaway master DB.
"""

import pytest

from app.database import MasterSessionLocal
from app.orchestration.service import (
    HardFailureBlocksDispatchError,
    IdempotencyConflictError,
    OrchestrationService,
    TenantMismatchError,
)


@pytest.fixture
def db():
    session = MasterSessionLocal()
    yield session
    session.close()


@pytest.fixture
def svc(db):
    return OrchestrationService(db)


def make_run(svc, tenant_id="tenant-a", assignments=None):
    intent = svc.create_business_intent(
        tenant_id=tenant_id, project_slug="demo", title="Ship health endpoint",
        description="Add a health endpoint", priority="HIGH", requester="qa-bot",
    )
    run = svc.create_delivery_run(
        intent=intent, assignments=assignments or {"engineering": True, "infrastructure": True, "qa": True},
    )
    return intent, run


def test_business_intent_runtime(svc):
    intent, _ = make_run(svc)
    assert intent.status == "PLANNED"
    assert intent.canonical_payload["businessIntentId"] == intent.business_intent_id


def test_delivery_work_package_runtime(svc):
    _, run = make_run(svc)
    assert run.work_package_payload["state"] == "PLANNED"
    assert run.work_package_payload["assignments"]["engineering"] is True
    assert run.current_stage == "PLAN"


def test_dispatch_idempotency_same_key_same_payload(svc):
    _, run = make_run(svc)
    payload = {"engineeringWorkPackageId": "ewp-1", "requirements": "do it"}
    d1 = svc.register_dispatch(
        run=run, specialist="ENGINEERING", contract_name="EngineeringWorkPackage",
        canonical_id="ewp-1", payload=payload, idempotency_key="idem-1", adapter_status="REAL_RUNTIME",
    )
    d2 = svc.register_dispatch(
        run=run, specialist="ENGINEERING", contract_name="EngineeringWorkPackage",
        canonical_id="ewp-1", payload=payload, idempotency_key="idem-1", adapter_status="REAL_RUNTIME",
    )
    assert d1.id == d2.id  # same key + same payload -> same logical result


def test_dispatch_idempotency_conflict_on_different_payload(svc):
    _, run = make_run(svc)
    svc.register_dispatch(
        run=run, specialist="ENGINEERING", contract_name="EngineeringWorkPackage",
        canonical_id="ewp-1", payload={"a": 1}, idempotency_key="idem-2", adapter_status="REAL_RUNTIME",
    )
    with pytest.raises(IdempotencyConflictError):
        svc.register_dispatch(
            run=run, specialist="ENGINEERING", contract_name="EngineeringWorkPackage",
            canonical_id="ewp-1", payload={"a": 2}, idempotency_key="idem-2", adapter_status="REAL_RUNTIME",
        )


def test_tenant_isolation_blocks_cross_tenant_access(svc):
    intent, run = make_run(svc, tenant_id="tenant-a")
    with pytest.raises(TenantMismatchError):
        svc.require_tenant(run, "tenant-b")


def _engineering_result_payload(run, status="SUCCESS", blocking=None):
    payload = {
        "engineeringResultId": "er-1", "correlationId": run.correlation_id, "workPackageId": run.work_package_id,
        "status": status, "repo": "r", "branch": "b", "commit": "c", "pipeline": {},
        "evidence": [{"type": "TEST_RESULTS", "source": "idea-to-code", "reference": "ic://x"}],
        "completedAt": "2026-08-12T00:00:00Z",
    }
    if blocking is not None:
        payload["conductorPolicy"] = {"blocking": blocking}
    return payload


def _infra_result_payload(run, status="SUCCESS"):
    return {
        "infrastructureResultId": "ifr-1", "correlationId": run.correlation_id, "workPackageId": run.work_package_id,
        "infrastructureRequestId": "ir-1", "status": status, "provider": "AWS", "platform": "KUBERNETES",
        "evidence": [{"type": "VALIDATION_RESULTS", "source": "infra-again", "reference": "infra://x"}],
        "completedAt": "2026-08-12T00:00:00Z",
    }


def _qa_result_payload(run, gate="APPROVED"):
    return {
        "qaResultId": "qr-1", "correlationId": run.correlation_id, "workPackageId": run.work_package_id,
        "qaRequestId": "qar-1", "status": "COMPLETED",
        "testSummary": {"total": 3, "passed": 3, "failed": 0, "skipped": 0},
        "qualityGate": gate,
        "evidence": [{"type": "QA_TEST_RESULTS", "source": "qa-again", "reference": "qa://x"}],
        "completedAt": "2026-08-12T00:00:00Z",
    }


def test_readiness_all_success_ready(svc):
    _, run = make_run(svc)
    svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult",
                       payload=_engineering_result_payload(run))
    svc.intake_result(run=run, specialist="INFRASTRUCTURE", contract_name="InfrastructureResult",
                       payload=_infra_result_payload(run))
    svc.intake_result(run=run, specialist="QA", contract_name="QAResult",
                       payload=_qa_result_payload(run))
    decision = svc.compute_readiness(run)
    assert decision.decision == "READY_FOR_DELIVERY"
    assert decision.reason_code == "READY_ALL_REQUIRED_GATES_PASS"


def test_readiness_engineering_failed_blocks_downstream_and_not_ready(svc):
    _, run = make_run(svc)
    svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult",
                       payload=_engineering_result_payload(run, status="FAILED"))

    with pytest.raises(HardFailureBlocksDispatchError):
        svc.assert_no_downstream_after_hard_failure(run, "INFRASTRUCTURE")
    with pytest.raises(HardFailureBlocksDispatchError):
        svc.assert_no_downstream_after_hard_failure(run, "QA")

    decision = svc.compute_readiness(run)
    assert decision.decision == "NOT_READY"
    assert decision.reason_code == "BLOCKED_MISSING_REQUIRED_RESULT" or decision.reason_code == "BLOCKED_ENGINEERING_FAILED"


def test_readiness_qa_rejected_not_ready(svc):
    _, run = make_run(svc)
    svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult",
                       payload=_engineering_result_payload(run))
    svc.intake_result(run=run, specialist="INFRASTRUCTURE", contract_name="InfrastructureResult",
                       payload=_infra_result_payload(run))
    svc.intake_result(run=run, specialist="QA", contract_name="QAResult",
                       payload=_qa_result_payload(run, gate="REJECTED"))
    decision = svc.compute_readiness(run)
    assert decision.decision == "NOT_READY"
    assert decision.reason_code == "BLOCKED_QA_REJECTED"


def test_readiness_partial_non_blocking_engineering_ready_with_caveat(svc):
    _, run = make_run(svc)
    svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult",
                       payload=_engineering_result_payload(run, status="PARTIAL", blocking=False))
    svc.intake_result(run=run, specialist="INFRASTRUCTURE", contract_name="InfrastructureResult",
                       payload=_infra_result_payload(run))
    svc.intake_result(run=run, specialist="QA", contract_name="QAResult",
                       payload=_qa_result_payload(run))
    decision = svc.compute_readiness(run)
    assert decision.decision == "READY_FOR_DELIVERY"
    assert decision.reason_code == "READY_WITH_NON_BLOCKING_ENGINEERING_PARTIAL"


def test_readiness_partial_blocking_engineering_not_ready(svc):
    _, run = make_run(svc)
    svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult",
                       payload=_engineering_result_payload(run, status="PARTIAL", blocking=True))
    svc.intake_result(run=run, specialist="INFRASTRUCTURE", contract_name="InfrastructureResult",
                       payload=_infra_result_payload(run))
    svc.intake_result(run=run, specialist="QA", contract_name="QAResult",
                       payload=_qa_result_payload(run))
    decision = svc.compute_readiness(run)
    assert decision.decision == "NOT_READY"
    assert decision.reason_code == "BLOCKED_ENGINEERING_PARTIAL"


def test_result_intake_rejects_correlation_mismatch(svc):
    _, run = make_run(svc)
    payload = _engineering_result_payload(run)
    payload["correlationId"] = "wrong-corr"
    with pytest.raises(ValueError):
        svc.intake_result(run=run, specialist="ENGINEERING", contract_name="EngineeringResult", payload=payload)
