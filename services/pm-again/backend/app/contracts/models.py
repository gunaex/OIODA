"""Pydantic v2 runtime bindings for the two canonical contracts PM Again is
authority-adjacent for (DeliveryWorkPackage as consumer, PMStatus as
producer). These are convenience/typing layers only — the vendored JSON
Schemas in vendored/v1/schemas/ remain the actual source of truth, and
CanonicalContractValidator is what enforces conformance. Do not add fields
here that aren't in the canonical schema (NO_PARALLEL_CONTRACT_AUTHORITY)."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkPackageState(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    BLOCKED = "BLOCKED"
    ENGINEERING_COMPLETE = "ENGINEERING_COMPLETE"
    INFRA_READY = "INFRA_READY"
    QA_PENDING = "QA_PENDING"
    QA_APPROVED = "QA_APPROVED"
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY"
    NOT_READY = "NOT_READY"
    CANCELLED = "CANCELLED"


class WorkPackageAssignments(BaseModel):
    pm: Optional[bool] = None
    engineering: Optional[bool] = None
    infrastructure: Optional[bool] = None
    qa: Optional[bool] = None


class EngineeringContext(BaseModel):
    requirements: Optional[str] = None
    constraints: Optional[dict] = None


class InfrastructureContext(BaseModel):
    database: Optional[dict] = None
    applicationRuntime: Optional[dict] = None


class QAContext(BaseModel):
    businessAcceptanceCriteria: Optional[list[str]] = None
    technicalAcceptanceCriteria: Optional[list[str]] = None


class DeliveryWorkPackage(BaseModel):
    workPackageId: str
    correlationId: str
    businessIntentId: str
    title: str
    description: Optional[str] = None
    priority: Priority
    state: WorkPackageState
    assignments: WorkPackageAssignments
    dependencies: Optional[list[str]] = None
    engineeringContext: Optional[EngineeringContext] = None
    infrastructureContext: Optional[InfrastructureContext] = None
    qaContext: Optional[QAContext] = None
    createdAt: datetime
    updatedAt: Optional[datetime] = None


class ProjectStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class PMStatusTask(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    assignedTo: Optional[str] = None


class PMStatusBlocker(BaseModel):
    id: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None


class PMStatusDependency(BaseModel):
    workPackageId: Optional[str] = None
    status: Optional[str] = None


class PMStatusEvidence(BaseModel):
    type: Optional[str] = None
    source: Optional[str] = None
    reference: Optional[str] = None
    summary: Optional[str] = None


class PMStatus(BaseModel):
    pmStatusId: str
    correlationId: str
    workPackageId: str
    projectId: Optional[str] = None
    projectStatus: ProjectStatus
    milestone: Optional[str] = None
    tasks: Optional[list[PMStatusTask]] = None
    blockers: Optional[list[PMStatusBlocker]] = None
    dependencies: Optional[list[PMStatusDependency]] = None
    estimatedCompletion: Optional[datetime] = None
    evidence: Optional[list[PMStatusEvidence]] = None
    reportedAt: datetime


__all__ = ["DeliveryWorkPackage", "PMStatus", "ProjectStatus", "Priority", "WorkPackageState"]
