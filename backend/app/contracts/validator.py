import json
import os
from functools import lru_cache

from jsonschema import Draft202012Validator, ValidationError

_VENDORED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendored", "v1", "schemas")

# AGAIN-ECOSYSTEM (contracts/v1/) is the canonical source of truth (ADR-003).
# This is a verbatim vendored copy — see vendored/manifest.json for the exact
# source commit. Never hand-write a competing definition of these shapes.
V1_CONTRACTS = [
    "BusinessIntent",
    "DeliveryReadinessResult",
    "DeliveryWorkPackage",
    "EngineeringResult",
    "EngineeringWorkPackage",
    "InfrastructureRequest",
    "InfrastructureResult",
    "OSMessageEnvelope",
    "PMStatus",
    "QARequest",
    "QAResult",
]


@lru_cache(maxsize=None)
def load_schema(contract_name: str) -> dict:
    if contract_name not in V1_CONTRACTS:
        raise ValueError(f"Unknown canonical contract: {contract_name}")
    path = os.path.join(_VENDORED_DIR, f"{contract_name}.json")
    with open(path) as f:
        return json.load(f)


class CanonicalContractValidator:
    """Single validation boundary for canonical v1 contracts. Raises
    jsonschema.ValidationError on a non-conforming payload rather than
    silently coercing it — contract drift must be loud, not swallowed."""

    def __init__(self, contract_name: str):
        self.contract_name = contract_name
        self._validator = Draft202012Validator(load_schema(contract_name))

    def validate(self, payload: dict) -> None:
        self._validator.validate(payload)

    def is_valid(self, payload: dict) -> bool:
        return self._validator.is_valid(payload)


def load_all_schemas() -> dict[str, dict]:
    """Loads every vendored v1 schema — used by the drift-detection test to
    prove ALL_11_CANONICAL_CONTRACTS_LOAD without special-casing any one."""
    return {name: load_schema(name) for name in V1_CONTRACTS}


__all__ = ["CanonicalContractValidator", "ValidationError", "V1_CONTRACTS", "load_schema", "load_all_schemas"]
