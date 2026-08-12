"""ALL_11_CANONICAL_CONTRACTS_LOAD / CONTRACT_DRIFT_DETECTABLE."""

import pytest
from jsonschema import ValidationError

from app.contracts.validator import CanonicalContractValidator, V1_CONTRACTS, load_all_schemas
from app.contracts.models import DeliveryWorkPackage, PMStatus


def test_all_11_canonical_contracts_load():
    schemas = load_all_schemas()
    assert len(schemas) == 11
    assert set(schemas.keys()) == set(V1_CONTRACTS)
    for name, schema in schemas.items():
        assert schema["title"] == name


VALID_DELIVERY_WORK_PACKAGE = {
    "workPackageId": "wp-001",
    "correlationId": "e2e-golden-001",
    "businessIntentId": "bi-001",
    "title": "Production-ready web application",
    "priority": "HIGH",
    "state": "PLANNED",
    "assignments": {"pm": True, "engineering": True},
    "createdAt": "2026-08-12T00:00:00Z",
}

VALID_PM_STATUS = {
    "pmStatusId": "pms-001",
    "correlationId": "e2e-golden-001",
    "workPackageId": "wp-001",
    "projectStatus": "IN_PROGRESS",
    "reportedAt": "2026-08-12T00:00:00Z",
}


def test_delivery_work_package_schema_validates_conforming_payload():
    validator = CanonicalContractValidator("DeliveryWorkPackage")
    validator.validate(VALID_DELIVERY_WORK_PACKAGE)  # must not raise
    DeliveryWorkPackage.model_validate(VALID_DELIVERY_WORK_PACKAGE)  # must not raise


def test_delivery_work_package_schema_rejects_broken_payload():
    validator = CanonicalContractValidator("DeliveryWorkPackage")
    broken = dict(VALID_DELIVERY_WORK_PACKAGE)
    del broken["businessIntentId"]  # required field missing
    with pytest.raises(ValidationError):
        validator.validate(broken)

    broken_enum = dict(VALID_DELIVERY_WORK_PACKAGE, priority="SUPER_URGENT")
    with pytest.raises(ValidationError):
        validator.validate(broken_enum)


def test_pmstatus_schema_validates_conforming_payload():
    validator = CanonicalContractValidator("PMStatus")
    validator.validate(VALID_PM_STATUS)
    PMStatus.model_validate(VALID_PM_STATUS)


def test_pmstatus_schema_rejects_broken_payload():
    validator = CanonicalContractValidator("PMStatus")
    broken = dict(VALID_PM_STATUS)
    del broken["reportedAt"]
    with pytest.raises(ValidationError):
        validator.validate(broken)

    broken_enum = dict(VALID_PM_STATUS, projectStatus="ON_FIRE")
    with pytest.raises(ValidationError):
        validator.validate(broken_enum)
