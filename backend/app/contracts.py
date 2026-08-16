"""Versioned cross-service contract governance.

Every outbound ecosystem payload carries an explicit ``contract`` object
with ``name`` and ``version``. Compatibility policy:

  major version  = breaking change (consumers MUST reject an unsupported major)
  minor version  = backward-compatible additive change
  patch          = clarification / bug-fix with no shape change

Document Again never silently changes an existing payload shape — a shape
change is a new major version and existing consumers keep the old major.
"""
from __future__ import annotations

# contract name -> highest supported MAJOR version
SUPPORTED_CONTRACTS = {
    "execution-handoff": 1,
    "qa-validation-handoff": 1,
    "acknowledgement": 1,
    "ecosystem-event": 1,
    "external-reference": 1,
    "document-again-handoff": 1,
}


class ContractVersionError(Exception):
    """Raised when a payload's contract is missing or unsupported."""


def build_contract(name: str, version: int = 1) -> dict:
    if name not in SUPPORTED_CONTRACTS:
        raise ContractVersionError(f"unknown contract {name!r}")
    if version != SUPPORTED_CONTRACTS[name]:
        raise ContractVersionError(f"contract {name} version {version} is not supported")
    return {"name": name, "version": version}


def versioned_payload(name: str, version: int, **fields) -> dict:
    """Wrap domain fields in an explicit versioned contract envelope."""
    return {"contract": build_contract(name, version), **fields}


def require_compatible(payload: dict, name: str) -> dict:
    """Validate an inbound contract envelope against a supported major.

    A missing contract or an unsupported major version is rejected — never
    silently misread. A supported major with any minor/patch is accepted.
    """
    contract = payload.get("contract") if isinstance(payload, dict) else None
    if not isinstance(contract, dict):
        raise ContractVersionError(f"missing contract envelope for {name!r}")
    if contract.get("name") != name:
        raise ContractVersionError(f"contract name mismatch: expected {name!r}, got {contract.get('name')!r}")
    version = contract.get("version")
    if not isinstance(version, int):
        raise ContractVersionError("contract version must be an integer")
    if name not in SUPPORTED_CONTRACTS:
        raise ContractVersionError(f"unknown contract {name!r}")
    if version > SUPPORTED_CONTRACTS[name]:
        raise ContractVersionError(
            f"contract {name} version {version} exceeds supported major {SUPPORTED_CONTRACTS[name]}"
        )
    return payload
