"""Account Again — API schemas (Pydantic)."""

from typing import Optional, List
from pydantic import BaseModel, Field

# ── Tenant ──
class TenantCreate(BaseModel):
    name: str
    tenantId: Optional[str] = None

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

# ── Account ──
class AccountCreate(BaseModel):
    tenantId: str
    email: str
    displayName: str
    accountId: Optional[str] = None

class AccountUpdate(BaseModel):
    displayName: Optional[str] = None
    status: Optional[str] = None

# ── Subject Identity ──
class SubjectIdentityCreate(BaseModel):
    accountId: str
    tenantId: str
    identityProvider: str = "LOCAL"
    authMethod: str = "PASSWORD"
    password: Optional[str] = None  # Only for LOCAL/PASSWORD
    providerSubject: Optional[str] = None

# ── Role / Permission ──
class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None

class PermissionCreate(BaseModel):
    name: str
    description: Optional[str] = None

class AccountRoleAssign(BaseModel):
    accountId: str
    roleId: str
    tenantId: str

class RolePermissionAssign(BaseModel):
    roleId: str
    permissionId: str

# ── Product Entitlement ──
class ProductEntitlementCreate(BaseModel):
    tenantId: str
    accountId: Optional[str] = None
    subjectId: Optional[str] = None
    productId: str
    validFrom: Optional[str] = None
    validUntil: Optional[str] = None

class ProductEntitlementUpdate(BaseModel):
    status: Optional[str] = None

# ── AI Entitlement ──
class AIEntitlementCreate(BaseModel):
    tenantId: str
    accountId: Optional[str] = None
    capability: str
    providerConstraint: Optional[str] = None
    modelConstraint: Optional[str] = None
    localOnly: bool = False
    cloudAllowed: bool = True
    maxCostCents: Optional[int] = None
    maxTokens: Optional[int] = None

class AIEntitlementUpdate(BaseModel):
    status: Optional[str] = None

# ── Credential Reference ──
class CredentialRefCreate(BaseModel):
    tenantId: str
    ownerAccountId: Optional[str] = None
    provider: str
    credentialType: str
    secretStoreType: str = "ACCOUNT_AGAIN_VAULT"
    secretStoreReference: Optional[str] = None
    expiresAt: Optional[str] = None

class CredentialRefRotate(BaseModel):
    secretStoreReference: Optional[str] = None

# ── Service Identity ──
class ServiceIdentityCreate(BaseModel):
    systemId: str
    tenantId: Optional[str] = None
    allowedCapabilities: List[str] = Field(default_factory=list)

# ── Session ──
class SessionCreate(BaseModel):
    subjectId: str
    tenantId: str
    expiresAt: str

# ── Entitlement Evaluation ──
class EntitlementEvaluateRequest(BaseModel):
    tenantId: Optional[str] = None
    accountId: Optional[str] = None
    subjectId: Optional[str] = None
    serviceSystemId: Optional[str] = None
    productId: Optional[str] = None
    capability: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    correlationId: Optional[str] = None
    idempotencyKey: Optional[str] = None

# ── Quota ──
class QuotaPolicyCreate(BaseModel):
    tenantId: str
    scope: str
    scopeId: Optional[str] = None
    requestsPerDay: Optional[int] = None
    tokensPerDay: Optional[int] = None
    tokensPerMonth: Optional[int] = None
    costCentsPerMonth: Optional[int] = None

# ── Usage ──
class UsageRecordCreate(BaseModel):
    tenantId: str
    accountId: Optional[str] = None
    capability: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    promptTokens: Optional[int] = None
    completionTokens: Optional[int] = None
    totalTokens: Optional[int] = None
    costCents: Optional[int] = None
    correlationId: Optional[str] = None
    idempotencyKey: Optional[str] = None
