"""
Canonical AGAIN-ECOSYSTEM v2 support contract bindings (QA-E1).
Mirrors contracts/vendored/v2/schemas/*.json exactly. Canonical authority is
AGAIN-ECOSYSTEM — see vendored/manifest.json.
"""

from typing import Any, Literal, Optional

from pydantic import Field

from app.contracts.base import CanonicalModel


class IdentityClaims(CanonicalModel):
    _contract_name = "IdentityClaims"

    identityClaimsId: str
    correlationId: Optional[str] = None
    accountId: str
    tenantId: Optional[str] = None
    subjectId: str
    subjectType: Optional[Literal["USER", "SERVICE", "SYSTEM"]] = None
    roles: list[str] = Field(default_factory=list)
    productEntitlements: list[dict[str, Any]] = Field(default_factory=list)
    sessionRef: Optional[str] = None
    issuer: Literal["account-again"] = "account-again"
    issuedAt: str
    expiresAt: str


class ServiceIdentity(CanonicalModel):
    _contract_name = "ServiceIdentity"

    serviceIdentityId: str
    systemId: Literal[
        "CONDUCTOR_MAIN", "PM_AGAIN", "IDEA_TO_CODE", "INFRA_AGAIN",
        "QA_AGAIN", "LOCAL_AI_CONTROL_CENTER", "ACCOUNT_AGAIN",
    ]
    tenantId: Optional[str] = None
    status: Literal["ACTIVE", "REVOKED"]
    allowedCapabilities: list[str] = Field(default_factory=list)
    correlationId: Optional[str] = None
    createdAt: str
    revokedAt: Optional[str] = None


class CredentialRef(CanonicalModel):
    _contract_name = "CredentialRef"

    credentialRef: str
    tenantId: str
    ownerAccountId: Optional[str] = None
    provider: str
    credentialType: Literal[
        "AI_PROVIDER_API_KEY", "CLOUD_PROVIDER_ACCESS_KEY", "DATABASE_CONNECTION",
        "SERVICE_ACCOUNT_KEY", "OAUTH_CLIENT", "TLS_CERTIFICATE",
        "GIT_DEPLOY_KEY", "WEBHOOK_SECRET", "ENCRYPTION_KEY_REF",
    ]
    secretStoreType: Optional[Literal["ACCOUNT_AGAIN_VAULT", "EXTERNAL_HSM", "CLOUD_KMS"]] = None
    secretStoreReference: Optional[str] = None
    status: Literal["ACTIVE", "EXPIRING", "EXPIRED", "REVOKED", "ROTATING"]
    createdAt: Optional[str] = None
    rotatedAt: Optional[str] = None
    expiresAt: Optional[str] = None
    revokedAt: Optional[str] = None


class EntitlementDecision(CanonicalModel):
    _contract_name = "EntitlementDecision"

    entitlementDecisionId: str
    correlationId: Optional[str] = None
    accountId: Optional[str] = None
    tenantId: Optional[str] = None
    decision: Literal["ALLOW", "DENY", "CONDITIONAL"]
    reasonCode: str
    reasonMessage: Optional[str] = None
    capability: Optional[str] = None
    providerConstraints: Optional[dict[str, Any]] = None
    modelConstraints: Optional[dict[str, Any]] = None
    localOnly: Optional[bool] = None
    cloudAllowed: Optional[bool] = None
    quotaRef: Optional[str] = None
    quotaRemaining: Optional[int] = None
    policyVersion: Optional[str] = None
    evaluatedAt: str
    evidenceRef: Optional[str] = None


class AIExecutionRequest(CanonicalModel):
    _contract_name = "AIExecutionRequest"

    requestId: str
    correlationId: str
    idempotencyKey: Optional[str] = None
    capability: Literal[
        "CODE_PLANNING", "CODE_EXECUTION", "CODE_VERIFICATION",
        "INFRASTRUCTURE_PLANNING", "QA_ANALYSIS", "DOCUMENT_GENERATION",
        "BUSINESS_ANALYSIS", "GENERAL_REASONING",
    ]
    inputRef: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    constraints: Optional[dict[str, Any]] = None
    dataSensitivity: Optional[Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]] = None
    privacy: Optional[Literal["LOCAL_REQUIRED", "LOCAL_PREFERRED", "CLOUD_ALLOWED"]] = None
    modelPreference: Optional[dict[str, Any]] = None
    identityClaimsRef: Optional[str] = None
    entitlementDecisionRef: Optional[str] = None
    credentialRefs: list[dict[str, Any]] = Field(default_factory=list)
    budgetContext: Optional[dict[str, Any]] = None
    createdAt: Optional[str] = None


class AIExecutionResult(CanonicalModel):
    _contract_name = "AIExecutionResult"

    requestId: str
    correlationId: str
    status: Literal["COMPLETED", "PARTIAL", "FAILED", "BLOCKED_BY_AIRLOCK", "BLOCKED_BY_POLICY", "TIMED_OUT"]
    outputRef: Optional[str] = None
    outputSummary: Optional[str] = None
    providerUsed: str
    modelUsed: str
    routingProvenance: Optional[dict[str, Any]] = None
    usage: Optional[dict[str, Any]] = None
    policyResult: Optional[dict[str, Any]] = None
    evidenceRef: Optional[str] = None
    completedAt: str


class EvidenceReference(CanonicalModel):
    _contract_name = "EvidenceReference"

    evidenceId: str
    correlationId: Optional[str] = None
    evidenceType: str
    ownerSystem: Literal[
        "conductor-main", "pm-again", "idea-to-code", "infrastructure-again",
        "qa-again", "account-again", "local-ai-control-center",
    ]
    reference: str
    digest: Optional[dict[str, Any]] = None
    summary: Optional[str] = None
    createdAt: Optional[str] = None
