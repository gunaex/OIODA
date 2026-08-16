"""Account Again — Quota policy model."""

from sqlalchemy import Column, String, Integer
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class QuotaPolicy(Base):
    __tablename__ = "quota_policies"

    policy_id = Column(String, primary_key=True, default=_new_id)
    tenant_id = Column(String, nullable=False, index=True)
    scope = Column(String, nullable=False)
    scope_id = Column(String, nullable=True)
    requests_per_day = Column(Integer, nullable=True)
    tokens_per_day = Column(Integer, nullable=True)
    tokens_per_month = Column(Integer, nullable=True)
    cost_cents_per_month = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "policyId": self.policy_id,
            "tenantId": self.tenant_id,
            "scope": self.scope,
            "scopeId": self.scope_id,
            "requestsPerDay": self.requests_per_day,
            "tokensPerDay": self.tokens_per_day,
            "tokensPerMonth": self.tokens_per_month,
            "costCentsPerMonth": self.cost_cents_per_month,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
