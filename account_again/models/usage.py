"""Account Again — Usage record model."""

from sqlalchemy import Column, String, Integer
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class UsageRecord(Base):
    __tablename__ = "usage_records"

    record_id = Column(String, primary_key=True, default=_new_id)
    tenant_id = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=True, index=True)
    capability = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost_cents = Column(Integer, nullable=True)
    correlation_id = Column(String, nullable=True, index=True)
    recorded_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "recordId": self.record_id,
            "tenantId": self.tenant_id,
            "accountId": self.account_id,
            "capability": self.capability,
            "provider": self.provider,
            "model": self.model,
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "totalTokens": self.total_tokens,
            "costCents": self.cost_cents,
            "correlationId": self.correlation_id,
            "recordedAt": self.recorded_at,
        }
