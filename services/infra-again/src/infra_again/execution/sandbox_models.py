"""Phase 8 Sandbox Control Model — domain models for controlled cloud execution.

SANDBOX execution mode with explicit safety constraints:
  - explicit account/project + identity verification
  - resource allowlist
  - cost ceiling
  - TTL
  - ownership tags
  - cleanup policy
  - credential lease (temp/least-privilege)
  - production=false
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


# ============================================================================
# Enums
# ============================================================================


class SandboxApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class CredentialSource(str, Enum):
    TEMPORARY_STS = "TEMPORARY_STS"
    INSTANCE_PROFILE = "INSTANCE_PROFILE"
    OIDC_WEB_IDENTITY = "OIDC_WEB_IDENTITY"
    ENV_VARIABLE = "ENV_VARIABLE"
    NONE = "NONE"


class SandboxExecutionState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PREFLIGHT_RUNNING = "PREFLIGHT_RUNNING"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    CREDENTIAL_LEASED = "CREDENTIAL_LEASED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VALIDATING = "VALIDATING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CLEANING_UP = "CLEANING_UP"
    CLEANED_UP = "CLEANED_UP"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class CostCurrency(str, Enum):
    USD = "USD"


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class SandboxResourceAllowlist:
    """Resources permitted in sandbox execution."""
    services: list[str] = field(default_factory=list)  # e.g. ["s3", "ec2"]
    max_resource_count: int = 1
    blocked_services: list[str] = field(default_factory=lambda: [
        "rds", "eks", "ec2", "natgateway", "vpc", "iam", "organizations",
    ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "services": self.services,
            "maxResourceCount": self.max_resource_count,
            "blockedServices": self.blocked_services,
        }

    def is_allowed(self, service: str) -> bool:
        return service.lower() in [s.lower() for s in self.services]


@dataclass
class CostEstimate:
    """Bounded cost estimate for sandbox execution."""
    estimated_maximum_cost: float = 0.0
    currency: CostCurrency = CostCurrency.USD
    cost_window_hours: float = 1.0  # billing window
    ceiling: float = 5.0  # hard cap
    source: str = "RULE_BASED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimatedMaximumCost": self.estimated_maximum_cost,
            "currency": self.currency.value,
            "costWindowHours": self.cost_window_hours,
            "ceiling": self.ceiling,
            "source": self.source,
        }

    @property
    def exceeds_ceiling(self) -> bool:
        return self.estimated_maximum_cost > self.ceiling


@dataclass
class SandboxAccount:
    """Verified cloud account identity."""
    account_id: str = ""
    provider: str = "aws"  # aws, gcp
    caller_identity: dict[str, Any] = field(default_factory=dict)
    # caller_identity contains:
    #   - Account (AWS) / projectId (GCP)
    #   - Arn / principal
    #   - UserId
    verified: bool = False
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "provider": self.provider,
            "callerIdentity": {
                "account": self.caller_identity.get("Account", ""),
                "arn": self.caller_identity.get("Arn", ""),
                "userId": self.caller_identity.get("UserId", ""),
            },
            "verified": self.verified,
            "verifiedAt": self.verified_at,
        }


@dataclass
class CredentialLease:
    """Temporary, least-privilege credential reference (NEVER store secrets)."""
    lease_id: str = field(default_factory=lambda: f"CRED-{uuid4().hex[:8].upper()}")
    source: CredentialSource = CredentialSource.NONE
    principal_arn: str = ""
    account_id: str = ""
    expiration: str = ""  # ISO 8601
    scope: list[str] = field(default_factory=list)  # allowed actions

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaseId": self.lease_id,
            "source": self.source.value,
            "principalArn": self.principal_arn,
            "accountId": self.account_id,
            "expiration": self.expiration,
            "scope": self.scope,
        }

    @property
    def is_expired(self) -> bool:
        if not self.expiration:
            return True
        try:
            exp = datetime.fromisoformat(self.expiration.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return True


@dataclass
class CleanupPolicy:
    """Ownership-safe cleanup policy for sandbox resources."""
    delete_after_ttl: bool = True
    require_ownership_proof: bool = True
    ownership_predicate: dict[str, str] = field(default_factory=lambda: {
        "managedBy": "infra-again",
        "ephemeral": "true",
        "sandbox": "true",
    })
    post_cleanup_observation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "deleteAfterTtl": self.delete_after_ttl,
            "requireOwnershipProof": self.require_ownership_proof,
            "ownershipPredicate": self.ownership_predicate,
            "postCleanupObservation": self.post_cleanup_observation,
        }


@dataclass
class OwnershipTags:
    """Required ownership metadata for sandbox resources."""
    managed_by: str = "infra-again"
    run_id: str = ""
    ephemeral: str = "true"
    sandbox: str = "true"
    phase: str = "8"

    def to_dict(self) -> dict[str, str]:
        return {
            "managedBy": self.managed_by,
            "runId": self.run_id,
            "ephemeral": self.ephemeral,
            "sandbox": self.sandbox,
            "phase": self.phase,
        }

    def to_aws_tags(self) -> list[dict[str, str]]:
        """Convert to AWS tag format."""
        return [
            {"Key": "managedBy", "Value": self.managed_by},
            {"Key": "runId", "Value": self.run_id},
            {"Key": "ephemeral", "Value": self.ephemeral},
            {"Key": "sandbox", "Value": self.sandbox},
            {"Key": "phase", "Value": self.phase},
        ]


@dataclass
class SandboxTarget:
    """Explicit sandbox execution target with safety constraints."""
    sandbox_target_id: str = field(default_factory=lambda: f"SAND-{uuid4().hex[:8].upper()}")
    provider: str = "aws"
    account: SandboxAccount = field(default_factory=SandboxAccount)
    region: str = ""
    environment: str = "sandbox"
    resource_allowlist: SandboxResourceAllowlist = field(default_factory=SandboxResourceAllowlist)
    cost_estimate: CostEstimate = field(default_factory=CostEstimate)
    ttl_hours: float = 1.0
    ownership_tags: OwnershipTags = field(default_factory=OwnershipTags)
    cleanup_policy: CleanupPolicy = field(default_factory=CleanupPolicy)
    credential_lease: CredentialLease = field(default_factory=CredentialLease)
    production: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandboxTargetId": self.sandbox_target_id,
            "provider": self.provider,
            "account": self.account.to_dict(),
            "region": self.region,
            "environment": self.environment,
            "resourceAllowlist": self.resource_allowlist.to_dict(),
            "costEstimate": self.cost_estimate.to_dict(),
            "ttlHours": self.ttl_hours,
            "ownershipTags": self.ownership_tags.to_dict(),
            "cleanupPolicy": self.cleanup_policy.to_dict(),
            "credentialLease": self.credential_lease.to_dict(),
            "production": self.production,
            "createdAt": self.created_at,
        }


@dataclass
class SandboxApproval:
    """User approval for real sandbox mutation."""
    approval_id: str = field(default_factory=lambda: f"APRV-{uuid4().hex[:8].upper()}")
    sandbox_target_id: str = ""
    execution_package_id: str = ""
    bound_plan_checksum: str = ""
    bound_target_checksum: str = ""
    state: SandboxApprovalState = SandboxApprovalState.PENDING
    approved_by: str = ""
    approved_at: str = ""
    expires_at: str = ""
    warning_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approvalId": self.approval_id,
            "sandboxTargetId": self.sandbox_target_id,
            "executionPackageId": self.execution_package_id,
            "boundPlanChecksum": self.bound_plan_checksum,
            "boundTargetChecksum": self.bound_target_checksum,
            "state": self.state.value,
            "approvedBy": self.approved_by,
            "approvedAt": self.approved_at,
            "expiresAt": self.expires_at,
            "warningMessage": self.warning_message,
        }

    def generate_warning(self, target: SandboxTarget, cost: CostEstimate) -> str:
        self.warning_message = (
            f"You are approving a real cloud SANDBOX execution.\n\n"
            f"Provider: {target.provider.upper()}\n"
            f"Account: {target.account.account_id}\n"
            f"Region: {target.region}\n"
            f"Resource scope: {target.resource_allowlist.services}\n"
            f"Estimated maximum cost: ${cost.estimated_maximum_cost:.2f} {cost.currency.value}\n"
            f"TTL: {target.ttl_hours}h\n\n"
            f"This action may create real cloud resources.\n"
            f"Production resources are not permitted."
        )
        return self.warning_message

    def is_bound_to(self, plan_checksum: str, target_checksum: str) -> bool:
        return (
            self.bound_plan_checksum == plan_checksum
            and self.bound_target_checksum == target_checksum
        )

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return True


@dataclass
class SandboxPreflightResult:
    """Result of sandbox-specific preflight checks."""
    preflight_id: str = field(default_factory=lambda: f"SBPF-{uuid4().hex[:8].upper()}")
    package_id: str = ""
    sandbox_target_id: str = ""

    # Individual checks
    plan_checksum_match: bool = False
    sandbox_fidelity: bool = False
    account_verified: bool = False
    region_set: bool = False
    resource_allowlist_valid: bool = False
    cost_within_ceiling: bool = False
    ttl_set: bool = False
    ownership_tags_set: bool = False
    cleanup_policy_set: bool = False
    credentials_valid: bool = False
    provider_identity_verified: bool = False
    production_is_false: bool = False

    # Overall
    all_passed: bool = False
    failures: list[str] = field(default_factory=list)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "preflightId": self.preflight_id,
            "packageId": self.package_id,
            "sandboxTargetId": self.sandbox_target_id,
            "checks": {
                "planChecksumMatch": self.plan_checksum_match,
                "sandboxFidelity": self.sandbox_fidelity,
                "accountVerified": self.account_verified,
                "regionSet": self.region_set,
                "resourceAllowlistValid": self.resource_allowlist_valid,
                "costWithinCeiling": self.cost_within_ceiling,
                "ttlSet": self.ttl_set,
                "ownershipTagsSet": self.ownership_tags_set,
                "cleanupPolicySet": self.cleanup_policy_set,
                "credentialsValid": self.credentials_valid,
                "providerIdentityVerified": self.provider_identity_verified,
                "productionIsFalse": self.production_is_false,
            },
            "allPassed": self.all_passed,
            "failures": self.failures,
            "checkedAt": self.checked_at,
        }


class SandboxBlockerReason(str, Enum):
    PLAN_CHECKSUM_MISMATCH = "PLAN_CHECKSUM_MISMATCH"
    SANDBOX_FIDELITY_NOT_ALLOWED = "SANDBOX_FIDELITY_NOT_ALLOWED"
    ACCOUNT_NOT_VERIFIED = "ACCOUNT_NOT_VERIFIED"
    SANDBOX_ACCOUNT_MISMATCH = "SANDBOX_ACCOUNT_MISMATCH"
    REGION_NOT_SET = "REGION_NOT_SET"
    RESOURCE_NOT_ALLOWED = "RESOURCE_NOT_ALLOWED"
    SANDBOX_COST_LIMIT_EXCEEDED = "SANDBOX_COST_LIMIT_EXCEEDED"
    TTL_NOT_SET = "TTL_NOT_SET"
    OWNERSHIP_TAGS_MISSING = "OWNERSHIP_TAGS_MISSING"
    CLEANUP_POLICY_NOT_SET = "CLEANUP_POLICY_NOT_SET"
    CREDENTIALS_INVALID = "CREDENTIALS_INVALID"
    PROVIDER_IDENTITY_NOT_VERIFIED = "PROVIDER_IDENTITY_NOT_VERIFIED"
    PRODUCTION_NOT_FALSE = "PRODUCTION_NOT_FALSE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_MISMATCH = "APPROVAL_MISMATCH"
