"""Phase 9.1.1 Immutable Approval + Airlock State Machine.

Approval binds immutably to:
  account, principal, region, bucket, TTL, cost, planChecksum, packageChecksum,
  resourceAllowlist, sandbox=true, production=false

Airlock state machine:
  DISCOVERY → PREFLIGHT_PASSED → APPROVAL_PENDING → APPROVED →
  ADMIN_AUTH_REQUIRED → ADMIN_AUTH_VERIFIED → AIRLOCK_PASSED → EXECUTING

Mutation guard prevents any AWS mutation without AIRLOCK_PASSED.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


# ══════════════════════════════════════════════════════════
# Airlock States
# ══════════════════════════════════════════════════════════
class AirlockState(str, Enum):
    DISCOVERY = "DISCOVERY"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    APPROVAL_INVALIDATED = "APPROVAL_INVALIDATED"
    ADMIN_AUTH_REQUIRED = "ADMIN_AUTH_REQUIRED"
    ADMIN_AUTH_VERIFIED = "ADMIN_AUTH_VERIFIED"
    AIRLOCK_PASSED = "AIRLOCK_PASSED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    LOCKED = "LOCKED"


class ApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    INVALIDATED = "INVALIDATED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


# ══════════════════════════════════════════════════════════
# Immutable Approval
# ══════════════════════════════════════════════════════════
@dataclass
class ImmutableApproval:
    """Immutable sandbox execution approval bound to exact resource identity."""

    approval_id: str = field(default_factory=lambda: f"APRV-{uuid4().hex[:8].upper()}")
    approval_digest: str = ""
    created_at: str = ""
    approved_by: str = ""
    approved_at: str = ""
    state: ApprovalState = ApprovalState.PENDING

    # Immutable bound values
    aws_account: str = ""
    principal_arn: str = ""
    region: str = ""
    bucket_name: str = ""
    ttl_hours: float = 1.0
    expires_at: str = ""
    cost_ceiling: float = 0.10
    execution_package_id: str = ""
    plan_id: str = ""
    plan_checksum: str = ""
    package_plan_checksum: str = ""
    resource_allowlist: list[str] = field(default_factory=lambda: ["s3"])
    sandbox: bool = True
    production: bool = False

    # Admin airlock
    admin_verified: bool = False
    admin_verified_at: str = ""

    def compute_canonical(self) -> str:
        """Compute canonical JSON for digest."""
        data = {
            "approvalId": self.approval_id,
            "awsAccount": self.aws_account,
            "principalArn": self.principal_arn,
            "region": self.region,
            "bucketName": self.bucket_name,
            "ttlHours": self.ttl_hours,
            "expiresAt": self.expires_at,
            "costCeiling": self.cost_ceiling,
            "executionPackageId": self.execution_package_id,
            "planId": self.plan_id,
            "planChecksum": self.plan_checksum,
            "packagePlanChecksum": self.package_plan_checksum,
            "resourceAllowlist": sorted(self.resource_allowlist),
            "sandbox": self.sandbox,
            "production": self.production,
        }
        return json.dumps(data, sort_keys=True)

    def compute_digest(self) -> str:
        """SHA256 of canonical JSON."""
        return hashlib.sha256(self.compute_canonical().encode()).hexdigest()

    def seal(self, approved_by: str = "") -> None:
        """Seal the approval with computed digest."""
        self.approved_by = approved_by
        self.approved_at = datetime.now(timezone.utc).isoformat()
        self.approval_digest = self.compute_digest()
        self.state = ApprovalState.APPROVED

    def verify_digest(self) -> tuple[bool, str]:
        """Verify current state matches sealed digest."""
        if self.state != ApprovalState.APPROVED:
            return False, f"Not approved: {self.state.value}"
        current = self.compute_digest()
        if current != self.approval_digest:
            self.state = ApprovalState.INVALIDATED
            return False, f"SANDBOX_APPROVAL_INVALIDATED: digest mismatch"
        return True, "DIGEST_MATCH"

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "approvalId": self.approval_id,
            "approvalDigest": self.approval_digest,
            "createdAt": self.created_at,
            "approvedBy": self.approved_by,
            "approvedAt": self.approved_at,
            "state": self.state.value,
            "awsAccount": self.aws_account,
            "principalArn": self.principal_arn,
            "region": self.region,
            "bucketName": self.bucket_name,
            "ttlHours": self.ttl_hours,
            "expiresAt": self.expires_at,
            "costCeiling": self.cost_ceiling,
            "executionPackageId": self.execution_package_id,
            "planId": self.plan_id,
            "planChecksum": self.plan_checksum,
            "packagePlanChecksum": self.package_plan_checksum,
            "resourceAllowlist": self.resource_allowlist,
            "sandbox": self.sandbox,
            "production": self.production,
            "adminVerified": self.admin_verified,
            "adminVerifiedAt": self.admin_verified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImmutableApproval:
        return cls(
            approval_id=data.get("approvalId", ""),
            approval_digest=data.get("approvalDigest", ""),
            created_at=data.get("createdAt", ""),
            approved_by=data.get("approvedBy", ""),
            approved_at=data.get("approvedAt", ""),
            state=ApprovalState(data.get("state", "PENDING")),
            aws_account=data.get("awsAccount", ""),
            principal_arn=data.get("principalArn", ""),
            region=data.get("region", ""),
            bucket_name=data.get("bucketName", ""),
            ttl_hours=data.get("ttlHours", 1.0),
            expires_at=data.get("expiresAt", ""),
            cost_ceiling=data.get("costCeiling", 0.10),
            execution_package_id=data.get("executionPackageId", ""),
            plan_id=data.get("planId", ""),
            plan_checksum=data.get("planChecksum", ""),
            package_plan_checksum=data.get("packagePlanChecksum", ""),
            resource_allowlist=data.get("resourceAllowlist", ["s3"]),
            sandbox=data.get("sandbox", True),
            production=data.get("production", False),
            admin_verified=data.get("adminVerified", False),
            admin_verified_at=data.get("adminVerifiedAt", ""),
        )

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> Optional[ImmutableApproval]:
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))


# ══════════════════════════════════════════════════════════
# Airlock Context
# ══════════════════════════════════════════════════════════
@dataclass
class AirlockContext:
    """Execution context that MUST be satisfied before any AWS mutation."""

    approval_valid: bool = False
    admin_verified: bool = False
    airlock_passed: bool = False
    sandbox: bool = True
    production: bool = False
    state: AirlockState = AirlockState.DISCOVERY
    approval_id: str = ""
    admin_verified_at: str = ""

    def assert_airlock(self) -> None:
        """Raise if airlock not satisfied. Call at AWS mutation boundary."""
        if not self.approval_valid:
            raise AirlockNotSatisfied(
                "REAL_CLOUD_AIRLOCK_NOT_SATISFIED: approval not valid"
            )
        if not self.admin_verified:
            raise AirlockNotSatisfied(
                "REAL_CLOUD_AIRLOCK_NOT_SATISFIED: admin not verified"
            )
        if not self.airlock_passed:
            raise AirlockNotSatisfied(
                f"REAL_CLOUD_AIRLOCK_NOT_SATISFIED: "
                f"approval={self.approval_valid} admin={self.admin_verified} "
                f"airlock={self.airlock_passed} state={self.state.value}"
            )
        if self.production:
            raise AirlockNotSatisfied("PRODUCTION_BLOCKED")


class AirlockNotSatisfied(Exception):
    """Raised when AWS mutation is attempted without airlock."""
    pass


# ══════════════════════════════════════════════════════════
# Reconciliation helpers
# ══════════════════════════════════════════════════════════
class ReconciliationResult(str, Enum):
    RESOURCE_CREATED = "RESOURCE_CREATED"
    RESOURCE_NOT_CREATED = "RESOURCE_NOT_CREATED"
    INCONCLUSIVE = "INCONCLUSIVE"


class CleanupObservation(str, Enum):
    ABSENT_VERIFIED = "ABSENT_VERIFIED"
    PRESENT = "PRESENT"
    INCONCLUSIVE = "INCONCLUSIVE"


AMBIGUOUS_FAILURE_PATTERNS = [
    "timeout", "timed out", "connection reset", "connection refused",
    "broken pipe", "service unavailable", "internal server error",
    "503", "504", "502", "500", "request timeout",
]


def classify_create_failure(error: Exception) -> tuple[str, ReconciliationResult]:
    """Classify a CreateBucket failure as definitive or ambiguous."""
    error_str = str(error).lower()
    for pattern in AMBIGUOUS_FAILURE_PATTERNS:
        if pattern in error_str:
            return "AMBIGUOUS", ReconciliationResult.INCONCLUSIVE
    # Check for definitive "already exists" or "bucket name taken"
    if any(x in error_str for x in ["already exists", "already taken",
                                      "bucketalreadyexists", "bucket already",
                                      "your previous request"]):
        return "DEFINITIVE_EXISTS", ReconciliationResult.RESOURCE_CREATED
    return "DEFINITIVE_FAILURE", ReconciliationResult.RESOURCE_NOT_CREATED


def classify_post_cleanup_error(error: Exception) -> CleanupObservation:
    """Classify post-cleanup observation. Only 404/NoSuchBucket proves absence."""
    error_str = str(error).lower()
    # Only these prove absence
    if any(x in error_str for x in ["404", "not found", "nosuchbucket", "no such bucket"]):
        return CleanupObservation.ABSENT_VERIFIED
    # These are NOT proof of absence
    if any(x in error_str for x in ["403", "access denied", "forbidden",
                                      "expired", "timeout", "timed out",
                                      "connection", "network", "dns"]):
        return CleanupObservation.INCONCLUSIVE
    return CleanupObservation.INCONCLUSIVE
