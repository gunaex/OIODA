"""Account Again — ServiceIdentity model."""

from sqlalchemy import Column, String, JSON
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


VALID_SYSTEM_IDS = {
    "CONDUCTOR_MAIN", "PM_AGAIN", "IDEA_TO_CODE",
    "INFRA_AGAIN", "QA_AGAIN", "LOCAL_AI_CONTROL_CENTER", "ACCOUNT_AGAIN",
    "DOCUMENT_AGAIN",
}


class ServiceIdentity(Base):
    __tablename__ = "service_identities"

    service_identity_id = Column(String, primary_key=True, default=_new_id)
    system_id = Column(String, nullable=False, unique=True)
    tenant_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")
    allowed_capabilities = Column(JSON, nullable=True, default=list)
    created_at = Column(String, nullable=False, default=_now)
    revoked_at = Column(String, nullable=True)
    # E5.1: bcrypt hash of the client secret used for OAuth2-client-credentials-style
    # token issuance (POST /auth/service-token). Never the plaintext secret — the
    # plaintext is returned exactly once, at creation/rotation time, and never stored.
    client_secret_hash = Column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "serviceIdentityId": self.service_identity_id,
            "systemId": self.system_id,
            "tenantId": self.tenant_id,
            "status": self.status,
            "allowedCapabilities": self.allowed_capabilities or [],
            "createdAt": self.created_at,
            "revokedAt": self.revoked_at,
        }
