"""
Conductor Again — Canonical AGAIN-ECOSYSTEM Contract Bindings (E8-A)

Canonical authority for all contracts in this package is AGAIN-ECOSYSTEM
(see vendored/manifest.json for the exact vendored source commit). Conductor
Main does not define or fork contract semantics — the models here are
generated/validated Python bindings only.

Usage:
    from app.contracts import v1, v2
    from app.contracts.validator import CanonicalContractValidator

    bi = v1.BusinessIntent(businessIntentId="bi-1", correlationId="c-1",
                            title="...", description="...", priority="HIGH",
                            createdAt="2026-08-12T00:00:00Z")
    CanonicalContractValidator.validate("BusinessIntent", bi.to_canonical_dict())
"""

from app.contracts.validator import CanonicalContractValidator, ALL_CONTRACTS, V1_CONTRACTS, V2_CONTRACTS

__all__ = ["CanonicalContractValidator", "ALL_CONTRACTS", "V1_CONTRACTS", "V2_CONTRACTS"]
