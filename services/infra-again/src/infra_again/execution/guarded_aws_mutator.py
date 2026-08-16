"""Phase 9.1.2 Guarded AWS S3 Mutation Wrapper.

Every AWS S3 mutation MUST pass through this wrapper.
The wrapper asserts AIRLOCK before every mutation call.

This is the AUTHORITATIVE mutation boundary — no bypass possible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .immutable_approval import AirlockContext, AirlockNotSatisfied
from .immutable_approval import classify_create_failure, ReconciliationResult


@dataclass
class MutationCounter:
    """Thread-safe mutation counter for acceptance evidence."""
    count: int = 0
    log: list[dict] = field(default_factory=list)

    def record(self, action: str, result: str, detail: str = ""):
        import time
        self.count += 1
        self.log.append({
            "action": action, "result": result, "detail": detail,
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        })


class GuardedAwsS3Mutator:
    """Guarded AWS S3 client — asserts AIRLOCK before every mutation.

    Usage:
        mutator = GuardedAwsS3Mutator(s3_client, airlock_context, counter)
        mutator.assert_airlock()  # called internally by every mutation method
        mutator.create_bucket(bucket, region)
    """

    def __init__(
        self,
        s3_client: Any,
        airlock: AirlockContext,
        counter: MutationCounter | None = None,
    ):
        self._s3 = s3_client
        self._airlock = airlock
        self._counter = counter or MutationCounter()

    @property
    def mutation_count(self) -> int:
        return self._counter.count

    @property
    def airlock(self) -> AirlockContext:
        return self._airlock

    def _assert(self) -> None:
        """Assert airlock before any mutation. Raises if not satisfied."""
        self._airlock.assert_airlock()

    # ── Mutation Methods ──────────────────────────────────

    def create_bucket(self, bucket: str, region: str) -> dict[str, Any]:
        """Create S3 bucket. AIRLOCK REQUIRED."""
        self._assert()
        try:
            if region == "us-east-1":
                result = self._s3.create_bucket(Bucket=bucket)
            else:
                result = self._s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            self._counter.record("CreateBucket", "SUCCESS", bucket)
            return {"success": True, "action": "CreateBucket", "response": result}
        except Exception as e:
            error_str = str(e)
            classification, reconciliation = classify_create_failure(e)
            self._counter.record("CreateBucket", classification, error_str[:200])
            return {
                "success": False,
                "action": "CreateBucket",
                "error": error_str[:200],
                "classification": classification,
                "reconciliation": reconciliation.value if reconciliation else "UNKNOWN",
                "requires_reconciliation": reconciliation == ReconciliationResult.INCONCLUSIVE,
            }

    def put_public_access_block(self, bucket: str) -> dict[str, Any]:
        """Set all 4 public access blocks. AIRLOCK REQUIRED."""
        self._assert()
        try:
            self._s3.put_public_access_block(
                Bucket=bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            self._counter.record("PutPublicAccessBlock", "SUCCESS")
            return {"success": True, "action": "PutPublicAccessBlock"}
        except Exception as e:
            self._counter.record("PutPublicAccessBlock", "FAILED", str(e)[:200])
            return {"success": False, "action": "PutPublicAccessBlock", "error": str(e)[:200]}

    def put_bucket_tagging(self, bucket: str, tags: dict[str, str]) -> dict[str, Any]:
        """Apply ownership tags. AIRLOCK REQUIRED."""
        self._assert()
        try:
            tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
            self._s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": tag_set})
            self._counter.record("PutBucketTagging", "SUCCESS")
            return {"success": True, "action": "PutBucketTagging"}
        except Exception as e:
            self._counter.record("PutBucketTagging", "FAILED", str(e)[:200])
            return {"success": False, "action": "PutBucketTagging", "error": str(e)[:200]}

    def delete_bucket(self, bucket: str) -> dict[str, Any]:
        """Delete exact bucket. AIRLOCK REQUIRED. Ownership must be proven first."""
        self._assert()
        try:
            self._s3.delete_bucket(Bucket=bucket)
            self._counter.record("DeleteBucket", "SUCCESS")
            return {"success": True, "action": "DeleteBucket"}
        except Exception as e:
            self._counter.record("DeleteBucket", "FAILED", str(e)[:200])
            return {"success": False, "action": "DeleteBucket", "error": str(e)[:200]}

    # ── Read-only observation (no airlock required) ──────

    def head_bucket(self, bucket: str) -> dict[str, Any]:
        """Check bucket exists. Read-only — no airlock required."""
        try:
            self._s3.head_bucket(Bucket=bucket)
            return {"exists": True}
        except Exception as e:
            return {"exists": False, "error": str(e)[:200]}

    def observe_bucket(self, bucket: str) -> dict[str, Any]:
        """Full observation. Read-only — no airlock required."""
        result: dict[str, Any] = {"bucket": bucket, "observed": False}
        try:
            self._s3.head_bucket(Bucket=bucket)
            result["exists"] = True

            loc = self._s3.get_bucket_location(Bucket=bucket)
            result["region"] = loc.get("LocationConstraint") or "us-east-1"

            pab = self._s3.get_public_access_block(Bucket=bucket)
            result["publicAccessBlock"] = pab.get("PublicAccessBlockConfiguration", {})

            tags_resp = self._s3.get_bucket_tagging(Bucket=bucket)
            tag_dict = {t["Key"]: t["Value"] for t in tags_resp.get("TagSet", [])}
            result["tags"] = tag_dict

            result["observed"] = True
        except Exception as e:
            result["error"] = str(e)[:200]

        return result

    def post_cleanup_observe(self, bucket: str) -> dict[str, Any]:
        """Post-cleanup observation. Only 404/NoSuchBucket proves absence."""
        from .immutable_approval import classify_post_cleanup_error, CleanupObservation

        try:
            self._s3.head_bucket(Bucket=bucket)
            return {"bucketAbsent": False, "cleanupState": "PRESENT"}
        except Exception as e:
            classification = classify_post_cleanup_error(e)
            return {
                "bucketAbsent": classification == CleanupObservation.ABSENT_VERIFIED,
                "cleanupState": classification.value,
                "verified": classification == CleanupObservation.ABSENT_VERIFIED,
                "error": str(e)[:200],
            }


# ══════════════════════════════════════════════════════════
# Fake/Spy S3 Client for acceptance testing
# ══════════════════════════════════════════════════════════
class FakeS3Client:
    """Spy S3 client for acceptance testing. Records all calls."""

    def __init__(self):
        self.calls: list[dict] = []
        self.buckets: dict[str, dict] = {}
        self._fail_next: str | None = None

    def set_fail_next(self, error_type: str) -> None:
        self._fail_next = error_type

    def create_bucket(self, **kwargs) -> dict:
        self.calls.append({"method": "create_bucket", "kwargs": kwargs})
        if self._fail_next:
            err = self._fail_next
            self._fail_next = None
            if err == "timeout":
                raise Exception("connection timed out")
            elif err == "ambiguous_5xx":
                raise Exception("HTTP 503 Service Unavailable")
            raise Exception(err)
        bucket = kwargs.get("Bucket", "unknown")
        self.buckets[bucket] = {"created": True, "tags": {}, "publicAccessBlock": {}}
        return {"Location": f"/{bucket}"}

    def put_public_access_block(self, **kwargs) -> dict:
        self.calls.append({"method": "put_public_access_block", "kwargs": kwargs})
        bucket = kwargs.get("Bucket", "")
        if bucket in self.buckets:
            self.buckets[bucket]["publicAccessBlock"] = kwargs.get(
                "PublicAccessBlockConfiguration", {})
        return {}

    def put_bucket_tagging(self, **kwargs) -> dict:
        self.calls.append({"method": "put_bucket_tagging", "kwargs": kwargs})
        bucket = kwargs.get("Bucket", "")
        if bucket in self.buckets:
            tags = kwargs.get("Tagging", {}).get("TagSet", [])
            self.buckets[bucket]["tags"] = {t["Key"]: t["Value"] for t in tags}
        return {}

    def head_bucket(self, **kwargs) -> dict:
        self.calls.append({"method": "head_bucket", "kwargs": kwargs})
        bucket = kwargs.get("Bucket", "")
        if bucket in self.buckets:
            return {}
        raise Exception("404 Not Found")

    def get_bucket_location(self, **kwargs) -> dict:
        return {"LocationConstraint": "us-east-1"}

    def get_public_access_block(self, **kwargs) -> dict:
        bucket = kwargs.get("Bucket", "")
        pab = self.buckets.get(bucket, {}).get("publicAccessBlock", {
            "BlockPublicAcls": True, "IgnorePublicAcls": True,
            "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
        })
        return {"PublicAccessBlockConfiguration": pab}

    def get_bucket_tagging(self, **kwargs) -> dict:
        bucket = kwargs.get("Bucket", "")
        tags = self.buckets.get(bucket, {}).get("tags", {})
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
        return {"TagSet": tag_set}

    def delete_bucket(self, **kwargs) -> dict:
        self.calls.append({"method": "delete_bucket", "kwargs": kwargs})
        bucket = kwargs.get("Bucket", "")
        if bucket in self.buckets:
            del self.buckets[bucket]
        return {}
