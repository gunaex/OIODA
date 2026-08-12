"""Account Again — Role & Permission models (RBAC)."""

from sqlalchemy import Column, String
from account_again.database import Base
from account_again.models.tenant import _new_id, _now


class Role(Base):
    __tablename__ = "roles"

    role_id = Column(String, primary_key=True, default=_new_id)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "roleId": self.role_id,
            "name": self.name,
            "description": self.description,
            "createdAt": self.created_at,
        }


class Permission(Base):
    __tablename__ = "permissions"

    permission_id = Column(String, primary_key=True, default=_new_id)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)

    def to_dict(self) -> dict:
        return {
            "permissionId": self.permission_id,
            "name": self.name,
            "description": self.description,
        }


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(String, primary_key=True, default=_new_id)
    role_id = Column(String, nullable=False, index=True)
    permission_id = Column(String, nullable=False)


class AccountRole(Base):
    __tablename__ = "account_roles"

    id = Column(String, primary_key=True, default=_new_id)
    account_id = Column(String, nullable=False, index=True)
    role_id = Column(String, nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    assigned_at = Column(String, nullable=False, default=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "accountId": self.account_id,
            "roleId": self.role_id,
            "tenantId": self.tenant_id,
            "assignedAt": self.assigned_at,
        }
