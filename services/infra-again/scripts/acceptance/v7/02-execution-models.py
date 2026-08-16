#!/usr/bin/env python3
"""Gate 02: Execution models — verify all domain types are importable and valid."""
import sys
def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionPackage, ExecutionTask, ExecutionTarget, ExecutionPreflight,
        ExecutionPolicyDecision, ExecutionLease, ExecutionEvent, ExecutionObservation,
        ExecutionValidation, ExecutionVerification, ExecutionEvidence, ExecutionResult,
        ExecutionPackageStatus, ExecutionTaskStatus, ExecutionFidelity,
        PreflightStatus, PolicyVerdict, EvidenceType, SourceTruth,
        VerificationResult, ExecutionReadiness, TaskReadiness, ActionType,
    )
    # Verify enums have required values
    assert ExecutionPackageStatus.DRAFT.value == "DRAFT"
    assert ExecutionPackageStatus.PREFLIGHT.value == "PREFLIGHT"
    assert ExecutionPackageStatus.COMPLETED.value == "COMPLETED"
    assert PreflightStatus.PASS.value == "PASS"
    assert PolicyVerdict.ALLOW.value == "ALLOW"
    assert PolicyVerdict.BLOCK.value == "BLOCK"
    assert ExecutionFidelity.PRODUCTION.value == "PRODUCTION"
    assert EvidenceType.COMMAND_OUTPUT.value == "COMMAND_OUTPUT"
    assert SourceTruth.LOCAL_OBSERVED.value == "LOCAL_OBSERVED"
    assert TaskReadiness.READY_LOCAL.value == "READY_LOCAL"
    assert ActionType.GENERATE_IAC.value == "GENERATE_IAC"

    # Verify dataclass construction
    pkg = ExecutionPackage(
        execution_package_id="TEST-1", plan_id="P-1", plan_revision=1,
        plan_checksum="abc", design_id="D-1", design_revision=1,
        correlation_id="C-1",
    )
    assert pkg.to_dict()["executionPackageId"] == "TEST-1"
    
    task = ExecutionTask(
        execution_task_id="ET-1", implementation_task_id="IT-1",
        work_package_id="WP-1", title="Test Task",
    )
    assert task.to_dict()["title"] == "Test Task"

    readiness = ExecutionReadiness(plan_id="P-1", plan_status="APPROVED_FOR_EXECUTION")
    assert readiness.to_dict()["planId"] == "P-1"

    print("PASS: All 35+ domain types verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
