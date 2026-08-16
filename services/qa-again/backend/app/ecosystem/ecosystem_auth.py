"""
QA Again — Ecosystem auth boundary (QA-E6).

ECOSYSTEM_MODE=true makes Account Again authoritative for tenant/product
entitlement. Local JWT auth (app/auth.py) remains for session/identity of
the human operator — demoted, dev-only, and explicitly NOT authoritative
for tenant or entitlement decisions in ecosystem mode
(LOCAL_AUTH_NOT_AUTHORITATIVE_IN_ECOSYSTEM_MODE). Mirrors PM Again's own
app/ecosystem/ecosystem_auth.py and Conductor's
app/orchestration/ecosystem_auth.py for consistency across the ecosystem.
"""

import os

from fastapi import Depends, HTTPException, Request

from .. import models
from ..auth import get_current_user
from ..database import MasterSessionLocal
from . import account_again_client

ECOSYSTEM_MODE = os.environ.get("ECOSYSTEM_MODE", "false").lower() == "true"
QA_AGAIN_PRODUCT_ID = "QA_AGAIN"
DEFAULT_TENANT_ID = "local-tenant"


class EcosystemIdentity:
    def __init__(self, tenant_id: str, user: models.User, entitlement_decision: dict | None):
        self.tenant_id = tenant_id
        self.user = user
        self.entitlement_decision = entitlement_decision


def require_ecosystem_identity(
    request: Request,
    user: models.User = Depends(get_current_user),
) -> EcosystemIdentity:
    """Resolves the caller's tenant. Local session auth (app/auth.py) still
    supplies human session identity/role — migrating human session auth
    fully to Account Again IdentityClaims is out of QA-E6's scope (disclosed
    limitation, matches PM-E6's same call). What IS enforced here, live, is
    Account Again's authority over TENANT and PRODUCT ENTITLEMENT in
    ecosystem mode: a valid local session and the right global role are not
    enough on their own."""
    tenant_id = request.headers.get("X-Tenant-Id") or user.tenant_id or DEFAULT_TENANT_ID

    if not ECOSYSTEM_MODE:
        return EcosystemIdentity(tenant_id=tenant_id, user=user, entitlement_decision=None)

    decision = account_again_client.evaluate_entitlement(
        tenant_id=tenant_id, product_id=QA_AGAIN_PRODUCT_ID, service_system_id=QA_AGAIN_PRODUCT_ID
    )
    if decision.get("decision") != "ALLOW":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "QA_AGAIN_ENTITLEMENT_DENIED",
                "reasonCode": decision.get("reasonCode"),
                "reasonMessage": decision.get("reasonMessage"),
            },
        )
    return EcosystemIdentity(tenant_id=tenant_id, user=user, entitlement_decision=decision)


def require_project_tenant_match(
    slug: str, request: Request, identity: EcosystemIdentity = Depends(require_ecosystem_identity)
) -> EcosystemIdentity:
    """Layered on top of require_ecosystem_identity for slug-scoped routes.
    Only actually enforced when ECOSYSTEM_MODE=true — a project can carry a
    tenant_id (recorded at ecosystem intake time regardless of mode)
    without that yet gating a local dev human session that isn't presenting
    any tenant context of its own. A project with no tenant_id at all is
    always exempt. 404, not 403, on mismatch: matches Conductor's and PM
    Again's own convention of not leaking cross-tenant existence."""
    if not ECOSYSTEM_MODE:
        return identity
    with MasterSessionLocal() as master_db:
        project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
        if project and project.tenant_id and project.tenant_id != identity.tenant_id:
            raise HTTPException(status_code=404, detail="Project not found")
    return identity
