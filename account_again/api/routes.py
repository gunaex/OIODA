"""Account Again — API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
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
    ServiceTokenRequest, ServiceSecretRotateRequest,
)
from account_again.services import (
    EntitlementRequest, evaluate_entitlement,
    write_audit, check_idempotent, record_idempotent,
    secret_resolver,
)
from account_again.services import service_auth
from account_again.services.service_auth import ServiceTokenError
import secrets as _secrets
from passlib.hash import bcrypt as passlib_bcrypt
try:
    import bcrypt as _bcrypt_lib
    def _hash_password(pw: str) -> str:
        return _bcrypt_lib.hashpw(pw.encode(), _bcrypt_lib.gensalt()).decode()
    def _verify_password(pw: str, hashed: str) -> bool:
        return _bcrypt_lib.checkpw(pw.encode(), hashed.encode())
except Exception:
    def _hash_password(pw: str) -> str:
        return passlib_bcrypt.hash(pw)
    def _verify_password(pw: str, hashed: str) -> bool:
        return passlib_bcrypt.verify(pw, hashed)

router = APIRouter()


# ── E5.1 Service Auth Dependencies ──
# LOCAL_OIDC_COMPATIBLE_SERVICE_AUTH: verifies a Bearer JWT (RS256, issued by
# POST /auth/service-token) and re-checks the ServiceIdentity's live DB status on every
# call — token validity alone is never sufficient (E5.1 §10).

class VerifiedServiceCaller:
    def __init__(self, system_id: str, service_identity_id: str, tenant_id: Optional[str]):
        self.system_id = system_id
        self.service_identity_id = service_identity_id
        self.tenant_id = tenant_id


def _load_and_check_service_identity(db: Session, claims: dict) -> VerifiedServiceCaller:
    svc = db.query(ServiceIdentity).filter(
        ServiceIdentity.service_identity_id == claims["serviceIdentityId"]
    ).first()
    if not svc:
        raise HTTPException(401, "Service identity referenced by token no longer exists")
    if svc.status == "REVOKED":
        raise HTTPException(403, f"Service identity {svc.system_id} has been revoked since token issuance")
    if svc.system_id != claims["systemId"]:
        # Token claim and current DB record disagree — treat as invalid rather than
        # trusting either blindly.
        raise HTTPException(401, "Token systemId does not match current service identity record")
    return VerifiedServiceCaller(system_id=svc.system_id, service_identity_id=svc.service_identity_id, tenant_id=claims.get("tenantId"))


def require_service_token(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> VerifiedServiceCaller:
    """Hard dependency — used on the most sensitive endpoints (credential resolution,
    usage submission). Missing/malformed/invalid/expired token or revoked identity ->
    401/403. The legacy X-AGAIN-Service-Context header is NEVER consulted here — it is
    not authoritative (E5.1 §6)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing service bearer token")
    token = authorization[len("Bearer "):]
    try:
        claims = service_auth.verify_service_token(token)
    except ServiceTokenError as e:
        raise HTTPException(401, f"Invalid service token: {e}")
    return _load_and_check_service_identity(db, claims)


def optional_service_token(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> Optional[VerifiedServiceCaller]:
    """Soft dependency — used on /entitlements/evaluate, which E3/E4/E4.1 already have
    ~68 passing tests calling without any token (subject/account-based checks, not just
    service calls). Verifying a token WHEN PRESENT (rather than requiring one always)
    lets E5.1 prove the token path is real without a large, out-of-scope rewrite of
    every prior test file. See docs/current-state/E5_1_TRUST_CLOSURE.md for this
    explicit, disclosed scoping decision."""
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Malformed Authorization header")
    token = authorization[len("Bearer "):]
    try:
        claims = service_auth.verify_service_token(token)
    except ServiceTokenError as e:
        raise HTTPException(401, f"Invalid service token: {e}")
    return _load_and_check_service_identity(db, claims)


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
def resolve_credential_ref(
    credential_ref: str, body: CredentialResolveRequest, db: Session = Depends(get_db),
    caller: VerifiedServiceCaller = Depends(require_service_token),
):
    # E5.1 §6/§15: the authenticated token identity is authoritative. A body-supplied
    # serviceSystemId that disagrees with the token is rejected outright, never
    # silently normalized to either side.
    if body.serviceSystemId and body.serviceSystemId != caller.system_id:
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_IDENTITY_MISMATCH", tenant_id=body.tenantId,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Authenticated token identity does not match declared serviceSystemId")

    cr = db.query(CredentialReference).filter(CredentialReference.credential_ref == credential_ref).first()
    if not cr:
        raise HTTPException(404, "Credential reference not found")

    if cr.tenant_id != body.tenantId:
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_TENANT_MISMATCH", tenant_id=body.tenantId,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Credential reference does not belong to the requesting tenant")

    if cr.status == "REVOKED":
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_REVOKED", tenant_id=cr.tenant_id,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Credential reference is revoked")

    if cr.expires_at and cr.expires_at < _now():
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_EXPIRED", tenant_id=cr.tenant_id,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Credential reference has expired")

    # Requesting service identity status (ACTIVE, not revoked) was already verified by
    # the require_service_token dependency above — no redundant re-check needed here.

    secret = secret_resolver.resolve(credential_ref, cr.provider, body.purpose)

    if secret is None:
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="CREDENTIAL_RESOLVE_DENIED", target_type="CredentialReference",
                    target_id=credential_ref, result="DENY_UNRESOLVABLE", tenant_id=cr.tenant_id,
                    correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(424, "Credential reference could not be resolved to a secret value")

    # Audit records the fact of resolution — never the secret value itself.
    write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
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


@router.post("/service-identities/{service_identity_id}/rotate-client-secret")
def rotate_client_secret(service_identity_id: str, body: ServiceSecretRotateRequest, db: Session = Depends(get_db)):
    """Generates (or, for deterministic local testing, accepts) a client secret for
    OAuth2-client-credentials-style token issuance. Returns the PLAINTEXT secret exactly
    once — only the bcrypt hash is ever stored. Losing the returned value means rotating
    again; there is no way to recover it, by design."""
    svc = db.query(ServiceIdentity).filter(ServiceIdentity.service_identity_id == service_identity_id).first()
    if not svc:
        raise HTTPException(404, "Service identity not found")
    plaintext = body.clientSecret or _secrets.token_urlsafe(32)
    svc.client_secret_hash = _hash_password(plaintext)
    db.commit()
    write_audit(db, actor_type="SYSTEM", actor_id="init", action="SERVICE_CLIENT_SECRET_ROTATED",
                target_type="ServiceIdentity", target_id=svc.service_identity_id, result="SUCCESS")
    db.commit()
    return {"serviceIdentityId": svc.service_identity_id, "systemId": svc.system_id, "clientSecret": plaintext}


# ── E5.1 Service Auth ──
@router.post("/auth/service-token")
def issue_service_token(body: ServiceTokenRequest, db: Session = Depends(get_db)):
    svc = db.query(ServiceIdentity).filter(ServiceIdentity.system_id == body.systemId).first()
    if not svc or not svc.client_secret_hash:
        write_audit(db, actor_type="SERVICE", actor_id=body.systemId, action="SERVICE_TOKEN_ISSUE_DENIED",
                    target_type="ServiceIdentity", target_id=body.systemId, result="DENY_UNKNOWN_OR_NO_SECRET")
        db.commit()
        raise HTTPException(401, "Unknown service identity or no client secret configured")
    if svc.status == "REVOKED":
        write_audit(db, actor_type="SERVICE", actor_id=body.systemId, action="SERVICE_TOKEN_ISSUE_DENIED",
                    target_type="ServiceIdentity", target_id=svc.service_identity_id, result="DENY_REVOKED")
        db.commit()
        raise HTTPException(403, "Service identity is revoked")
    if not _verify_password(body.clientSecret, svc.client_secret_hash):
        write_audit(db, actor_type="SERVICE", actor_id=body.systemId, action="SERVICE_TOKEN_ISSUE_DENIED",
                    target_type="ServiceIdentity", target_id=svc.service_identity_id, result="DENY_BAD_SECRET")
        db.commit()
        raise HTTPException(401, "Invalid client secret")

    result = service_auth.issue_service_token(
        service_identity_id=svc.service_identity_id, system_id=svc.system_id, tenant_id=svc.tenant_id,
    )
    # Audit records issuance — never the token value itself.
    write_audit(db, actor_type="SERVICE", actor_id=svc.system_id, action="SERVICE_TOKEN_ISSUED",
                target_type="ServiceIdentity", target_id=svc.service_identity_id, result="SUCCESS")
    db.commit()
    return {"accessToken": result["accessToken"], "tokenType": result["tokenType"], "expiresIn": result["expiresIn"]}


@router.get("/.well-known/jwks.json")
def jwks():
    return service_auth.get_jwks()


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
# E5.1 §7: token is OPTIONAL here (soft dependency), not hard-required like credential
# resolve/usage — this endpoint is also called with subject/account-based (human)
# context by E3's pre-existing test suite, which has no token concept at all. When a
# token IS supplied, it is authoritative and a disagreeing body.serviceSystemId is
# rejected — never silently trusted. See docs/current-state/E5_1_TRUST_CLOSURE.md for
# this explicit, disclosed scoping decision.
@router.post("/entitlements/evaluate")
def evaluate(
    body: EntitlementEvaluateRequest, db: Session = Depends(get_db),
    caller: Optional[VerifiedServiceCaller] = Depends(optional_service_token),
):
    # Idempotency check
    if body.idempotencyKey:
        existing = check_idempotent(db, body.idempotencyKey)
        if existing:
            return {"decision": "DUPLICATE", "idempotentResult": existing}

    effective_service_system_id = body.serviceSystemId
    if caller:
        if body.serviceSystemId and body.serviceSystemId != caller.system_id:
            raise HTTPException(403, "Authenticated token identity does not match declared serviceSystemId")
        effective_service_system_id = caller.system_id

    req = EntitlementRequest(
        tenant_id=body.tenantId,
        account_id=body.accountId,
        subject_id=body.subjectId,
        service_system_id=effective_service_system_id,
        product_id=body.productId,
        capability=body.capability,
        provider=body.provider,
        model=body.model,
        correlation_id=body.correlationId,
    )
    decision = evaluate_entitlement(db, req)

    result_dict = {
        "entitlementDecisionId": decision.entitlement_decision_id,
        "decision": decision.decision,
        "reasonCode": decision.reason_code,
        "reasonMessage": decision.reason_message,
        "accountId": decision.account_id,
        "tenantId": decision.tenant_id,
        "capability": decision.capability,
        "providerConstraints": decision.provider_constraints,
        "modelConstraints": decision.model_constraints,
        "localOnly": decision.local_only,
        "cloudAllowed": decision.cloud_allowed,
        "quotaRemaining": decision.quota_remaining,
        "policyVersion": decision.policy_version,
        "evaluatedAt": decision.evaluated_at,
        "evidenceRef": decision.evidence_ref,
    }

    # Record idempotency
    if body.idempotencyKey:
        record_idempotent(db, body.idempotencyKey, result_dict)

    # Audit — target_id is now the immutable entitlementDecisionId (traceable), reason
    # code moved into metadata rather than overloading target_id (E4.1 §5).
    write_audit(db, actor_type="SYSTEM", actor_id="entitlement-engine",
                action="ENTITLEMENT_EVALUATION",
                target_type="EntitlementDecision", target_id=decision.entitlement_decision_id,
                result=decision.decision, tenant_id=decision.tenant_id,
                correlation_id=body.correlationId,
                metadata={"reasonCode": decision.reason_code})
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
def record_usage(
    body: UsageRecordCreate, db: Session = Depends(get_db),
    caller: VerifiedServiceCaller = Depends(require_service_token),
):
    if body.idempotencyKey:
        existing = check_idempotent(db, body.idempotencyKey)
        if existing:
            return {"status": "DUPLICATE", "idempotentResult": existing}

    # E5.1 §15: caller identity comes from the verified token, never the request body.
    # A body-supplied serviceSystemId that disagrees with the token is rejected outright.
    if body.serviceSystemId and body.serviceSystemId != caller.system_id:
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="USAGE_SUBMISSION_DENIED", target_type="UsageRecord",
                    target_id=caller.system_id, result="DENY_IDENTITY_MISMATCH",
                    tenant_id=body.tenantId, correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, "Authenticated token identity does not match declared serviceSystemId")

    # E4.1 §19 domain-level tenant enforcement, now driven by the verified caller
    # identity rather than a self-reported body field.
    if caller.tenant_id and caller.tenant_id != body.tenantId:
        write_audit(db, actor_type="SERVICE", actor_id=caller.system_id,
                    action="USAGE_SUBMISSION_DENIED", target_type="UsageRecord",
                    target_id=caller.system_id, result="DENY_TENANT_MISMATCH",
                    tenant_id=body.tenantId, correlation_id=body.correlationId)
        db.commit()
        raise HTTPException(403, f"Service identity {caller.system_id} is scoped to a different tenant")

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
