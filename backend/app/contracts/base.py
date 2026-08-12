"""Shared base for canonical AGAIN-ECOSYSTEM contract bindings (E8-A)."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class CanonicalModel(BaseModel):
    """Base for every canonical contract binding.

    extra="allow" mirrors the canonical schemas, none of which declare
    additionalProperties: false — a binding that rejected unknown fields
    would be stricter than the canonical authority, which is itself a form
    of drift.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    _contract_name: ClassVar[str] = ""

    def to_canonical_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def validate_canonical(cls, data: dict[str, Any]):
        """Parse into this binding AND check against the vendored canonical
        JSON Schema. Raises ContractValidationError on drift/violation."""
        from app.contracts.validator import CanonicalContractValidator

        instance = cls.model_validate(data)
        CanonicalContractValidator.validate(cls._contract_name, instance.to_canonical_dict())
        return instance
