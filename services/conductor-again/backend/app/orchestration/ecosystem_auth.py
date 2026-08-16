"""
Conductor Again — Ecosystem auth boundary (E8-C).

ECOSYSTEM_MODE=true makes Account Again authoritative for tenant/product
entitlement on every orchestration endpoint. Local JWT auth (app/auth.py)
remains as LEGACY_LOCAL_AUTH for session/identity of the human operator —
demoted, dev-only, and explicitly NOT authoritative for tenant or
entitlement decisions in ecosystem mode (§30).
"""

import os

from fastapi import Depends, HTTPException, Request

from app.auth import get_current_user
from app.integration.account_again_client import AccountAgainClient
from app.models import User

ECOSYSTEM_MODE = os.getenv("ECOSYSTEM_MODE", "false").lower() == "true"
CONDUCTOR_PRODUCT_ID = "CONDUCTOR_MAIN"
DEFAULT_TENANT_ID = "local-tenant"


class EcosystemIdentity:
    """Resolved identity for one orchestration request."""

    def __init__(self, tenant_id: str, user: User, entitlement_decision: dict | None):
        self.tenant_id = tenant_id
        self.user = user
        self.entitlement_decision = entitlement_decision


def require_ecosystem_identity(
    request: Request,
    user: User = Depends(get_current_user),
) -> EcosystemIdentity:
    """FastAPI dependency for orchestration endpoints.

    Human session identity still comes from LEGACY_LOCAL_AUTH (app/auth.py) —
    migrating human session auth fully to Account Again IdentityClaims is out
    of E8's scope (disclosed limitation). What IS enforced here, live, is
    Account Again's authority over TENANT and PRODUCT ENTITLEMENT: every
    orchestration request must resolve a tenant and, in ecosystem mode, be
    ALLOWed by Account Again's entitlement engine for CONDUCTOR_MAIN — local
    auth cannot bypass this (§30).
    """
    tenant_id = request.headers.get("X-Tenant-Id") or DEFAULT_TENANT_ID

    if not ECOSYSTEM_MODE:
        return EcosystemIdentity(tenant_id=tenant_id, user=user, entitlement_decision=None)

    decision = AccountAgainClient.evaluate_entitlement(
        tenant_id=tenant_id, product_id=CONDUCTOR_PRODUCT_ID,
        correlation_id=request.headers.get("X-Correlation-Id"),
    )
    if decision.get("decision") != "ALLOW":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CONDUCTOR_ENTITLEMENT_DENIED",
                "reasonCode": decision.get("reasonCode"),
                "reasonMessage": decision.get("reasonMessage"),
            },
        )
    return EcosystemIdentity(tenant_id=tenant_id, user=user, entitlement_decision=decision)
