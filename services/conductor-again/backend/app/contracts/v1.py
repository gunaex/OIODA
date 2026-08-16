"""
Canonical AGAIN-ECOSYSTEM v1 contract bindings (E8-A).
Mirrors contracts/vendored/v1/schemas/*.json exactly. Canonical authority is
AGAIN-ECOSYSTEM — see vendored/manifest.json.
"""

from typing import Any, Literal, Optional

from pydantic import Field

from app.contracts.base import CanonicalModel

Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class OSMessageEnvelope(CanonicalModel):
    _contract_name = "OSMessageEnvelope"

    envelopeId: str
    correlationId: str
    causationId: Optional[str] = None
    messageType: str
    contractVersion: Optional[str] = None
    source: str
    idempotencyKey: Optional[str] = None
    timestamp: str
    payload: dict[str, Any]
    traceContext: Optional[dict[str, Any]] = None


class BusinessIntent(CanonicalModel):
    _contract_name = "BusinessIntent"

    businessIntentId: str
    correlationId: str
    title: str
    description: str
    priority: Priority
    requester: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    createdAt: str


class DeliveryWorkPackage(CanonicalModel):
    _contract_name = "DeliveryWorkPackage"

    workPackageId: str
    correlationId: str
    businessIntentId: str
    title: str
    description: Optional[str] = None
    priority: Priority
    state: Literal[
        "DRAFT", "PLANNED", "IN_PROGRESS", "WAITING_FOR_HUMAN", "BLOCKED",
        "ENGINEERING_COMPLETE", "INFRA_READY", "QA_PENDING", "QA_APPROVED",
        "READY_FOR_DELIVERY", "NOT_READY", "CANCELLED",
    ]
    assignments: dict[str, bool]
    dependencies: list[str] = Field(default_factory=list)
    engineeringContext: Optional[dict[str, Any]] = None
    infrastructureContext: Optional[dict[str, Any]] = None
    qaContext: Optional[dict[str, Any]] = None
    createdAt: str
    updatedAt: Optional[str] = None


class PMStatus(CanonicalModel):
    _contract_name = "PMStatus"

    pmStatusId: str
    correlationId: str
    workPackageId: str
    projectId: Optional[str] = None
    projectStatus: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BLOCKED", "CANCELLED"]
    milestone: Optional[str] = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    estimatedCompletion: Optional[str] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    reportedAt: str


class EngineeringWorkPackage(CanonicalModel):
    _contract_name = "EngineeringWorkPackage"

    engineeringWorkPackageId: str
    correlationId: str
    workPackageId: str
    requirements: str
    constraints: Optional[dict[str, Any]] = None
    targetRepo: Optional[str] = None
    createdAt: str


class EngineeringResult(CanonicalModel):
    _contract_name = "EngineeringResult"

    engineeringResultId: str
    correlationId: str
    workPackageId: str
    status: Literal["SUCCESS", "PARTIAL", "FAILED", "REPAIRED"]
    repo: str
    branch: str
    commit: str
    pipeline: dict[str, Any]
    evidence: list[dict[str, Any]]
    artifacts: Optional[dict[str, Any]] = None
    completedAt: str


class InfrastructureRequest(CanonicalModel):
    _contract_name = "InfrastructureRequest"

    infrastructureRequestId: str
    correlationId: str
    workPackageId: str
    engineeringResultId: str
    requirements: dict[str, Any]
    artifacts: Optional[dict[str, Any]] = None
    createdAt: str


class InfrastructureResult(CanonicalModel):
    _contract_name = "InfrastructureResult"

    infrastructureResultId: str
    correlationId: str
    workPackageId: str
    infrastructureRequestId: str
    status: Literal["SUCCESS", "PARTIAL", "FAILED"]
    provider: Literal["AWS", "GCP", "ON_PREM"]
    platform: Literal["KUBERNETES", "OPENSHIFT", "NATIVE_VM", "BARE_METAL"]
    providerDetail: Optional[dict[str, Any]] = None
    endpoints: list[dict[str, Any]] = Field(default_factory=list)
    pipeline: Optional[dict[str, Any]] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    completedAt: str


class QARequest(CanonicalModel):
    _contract_name = "QARequest"

    qaRequestId: str
    correlationId: str
    workPackageId: str
    releaseCandidate: dict[str, Any]
    acceptanceCriteria: dict[str, Any]
    engineeringResultReference: Optional[str] = None
    infrastructureResultReference: Optional[str] = None
    knownIssues: list[dict[str, Any]] = Field(default_factory=list)
    recommendedRegressionAreas: list[str] = Field(default_factory=list)
    createdAt: str


class QAResult(CanonicalModel):
    _contract_name = "QAResult"

    qaResultId: str
    correlationId: str
    workPackageId: str
    qaRequestId: str
    status: Literal["COMPLETED", "PARTIAL", "FAILED"]
    testSummary: dict[str, int]
    defects: list[dict[str, Any]] = Field(default_factory=list)
    qualityGate: Literal["APPROVED", "REJECTED", "PENDING"]
    acceptanceValidation: Optional[dict[str, Any]] = None
    recommendedRegressionAreas: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]]
    completedAt: str


class DeliveryReadinessResult(CanonicalModel):
    _contract_name = "DeliveryReadinessResult"

    deliveryReadinessResultId: str
    correlationId: str
    workPackageId: str
    decision: Literal["READY_FOR_DELIVERY", "NOT_READY"]
    reason: Optional[str] = None
    aggregatedEvidence: dict[str, Any]
    specialistResults: Optional[dict[str, Any]] = None
    decidedBy: Literal["conductor-main"] = "conductor-main"
    decidedAt: str
