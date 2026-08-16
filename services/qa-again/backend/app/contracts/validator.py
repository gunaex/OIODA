"""
QA Again — Canonical Contract Validator (QA-E1)

Single validation boundary for every canonical AGAIN-ECOSYSTEM contract that
enters or leaves QA Again. Do not scatter jsonschema calls across routers —
call CanonicalContractValidator.validate() at the edge instead.

Canonical authority is AGAIN-ECOSYSTEM (see contracts/vendored/manifest.json).
This module validates against a vendored, version-pinned copy of those JSON
Schemas. It does not define, extend, or fork contract semantics.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

VENDORED_DIR = Path(__file__).parent / "vendored"

V1_CONTRACTS = [
    "OSMessageEnvelope",
    "BusinessIntent",
    "DeliveryWorkPackage",
    "PMStatus",
    "EngineeringWorkPackage",
    "EngineeringResult",
    "InfrastructureRequest",
    "InfrastructureResult",
    "QARequest",
    "QAResult",
    "DeliveryReadinessResult",
]

V2_CONTRACTS = [
    "IdentityClaims",
    "ServiceIdentity",
    "CredentialRef",
    "EntitlementDecision",
    "AIExecutionRequest",
    "AIExecutionResult",
    "EvidenceReference",
]

ALL_CONTRACTS = V1_CONTRACTS + V2_CONTRACTS


class ContractNotFoundError(Exception):
    pass


class ContractValidationError(Exception):
    def __init__(self, contract_name: str, errors: list[str]):
        self.contract_name = contract_name
        self.errors = errors
        super().__init__(f"{contract_name} failed canonical validation: {errors}")


def _schema_path(contract_name: str) -> Path:
    if contract_name in V1_CONTRACTS:
        return VENDORED_DIR / "v1" / "schemas" / f"{contract_name}.json"
    if contract_name in V2_CONTRACTS:
        return VENDORED_DIR / "v2" / "schemas" / f"{contract_name}.json"
    raise ContractNotFoundError(f"Unknown canonical contract: {contract_name}")


@lru_cache(maxsize=None)
def load_schema(contract_name: str) -> dict:
    path = _schema_path(contract_name)
    if not path.exists():
        raise ContractNotFoundError(f"Vendored schema missing for {contract_name}: {path}")
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_manifest() -> dict:
    with open(VENDORED_DIR / "manifest.json") as f:
        return json.load(f)


class CanonicalContractValidator:
    """The single validation boundary for canonical AGAIN-ECOSYSTEM contracts."""

    @staticmethod
    def validate(contract_name: str, payload: dict[str, Any]) -> None:
        """Validate payload against the vendored canonical JSON Schema.

        Raises ContractValidationError with the full list of schema violations
        if payload does not conform. Raises ContractNotFoundError if
        contract_name is not one of the 11 v1 / 7 v2 canonical contracts.
        """
        schema = load_schema(contract_name)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
        if errors:
            raise ContractValidationError(
                contract_name,
                [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors],
            )

    @staticmethod
    def is_valid(contract_name: str, payload: dict[str, Any]) -> bool:
        try:
            CanonicalContractValidator.validate(contract_name, payload)
            return True
        except (ContractValidationError, ContractNotFoundError):
            return False

    @staticmethod
    def validate_version(contract_name: str, payload_version: str) -> bool:
        """Check payload_version against the schema's declared 'version' field."""
        schema = load_schema(contract_name)
        return schema.get("version") == payload_version

    @staticmethod
    def contract_version(contract_name: str) -> str:
        return load_schema(contract_name).get("version", "")

    @staticmethod
    def all_contracts_load() -> dict[str, bool]:
        results = {}
        for name in ALL_CONTRACTS:
            try:
                load_schema(name)
                results[name] = True
            except (ContractNotFoundError, jsonschema.exceptions.SchemaError):
                results[name] = False
        return results
