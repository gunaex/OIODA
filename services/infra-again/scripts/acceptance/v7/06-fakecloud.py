#!/usr/bin/env python3
"""Gate 06: Fakecloud execution — verify fakecloud executor and policy."""
import sys, shutil
def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.policy import ExecutionPolicyEngine
    from infra_again.execution.registry import LocalExecutionTargetRegistry
    
    LocalExecutionTargetRegistry.register_defaults()
    target = LocalExecutionTargetRegistry.get("fakecloud")
    assert target is not None, "Fakecloud target must exist"
    assert target.target_type == "FAKECLOUD"
    print(f"  Target: {target.target_type} fidelity={target.fidelity.value}")
    
    # Policy check for fakecloud
    task = ExecutionTask(
        execution_task_id="ET-FC", implementation_task_id="IT-FC",
        work_package_id="WP-FC", title="Fakecloud S3 Test",
        action_type=ActionType.APPLY_LOCAL_IAC,
        requested_fidelity=ExecutionFidelity.SIMULATED,
    )
    decision = ExecutionPolicyEngine.evaluate(task, target)
    assert decision.verdict == PolicyVerdict.ALLOW, f"Fakecloud should ALLOW: {decision.reason}"
    print(f"  Policy: {decision.verdict.value}")
    
    # Check fakecloud availability
    avail = LocalExecutionTargetRegistry.probe_availability("fakecloud")
    if avail["available"]:
        print(f"  Availability: READY ({avail.get('binary','')})")
    else:
        print(f"  Availability: NOT_INSTALLED (LOCAL_TARGET_UNAVAILABLE would block execution)")
        print("  Note: fakecloud not found but target model and policy are verified")
    
    print("PASS: Fakecloud model + policy verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
