"""Account Again — Session model (metadata only)."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class SessionRecord(Base):
    __tablename__ = "session_records"

    session_id = Column(String, primary_key=True, default=_new_id)
    subject_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="ACTIVE")
    issued_at = Column(String, nullable=False, default=_now)
    expires_at = Column(String, nullable=False)
    revoked_at = Column(String, nullable=True)
    created_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "sessionId": self.session_id,
            "subjectId": self.subject_id,
            "tenantId": self.tenant_id,
            "status": self.status,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
            "revokedAt": self.revoked_at,
        }
