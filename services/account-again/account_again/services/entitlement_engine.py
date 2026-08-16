"""Account Again — Entitlement decision engine.

Answers: may this subject/service use this product/capability/provider?
Authority: Account Again (NOT Local AI Control Center).
"""

from dataclasses import dataclass, field
from typing import Optional, List
from sqlalchemy.orm import Session

from account_again.models import (
    Tenant, Account, SubjectIdentity, ServiceIdentity,
    ProductEntitlement, AIEntitlement, QuotaPolicy, UsageRecord,
)
from account_again.models.tenant import _new_id

# Canonical reason-code vocabulary (E4.1 §6). This Python list is the single source of
# truth — contracts/v2/schemas/EntitlementDecision.json's reasonCode enum is generated
# to match it exactly (see scripts/export-reason-codes.py); the engine must never emit
# a code outside this set (enforced by test_e4_1_reason_codes_canonical.py).
REASON_CODES = {
    "ENTITLED",
    "TENANT_NOT_FOUND",
    "TENANT_SUSPENDED",
    "TENANT_DISABLED",
    "TENANT_MISMATCH",
    "SUBJECT_NOT_FOUND",
    "SUBJECT_DISABLED",
    "ACCOUNT_NOT_FOUND",
    "ACCOUNT_DISABLED",
    "SERVICE_IDENTITY_NOT_FOUND",
    "REVOKED_SERVICE_IDENTITY",
    "PRODUCT_NOT_ENTITLED",
    "CAPABILITY_NOT_ENTITLED",
    "PROVIDER_NOT_ALLOWED",
    "MODEL_NOT_ALLOWED",
    "CLOUD_NOT_ALLOWED",
    "QUOTA_EXCEEDED",
}

# Providers Account Again treats as local (no network egress, no credential needed).
# Mirrors Local AI Control Center's own provider classification (DEFAULT_PROVIDERS in
# src/lib/providers/types.ts) but is independently authoritative here — Account Again
# must decide cloud/local policy itself, not trust the caller's self-declared type.
LOCAL_PROVIDER_IDS = {"ollama"}


@dataclass
class EntitlementRequest:
    """Input to the entitlement decision engine."""
    tenant_id: Optional[str] = None
    account_id: Optional[str] = None
    subject_id: Optional[str] = None
    service_system_id: Optional[str] = None
    product_id: Optional[str] = None
    capability: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class EntitlementDecision:
    """Output of the entitlement decision engine."""
    decision: str  # ALLOW or DENY
    reason_code: str
    entitlement_decision_id: str = ""
    reason_message: str = ""
    account_id: Optional[str] = None
    tenant_id: Optional[str] = None
    capability: Optional[str] = None
    provider_constraints: dict = field(default_factory=dict)
    model_constraints: dict = field(default_factory=dict)
    local_only: bool = False
    cloud_allowed: bool = True
    quota_remaining: Optional[int] = None
    policy_version: str = "2.0.0"
    evaluated_at: Optional[str] = None
    evidence_ref: Optional[str] = None


def evaluate_entitlement(db: Session, request: EntitlementRequest) -> EntitlementDecision:
    """Evaluate whether a subject/service is entitled to the requested action.

    Checks (in order):
    1. Tenant status
    2. Account status (if human subject)
    3. Service identity status (if service)
    4. Product entitlement
    5. AI capability entitlement
    6. Provider/model constraints
    6.5. Cloud/local policy (E4.1)
    7. Quota/budget limits

    Every decision — ALLOW or DENY — carries a unique entitlement_decision_id (E4.1 §5)
    and a reason_code drawn exclusively from REASON_CODES (E4.1 §6, enforced by
    tests/test_e4_1_reason_codes_canonical.py).
    """
    from account_again.models.tenant import _now

    decision_id = _new_id()
    evaluated_at = _now()

    def deny(reason_code: str, reason_message: str, **kw) -> EntitlementDecision:
        assert reason_code in REASON_CODES, f"reason_code {reason_code} not in canonical REASON_CODES"
        return EntitlementDecision(
            decision="DENY", reason_code=reason_code, reason_message=reason_message,
            entitlement_decision_id=decision_id, evaluated_at=evaluated_at, **kw,
        )

    # ── 1. Tenant check ──
    tenant_id = request.tenant_id
    if tenant_id:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            return deny("TENANT_NOT_FOUND", f"Tenant {tenant_id} not found", tenant_id=tenant_id)
        if tenant.status == "SUSPENDED":
            return deny("TENANT_SUSPENDED", f"Tenant {tenant_id} is suspended", tenant_id=tenant_id)
        if tenant.status == "DISABLED":
            return deny("TENANT_DISABLED", f"Tenant {tenant_id} is disabled", tenant_id=tenant_id)

    # ── 2. Human subject check ──
    account_id = request.account_id
    if request.subject_id:
        identity = db.query(SubjectIdentity).filter(
            SubjectIdentity.subject_id == request.subject_id
        ).first()
        if not identity:
            return deny("SUBJECT_NOT_FOUND", f"Subject {request.subject_id} not found", tenant_id=tenant_id)
        if identity.status != "ACTIVE":
            return deny("SUBJECT_DISABLED", f"Subject {request.subject_id} is {identity.status}",
                         tenant_id=tenant_id, account_id=identity.account_id)
        account_id = identity.account_id
        tenant_id = identity.tenant_id
        # Tenant scoping: subject must belong to the requested tenant
        if request.tenant_id and identity.tenant_id != request.tenant_id:
            return deny("TENANT_MISMATCH", "Subject does not belong to requested tenant",
                         tenant_id=request.tenant_id, account_id=account_id)

    if account_id:
        account = db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            return deny("ACCOUNT_NOT_FOUND", f"Account {account_id} not found", tenant_id=tenant_id)
        if account.status == "DISABLED":
            return deny("ACCOUNT_DISABLED", f"Account {account_id} is disabled",
                         tenant_id=tenant_id, account_id=account_id)
        tenant_id = account.tenant_id

    # ── 3. Service identity check ──
    if request.service_system_id:
        svc = db.query(ServiceIdentity).filter(
            ServiceIdentity.system_id == request.service_system_id
        ).first()
        if not svc:
            return deny("SERVICE_IDENTITY_NOT_FOUND",
                         f"Service identity {request.service_system_id} not found", tenant_id=tenant_id)
        if svc.status == "REVOKED":
            return deny("REVOKED_SERVICE_IDENTITY",
                         f"Service identity {request.service_system_id} is revoked", tenant_id=tenant_id)
        # Service identity, once bound to a tenant, may not act for a different tenant.
        if svc.tenant_id and request.tenant_id and svc.tenant_id != request.tenant_id:
            return deny("TENANT_MISMATCH", "Service identity does not belong to requested tenant",
                         tenant_id=request.tenant_id)

    # ── 4. Product entitlement check ──
    if request.product_id and tenant_id:
        pe = db.query(ProductEntitlement).filter(
            ProductEntitlement.tenant_id == tenant_id,
            ProductEntitlement.product_id == request.product_id,
            ProductEntitlement.status == "ACTIVE",
        ).first()
        if not pe:
            return deny("PRODUCT_NOT_ENTITLED",
                         f"Tenant {tenant_id} is not entitled to product {request.product_id}",
                         tenant_id=tenant_id, account_id=account_id)

    # ── 5. AI capability entitlement check ──
    provider_constraints = {}
    model_constraints = {}
    local_only = False
    cloud_allowed = True

    if request.capability and tenant_id:
        ae = db.query(AIEntitlement).filter(
            AIEntitlement.tenant_id == tenant_id,
            AIEntitlement.capability == request.capability,
            AIEntitlement.status == "ACTIVE",
        ).first()
        if not ae:
            return deny("CAPABILITY_NOT_ENTITLED",
                         f"Tenant {tenant_id} is not entitled to AI capability {request.capability}",
                         tenant_id=tenant_id, account_id=account_id, capability=request.capability)
        if ae.provider_constraint:
            provider_constraints["allowed"] = [ae.provider_constraint]
        if ae.model_constraint:
            model_constraints["allowed"] = [ae.model_constraint]
        local_only = ae.local_only
        cloud_allowed = ae.cloud_allowed

    # ── 6. Provider constraint check ──
    if request.provider and provider_constraints.get("allowed"):
        if request.provider not in provider_constraints["allowed"]:
            return deny("PROVIDER_NOT_ALLOWED",
                         f"Provider {request.provider} is not allowed for capability {request.capability}",
                         tenant_id=tenant_id, account_id=account_id, capability=request.capability,
                         provider_constraints=provider_constraints)

    # ── 7. Model constraint check ──
    if request.model and model_constraints.get("allowed"):
        if request.model not in model_constraints["allowed"]:
            return deny("MODEL_NOT_ALLOWED",
                         f"Model {request.model} is not allowed for capability {request.capability}",
                         tenant_id=tenant_id, account_id=account_id, capability=request.capability,
                         model_constraints=model_constraints)

    # ── 6.5. Cloud/local policy check (E4.1) ──
    # Account Again decides local/cloud classification independently — it does not trust
    # the caller's own labeling. A provider not in LOCAL_PROVIDER_IDS is treated as cloud.
    if request.provider and request.capability:
        is_cloud_provider = request.provider not in LOCAL_PROVIDER_IDS
        if is_cloud_provider and (local_only or not cloud_allowed):
            return deny("CLOUD_NOT_ALLOWED",
                         f"Capability {request.capability} does not permit cloud provider "
                         f"{request.provider} (localOnly={local_only}, cloudAllowed={cloud_allowed})",
                         tenant_id=tenant_id, account_id=account_id, capability=request.capability,
                         local_only=local_only, cloud_allowed=cloud_allowed)

    # ── 8. Quota check ──
    if tenant_id:
        policies = db.query(QuotaPolicy).filter(
            QuotaPolicy.tenant_id == tenant_id,
            QuotaPolicy.status == "ACTIVE",
        ).all()
        for policy in policies:
            if policy.tokens_per_day:
                # Check recent daily usage
                from datetime import datetime, timezone, timedelta
                since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
                daily = db.query(UsageRecord).filter(
                    UsageRecord.tenant_id == tenant_id,
                    UsageRecord.recorded_at >= since,
                ).all()
                daily_tokens = sum((r.total_tokens or 0) for r in daily)
                if daily_tokens >= policy.tokens_per_day:
                    return deny("QUOTA_EXCEEDED",
                                 f"Daily token quota ({policy.tokens_per_day}) exceeded: {daily_tokens}",
                                 tenant_id=tenant_id, account_id=account_id, quota_remaining=0)

    # ── ALLOW ──
    return EntitlementDecision(
        decision="ALLOW",
        reason_code="ENTITLED",
        entitlement_decision_id=decision_id,
        reason_message="All entitlement checks passed",
        account_id=account_id,
        tenant_id=tenant_id,
        capability=request.capability,
        provider_constraints=provider_constraints,
        model_constraints=model_constraints,
        local_only=local_only,
        cloud_allowed=cloud_allowed,
        evaluated_at=evaluated_at,
    )
