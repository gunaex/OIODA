"""Tenant scoping primitives shared across the request and service layers.

The actor context (routers.deps) sets the current tenant for the duration of
a request; service-layer ``guard_project`` reads it and blocks cross-tenant
access. In local development mode the current tenant is only set when the
caller explicitly supplies ``X-Tenant-Id``, so tenant isolation is enforced
where a tenant is actually in play and remains transparent otherwise.
"""
from __future__ import annotations

import contextvars

CURRENT_TENANT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "da_current_tenant", default=None
)


def set_current_tenant(tenant_id: str | None) -> None:
    CURRENT_TENANT.set(tenant_id)


def current_tenant() -> str | None:
    return CURRENT_TENANT.get()


def tenant_scoped() -> bool:
    """True when the request carries an explicit tenant (enforcement active)."""
    return current_tenant() is not None
