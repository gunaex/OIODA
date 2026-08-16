#!/usr/bin/env python3
"""Gate 08: Safety blocks — real AWS, production, ownership."""
import sys
def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.policy import ExecutionPolicyEngine
    
    task = ExecutionTask(
        execution_task_id="ET-SAFE", implementation_task_id="IT-1",
        work_package_id="WP-1", title="Safety Test",
        action_type=ActionType.APPLY_LOCAL_IAC,
        requested_fidelity=ExecutionFidelity.LOCAL_RUNTIME,
    )
    
    # Test 1: Real AWS endpoint → BLOCK
    real_aws = ExecutionTarget(target_id="real-aws", target_type="AWS",
                               fidelity=ExecutionFidelity.SANDBOX,
                               endpoint_reference="https://s3.amazonaws.com")
    d = ExecutionPolicyEngine.evaluate(task, real_aws)
    assert d.verdict == PolicyVerdict.BLOCK, f"Real AWS should BLOCK, got {d.verdict.value}"
    assert "REAL_CLOUD" in d.reason_code
    print(f"  Real AWS: BLOCK ({d.reason_code})")
    
    # Test 2: Production → BLOCK
    prod = ExecutionTarget(target_id="prod", target_type="AWS_PRODUCTION",
                           fidelity=ExecutionFidelity.PRODUCTION)
    d2 = ExecutionPolicyEngine.evaluate(task, prod)
    assert d2.verdict == PolicyVerdict.BLOCK
    print(f"  Production: BLOCK ({d2.reason_code})")
    
    # Test 3: Local allowed
    local = ExecutionTarget(target_id="kind", target_type="KIND",
                            fidelity=ExecutionFidelity.LOCAL_RUNTIME,
                            endpoint_reference="")
    d3 = ExecutionPolicyEngine.evaluate(task, local)
    assert d3.verdict == PolicyVerdict.ALLOW, f"Local should ALLOW, got {d3.verdict.value}: {d3.reason}"
    print(f"  Local: ALLOW ({d3.reason_code})")
    
    # Test 4: Fakecloud allowed
    fc = ExecutionTarget(target_id="fakecloud", target_type="FAKECLOUD",
                         fidelity=ExecutionFidelity.SIMULATED,
                         endpoint_reference="http://localhost:4566")
    fc_task = ExecutionTask(
        execution_task_id="ET-FC", implementation_task_id="IT-FC",
        work_package_id="WP-FC", title="Fakecloud Test",
        action_type=ActionType.APPLY_LOCAL_IAC,
        requested_fidelity=ExecutionFidelity.SIMULATED,
    )
    d4 = ExecutionPolicyEngine.evaluate(fc_task, fc)
    assert d4.verdict == PolicyVerdict.ALLOW, f"Fakecloud should ALLOW, got {d4.verdict.value}: {d4.reason}"
    print(f"  Fakecloud: ALLOW")
    
    print("PASS: All safety blocks verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
