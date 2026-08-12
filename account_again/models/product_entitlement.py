"""Account Again — Product Entitlement model."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class ProductEntitlement(Base):
    __tablename__ = "product_entitlements"

    entitlement_id = Column(String, primary_key=True, default=_new_id)
    tenant_id = Column(String, nullable=False, index=True)
    account_id = Column(String, nullable=True, index=True)
    subject_id = Column(String, nullable=True)
    product_id = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    valid_from = Column(String, nullable=True)
    valid_until = Column(String, nullable=True)
    policy_ref = Column(String, nullable=True)
    created_at = Column(String, nullable=False, default=_now)
    updated_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "entitlementId": self.entitlement_id,
            "tenantId": self.tenant_id,
            "accountId": self.account_id,
            "subjectId": self.subject_id,
            "productId": self.product_id,
            "status": self.status,
            "validFrom": self.valid_from,
            "validUntil": self.valid_until,
            "policyRef": self.policy_ref,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
