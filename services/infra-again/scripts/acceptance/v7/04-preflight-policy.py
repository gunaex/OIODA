#!/usr/bin/env python3
"""Gate 04: Preflight + Policy — verify checks and AIRLOCK decisions."""
import sys
def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionPackage, ExecutionTask, ExecutionTarget, ExecutionFidelity,
        ActionType, PolicyVerdict,
    )
    from infra_again.execution.preflight import PreflightEngine
    from infra_again.execution.policy import ExecutionPolicyEngine
    
    # Preflight on a plan-only package
    pkg = ExecutionPackage(
        execution_package_id="PF-1", plan_id="P-1", plan_revision=1,
        plan_checksum="abc123", design_id="D-1", design_revision=1,
        correlation_id="C-1",
        target=ExecutionTarget(target_id="plan-only", target_type="PLAN_ONLY",
                               fidelity=ExecutionFidelity.PLAN_ONLY),
        fidelity=ExecutionFidelity.PLAN_ONLY,
    )
    checks = PreflightEngine.run(pkg)
    assert len(checks) == 14, f"Expected 14 checks, got {len(checks)}"
    
    summary = PreflightEngine.summary(checks)
    assert summary["PASS"] >= 10
    assert summary["BLOCK"] == 0
    print(f"  Preflight: {summary}")
    
    # Policy: PLAN_ONLY → ALLOW
    task = ExecutionTask(
        execution_task_id="ET-1", implementation_task_id="IT-1",
        work_package_id="WP-1", title="Test",
        action_type=ActionType.GENERATE_IAC,
        requested_fidelity=ExecutionFidelity.PLAN_ONLY,
    )
    target = ExecutionTarget(target_id="plan-only", target_type="PLAN_ONLY",
                             fidelity=ExecutionFidelity.PLAN_ONLY)
    decision = ExecutionPolicyEngine.evaluate(task, target)
    assert decision.verdict == PolicyVerdict.ALLOW, f"Expected ALLOW, got {decision.verdict.value}: {decision.reason}"
    print(f"  Policy: {decision.verdict.value} - {decision.reason}")
    
    # Policy: PRODUCTION → BLOCK
    prod_target = ExecutionTarget(target_id="prod", target_type="AWS_PRODUCTION",
                                  fidelity=ExecutionFidelity.PRODUCTION)
    prod_decision = ExecutionPolicyEngine.evaluate(task, prod_target)
    assert prod_decision.verdict == PolicyVerdict.BLOCK
    assert "PRODUCTION_BLOCKED" in prod_decision.reason_code
    print(f"  Production: {prod_decision.verdict.value} - {prod_decision.reason_code}")
    
    # Policy: Real AWS endpoint → BLOCK
    real_target = ExecutionTarget(target_id="real", target_type="AWS",
                                  fidelity=ExecutionFidelity.SANDBOX,
                                  endpoint_reference="https://s3.amazonaws.com")
    real_decision = ExecutionPolicyEngine.evaluate(task, real_target)
    assert real_decision.verdict == PolicyVerdict.BLOCK
    print(f"  Real AWS: {real_decision.verdict.value} - {real_decision.reason_code}")
    
    print("PASS: Preflight + Policy verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
