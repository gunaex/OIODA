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
    reason_message: str = ""
    account_id: Optional[str] = None
    tenant_id: Optional[str] = None
    capability: Optional[str] = None
    provider_constraints: dict = field(default_factory=dict)
    model_constraints: dict = field(default_factory=dict)
    local_only: bool = False
    quota_remaining: Optional[int] = None
    policy_version: str = "1.0.0"
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
    7. Quota/budget limits
    """
    from account_again.models.tenant import _now

    # ── 1. Tenant check ──
    tenant_id = request.tenant_id
    if tenant_id:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            return EntitlementDecision(
                decision="DENY", reason_code="TENANT_NOT_FOUND",
                reason_message=f"Tenant {tenant_id} not found",
                tenant_id=tenant_id, evaluated_at=_now(),
            )
        if tenant.status == "SUSPENDED":
            return EntitlementDecision(
                decision="DENY", reason_code="TENANT_SUSPENDED",
                reason_message=f"Tenant {tenant_id} is suspended",
                tenant_id=tenant_id, evaluated_at=_now(),
            )
        if tenant.status == "DISABLED":
            return EntitlementDecision(
                decision="DENY", reason_code="TENANT_DISABLED",
                reason_message=f"Tenant {tenant_id} is disabled",
                tenant_id=tenant_id, evaluated_at=_now(),
            )

    # ── 2. Human subject check ──
    account_id = request.account_id
    if request.subject_id:
        identity = db.query(SubjectIdentity).filter(
            SubjectIdentity.subject_id == request.subject_id
        ).first()
        if not identity:
            return EntitlementDecision(
                decision="DENY", reason_code="SUBJECT_NOT_FOUND",
                reason_message=f"Subject {request.subject_id} not found",
                tenant_id=tenant_id, evaluated_at=_now(),
            )
        if identity.status != "ACTIVE":
            return EntitlementDecision(
                decision="DENY", reason_code="SUBJECT_DISABLED",
                reason_message=f"Subject {request.subject_id} is {identity.status}",
                tenant_id=tenant_id, account_id=identity.account_id, evaluated_at=_now(),
            )
        account_id = identity.account_id
        tenant_id = identity.tenant_id
        # Tenant scoping: subject must belong to the requested tenant
        if request.tenant_id and identity.tenant_id != request.tenant_id:
            return EntitlementDecision(
                decision="DENY", reason_code="TENANT_MISMATCH",
                reason_message="Subject does not belong to requested tenant",
                tenant_id=request.tenant_id, account_id=account_id, evaluated_at=_now(),
            )

    if account_id:
        account = db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            return EntitlementDecision(
                decision="DENY", reason_code="ACCOUNT_NOT_FOUND",
                reason_message=f"Account {account_id} not found",
                tenant_id=tenant_id, evaluated_at=_now(),
            )
        if account.status == "DISABLED":
            return EntitlementDecision(
                decision="DENY", reason_code="ACCOUNT_DISABLED",
                reason_message=f"Account {account_id} is disabled",
                tenant_id=tenant_id, account_id=account_id, evaluated_at=_now(),
            )
        tenant_id = account.tenant_id

    # ── 3. Service identity check ──
    if request.service_system_id:
        svc = db.query(ServiceIdentity).filter(
            ServiceIdentity.system_id == request.service_system_id
        ).first()
        if not svc:
            return EntitlementDecision(
                decision="DENY", reason_code="SERVICE_IDENTITY_NOT_FOUND",
                reason_message=f"Service identity {request.service_system_id} not found",
                tenant_id=tenant_id, evaluated_at=_now(),
            )
        if svc.status == "REVOKED":
            return EntitlementDecision(
                decision="DENY", reason_code="REVOKED_SERVICE_IDENTITY",
                reason_message=f"Service identity {request.service_system_id} is revoked",
                tenant_id=tenant_id, evaluated_at=_now(),
            )

    # ── 4. Product entitlement check ──
    if request.product_id and tenant_id:
        pe = db.query(ProductEntitlement).filter(
            ProductEntitlement.tenant_id == tenant_id,
            ProductEntitlement.product_id == request.product_id,
            ProductEntitlement.status == "ACTIVE",
        ).first()
        if not pe:
            return EntitlementDecision(
                decision="DENY", reason_code="PRODUCT_NOT_ENTITLED",
                reason_message=f"Tenant {tenant_id} is not entitled to product {request.product_id}",
                tenant_id=tenant_id, account_id=account_id, evaluated_at=_now(),
            )

    # ── 5. AI capability entitlement check ──
    provider_constraints = {}
    model_constraints = {}
    local_only = False

    if request.capability and tenant_id:
        ae = db.query(AIEntitlement).filter(
            AIEntitlement.tenant_id == tenant_id,
            AIEntitlement.capability == request.capability,
            AIEntitlement.status == "ACTIVE",
        ).first()
        if not ae:
            return EntitlementDecision(
                decision="DENY", reason_code="CAPABILITY_NOT_ENTITLED",
                reason_message=f"Tenant {tenant_id} is not entitled to AI capability {request.capability}",
                tenant_id=tenant_id, account_id=account_id,
                capability=request.capability, evaluated_at=_now(),
            )
        if ae.provider_constraint:
            provider_constraints["allowed"] = [ae.provider_constraint]
        if ae.model_constraint:
            model_constraints["allowed"] = [ae.model_constraint]
        local_only = ae.local_only

    # ── 6. Provider constraint check ──
    if request.provider and provider_constraints.get("allowed"):
        if request.provider not in provider_constraints["allowed"]:
            return EntitlementDecision(
                decision="DENY", reason_code="PROVIDER_NOT_ALLOWED",
                reason_message=f"Provider {request.provider} is not allowed for capability {request.capability}",
                tenant_id=tenant_id, account_id=account_id,
                capability=request.capability, provider_constraints=provider_constraints,
                evaluated_at=_now(),
            )

    # ── 7. Model constraint check ──
    if request.model and model_constraints.get("allowed"):
        if request.model not in model_constraints["allowed"]:
            return EntitlementDecision(
                decision="DENY", reason_code="MODEL_NOT_ALLOWED",
                reason_message=f"Model {request.model} is not allowed for capability {request.capability}",
                tenant_id=tenant_id, account_id=account_id,
                capability=request.capability, model_constraints=model_constraints,
                evaluated_at=_now(),
            )

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
                    return EntitlementDecision(
                        decision="DENY", reason_code="QUOTA_EXCEEDED",
                        reason_message=f"Daily token quota ({policy.tokens_per_day}) exceeded: {daily_tokens}",
                        tenant_id=tenant_id, account_id=account_id,
                        quota_remaining=0, evaluated_at=_now(),
                    )

    # ── ALLOW ──
    return EntitlementDecision(
        decision="ALLOW",
        reason_code="ENTITLED",
        reason_message="All entitlement checks passed",
        account_id=account_id,
        tenant_id=tenant_id,
        capability=request.capability,
        provider_constraints=provider_constraints,
        model_constraints=model_constraints,
        local_only=local_only,
        evaluated_at=_now(),
    )
