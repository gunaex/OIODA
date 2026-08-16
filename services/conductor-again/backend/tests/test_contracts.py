"""
E8-A — Canonical contract binding tests.

Proves the 11 v1 + 7 v2 AGAIN-ECOSYSTEM canonical contracts load, validate,
and cannot silently drift out from under the vendored copy.
"""

import json
from pathlib import Path

import pytest

from app.contracts import v1, v2
from app.contracts.validator import (
    ALL_CONTRACTS,
    V1_CONTRACTS,
    V2_CONTRACTS,
    CanonicalContractValidator,
    ContractValidationError,
    load_manifest,
    load_schema,
)

VENDORED_DIR = Path(__file__).parent.parent / "app" / "contracts" / "vendored"
EXAMPLES_DIR = Path("/Users/kanphong/AGAIN-ECOSYSTEM/contracts/v1/examples")


def test_canonical_contract_source_recorded():
    manifest = load_manifest()
    assert manifest["canonicalAuthority"] == "AGAIN-ECOSYSTEM"
    assert manifest["sourceCommit"]
    assert manifest["sourceRepo"]


def test_all_11_v1_contracts_load():
    assert len(V1_CONTRACTS) == 11
    for name in V1_CONTRACTS:
        schema = load_schema(name)
        assert schema["title"] == name


def test_all_7_v2_contracts_load():
    assert len(V2_CONTRACTS) == 7
    for name in V2_CONTRACTS:
        schema = load_schema(name)
        assert schema["title"] == name


def test_all_18_canonical_contracts_load():
    results = CanonicalContractValidator.all_contracts_load()
    assert all(results.values()), results
    assert len(results) == 18


@pytest.mark.parametrize(
    "name,model_cls,minimal",
    [
        ("BusinessIntent", v1.BusinessIntent, {
            "businessIntentId": "bi-1", "correlationId": "c-1", "title": "t",
            "description": "d", "priority": "HIGH", "createdAt": "2026-08-12T00:00:00Z",
        }),
        ("DeliveryWorkPackage", v1.DeliveryWorkPackage, {
            "workPackageId": "wp-1", "correlationId": "c-1", "businessIntentId": "bi-1",
            "title": "t", "priority": "HIGH", "state": "DRAFT",
            "assignments": {"engineering": True}, "createdAt": "2026-08-12T00:00:00Z",
        }),
        ("EngineeringWorkPackage", v1.EngineeringWorkPackage, {
            "engineeringWorkPackageId": "ewp-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "requirements": "build it", "createdAt": "2026-08-12T00:00:00Z",
        }),
        ("EngineeringResult", v1.EngineeringResult, {
            "engineeringResultId": "er-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "status": "SUCCESS", "repo": "r", "branch": "b", "commit": "c",
            "pipeline": {}, "evidence": [], "completedAt": "2026-08-12T00:00:00Z",
        }),
        ("InfrastructureRequest", v1.InfrastructureRequest, {
            "infrastructureRequestId": "ir-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "engineeringResultId": "er-1", "requirements": {}, "createdAt": "2026-08-12T00:00:00Z",
        }),
        ("InfrastructureResult", v1.InfrastructureResult, {
            "infrastructureResultId": "ifr-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "infrastructureRequestId": "ir-1", "status": "SUCCESS", "provider": "AWS",
            "platform": "KUBERNETES", "evidence": [], "completedAt": "2026-08-12T00:00:00Z",
        }),
        ("QARequest", v1.QARequest, {
            "qaRequestId": "qar-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "releaseCandidate": {"repo": "r", "branch": "b", "commit": "c"},
            "acceptanceCriteria": {}, "createdAt": "2026-08-12T00:00:00Z",
        }),
        ("QAResult", v1.QAResult, {
            "qaResultId": "qr-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "qaRequestId": "qar-1", "status": "COMPLETED",
            "testSummary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
            "qualityGate": "APPROVED", "evidence": [], "completedAt": "2026-08-12T00:00:00Z",
        }),
        ("DeliveryReadinessResult", v1.DeliveryReadinessResult, {
            "deliveryReadinessResultId": "drr-1", "correlationId": "c-1", "workPackageId": "wp-1",
            "decision": "READY_FOR_DELIVERY", "aggregatedEvidence": {}, "decidedBy": "conductor-main",
            "decidedAt": "2026-08-12T00:00:00Z",
        }),
    ],
)
def test_v1_contract_runtime_binding(name, model_cls, minimal):
    instance = model_cls.validate_canonical(minimal)
    assert instance.to_canonical_dict()["correlationId"] == "c-1"


def test_pm_status_binding_not_used_but_valid():
    payload = {
        "pmStatusId": "pms-1", "correlationId": "c-1", "workPackageId": "wp-1",
        "projectStatus": "IN_PROGRESS", "reportedAt": "2026-08-12T00:00:00Z",
    }
    v1.PMStatus.validate_canonical(payload)


def test_os_message_envelope_binding():
    payload = {
        "envelopeId": "env-1", "correlationId": "c-1", "messageType": "BusinessIntent",
        "source": "conductor-main", "timestamp": "2026-08-12T00:00:00Z", "payload": {},
    }
    v1.OSMessageEnvelope.validate_canonical(payload)


def test_invalid_payload_rejected():
    with pytest.raises(Exception):
        v1.BusinessIntent.validate_canonical({"businessIntentId": "x"})


def test_invalid_payload_rejected_by_canonical_validator_directly():
    """Bypass the pydantic binding to prove the jsonschema boundary itself rejects
    a structurally-wrong-but-pydantic-permissive payload (e.g. bad enum value)."""
    payload = {
        "businessIntentId": "bi-1", "correlationId": "c-1", "title": "t",
        "description": "d", "priority": "NOT_A_REAL_PRIORITY", "createdAt": "2026-08-12T00:00:00Z",
    }
    with pytest.raises(ContractValidationError):
        CanonicalContractValidator.validate("BusinessIntent", payload)


def test_v2_entitlement_decision_binding():
    payload = {
        "entitlementDecisionId": "ed-1", "decision": "ALLOW", "reasonCode": "ENTITLED",
        "evaluatedAt": "2026-08-12T00:00:00Z",
    }
    v2.EntitlementDecision.validate_canonical(payload)


def test_v2_service_identity_binding():
    payload = {
        "serviceIdentityId": "si-1", "systemId": "CONDUCTOR_MAIN", "status": "ACTIVE",
        "createdAt": "2026-08-12T00:00:00Z",
    }
    v2.ServiceIdentity.validate_canonical(payload)


@pytest.mark.skipif(not EXAMPLES_DIR.exists(), reason="AGAIN-ECOSYSTEM checkout not available")
def test_drift_against_ecosystem_examples():
    """Contract drift detection: every AGAIN-ECOSYSTEM v1 example payload must
    still validate against our vendored schema copy. A failure here means the
    vendored copy has drifted from the canonical source and must be re-synced."""
    for name in V1_CONTRACTS:
        example_path = EXAMPLES_DIR / f"{name}.json"
        if not example_path.exists():
            continue
        with open(example_path) as f:
            example = json.load(f)
        CanonicalContractValidator.validate(name, example)


@pytest.mark.skipif(not Path("/Users/kanphong/AGAIN-ECOSYSTEM").exists(),
                     reason="AGAIN-ECOSYSTEM checkout not available")
def test_drift_vendored_matches_source_repo():
    """Byte-for-byte drift check: vendored schema files must match the source
    repo at the recorded commit. If this fails, either re-vendor (if the
    source moved forward intentionally) or investigate an unrecorded change."""
    source_dir = Path("/Users/kanphong/AGAIN-ECOSYSTEM/contracts")
    for version, names in (("v1", V1_CONTRACTS), ("v2", V2_CONTRACTS)):
        for name in names:
            vendored = VENDORED_DIR / version / "schemas" / f"{name}.json"
            source = source_dir / version / "schemas" / f"{name}.json"
            if not source.exists():
                continue
            assert vendored.read_text() == source.read_text(), f"{name} ({version}) has drifted from source"
