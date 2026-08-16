"""
Canonical contract type adapters for INFRA-AGAIN.

These Pydantic models conform to the AGAIN-ECOSYSTEM v1 contracts:
- InfrastructureRequest
- InfrastructureResult
- OSMessageEnvelope

See: AGAIN-ECOSYSTEM/contracts/v1/schemas/
Canonical commit: 24337c358a8db1712294f32729a5e25f1ca864d5
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums matching canonical contracts
# ---------------------------------------------------------------------------


class Availability(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Provider(str, Enum):
    AWS = "AWS"
    GCP = "GCP"
    ON_PREM = "ON_PREM"


class Platform(str, Enum):
    KUBERNETES = "KUBERNETES"
    OPENSHIFT = "OPENSHIFT"
    NATIVE_VM = "NATIVE_VM"
    BARE_METAL = "BARE_METAL"


class InfrastructureStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class MessageType(str, Enum):
    BUSINESS_INTENT = "BusinessIntent"
    DELIVERY_WORK_PACKAGE = "DeliveryWorkPackage"
    PM_STATUS = "PMStatus"
    ENGINEERING_WORK_PACKAGE = "EngineeringWorkPackage"
    ENGINEERING_RESULT = "EngineeringResult"
    INFRASTRUCTURE_REQUEST = "InfrastructureRequest"
    INFRASTRUCTURE_RESULT = "InfrastructureResult"
    QA_REQUEST = "QARequest"
    QA_RESULT = "QAResult"
    DELIVERY_READINESS_RESULT = "DeliveryReadinessResult"


class SourceOS(str, Enum):
    CONDUCTOR_MAIN = "conductor-main"
    PM_AGAIN = "pm-again"
    IDEA_TO_CODE = "idea-to-code"
    INFRASTRUCTURE_AGAIN = "infrastructure-again"
    QA_AGAIN = "qa-again"
    LOCAL_AI_CONTROL_CENTER = "local-ai-control-center"


class EvidenceType(str, Enum):
    ARCHITECTURE_PLAN = "ARCHITECTURE_PLAN"
    PLAN_APPROVAL = "PLAN_APPROVAL"
    IAC_OUTPUT = "IAC_OUTPUT"
    VALIDATION_RESULTS = "VALIDATION_RESULTS"


class IaCTool(str, Enum):
    OPENTOFU = "OPENTOFU"
    TERRAFORM = "TERRAFORM"


# ---------------------------------------------------------------------------
# InfrastructureRequest (canonical)
# ---------------------------------------------------------------------------


class DatabaseBackup(BaseModel):
    required: bool = False
    retention: str | None = None
    schedule: str | None = None


class DatabaseEncryption(BaseModel):
    atRest: bool = False
    inTransit: bool = False


class DatabaseRequirement(BaseModel):
    engine: str | None = None
    version: str | None = None
    availability: Availability | None = None
    backup: DatabaseBackup | None = None
    encryption: DatabaseEncryption | None = None
    storage: str | None = None


class ApplicationRuntimeRequirement(BaseModel):
    containerized: bool = False
    replicas: int = 1
    https: bool = False
    healthCheckPath: str | None = None
    port: int | None = None


class NetworkingRequirement(BaseModel):
    public: bool = False
    httpsOnly: bool = False
    domain: str | None = None


class InfrastructureRequirements(BaseModel):
    """Provider-neutral infrastructure requirements."""
    database: DatabaseRequirement | None = None
    applicationRuntime: ApplicationRuntimeRequirement | None = None
    networking: NetworkingRequirement | None = None
    providerHint: Provider | None = None


class Artifacts(BaseModel):
    dockerImage: str | None = None
    helmChart: str | None = None
    manifests: str | None = None


class InfrastructureRequest(BaseModel):
    """Canonical InfrastructureRequest from Conductor Main."""
    infrastructureRequestId: str
    correlationId: str
    workPackageId: str
    engineeringResultId: str
    requirements: InfrastructureRequirements
    artifacts: Artifacts | None = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# InfrastructureResult (canonical)
# ---------------------------------------------------------------------------


class ProviderDetail(BaseModel):
    region: str | None = None
    account: str | None = None
    resources: list[dict[str, Any]] = Field(default_factory=list)


class Endpoint(BaseModel):
    name: str
    url: str
    type: str = "HTTP"


class PipelineStage(BaseModel):
    status: str | None = None


class ProvisionStage(PipelineStage):
    iacReference: str | None = None
    tool: IaCTool | None = None


class ConfigureStage(PipelineStage):
    tool: str | None = None


class ValidateStage(PipelineStage):
    healthCheckPassed: bool | None = None
    connectivityVerified: bool | None = None
    httpsVerified: bool | None = None
    backupVerified: bool | None = None


class Pipeline(BaseModel):
    model_config = {"protected_namespaces": ()}

    architecturePlan: PipelineStage | None = None
    provision: ProvisionStage | None = None
    configure: ConfigureStage | None = None
    deploy: PipelineStage | None = None
    validate_: ValidateStage | None = Field(default=None, alias="validate")


class EvidenceItem(BaseModel):
    type: EvidenceType
    source: str
    reference: str
    summary: str | None = None
    timestamp: datetime | None = None


class InfrastructureResult(BaseModel):
    """Canonical InfrastructureResult returned to Conductor Main."""
    infrastructureResultId: str = Field(default_factory=lambda: f"ifr-{uuid4().hex[:8]}")
    correlationId: str
    workPackageId: str
    infrastructureRequestId: str
    status: InfrastructureStatus
    provider: Provider
    platform: Platform
    providerDetail: ProviderDetail | None = None
    endpoints: list[Endpoint] = Field(default_factory=list)
    pipeline: Pipeline | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    completedAt: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# OSMessageEnvelope (canonical)
# ---------------------------------------------------------------------------


class TraceContext(BaseModel):
    traceId: str | None = None
    spanId: str | None = None


class OSMessageEnvelope(BaseModel):
    """Standard envelope for all inter-OS messages in AGAIN Ecosystem."""
    envelopeId: str = Field(default_factory=lambda: f"env-{uuid4().hex[:12]}")
    correlationId: str
    causationId: str | None = None
    messageType: MessageType
    contractVersion: str = "1.0.0"
    source: SourceOS
    idempotencyKey: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict[str, Any]
    traceContext: TraceContext | None = None
