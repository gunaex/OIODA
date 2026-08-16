"""
Canonical contract conformance tests.

Validates that INFRA-AGAIN types conform to the AGAIN-ECOSYSTEM v1 contracts:
- InfrastructureRequest
- InfrastructureResult
- OSMessageEnvelope

Canonical commit: 24337c358a8db1712294f32729a5e25f1ca864d5
"""

import json
import os
from datetime import datetime, timezone

import pytest

from infra_again.contracts import (
    EvidenceItem,
    EvidenceType,
    InfrastructureRequest,
    InfrastructureRequirements,
    InfrastructureResult,
    InfrastructureStatus,
    OSMessageEnvelope,
    MessageType,
    Platform,
    Provider,
    SourceOS,
)


# ---------------------------------------------------------------------------
# InfrastructureRequest conformance
# ---------------------------------------------------------------------------


class TestInfrastructureRequestConforms:
    """Validate InfrastructureRequest against canonical schema."""

    def test_all_required_fields_present(self):
        req = InfrastructureRequest(
            infrastructureRequestId="ir-001",
            correlationId="e2e-golden-001",
            workPackageId="wp-001",
            engineeringResultId="er-001",
            requirements=InfrastructureRequirements(),
        )
        assert req.infrastructureRequestId == "ir-001"
        assert req.correlationId == "e2e-golden-001"
        assert req.workPackageId == "wp-001"
        assert req.engineeringResultId == "er-001"
        assert req.createdAt is not None

    def test_provider_hint_enum(self):
        req = InfrastructureRequest(
            infrastructureRequestId="ir-001",
            correlationId="corr-001",
            workPackageId="wp-001",
            engineeringResultId="er-001",
            requirements=InfrastructureRequirements(providerHint=Provider.AWS),
        )
        assert req.requirements.providerHint == Provider.AWS

    def test_created_at_is_datetime(self):
        req = InfrastructureRequest(
            infrastructureRequestId="ir-001",
            correlationId="corr-001",
            workPackageId="wp-001",
            engineeringResultId="er-001",
            requirements=InfrastructureRequirements(),
        )
        assert isinstance(req.createdAt, datetime)

    def test_roundtrip_serialization(self):
        req = InfrastructureRequest(
            infrastructureRequestId="ir-001",
            correlationId="e2e-golden-001",
            workPackageId="wp-001",
            engineeringResultId="er-001",
            requirements=InfrastructureRequirements(
                providerHint=Provider.AWS,
            ),
        )
        data = req.model_dump(mode="json")
        assert data["infrastructureRequestId"] == "ir-001"
        # Re-parse
        req2 = InfrastructureRequest.model_validate(data)
        assert req2.infrastructureRequestId == req.infrastructureRequestId

    def test_provider_neutral_intent_no_aws_skus(self):
        """Validate that requirements are provider-neutral, not AWS-specific."""
        req = InfrastructureRequest(
            infrastructureRequestId="ir-001",
            correlationId="corr-001",
            workPackageId="wp-001",
            engineeringResultId="er-001",
            requirements=InfrastructureRequirements(),
        )
        data = req.model_dump_json()
        # Must NOT contain AWS-specific terms
        assert "db.r6g" not in data
        assert "m7i" not in data
        assert "n2-standard" not in data
        assert "EKS" not in data


# ---------------------------------------------------------------------------
# InfrastructureResult conformance
# ---------------------------------------------------------------------------


class TestInfrastructureResultConforms:
    """Validate InfrastructureResult against canonical schema."""

    def test_all_required_fields_present(self):
        result = InfrastructureResult(
            correlationId="e2e-golden-001",
            workPackageId="wp-001",
            infrastructureRequestId="ir-001",
            status=InfrastructureStatus.SUCCESS,
            provider=Provider.AWS,
            platform=Platform.KUBERNETES,
        )
        assert result.infrastructureResultId is not None
        assert result.correlationId == "e2e-golden-001"
        assert result.status == InfrastructureStatus.SUCCESS

    def test_evidence_structure(self):
        result = InfrastructureResult(
            correlationId="corr-001",
            workPackageId="wp-001",
            infrastructureRequestId="ir-001",
            status=InfrastructureStatus.SUCCESS,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            evidence=[
                EvidenceItem(
                    type=EvidenceType.ARCHITECTURE_PLAN,
                    source="infrastructure-again",
                    reference="plan-001",
                    summary="Test plan",
                    timestamp=datetime.now(timezone.utc),
                ),
            ],
        )
        assert len(result.evidence) == 1
        assert result.evidence[0].type == EvidenceType.ARCHITECTURE_PLAN

    def test_provider_platform_separation(self):
        """Validate that Provider and Platform are separate fields."""
        result = InfrastructureResult(
            correlationId="corr-001",
            workPackageId="wp-001",
            infrastructureRequestId="ir-001",
            status=InfrastructureStatus.SUCCESS,
            provider=Provider.AWS,
            platform=Platform.OPENSHIFT,
        )
        # Provider and platform are independent
        assert result.provider == Provider.AWS
        assert result.platform == Platform.OPENSHIFT
        # OCP is platform, not provider
        assert result.platform != "AWS"


# ---------------------------------------------------------------------------
# OSMessageEnvelope conformance
# ---------------------------------------------------------------------------


class TestOSMessageEnvelopeConforms:
    """Validate OSMessageEnvelope against canonical schema."""

    def test_all_required_fields_present(self):
        env = OSMessageEnvelope(
            correlationId="e2e-golden-001",
            messageType=MessageType.INFRASTRUCTURE_RESULT,
            source=SourceOS.INFRASTRUCTURE_AGAIN,
            payload={"status": "SUCCESS"},
        )
        assert env.envelopeId is not None
        assert env.correlationId == "e2e-golden-001"
        assert env.source == SourceOS.INFRASTRUCTURE_AGAIN
        assert env.contractVersion == "1.0.0"

    def test_idempotency_key(self):
        env = OSMessageEnvelope(
            correlationId="corr-001",
            messageType=MessageType.INFRASTRUCTURE_RESULT,
            source=SourceOS.INFRASTRUCTURE_AGAIN,
            payload={},
            idempotencyKey="idem-abc",
        )
        assert env.idempotencyKey == "idem-abc"

    def test_causation_chain(self):
        env = OSMessageEnvelope(
            correlationId="corr-001",
            causationId="env-previous",
            messageType=MessageType.INFRASTRUCTURE_RESULT,
            source=SourceOS.INFRASTRUCTURE_AGAIN,
            payload={},
        )
        assert env.causationId == "env-previous"
