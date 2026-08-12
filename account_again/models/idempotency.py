"""Account Again — Idempotency model."""

from sqlalchemy import Column, String, JSON
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key = Column(String, primary_key=True)
    result = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="COMPLETED")
    created_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "status": self.status,
            "createdAt": self.created_at,
        }
