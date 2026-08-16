"""
AWS Provider Adapter — PLAN_ONLY + SIMULATED (fakecloud) implementation.

Supports:
- PLAN_ONLY: architecture planning without credentials
- SIMULATED: real boto3 calls against fakecloud local AWS emulator

Do NOT silently fall back to real AWS.
Do NOT hardcode AWS service names into provider-neutral abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ...core.domain import (
    CapabilityMapping,
    CapabilityRequirement,
    ChangeAction,
    ChangeItem,
    ChangeSet,
    ExecutionMode,
    ExecutionTarget,
    ExecutionTargetType,
    InfrastructurePlan,
    Provider,
    TruthStatus,
    ValidationResult,
)
from ..interface import ProviderAdapter, ProviderCapability


# ---------------------------------------------------------------------------
# Known AWS capability catalog (minimal, provider-neutral map)
# ---------------------------------------------------------------------------


@dataclass
class AwsCapabilityMapping:
    """Maps provider-neutral requirements to AWS resource types."""
    requirement_key: str
    aws_service: str
    aws_resource_type: str
    notes: str


# This is a minimal, curated mapping — NOT a full cloud catalog.
# Future: replace with Dynamic Capability Registry data.
AWS_CAPABILITY_MAP: list[AwsCapabilityMapping] = [
    AwsCapabilityMapping("database", "RDS", "AWS::RDS::DBInstance",
                         "Managed relational database"),
    AwsCapabilityMapping("database", "Aurora", "AWS::RDS::DBCluster",
                         "Aurora cluster for production workloads"),
    AwsCapabilityMapping("object_storage", "S3", "AWS::S3::Bucket",
                         "Object storage"),
    AwsCapabilityMapping("container_runtime", "ECS", "AWS::ECS::Service",
                         "Container orchestration (ECS)"),
    AwsCapabilityMapping("container_runtime", "EKS", "AWS::EKS::Cluster",
                         "Managed Kubernetes (EKS)"),
    AwsCapabilityMapping("application_load_balancer", "ALB", "AWS::ElasticLoadBalancingV2::LoadBalancer",
                         "Application Load Balancer"),
    AwsCapabilityMapping("cdn", "CloudFront", "AWS::CloudFront::Distribution",
                         "Content delivery network"),
    AwsCapabilityMapping("dns", "Route53", "AWS::Route53::RecordSet",
                         "DNS management"),
    AwsCapabilityMapping("secrets", "SecretsManager", "AWS::SecretsManager::Secret",
                         "Secrets management"),
    AwsCapabilityMapping("encryption_key", "KMS", "AWS::KMS::Key",
                         "Key management"),
]


class AwsProviderAdapter(ProviderAdapter):
    """
    AWS Provider Adapter.

    Currently implements PLAN_ONLY mode.
    No real AWS credentials required.
    Does NOT execute real infrastructure changes in this implementation.
    """

    @property
    def provider(self) -> Provider:
        return Provider.AWS

    # ------------------------------------------------------------------
    # Discover
    # ------------------------------------------------------------------

    async def discover(self, target: ExecutionTarget) -> dict[str, Any]:
        """
        Discover current AWS infrastructure state.

        Returns NOT_CONFIGURED if no AWS credentials available.
        PLAN_ONLY and SIMULATED modes return empty discovery.
        """
        if target.mode in (ExecutionMode.PLAN_ONLY, ExecutionMode.SIMULATED):
            return {
                "status": TruthStatus.NOT_CONFIGURED.value,
                "resources": {},
                "note": "PLAN_ONLY/SIMULATED — no real AWS discovery",
            }
        # Real discovery would use boto3/AWS SDK here
        return {
            "status": TruthStatus.NOT_CONFIGURED.value,
            "resources": {},
            "note": "AWS credentials not configured",
        }

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    async def plan(
        self,
        requirements: list[CapabilityRequirement],
        target: ExecutionTarget,
    ) -> InfrastructurePlan:
        """
        Generate an AWS infrastructure plan from provider-neutral requirements.

        Maps capabilities to AWS resource types using the capability map.
        Does NOT require AWS credentials.
        """
        plan = InfrastructurePlan(
            provider=Provider.AWS,
            platform=target.platform,
            execution_target=target,
        )

        for req in requirements:
            mapping = self._map_to_aws(req)
            if mapping:
                plan.capability_mappings.append(mapping)

        plan.risk_assessment = self._assess_risks(plan)
        return plan

    # ------------------------------------------------------------------
    # Validate Plan
    # ------------------------------------------------------------------

    async def validate_plan(self, plan: InfrastructurePlan) -> list[str]:
        """Validate plan against known AWS constraints."""
        warnings: list[str] = []

        if not plan.capability_mappings:
            warnings.append("Plan contains no capability mappings")

        if plan.provider != Provider.AWS:
            warnings.append(f"Plan provider mismatch: expected AWS, got {plan.provider}")

        return warnings

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    async def apply(
        self,
        plan: InfrastructurePlan,
        target: ExecutionTarget,
    ) -> ChangeSet:
        """
        Execute plan. PLAN_ONLY returns empty. SIMULATED+FAKECLOUD uses boto3.
        """
        if target.mode == ExecutionMode.PLAN_ONLY:
            return ChangeSet(provider=Provider.AWS, platform=target.platform, iac_tool="OPENTOFU")

        if target.mode == ExecutionMode.SIMULATED and target.target_type == ExecutionTargetType.FAKECLOUD:
            return await self._apply_fakecloud(plan, target)

        return ChangeSet(provider=Provider.AWS, platform=target.platform, iac_tool="OPENTOFU")

    async def _apply_fakecloud(self, plan: InfrastructurePlan, target: ExecutionTarget) -> ChangeSet:
        """Real boto3 S3 operations against fakecloud."""
        import boto3

        endpoint = target.endpoint or "http://localhost:4566"
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )

        changes: list[ChangeItem] = []
        for mapping in plan.capability_mappings:
            if mapping.resource_type == "AWS::S3::Bucket":
                bucket_name = mapping.resource_properties.get("bucket_name", f"infra-again-{plan.plan_id[:8]}")
                try:
                    s3.create_bucket(Bucket=bucket_name)
                    changes.append(ChangeItem(
                        action=ChangeAction.CREATE,
                        resource_type="AWS::S3::Bucket",
                        resource_id=bucket_name,
                        properties={"bucket_name": bucket_name, "endpoint": endpoint},
                    ))
                except Exception as e:
                    changes.append(ChangeItem(
                        action=ChangeAction.CREATE,
                        resource_type="AWS::S3::Bucket",
                        resource_id=bucket_name,
                        properties={"error": str(e)},
                        is_destructive=False,
                    ))

            elif mapping.resource_type == "AWS::S3::Object":
                bucket = mapping.resource_properties.get("bucket", "")
                key = mapping.resource_properties.get("key", "test-object")
                body = mapping.resource_properties.get("body", "hello-again")
                try:
                    s3.put_object(Bucket=bucket, Key=key, Body=body)
                    changes.append(ChangeItem(
                        action=ChangeAction.CREATE,
                        resource_type="AWS::S3::Object",
                        resource_id=f"{bucket}/{key}",
                        properties={"bucket": bucket, "key": key},
                    ))
                except Exception as e:
                    changes.append(ChangeItem(
                        action=ChangeAction.CREATE,
                        resource_type="AWS::S3::Object",
                        resource_id=f"{bucket}/{key}",
                        properties={"error": str(e)},
                    ))

        return ChangeSet(changes=changes, provider=Provider.AWS, platform=target.platform, iac_tool="DIRECT")

    # ------------------------------------------------------------------
    # Observe
    # ------------------------------------------------------------------

    async def observe(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Observe actual infrastructure state."""
        if target.mode == ExecutionMode.PLAN_ONLY:
            return {"observed": {}, "note": "PLAN_ONLY — no real observation"}

        if target.mode == ExecutionMode.SIMULATED and target.target_type == ExecutionTargetType.FAKECLOUD:
            return await self._observe_fakecloud(target, resource_ids)

        return {"observed": {}, "status": TruthStatus.NOT_CONFIGURED.value}

    async def _observe_fakecloud(
        self, target: ExecutionTarget, resource_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Query fakecloud for actual S3 state."""
        import boto3

        endpoint = target.endpoint or "http://localhost:4566"
        try:
            s3 = boto3.client(
                "s3", endpoint_url=endpoint,
                aws_access_key_id="test", aws_secret_access_key="test",
                region_name="us-east-1",
            )
            resp = s3.list_buckets()
            buckets = {b["Name"]: {"name": b["Name"], "creation_date": str(b.get("CreationDate", ""))}
                       for b in resp.get("Buckets", [])}

            if resource_ids:
                buckets = {k: v for k, v in buckets.items() if k in resource_ids}

            return {
                "observed": buckets,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "resource_count": len(buckets),
            }
        except Exception as e:
            return {
                "observed": {},
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(
        self,
        desired: dict[str, Any],
        observed: dict[str, Any],
    ) -> list[ValidationResult]:
        """Compare desired vs observed state."""
        results: list[ValidationResult] = []
        observed_data = observed.get("observed", observed)

        for key, desired_state in desired.items():
            obs_state = observed_data.get(key) if isinstance(observed_data, dict) else None
            matches = obs_state is not None

            result = ValidationResult(
                resource_id=key,
                desired_state=desired_state if isinstance(desired_state, dict) else {"value": desired_state},
                observed_state=obs_state,
                matches=matches,
                drift_detected=not matches,
                drift_details="" if matches else f"Resource {key} not found in observed state",
                observed_at=datetime.now(timezone.utc),
            )
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Destroy
    # ------------------------------------------------------------------

    async def destroy(
        self,
        target: ExecutionTarget,
        resource_ids: list[str] | None = None,
    ) -> ChangeSet:
        """Destroy resources — gated by ownership policy upstream."""
        if target.mode == ExecutionMode.PLAN_ONLY:
            return ChangeSet(provider=Provider.AWS)

        if target.mode == ExecutionMode.SIMULATED and target.target_type == ExecutionTargetType.FAKECLOUD:
            return await self._destroy_fakecloud(target, resource_ids or [])

        return ChangeSet(provider=Provider.AWS)

    async def _destroy_fakecloud(
        self, target: ExecutionTarget, resource_ids: list[str],
    ) -> ChangeSet:
        """Delete S3 buckets from fakecloud."""
        import boto3

        endpoint = target.endpoint or "http://localhost:4566"
        s3 = boto3.client(
            "s3", endpoint_url=endpoint,
            aws_access_key_id="test", aws_secret_access_key="test",
            region_name="us-east-1",
        )

        changes: list[ChangeItem] = []
        for rid in resource_ids:
            try:
                s3.delete_bucket(Bucket=rid)
                changes.append(ChangeItem(
                    action=ChangeAction.DELETE, resource_type="AWS::S3::Bucket",
                    resource_id=rid, is_destructive=True))
            except Exception as e:
                changes.append(ChangeItem(
                    action=ChangeAction.DELETE, resource_type="AWS::S3::Bucket",
                    resource_id=rid, properties={"error": str(e)}))

        return ChangeSet(changes=changes, provider=Provider.AWS, platform=target.platform)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def probe_status(self) -> TruthStatus:
        """Truthfully report AWS/fakecloud connection status."""
        import os

        # Check fakecloud first
        try:
            import httpx
            resp = httpx.get("http://localhost:4566/_fakecloud/health", timeout=2.0)
            if resp.status_code == 200:
                return TruthStatus.READY
        except Exception:
            pass

        # Check real AWS credentials
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            return TruthStatus.READY
        if os.path.exists(os.path.expanduser("~/.aws/credentials")):
            return TruthStatus.READY

        return TruthStatus.NOT_CONFIGURED

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    async def get_capabilities(self) -> list[ProviderCapability]:
        """Return currently known AWS capabilities."""
        capabilities: list[ProviderCapability] = []
        for mapping in AWS_CAPABILITY_MAP:
            capabilities.append(ProviderCapability(
                capability_id=f"aws-{mapping.aws_resource_type.lower().replace('::', '-')}",
                provider=Provider.AWS,
                resource_type=mapping.aws_resource_type,
                category=mapping.requirement_key,
                properties_schema={},
                lifecycle="CAPABILITY_MAPPED",
                provenance_url=f"https://docs.aws.amazon.com/{mapping.aws_service.lower()}",
            ))
        return capabilities

    async def map_capability(
        self,
        requirement: CapabilityRequirement,
    ) -> CapabilityMapping | None:
        """Map a provider-neutral requirement to an AWS resource."""
        mapping = self._map_to_aws(requirement)
        return mapping

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _map_to_aws(self, requirement: CapabilityRequirement) -> CapabilityMapping | None:
        """Internal: map requirement to AWS resource type."""
        for aws_map in AWS_CAPABILITY_MAP:
            if aws_map.requirement_key == requirement.name or aws_map.requirement_key in str(requirement.properties):
                return CapabilityMapping(
                    requirement=requirement,
                    provider=Provider.AWS,
                    resource_type=aws_map.aws_resource_type,
                    resource_properties=requirement.properties,
                    confidence=0.9,
                )
        return None

    def _assess_risks(self, plan: InfrastructurePlan) -> str:
        """Assess risks for the plan."""
        risks: list[str] = []
        if not plan.capability_mappings:
            risks.append("No resources mapped — plan may be incomplete")
        risks.append("PLAN_ONLY mode — no real infrastructure changes")
        return "; ".join(risks) if risks else "No significant risks identified"
