"""Account Again — CredentialReference model (metadata + reference only, NO raw secrets)."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


# FORBIDDEN field names that must never appear in CredentialReference payloads
FORBIDDEN_CREDENTIAL_FIELDS = {
    "rawSecret", "apiKey", "password", "privateKey",
    "refreshToken", "accessToken", "secret", "secretValue",
    "token", "key", "credentialValue",
}


class CredentialReference(Base):
    __tablename__ = "credential_references"

    credential_ref = Column(String, primary_key=True, default=_new_id)
    tenant_id = Column(String, nullable=False, index=True)
    owner_account_id = Column(String, nullable=True, index=True)
    provider = Column(String, nullable=False)
    credential_type = Column(String, nullable=False)
    secret_store_type = Column(String, nullable=False, default="ACCOUNT_AGAIN_VAULT")
    secret_store_reference = Column(String, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(String, nullable=False, default=_now)
    rotated_at = Column(String, nullable=True)
    expires_at = Column(String, nullable=True)
    revoked_at = Column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "credentialRef": self.credential_ref,
            "tenantId": self.tenant_id,
            "ownerAccountId": self.owner_account_id,
            "provider": self.provider,
            "credentialType": self.credential_type,
            "secretStoreType": self.secret_store_type,
            "secretStoreReference": self.secret_store_reference,
            "status": self.status,
            "createdAt": self.created_at,
            "rotatedAt": self.rotated_at,
            "expiresAt": self.expires_at,
            "revokedAt": self.revoked_at,
        }
