"""Account Again — SubjectIdentity model (auth identity separate from domain profile)."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class SubjectIdentity(Base):
    __tablename__ = "subject_identities"

    subject_id = Column(String, primary_key=True, default=_new_id)
    account_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    identity_provider = Column(String, nullable=False, default="LOCAL")
    provider_subject = Column(String, nullable=True)
    auth_method = Column(String, nullable=False, default="PASSWORD")
    password_hash = Column(String, nullable=True)  # only for LOCAL/PASSWORD
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        d = {
            "subjectId": self.subject_id,
            "accountId": self.account_id,
            "tenantId": self.tenant_id,
            "identityProvider": self.identity_provider,
            "providerSubject": self.provider_subject,
            "authMethod": self.auth_method,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        # NEVER include password_hash in normal dict output
        return d
