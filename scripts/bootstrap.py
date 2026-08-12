#!/usr/bin/env python3
"""Account Again — Bootstrap script.

Creates:
- local tenant
- admin account
- base roles and permissions
- service identities for all known AGAIN systems
- product/AI entitlements for local testing
"""

import sys
sys.path.insert(0, ".")

from account_again.database import SessionLocal, create_all
from account_again.models import (
    Tenant, Account, SubjectIdentity, Role, Permission, RolePermission, AccountRole,
    ProductEntitlement, AIEntitlement, ServiceIdentity, VALID_SYSTEM_IDS,
    CredentialReference, QuotaPolicy,
)
from account_again.models.tenant import _new_id, _now

CANONICAL_PRODUCTS = [
    "CONDUCTOR_MAIN", "PM_AGAIN", "IDEA_TO_CODE",
    "INFRA_AGAIN", "QA_AGAIN", "LOCAL_AI_CONTROL_CENTER",
]

CANONICAL_CAPABILITIES = [
    "AI_CHAT", "AI_CODE", "AI_ARCHITECTURE",
    "AI_QA", "AI_INFRA_PLANNING", "AI_RAG", "AI_AGENT",
]

BASE_PERMISSIONS = [
    "ACCOUNT_READ", "ACCOUNT_ADMIN",
    "PRODUCT_ACCESS_MANAGE", "AI_ENTITLEMENT_READ", "AI_ENTITLEMENT_MANAGE",
    "CREDENTIAL_REF_READ", "CREDENTIAL_REF_MANAGE",
    "SERVICE_IDENTITY_MANAGE", "AUDIT_READ",
]

BASE_ROLES = [
    ("ADMIN", "Full administrative access"),
    ("READ_ONLY", "Read-only access to account data"),
]


def bootstrap():
    create_all()
    db = SessionLocal()

    try:
        # ── Tenant ──
        tenant = Tenant(tenant_id="local-tenant", name="Local Development")
        db.add(tenant)
        db.flush()

        # ── Admin account ──
        admin = Account(
            account_id="admin-account",
            tenant_id=tenant.tenant_id,
            email="admin@local.again",
            display_name="Local Admin",
        )
        db.add(admin)
        db.flush()

        # ── Admin identity (LOCAL/PASSWORD) ──
        from passlib.hash import bcrypt as passlib_bcrypt
        try:
            import bcrypt as _bcrypt_lib
            _pw_hash = _bcrypt_lib.hashpw(b"admin-dev-only", _bcrypt_lib.gensalt()).decode()
        except Exception:
            _pw_hash = passlib_bcrypt.hash("admin-dev-only")
        ident = SubjectIdentity(
            subject_id="admin-subject",
            account_id=admin.account_id,
            tenant_id=tenant.tenant_id,
            identity_provider="LOCAL",
            auth_method="PASSWORD",
            password_hash=_pw_hash,
        )
        db.add(ident)
        db.flush()

        # ── Roles ──
        role_map = {}
        for name, desc in BASE_ROLES:
            r = Role(role_id=_new_id(), name=name, description=desc)
            db.add(r)
            db.flush()
            role_map[name] = r.role_id

        # ── Permissions ──
        perm_map = {}
        for pname in BASE_PERMISSIONS:
            p = Permission(permission_id=_new_id(), name=pname)
            db.add(p)
            db.flush()
            perm_map[pname] = p.permission_id

        # ── Admin role gets all permissions ──
        for pname in BASE_PERMISSIONS:
            db.add(RolePermission(id=_new_id(), role_id=role_map["ADMIN"], permission_id=perm_map[pname]))

        # ── Assign admin role to admin account ──
        db.add(AccountRole(id=_new_id(), account_id=admin.account_id, role_id=role_map["ADMIN"], tenant_id=tenant.tenant_id))

        # ── Product entitlements ──
        for pid in CANONICAL_PRODUCTS:
            db.add(ProductEntitlement(
                entitlement_id=_new_id(), tenant_id=tenant.tenant_id,
                product_id=pid, status="ACTIVE",
            ))

        # ── AI entitlements ──
        for cap in CANONICAL_CAPABILITIES:
            db.add(AIEntitlement(
                entitlement_id=_new_id(), tenant_id=tenant.tenant_id,
                capability=cap, status="ACTIVE",
            ))

        # ── Service identities ──
        for sid in VALID_SYSTEM_IDS:
            db.add(ServiceIdentity(
                service_identity_id=_new_id(), system_id=sid, status="ACTIVE",
            ))

        # ── Default quota ──
        db.add(QuotaPolicy(
            policy_id=_new_id(), tenant_id=tenant.tenant_id,
            scope="TENANT", tokens_per_day=100000, tokens_per_month=3000000,
            cost_cents_per_month=5000,
        ))

        db.commit()
        print("✓ Bootstrap complete")
        print(f"  Tenant:    {tenant.tenant_id}")
        print(f"  Account:   {admin.account_id} ({admin.email})")
        print(f"  Roles:     {list(role_map.keys())}")
        print(f"  Products:  {CANONICAL_PRODUCTS}")
        print(f"  AI Caps:   {CANONICAL_CAPABILITIES}")
        print(f"  Services:  {sorted(VALID_SYSTEM_IDS)}")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()
