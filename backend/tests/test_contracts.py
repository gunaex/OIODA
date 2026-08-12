"""QA-E1: canonical AGAIN-ECOSYSTEM contract binding and drift-detection tests."""

import pytest
from pydantic import ValidationError

from app.contracts import v1
from app.contracts.validator import (
    ALL_CONTRACTS,
    CanonicalContractValidator,
    ContractValidationError,
)

QA_REQUEST_EXAMPLE = {
    "qaRequestId": "qar-001",
    "correlationId": "e2e-golden-001",
    "workPackageId": "wp-001",
    "releaseCandidate": {
        "repo": "https://github.com/org/app-repo",
        "branch": "feature/e2e-golden-001",
        "commit": "abc123def456",
        "dockerImage": "registry.example.com/app-repo:abc123",
    },
    "acceptanceCriteria": {
        "business": ["Application responds to health check"],
        "technical": ["All unit tests pass"],
    },
    "engineeringResultReference": "er-001",
    "infrastructureResultReference": "ifr-001",
    "knownIssues": [],
    "recommendedRegressionAreas": ["health-endpoint"],
    "createdAt": "2026-08-09T03:00:00Z",
}

QA_RESULT_EXAMPLE = {
    "qaResultId": "qr-001",
    "correlationId": "e2e-golden-001",
    "workPackageId": "wp-001",
    "qaRequestId": "qar-001",
    "status": "COMPLETED",
    "testSummary": {"total": 25, "passed": 25, "failed": 0, "skipped": 0},
    "defects": [],
    "qualityGate": "APPROVED",
    "acceptanceValidation": {"businessCriteriaMet": True, "technicalCriteriaMet": True},
    "recommendedRegressionAreas": ["health-endpoint"],
    "evidence": [
        {
            "type": "QA_TEST_RESULTS",
            "source": "qa-again",
            "reference": "qa://evidences/test-run-001",
            "summary": "All 25 QA tests passed",
            "timestamp": "2026-08-09T03:30:00Z",
        }
    ],
    "completedAt": "2026-08-09T03:30:00Z",
}


def test_all_11_canonical_v1_contracts_load():
    results = CanonicalContractValidator.all_contracts_load()
    v1_names = [
        "OSMessageEnvelope", "BusinessIntent", "DeliveryWorkPackage", "PMStatus",
        "EngineeringWorkPackage", "EngineeringResult", "InfrastructureRequest",
        "InfrastructureResult", "QARequest", "QAResult", "DeliveryReadinessResult",
    ]
    assert len(v1_names) == 11
    for name in v1_names:
        assert results[name] is True, f"{name} failed to load"


def test_all_18_canonical_contracts_load():
    results = CanonicalContractValidator.all_contracts_load()
    assert len(ALL_CONTRACTS) == 18
    assert all(results.values()), {k: v for k, v in results.items() if not v}


def test_qarequest_binding_accepts_canonical_example():
    instance = v1.QARequest.validate_canonical(QA_REQUEST_EXAMPLE)
    assert instance.qaRequestId == "qar-001"
    assert instance.correlationId == "e2e-golden-001"


def test_qaresult_binding_accepts_canonical_example():
    instance = v1.QAResult.validate_canonical(QA_RESULT_EXAMPLE)
    assert instance.qaResultId == "qr-001"
    assert instance.qualityGate == "APPROVED"


def test_qarequest_binding_rejects_schema_violation():
    bad = dict(QA_REQUEST_EXAMPLE)
    del bad["releaseCandidate"]
    with pytest.raises((ContractValidationError, ValidationError)):
        v1.QARequest.validate_canonical(bad)


def test_qaresult_binding_rejects_invalid_quality_gate():
    bad = dict(QA_RESULT_EXAMPLE)
    bad["qualityGate"] = "MAYBE"
    with pytest.raises((ContractValidationError, ValidationError)):
        v1.QAResult.validate_canonical(bad)


def test_schema_level_violation_not_caught_by_pydantic_is_still_caught():
    """A violation the loose Pydantic binding wouldn't itself catch (extra
    schema constraint) must still be caught by the canonical JSON Schema
    validation step, not silently accepted."""
    bad = dict(QA_RESULT_EXAMPLE)
    bad["evidence"] = [{"type": "QA_TEST_RESULTS"}]  # missing required source/reference
    with pytest.raises((ContractValidationError, ValidationError)):
        v1.QAResult.validate_canonical(bad)


def test_no_parallel_contract_authority():
    """The binding's own serialized form must still satisfy the vendored
    canonical schema — QA Again cannot silently drift from the schema
    it claims to implement."""
    instance = v1.QARequest.model_validate(QA_REQUEST_EXAMPLE)
    CanonicalContractValidator.validate("QARequest", instance.to_canonical_dict())

    result_instance = v1.QAResult.model_validate(QA_RESULT_EXAMPLE)
    CanonicalContractValidator.validate("QAResult", result_instance.to_canonical_dict())
