#!/usr/bin/env python3
"""Gate 07: Kind execution — verify kind executor model and policy."""
import sys, shutil
def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.policy import ExecutionPolicyEngine
    from infra_again.execution.registry import LocalExecutionTargetRegistry
    
    LocalExecutionTargetRegistry.register_defaults()
    target = LocalExecutionTargetRegistry.get("kind")
    assert target is not None, "Kind target must exist"
    assert target.target_type == "KIND"
    
    task = ExecutionTask(
        execution_task_id="ET-KIND", implementation_task_id="IT-KIND",
        work_package_id="WP-KIND", title="Kind Deploy Test",
        action_type=ActionType.DEPLOY_LOCAL_WORKLOAD,
        requested_fidelity=ExecutionFidelity.LOCAL_RUNTIME,
    )
    decision = ExecutionPolicyEngine.evaluate(task, target)
    assert decision.verdict == PolicyVerdict.ALLOW, f"Kind should ALLOW: {decision.reason}"
    
    avail = LocalExecutionTargetRegistry.probe_availability("kind")
    print(f"  Target: KIND policy={decision.verdict.value} available={avail['available']}")
    
    print("PASS: Kind model + policy verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
