"""
Conductor Again — Core Orchestration Domain (E8-B)

Master-DB tables owned by Conductor Main. These store orchestration
METADATA and canonical-contract SNAPSHOTS (payload_json) — never specialist
domain data (no source code, no test corpus, no infra state, no AI provider
credentials). Every aggregate is tenant-scoped (tenant_id) per E8-C.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import MasterBase


def _uuid():
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════
# BusinessIntent — Conductor-owned orchestration metadata
# ═══════════════════════════════════════════════════════════

class OrchestrationBusinessIntent(MasterBase):
    __tablename__ = "orch_business_intents"

    id = Column(String(36), primary_key=True, default=_uuid)
    business_intent_id = Column(String(100), unique=True, nullable=False, index=True)  # canonical businessIntentId
    tenant_id = Column(String(100), nullable=False, index=True)
    project_slug = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    requester = Column(String(255), default="")
    tags = Column(JSON, default=list)
    # Internal richer state machine (§13). Canonical contract carries no status field
    # of its own for BusinessIntent — this is Conductor's orchestration metadata.
    status = Column(String(50), default="RECEIVED", index=True)
    # RECEIVED, ANALYZING, PLANNED, IN_EXECUTION, BLOCKED, READY_FOR_REVIEW, COMPLETED, FAILED
    canonical_payload = Column(JSON, nullable=False)  # last-validated canonical BusinessIntent snapshot
    created_by = Column(String(255), default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    runs = relationship("DeliveryRun", back_populates="business_intent", cascade="all, delete-orphan")


# ═══════════════════════════════════════════════════════════
# DeliveryRun — the orchestration aggregate (§21)
# ═══════════════════════════════════════════════════════════

class DeliveryRun(MasterBase):
    __tablename__ = "orch_delivery_runs"

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    business_intent_id = Column(String(36), ForeignKey("orch_business_intents.id"), nullable=False, index=True)
    work_package_id = Column(String(100), nullable=True, index=True)  # canonical DeliveryWorkPackage.workPackageId
    correlation_id = Column(String(100), nullable=False, index=True)
    # Deterministic stage flow (§22)
    current_stage = Column(String(50), default="INTENT", index=True)
    # INTENT, PLAN, ENGINEERING, INFRASTRUCTURE, QA, DELIVERY_READINESS, COMPLETE
    status = Column(String(50), default="IN_PROGRESS", index=True)
    # IN_PROGRESS, BLOCKED, READY_FOR_DELIVERY, NOT_READY, CANCELLED
    work_package_payload = Column(JSON, nullable=True)  # canonical DeliveryWorkPackage snapshot
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    business_intent = relationship("OrchestrationBusinessIntent", back_populates="runs")
    dispatches = relationship("SpecialistDispatch", back_populates="run", cascade="all, delete-orphan")
    results = relationship("SpecialistResult", back_populates="run", cascade="all, delete-orphan")
    readiness_decisions = relationship("ReadinessDecision", back_populates="run", cascade="all, delete-orphan")


# ═══════════════════════════════════════════════════════════
# Specialist dispatch — outbound side of the boundary (§39, §45, §46)
# ═══════════════════════════════════════════════════════════

class SpecialistDispatch(MasterBase):
    """A single outbound dispatch to a specialist adapter. Idempotency-keyed."""
    __tablename__ = "orch_specialist_dispatches"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_dispatch_idempotency_key"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("orch_delivery_runs.id"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    specialist = Column(String(50), nullable=False, index=True)  # ENGINEERING, INFRASTRUCTURE, QA, PM
    contract_name = Column(String(100), nullable=False)  # EngineeringWorkPackage, InfrastructureRequest, QARequest
    canonical_id = Column(String(100), nullable=False)  # e.g. engineeringWorkPackageId
    correlation_id = Column(String(100), nullable=False, index=True)
    causation_id = Column(String(100), nullable=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    request_payload = Column(JSON, nullable=False)
    adapter_status = Column(String(50), nullable=False)  # REAL_RUNTIME, FROZEN_RUNTIME, HARNESS, UNAVAILABLE
    dispatch_status = Column(String(50), default="PENDING")  # PENDING, SENT, ACKNOWLEDGED, FAILED
    response_payload = Column(JSON, nullable=True)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    sent_at = Column(DateTime, nullable=True)

    run = relationship("DeliveryRun", back_populates="dispatches")


# ═══════════════════════════════════════════════════════════
# Specialist result intake — inbound side of the boundary (§20)
# ═══════════════════════════════════════════════════════════

class SpecialistResult(MasterBase):
    __tablename__ = "orch_specialist_results"

    id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), ForeignKey("orch_delivery_runs.id"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    specialist = Column(String(50), nullable=False, index=True)  # ENGINEERING, INFRASTRUCTURE, QA, PM
    contract_name = Column(String(100), nullable=False)  # EngineeringResult, InfrastructureResult, QAResult, PMStatus
    canonical_id = Column(String(100), nullable=False)
    correlation_id = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False)  # the specialist's own status/qualityGate value
    payload = Column(JSON, nullable=False)  # full validated canonical result snapshot
    evidence_refs = Column(JSON, default=list)
    received_at = Column(DateTime, default=_utcnow)

    run = relationship("DeliveryRun", back_populates="results")


# ═══════════════════════════════════════════════════════════
# Delivery Readiness decision record (E8-F, §51)
# ═══════════════════════════════════════════════════════════

class ReadinessDecision(MasterBase):
    __tablename__ = "orch_readiness_decisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    decision_id = Column(String(100), unique=True, nullable=False, index=True)  # deliveryReadinessResultId
    run_id = Column(String(36), ForeignKey("orch_delivery_runs.id"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    correlation_id = Column(String(100), nullable=False, index=True)
    policy_version = Column(String(50), default="e8-readiness-policy-v1")
    decision = Column(String(50), nullable=False)  # READY_FOR_DELIVERY, NOT_READY
    reason_code = Column(String(100), nullable=False)
    reason = Column(Text, default="")
    inputs_ref = Column(JSON, default=dict)
    evidence_refs = Column(JSON, default=list)
    canonical_payload = Column(JSON, nullable=False)  # validated DeliveryReadinessResult snapshot
    decided_at = Column(DateTime, default=_utcnow)

    run = relationship("DeliveryRun", back_populates="readiness_decisions")


# ═══════════════════════════════════════════════════════════
# Tenant-scoping for existing ProjectRegistry (E8-C, §29)
# ═══════════════════════════════════════════════════════════
# NOTE: tenant_id is added to ProjectRegistry via a lightweight column added in
# app/models.py (see ProjectRegistry.tenant_id) rather than duplicated here.
