"""Account Again — AI Entitlement model."""

from sqlalchemy import Column, String, Integer, Boolean
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class AIEntitlement(Base):
    __tablename__ = "ai_entitlements"

    entitlement_id = Column(String, primary_key=True, default=_new_id)
    tenant_id = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=True, index=True)
    capability = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    provider_constraint = Column(String, nullable=True)
    model_constraint = Column(String, nullable=True)
    local_only = Column(Boolean, nullable=False, default=False)
    cloud_allowed = Column(Boolean, nullable=False, default=True)
    max_cost_cents = Column(Integer, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "entitlementId": self.entitlement_id,
            "tenantId": self.tenant_id,
            "accountId": self.account_id,
            "capability": self.capability,
            "status": self.status,
            "providerConstraint": self.provider_constraint,
            "modelConstraint": self.model_constraint,
            "localOnly": self.local_only,
            "cloudAllowed": self.cloud_allowed,
            "maxCostCents": self.max_cost_cents,
            "maxTokens": self.max_tokens,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
