"""Account Again — API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from account_again.database import get_db, create_all
from account_again.models import (
    Tenant, Account, SubjectIdentity, Role, Permission, RolePermission,
    AccountRole, ProductEntitlement, AIEntitlement, CredentialReference,
    FORBIDDEN_CREDENTIAL_FIELDS, ServiceIdentity, VALID_SYSTEM_IDS,
    SessionRecord, QuotaPolicy, UsageRecord, AuditRecord, IdempotencyRecord,
)
from account_again.models.tenant import _new_id, _now
from account_again.api.schemas import (
    TenantCreate, TenantUpdate, AccountCreate, AccountUpdate,
    SubjectIdentityCreate, RoleCreate, PermissionCreate,
    AccountRoleAssign, RolePermissionAssign,
    ProductEntitlementCreate, ProductEntitlementUpdate,
    AIEntitlementCreate, AIEntitlementUpdate,
    CredentialRefCreate, CredentialRefRotate, CredentialResolveRequest,
    ServiceIdentityCreate, SessionCreate,
    EntitlementEvaluateRequest,
    QuotaPolicyCreate, UsageRecordCreate,
)
from account_again.services import (
    EntitlementRequest, evaluate_entitlement,
    write_audit, check_idempotent, record_idempotent,
    secret_resolver,
)
from passlib.hash import bcrypt as passlib_bcrypt
try:
    import bcrypt as _bcrypt_lib
    def _hash_password(pw: str) -> str:
        return _bcrypt_lib.hashpw(pw.encode(), _bcrypt_lib.gensalt()).decode()
except Exception:
    def _hash_password(pw: str) -> str:
        return passlib_bcrypt.hash(pw)

router = APIRouter()


# ── Health ──
@router.get("/health")
def health():
    return {"status": "OK", "service": "account-again", "version": "1.0.0"}


# ── Tenants ──
@router.post("/tenants")
def create_tenant(body: TenantCreate, db: Session = Depends(get_db)):
    t = Tenant(tenant_id=body.tenantId or _new_id(), name=body.name)
    db.add(t)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="TENANT_CREATE",
                target_type="Tenant", target_id=t.tenant_id, result="SUCCESS",
                tenant_id=t.tenant_id)
    db.commit()
    return t.to_dict()


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db)):
    return [t.to_dict() for t in db.query(Tenant).all()]


@router.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    return t.to_dict()


@router.patch("/tenants/{tenant_id}")
def update_tenant(tenant_id: str, body: TenantUpdate, db: Session = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not t:
        raise HTTPException(404, "Tenant not found")
    if body.name is not None:
        t.name = body.name
    if body.status is not None:
        t.status = body.status
    t.updated_at = _now()
    db.commit()
    return t.to_dict()


# ── Accounts ──
@router.post("/accounts")
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    existing = db.query(Account).filter(Account.email == body.email).first()
    if existing:
        raise HTTPException(409, "Account with this email already exists")
    a = Account(
        account_id=body.accountId or _new_id(),
        tenant_id=body.tenantId,
        email=body.email,
        display_name=body.displayName,
    )
    db.add(a)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="ACCOUNT_CREATE",
                target_type="Account", target_id=a.account_id, result="SUCCESS",
                tenant_id=a.tenant_id)
    db.commit()
    return a.to_dict()


@router.get("/accounts")
def list_accounts(tenantId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Account)
    if tenantId:
        q = q.filter(Account.tenant_id == tenantId)
    return [a.to_dict() for a in q.all()]


@router.get("/accounts/{account_id}")
def get_account(account_id: str, db: Session = Depends(get_db)):
    a = db.query(Account).filter(Account.account_id == account_id).first()
    if not a:
        raise HTTPException(404, "Account not found")
    return a.to_dict()


@router.patch("/accounts/{account_id}")
def update_account(account_id: str, body: AccountUpdate, db: Session = Depends(get_db)):
    a = db.query(Account).filter(Account.account_id == account_id).first()
    if not a:
        raise HTTPException(404, "Account not found")
    if body.displayName is not None:
        a.display_name = body.displayName
    if body.status is not None:
        a.status = body.status
    a.updated_at = _now()
    db.commit()
    return a.to_dict()


# ── Subject Identities ──
@router.post("/identities")
def create_identity(body: SubjectIdentityCreate, db: Session = Depends(get_db)):
    password_hash = None
    if body.authMethod == "PASSWORD" and body.password:
        password_hash = _hash_password(body.password)
    ident = SubjectIdentity(
        subject_id=_new_id(),
        account_id=body.accountId,
        tenant_id=body.tenantId,
        identity_provider=body.identityProvider,
        auth_method=body.authMethod,
        password_hash=password_hash,
        provider_subject=body.providerSubject,
    )
    db.add(ident)
    db.commit()
    return ident.to_dict()


@router.get("/identities")
def list_identities(accountId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(SubjectIdentity)
    if accountId:
        q = q.filter(SubjectIdentity.account_id == accountId)
    return [i.to_dict() for i in q.all()]


# ── Roles ──
@router.post("/roles")
def create_role(body: RoleCreate, db: Session = Depends(get_db)):
    r = Role(role_id=_new_id(), name=body.name, description=body.description)
    db.add(r)
    db.commit()
    return r.to_dict()


@router.get("/roles")
def list_roles(db: Session = Depends(get_db)):
    return [r.to_dict() for r in db.query(Role).all()]


# ── Permissions ──
@router.post("/permissions")
def create_permission(body: PermissionCreate, db: Session = Depends(get_db)):
    p = Permission(permission_id=_new_id(), name=body.name, description=body.description)
    db.add(p)
    db.commit()
    return p.to_dict()


@router.get("/permissions")
def list_permissions(db: Session = Depends(get_db)):
    return [p.to_dict() for p in db.query(Permission).all()]


# ── Account Roles ──
@router.post("/account-roles")
def assign_account_role(body: AccountRoleAssign, db: Session = Depends(get_db)):
    ar = AccountRole(
        id=_new_id(),
        account_id=body.accountId,
        role_id=body.roleId,
        tenant_id=body.tenantId,
    )
    db.add(ar)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="ROLE_ASSIGN",
                target_type="AccountRole", target_id=ar.id, result="SUCCESS",
                tenant_id=body.tenantId)
    db.commit()
    return ar.to_dict()


# ── Role Permissions ──
@router.post("/role-permissions")
def assign_role_permission(body: RolePermissionAssign, db: Session = Depends(get_db)):
    rp = RolePermission(id=_new_id(), role_id=body.roleId, permission_id=body.permissionId)
    db.add(rp)
    db.commit()
    return {"id": rp.id, "roleId": rp.role_id, "permissionId": rp.permission_id}


# ── Product Entitlements ──
@router.post("/product-entitlements")
def create_product_entitlement(body: ProductEntitlementCreate, db: Session = Depends(get_db)):
    pe = ProductEntitlement(
        entitlement_id=_new_id(),
        tenant_id=body.tenantId,
        account_id=body.accountId,
        subject_id=body.subjectId,
        product_id=body.productId,
        valid_from=body.validFrom,
        valid_until=body.validUntil,
    )
    db.add(pe)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="PRODUCT_ENTITLEMENT_GRANT",
                target_type="ProductEntitlement", target_id=pe.entitlement_id,
                result="SUCCESS", tenant_id=body.tenantId)
    db.commit()
    return pe.to_dict()


@router.get("/product-entitlements")
def list_product_entitlements(tenantId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(ProductEntitlement)
    if tenantId:
        q = q.filter(ProductEntitlement.tenant_id == tenantId)
    return [pe.to_dict() for pe in q.all()]


@router.patch("/product-entitlements/{entitlement_id}")
def update_product_entitlement(entitlement_id: str, body: ProductEntitlementUpdate, db: Session = Depends(get_db)):
    pe = db.query(ProductEntitlement).filter(ProductEntitlement.entitlement_id == entitlement_id).first()
    if not pe:
        raise HTTPException(404, "Product entitlement not found")
    if body.status is not None:
        pe.status = body.status
    pe.updated_at = _now()
    db.commit()
    return pe.to_dict()


# ── AI Entitlements ──
@router.post("/ai-entitlements")
def create_ai_entitlement(body: AIEntitlementCreate, db: Session = Depends(get_db)):
    ae = AIEntitlement(
        entitlement_id=_new_id(),
        tenant_id=body.tenantId,
        account_id=body.accountId,
        capability=body.capability,
        provider_constraint=body.providerConstraint,
        model_constraint=body.modelConstraint,
        local_only=body.localOnly,
        cloud_allowed=body.cloudAllowed,
        max_cost_cents=body.maxCostCents,
        max_tokens=body.maxTokens,
    )
    db.add(ae)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="AI_ENTITLEMENT_GRANT",
                target_type="AIEntitlement", target_id=ae.entitlement_id,
                result="SUCCESS", tenant_id=body.tenantId)
    db.commit()
    return ae.to_dict()


@router.get("/ai-entitlements")
def list_ai_entitlements(tenantId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(AIEntitlement)
    if tenantId:
        q = q.filter(AIEntitlement.tenant_id == tenantId)
    return [ae.to_dict() for ae in q.all()]


@router.patch("/ai-entitlements/{entitlement_id}")
def update_ai_entitlement(entitlement_id: str, body: AIEntitlementUpdate, db: Session = Depends(get_db)):
    ae = db.query(AIEntitlement).filter(AIEntitlement.entitlement_id == entitlement_id).first()
    if not ae:
        raise HTTPException(404, "AI entitlement not found")
    if body.status is not None:
        ae.status = body.status
    ae.updated_at = _now()
    db.commit()
    return ae.to_dict()


# ── Credential References ──
@router.post("/credential-refs")
def create_credential_ref(body: CredentialRefCreate, db: Session = Depends(get_db)):
    # Security check: validate body has no raw secret fields
    body_dict = body.model_dump()
    for forbidden_field in FORBIDDEN_CREDENTIAL_FIELDS:
        if forbidden_field in body_dict and body_dict[forbidden_field]:
            raise HTTPException(400, f"CredentialReference must not contain raw secret field: {forbidden_field}")

    cr = CredentialReference(
        credential_ref=_new_id(),
        tenant_id=body.tenantId,
        owner_account_id=body.ownerAccountId,
        provider=body.provider,
        credential_type=body.credentialType,
        secret_store_type=body.secretStoreType,
        secret_store_reference=body.secretStoreReference,
        expires_at=body.expiresAt,
    )
    db.add(cr)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="CREDENTIAL_REF_CREATE",
                target_type="CredentialReference", target_id=cr.credential_ref,
                result="SUCCESS", tenant_id=body.tenantId)
    db.commit()
    return cr.to_dict()


@router.get("/credential-refs")
def list_credential_refs(tenantId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(CredentialReference)
    if tenantId:
        q = q.filter(CredentialReference.tenant_id == tenantId)
    return [cr.to_dict() for cr in q.all()]


@router.get("/credential-refs/{credential_ref}")
def get_credential_ref(credential_ref: str, db: Session = Depends(get_db)):
    cr = db.query(CredentialReference).filter(CredentialReference.credential_ref == credential_ref).first()
    if not cr:
        raise HTTPException(404, "Credential reference not found")
    # NEVER return raw secret — only metadata
    return cr.to_dict()


@router.post("/credential-refs/{credential_ref}/rotate")
def rotate_credential_ref(credential_ref: str, body: CredentialRefRotate, db: Session = Depends(get_db)):
    cr = db.query(CredentialReference).filter(CredentialReference.credential_ref == credential_ref).first()
    if not cr:
        raise HTTPException(404, "Credential reference not found")
    cr.rotated_at = _now()
    if body.secretStoreReference:
        cr.secret_store_reference = body.secretStoreReference
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="CREDENTIAL_REF_ROTATE",
                target_type="CredentialReference", target_id=cr.credential_ref,
                result="SUCCESS", tenant_id=cr.tenant_id)
    db.commit()
    return cr.to_dict()


@router.post("/credential-refs/{credential_ref}/revoke")
def revoke_credential_ref(credential_ref: str, db: Session = Depends(get_db)):
    cr = db.query(CredentialReference).filter(CredentialReference.credential_ref == credential_ref).first()
    if not cr:
        raise HTTPException(404, "Credential reference not found")
    cr.status = "REVOKED"
    cr.revoked_at = _now()
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="CREDENTIAL_REF_REVOKE",
                target_type="CredentialReference", target_id=cr.credential_ref,
                result="SUCCESS", tenant_id=cr.tenant_id)
    db.commit()
    return cr.to_dict()


# ── Credential Resolution Boundary ──
# Controlled runtime-secret handoff. This is the ONLY endpoint that may return a raw
# secret value, and only transiently: never persisted here, never written to audit
# metadata, never included in any other response. Callers (e.g. Local AI Control Center)
# must use the value immediately and must not persist it either.
@router.post("/credential-refs/{credential_ref}/resolve")
def resolve_credential_ref(credential_ref: str, body: CredentialResolveRequest, db: Session = Depends(get_db)):
    cr = db.query(CredentialReference).filter(CredentialReference.credential_ref == credential_ref).first()
    if not cr:
        raise HTTPException(404, "Credential reference not found")

    if cr.tenant_id != body.tenantId:
        write_audit(db, actor_type="SERVICE", actor_id=body.serviceSystemId or "unknown",
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_TENANT_MISMATCH", tenant_id=body.tenantId,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Credential reference does not belong to the requesting tenant")

    if cr.status == "REVOKED":
        write_audit(db, actor_type="SERVICE", actor_id=body.serviceSystemId or "unknown",
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_REVOKED", tenant_id=cr.tenant_id,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Credential reference is revoked")

    if cr.expires_at and cr.expires_at < _now():
        write_audit(db, actor_type="SERVICE", actor_id=body.serviceSystemId or "unknown",
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_EXPIRED", tenant_id=cr.tenant_id,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Credential reference has expired")

    if body.serviceSystemId:
        svc = db.query(ServiceIdentity).filter(ServiceIdentity.system_id == body.serviceSystemId).first()
        if not svc or svc.status == "REVOKED":
            write_audit(db, actor_type="SERVICE", actor_id=body.serviceSystemId,
                        action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                        target_id=credential_ref, result="DENY_SERVICE_IDENTITY", tenant_id=cr.tenant_id,
                        correlation_id=body.correlationId)
            db.commit()
            raise HTTPException(403, "Requesting service identity is not active")

    secret = secret_resolver.resolve(credential_ref, cr.provider, body.purpose)

    if secret is None:
        write_audit(db, actor_type="SERVICE", actor_id=body.serviceSystemId or "unknown",
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_UNRESOLVABLE", tenant_id=cr.tenant_id,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(424, "Credential reference could not be resolved to a secret value")

    # Audit records the fact of resolution — never the secret value itself.
    write_audit(db, actor_type="SERVICE", actor_id=body.serviceSystemId or "unknown",
                action="CREDENTIAL_RESOLVE", target_type="CredentialReference",
                target_id=credential_ref, result="SUCCESS", tenant_id=cr.tenant_id,
                correlation_id=body.correlationId)
    db.commit()

    return {
        "credentialRef": credential_ref,
        "provider": cr.provider,
        "secret": secret,
        "resolvedAt": _now(),
    }


# ── Service Identities ──
@router.post("/service-identities")
def create_service_identity(body: ServiceIdentityCreate, db: Session = Depends(get_db)):
    if body.systemId not in VALID_SYSTEM_IDS:
        raise HTTPException(400, f"Invalid systemId. Must be one of: {sorted(VALID_SYSTEM_IDS)}")
    existing = db.query(ServiceIdentity).filter(ServiceIdentity.system_id == body.systemId).first()
    if existing:
        raise HTTPException(409, f"Service identity for {body.systemId} already exists")
    svc = ServiceIdentity(
        service_identity_id=_new_id(),
        system_id=body.systemId,
        tenant_id=body.tenantId,
        allowed_capabilities=body.allowedCapabilities,
    )
    db.add(svc)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="SERVICE_IDENTITY_CREATE",
                target_type="ServiceIdentity", target_id=svc.service_identity_id,
                result="SUCCESS")
    db.commit()
    return svc.to_dict()


@router.get("/service-identities")
def list_service_identities(db: Session = Depends(get_db)):
    return [s.to_dict() for s in db.query(ServiceIdentity).all()]


@router.post("/service-identities/{service_identity_id}/revoke")
def revoke_service_identity(service_identity_id: str, db: Session = Depends(get_db)):
    svc = db.query(ServiceIdentity).filter(ServiceIdentity.service_identity_id == service_identity_id).first()
    if not svc:
        raise HTTPException(404, "Service identity not found")
    svc.status = "REVOKED"
    svc.revoked_at = _now()
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="SERVICE_IDENTITY_REVOKE",
                target_type="ServiceIdentity", target_id=svc.service_identity_id,
                result="SUCCESS")
    db.commit()
    return svc.to_dict()


# ── Sessions ──
@router.post("/sessions")
def create_session(body: SessionCreate, db: Session = Depends(get_db)):
    s = SessionRecord(
        session_id=_new_id(),
        subject_id=body.subjectId,
        tenant_id=body.tenantId,
        expires_at=body.expiresAt,
    )
    db.add(s)
    db.commit()
    return s.to_dict()


@router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: str, db: Session = Depends(get_db)):
    s = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
    if not s:
        raise HTTPException(404, "Session not found")
    s.status = "REVOKED"
    s.revoked_at = _now()
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="SESSION_REVOKE",
                target_type="SessionRecord", target_id=s.session_id,
                result="SUCCESS", tenant_id=s.tenant_id)
    db.commit()
    return s.to_dict()


# ── Entitlement Evaluation ──
@router.post("/entitlements/evaluate")
def evaluate(body: EntitlementEvaluateRequest, db: Session = Depends(get_db)):
    # Idempotency check
    if body.idempotencyKey:
        existing = check_idempotent(db, body.idempotencyKey)
        if existing:
            return {"decision": "DUPLICATE", "idempotentResult": existing}

    req = EntitlementRequest(
        tenant_id=body.tenantId,
        account_id=body.accountId,
        subject_id=body.subjectId,
        service_system_id=body.serviceSystemId,
        product_id=body.productId,
        capability=body.capability,
        provider=body.provider,
        model=body.model,
        correlation_id=body.correlationId,
    )
    decision = evaluate_entitlement(db, req)

    result_dict = {
        "decision": decision.decision,
        "reasonCode": decision.reason_code,
        "reasonMessage": decision.reason_message,
        "accountId": decision.account_id,
        "tenantId": decision.tenant_id,
        "capability": decision.capability,
        "providerConstraints": decision.provider_constraints,
        "modelConstraints": decision.model_constraints,
        "localOnly": decision.local_only,
        "quotaRemaining": decision.quota_remaining,
        "policyVersion": decision.policy_version,
        "evaluatedAt": decision.evaluated_at,
        "evidenceRef": decision.evidence_ref,
    }

    # Record idempotency
    if body.idempotencyKey:
        record_idempotent(db, body.idempotencyKey, result_dict)

    # Audit
    write_audit(db, actor_type="SYSTEM", actor_id="entitlement-engine",
                action="ENTITLEMENT_EVALUATION",
                target_type="EntitlementDecision", target_id=decision.reason_code,
                result=decision.decision, tenant_id=decision.tenant_id,
                correlation_id=body.correlationId)
    db.commit()
    return result_dict


# ── Quota Policies ──
@router.post("/quotas")
def create_quota_policy(body: QuotaPolicyCreate, db: Session = Depends(get_db)):
    qp = QuotaPolicy(
        policy_id=_new_id(),
        tenant_id=body.tenantId,
        scope=body.scope,
        scope_id=body.scopeId,
        requests_per_day=body.requestsPerDay,
        tokens_per_day=body.tokensPerDay,
        tokens_per_month=body.tokensPerMonth,
        cost_cents_per_month=body.costCentsPerMonth,
    )
    db.add(qp)
    db.commit()
    return qp.to_dict()


@router.get("/quotas")
def list_quota_policies(tenantId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(QuotaPolicy)
    if tenantId:
        q = q.filter(QuotaPolicy.tenant_id == tenantId)
    return [qp.to_dict() for qp in q.all()]


# ── Usage ──
@router.post("/usage")
def record_usage(body: UsageRecordCreate, db: Session = Depends(get_db)):
    if body.idempotencyKey:
        existing = check_idempotent(db, body.idempotencyKey)
        if existing:
            return {"status": "DUPLICATE", "idempotentResult": existing}

    ur = UsageRecord(
        record_id=_new_id(),
        tenant_id=body.tenantId,
        account_id=body.accountId,
        capability=body.capability,
        provider=body.provider,
        model=body.model,
        prompt_tokens=body.promptTokens,
        completion_tokens=body.completionTokens,
        total_tokens=body.totalTokens,
        cost_cents=body.costCents,
        correlation_id=body.correlationId,
    )
    db.add(ur)
    if body.idempotencyKey:
        record_idempotent(db, body.idempotencyKey, ur.to_dict())
    db.commit()
    return ur.to_dict()


@router.get("/usage")
def list_usage(tenantId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(UsageRecord)
    if tenantId:
        q = q.filter(UsageRecord.tenant_id == tenantId)
    return [u.to_dict() for u in q.order_by(UsageRecord.recorded_at.desc()).limit(100).all()]


# ── Audit ──
@router.get("/audit")
def list_audit(tenantId: Optional[str] = Query(None), limit: int = Query(100), db: Session = Depends(get_db)):
    q = db.query(AuditRecord)
    if tenantId:
        q = q.filter(AuditRecord.tenant_id == tenantId)
    return [a.to_dict() for a in q.order_by(AuditRecord.created_at.desc()).limit(limit).all()]
