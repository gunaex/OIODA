"""Account Again — Audit record model."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now

# Fields that must NEVER appear in audit payload
FORBIDDEN_AUDIT_FIELDS = {
    "password", "apiKey", "secret", "token",
    "credentialValue", "privateKey", "accessToken", "refreshToken",
}


class AuditRecord(Base):
    __tablename__ = "audit_records"

    audit_id = Column(String, primary_key=True, default=_new_id)
    actor_type = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    result = Column(String, nullable=False)
    correlation_id = Column(String, nullable=True, index=True)
    metadata_json = Column(String, nullable=True)
    created_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "auditId": self.audit_id,
            "actorType": self.actor_type,
            "actorId": self.actor_id,
            "tenantId": self.tenant_id,
            "action": self.action,
            "targetType": self.target_type,
            "targetId": self.target_id,
            "result": self.result,
            "correlationId": self.correlation_id,
            "metadata": self.metadata_json,
            "createdAt": self.created_at,
        }
