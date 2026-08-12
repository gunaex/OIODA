"""Account Again — Tenant model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from account_again.database import Base


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id = Column(String, primary_key=True, default=_new_id)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "tenantId": self.tenant_id,
            "name": self.name,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
