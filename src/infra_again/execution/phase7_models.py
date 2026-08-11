"""Phase 7 Execution Models — bridges ImplementationPlan to controlled execution.

These models are distinct from Phase 2 execution (orchestrator.py).
They reference ImplementationTask ids, not raw infrastructure changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime, timezone


# ===========================================================================
# Enums
# ===========================================================================

class ExecutionPackageStatus(str, Enum):
    DRAFT = "DRAFT"
    PREFLIGHT = "PREFLIGHT"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VALIDATING = "VALIDATING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"
    CANCELLED = "CANCELLED"


class ExecutionTaskStatus(str, Enum):
    PLANNED = "PLANNED"
    PREFLIGHT = "PREFLIGHT"
    READY = "READY"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    LEASED = "LEASED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VALIDATING = "VALIDATING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"
    CANCELLED = "CANCELLED"


class ExecutionFidelity(str, Enum):
    PLAN_ONLY = "PLAN_ONLY"
    SIMULATED = "SIMULATED"
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    LOCAL_PRIVATE_CLOUD = "LOCAL_PRIVATE_CLOUD"
    SANDBOX = "SANDBOX"
    CONTROLLED_REAL = "CONTROLLED_REAL"
    PRODUCTION = "PRODUCTION"


class PreflightStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PolicyVerdict(str, Enum):
    ALLOW = "ALLOW"
    ASK = "ASK"
    BLOCK = "BLOCK"


class EvidenceType(str, Enum):
    COMMAND_OUTPUT = "COMMAND_OUTPUT"
    API_RESPONSE = "API_RESPONSE"
    CONFIG_SNAPSHOT = "CONFIG_SNAPSHOT"
    TEST_RESULT = "TEST_RESULT"
    LOG = "LOG"
    ARCHITECTURE_DIFF = "ARCHITECTURE_DIFF"


class SourceTruth(str, Enum):
    GENERATED = "GENERATED"
    SIMULATED = "SIMULATED"
    LOCAL_OBSERVED = "LOCAL_OBSERVED"
    REPLAYED = "REPLAYED"
    REMOTE_OBSERVED = "REMOTE_OBSERVED"


class VerificationResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class TaskReadiness(str, Enum):
    READY_LOCAL = "READY_LOCAL"
    READY_SIMULATED = "READY_SIMULATED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    BLOCKED_UNSUPPORTED = "BLOCKED_UNSUPPORTED"
    BLOCKED_TARGET = "BLOCKED_TARGET"
    BLOCKED_PLAN_INVALID = "BLOCKED_PLAN_INVALID"
    FUTURE_REAL_EXECUTION = "FUTURE_REAL_EXECUTION"
    MANUAL = "MANUAL"


class ActionType(str, Enum):
    GENERATE_IAC = "GENERATE_IAC"
    VALIDATE_IAC = "VALIDATE_IAC"
    PLAN_IAC = "PLAN_IAC"
    APPLY_LOCAL_IAC = "APPLY_LOCAL_IAC"
    CREATE_LOCAL_NAMESPACE = "CREATE_LOCAL_NAMESPACE"
    DEPLOY_LOCAL_WORKLOAD = "DEPLOY_LOCAL_WORKLOAD"
    OBSERVE_RESOURCE = "OBSERVE_RESOURCE"
    VALIDATE_RESOURCE = "VALIDATE_RESOURCE"
    DESTROY_RUN_OWNED_RESOURCE = "DESTROY_RUN_OWNED_RESOURCE"


# ===========================================================================
# Domain Models
# ===========================================================================

@dataclass
class ExecutionTarget:
    """The local execution environment for a task."""
    target_id: str
    target_type: str  # FAKECLOUD, KIND, PLAN_ONLY, etc.
    provider: str = ""
    platform: str = ""
    fidelity: ExecutionFidelity = ExecutionFidelity.PLAN_ONLY
    endpoint_reference: str = ""
    environment_name: str = ""
    isolated: bool = True
    ephemeral: bool = True
    managed_by: str = "INFRA_AGAIN"
    created_by_run_id: str = ""
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "targetId": self.target_id,
            "targetType": self.target_type,
            "provider": self.provider,
            "platform": self.platform,
            "fidelity": self.fidelity.value,
            "endpointReference": self.endpoint_reference,
            "environmentName": self.environment_name,
            "isolated": self.isolated,
            "ephemeral": self.ephemeral,
            "managedBy": self.managed_by,
            "createdByRunId": self.created_by_run_id,
            "capabilities": self.capabilities,
        }


@dataclass
class ExecutionPreflight:
    """A single preflight check result."""
    check_id: str
    name: str
    status: PreflightStatus
    severity: str = "INFO"
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkId": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class ExecutionPolicyDecision:
    """Airlock policy decision for an execution request."""
    verdict: PolicyVerdict
    reason_code: str
    reason: str
    effective_fidelity: ExecutionFidelity = ExecutionFidelity.PLAN_ONLY
    constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reasonCode": self.reason_code,
            "reason": self.reason,
            "effectiveFidelity": self.effective_fidelity.value,
            "constraints": self.constraints,
        }

    @property
    def is_allowed(self) -> bool:
        return self.verdict == PolicyVerdict.ALLOW


@dataclass
class ExecutionLease:
    """Runner lease for an execution package."""
    lease_id: str
    runner_id: str
    execution_package_id: str
    expires_at: str = ""
    heartbeat_at: str = ""
    state: str = "ACQUIRED"

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc).isoformat() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaseId": self.lease_id,
            "runnerId": self.runner_id,
            "executionPackageId": self.execution_package_id,
            "expiresAt": self.expires_at,
            "heartbeatAt": self.heartbeat_at,
            "state": self.state,
        }


@dataclass
class ExecutionEvent:
    """Ordered event in an execution run."""
    event_id: str
    event_type: str
    package_id: str = ""
    task_id: str = ""
    timestamp: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type,
            "packageId": self.package_id,
            "taskId": self.task_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class ExecutionObservation:
    """Observation from the actual target (not desired state)."""
    task_id: str
    target_id: str
    observed_state: dict[str, Any] = field(default_factory=dict)
    observed_at: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id,
            "targetId": self.target_id,
            "observedState": self.observed_state,
            "observedAt": self.observed_at,
            "source": self.source,
        }


@dataclass
class ExecutionValidation:
    """Validation of observed vs expected."""
    criterion: str
    expected: Any
    observed: Any
    status: str = "UNKNOWN"  # PASS, FAIL, UNKNOWN
    evidence_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion": self.criterion,
            "expected": self.expected,
            "observed": self.observed,
            "status": self.status,
            "evidenceRef": self.evidence_ref,
        }


@dataclass
class ExecutionVerification:
    """Independent verification result."""
    verifier_id: str
    result: VerificationResult = VerificationResult.INCONCLUSIVE
    criteria: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifierId": self.verifier_id,
            "result": self.result.value,
            "criteria": self.criteria,
            "evidenceRefs": self.evidence_refs,
            "reason": self.reason,
        }


@dataclass
class ExecutionEvidence:
    """Captured evidence from execution."""
    evidence_id: str
    evidence_type: EvidenceType
    source: SourceTruth
    captured_at: str = ""
    checksum: str = ""
    path_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidenceId": self.evidence_id,
            "evidenceType": self.evidence_type.value,
            "source": self.source.value,
            "capturedAt": self.captured_at,
            "checksum": self.checksum,
            "pathRef": self.path_ref,
        }


# ===========================================================================
# Phase N5 — Observe / Validate / Verify / Evidence
# ===========================================================================


class DriftClassification(str, Enum):
    """Result of comparing an EXPECTED resource identity against what the
    Observer actually found on the target. Never invented speculatively —
    only emitted when the underlying observation genuinely supports it."""
    MISSING = "MISSING"      # expected resource not found in observation
    EXTRA = "EXTRA"           # unexpected but run-owned resource present
    CHANGED = "CHANGED"       # resource exists but an execution-relevant property differs
    UNKNOWN = "UNKNOWN"       # state cannot be confidently determined (observation error/partial)
    FOREIGN = "FOREIGN"       # resource exists but belongs to another run/owner — never touched
    ORPHANED = "ORPHANED"     # run-owned but no longer traces to the active approved execution intent


class VerifierDecision(str, Enum):
    """The independent Verifier's final decision. VERIFIED_SUCCESS is the
    ONLY status meaning 'independently confirmed' — every other value is a
    distinct, honest way of NOT confirming it. Executor COMPLETED alone can
    never produce this value."""
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    UNVERIFIED = "UNVERIFIED"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    OBSERVATION_FAILED = "OBSERVATION_FAILED"


@dataclass
class ResourceDrift:
    """One drift finding for one resource identity."""
    resource_id: str
    classification: DriftClassification
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resourceId": self.resource_id,
            "classification": self.classification.value,
            "detail": self.detail,
        }


@dataclass
class EvidencePackage:
    """The final traceable N5 artifact — binds the complete Plan ->
    AIRLOCK -> Execute -> Observe -> Validate -> Verify chain. Append-only:
    once persisted, callers must create a NEW EvidencePackage rather than
    mutate an existing one. Never carries secrets, raw credentials,
    reasoning_content, or chain-of-thought — only structured, inspectable
    facts about what was planned, executed, observed, and verified."""
    evidence_package_id: str
    correlation_id: str
    run_id: str
    execution_package_id: str
    plan_id: str
    plan_digest: str
    design_id: str
    design_revision: int
    provider: str
    fidelity: str

    airlock_result: str = ""
    executor_result: str = ""
    observation_result: str = ""
    validation_result: str = ""
    verifier_result: str = ""
    verifier_reason: str = ""

    resource_ids: list[str] = field(default_factory=list)
    drift_findings: list[ResourceDrift] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    cleanup_result: dict[str, Any] = field(default_factory=dict)

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidencePackageId": self.evidence_package_id,
            "correlationId": self.correlation_id,
            "runId": self.run_id,
            "executionPackageId": self.execution_package_id,
            "planId": self.plan_id,
            "planDigest": self.plan_digest,
            "designId": self.design_id,
            "designRevision": self.design_revision,
            "provider": self.provider,
            "fidelity": self.fidelity,
            "airlockResult": self.airlock_result,
            "executorResult": self.executor_result,
            "observationResult": self.observation_result,
            "validationResult": self.validation_result,
            "verifierResult": self.verifier_result,
            "verifierReason": self.verifier_reason,
            "resourceIds": self.resource_ids,
            "driftFindings": [d.to_dict() for d in self.drift_findings],
            "evidenceRefs": self.evidence_refs,
            "cleanupResult": self.cleanup_result,
            "createdAt": self.created_at,
        }


@dataclass
class ExecutionResult:
    """Final execution result summary."""
    run_id: str
    package_id: str
    status: ExecutionTaskStatus = ExecutionTaskStatus.PLANNED
    started_at: str = ""
    completed_at: str = ""
    tasks_total: int = 0
    tasks_passed: int = 0
    tasks_failed: int = 0
    tasks_blocked: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)
    validations: list[dict[str, Any]] = field(default_factory=list)
    verification: dict[str, Any] | None = None
    evidence_refs: list[str] = field(default_factory=list)
    cleanup_result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "packageId": self.package_id,
            "status": self.status.value,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "tasksTotal": self.tasks_total,
            "tasksPassed": self.tasks_passed,
            "tasksFailed": self.tasks_failed,
            "tasksBlocked": self.tasks_blocked,
            "observations": self.observations,
            "validations": self.validations,
            "verification": self.verification,
            "evidenceRefs": self.evidence_refs,
            "cleanupResult": self.cleanup_result,
        }


@dataclass
class ExecutionTask:
    """A single executable task derived from an ImplementationTask."""
    execution_task_id: str
    implementation_task_id: str
    work_package_id: str
    title: str
    action_type: ActionType = ActionType.GENERATE_IAC
    target_capability: str = ""
    requested_fidelity: ExecutionFidelity = ExecutionFidelity.PLAN_ONLY
    effective_fidelity: ExecutionFidelity = ExecutionFidelity.PLAN_ONLY
    policy_decision: ExecutionPolicyDecision | None = None
    preconditions: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    validation_criteria: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    status: ExecutionTaskStatus = ExecutionTaskStatus.PLANNED
    derived_from: list[dict[str, str]] = field(default_factory=list)
    # Phase N6 — exact service identity, carried through from N3's
    # ImplementationTask so the executor knows precisely which resource
    # type to apply/observe/destroy instead of guessing from a title
    # string. Empty defaults to FakecloudExecutor's original S3-only
    # behavior, so every pre-N6 caller/test is unaffected.
    canonical_service_id: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "executionTaskId": self.execution_task_id,
            "implementationTaskId": self.implementation_task_id,
            "workPackageId": self.work_package_id,
            "title": self.title,
            "actionType": self.action_type.value,
            "targetCapability": self.target_capability,
            "requestedFidelity": self.requested_fidelity.value,
            "effectiveFidelity": self.effective_fidelity.value,
            "policyDecision": self.policy_decision.to_dict() if self.policy_decision else None,
            "preconditions": self.preconditions,
            "inputs": self.inputs,
            "expectedOutputs": self.expected_outputs,
            "validationCriteria": self.validation_criteria,
            "evidenceRequirements": self.evidence_requirements,
            "status": self.status.value,
            "derivedFrom": self.derived_from,
            "canonicalServiceId": self.canonical_service_id,
            "provider": self.provider,
        }


@dataclass
class ExecutionPackage:
    """A complete execution package for an approved ImplementationPlan."""
    execution_package_id: str
    plan_id: str
    plan_revision: int
    plan_checksum: str
    design_id: str
    design_revision: int
    correlation_id: str
    status: ExecutionPackageStatus = ExecutionPackageStatus.DRAFT
    target: ExecutionTarget = field(default_factory=lambda: ExecutionTarget(target_id="plan-only", target_type="PLAN_ONLY"))
    fidelity: ExecutionFidelity = ExecutionFidelity.PLAN_ONLY
    tasks: list[ExecutionTask] = field(default_factory=list)
    preflight_checks: list[ExecutionPreflight] = field(default_factory=list)
    policy_decision: ExecutionPolicyDecision | None = None
    created_at: str = ""
    updated_at: str = ""
    execution_checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "executionPackageId": self.execution_package_id,
            "planId": self.plan_id,
            "planRevision": self.plan_revision,
            "planChecksum": self.plan_checksum,
            "designId": self.design_id,
            "designRevision": self.design_revision,
            "correlationId": self.correlation_id,
            "status": self.status.value,
            "target": self.target.to_dict(),
            "fidelity": self.fidelity.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "preflightChecks": [c.to_dict() for c in self.preflight_checks],
            "policyDecision": self.policy_decision.to_dict() if self.policy_decision else None,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "executionChecksum": self.execution_checksum,
        }


@dataclass
class ExecutionReadiness:
    """Readiness assessment for an ImplementationPlan."""
    plan_id: str
    plan_status: str
    total_tasks: int = 0
    ready_local: list[dict[str, Any]] = field(default_factory=list)
    ready_simulated: list[dict[str, Any]] = field(default_factory=list)
    manual: list[dict[str, Any]] = field(default_factory=list)
    waiting_approval: list[dict[str, Any]] = field(default_factory=list)
    future_real: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "planId": self.plan_id,
            "planStatus": self.plan_status,
            "totalTasks": self.total_tasks,
            "readyLocal": self.ready_local,
            "readySimulated": self.ready_simulated,
            "manual": self.manual,
            "waitingApproval": self.waiting_approval,
            "futureRealExecution": self.future_real,
            "blocked": self.blocked,
        }
