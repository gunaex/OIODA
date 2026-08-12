"""Account Again — Account model."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(String, primary_key=True, default=_new_id)
    tenant_id = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "accountId": self.account_id,
            "tenantId": self.tenant_id,
            "email": self.email,
            "displayName": self.display_name,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
