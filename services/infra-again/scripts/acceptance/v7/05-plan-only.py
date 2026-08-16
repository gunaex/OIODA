#!/usr/bin/env python3
"""Gate 05: PLAN_ONLY real execution — actual tofu fmt/init/validate/plan."""
import sys, os, tempfile, asyncio, shutil
def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType,
    )
    from infra_again.execution.executor import PlanOnlyExecutor
    tofu = shutil.which("tofu")
    if not tofu:
        print("FAIL: tofu not installed (required for PLAN_ONLY)")
        return 1
    task = ExecutionTask(
        execution_task_id="ET-PLAN-REAL", implementation_task_id="IT-1",
        work_package_id="WP-1", title="Plan-only Real Execution",
        action_type=ActionType.GENERATE_IAC,
        requested_fidelity=ExecutionFidelity.PLAN_ONLY,
    )
    target = ExecutionTarget(target_id="plan-only", target_type="PLAN_ONLY",
                             fidelity=ExecutionFidelity.PLAN_ONLY)
    executor = PlanOnlyExecutor()
    with tempfile.TemporaryDirectory() as work_dir:
        result = asyncio.run(executor.execute(task, target, work_dir, "GOLDEN-PLAN-REAL"))
    assert result.get("status")=="COMPLETED", f"Expected COMPLETED, got {result.get('status')}: {result.get('reason','')}"
    print(f"  Plan-only: {result['status']}")
    outputs = result.get("outputs",[])
    assert len(outputs)>=3, f"Expected >=3 outputs, got {len(outputs)}"
    for o in outputs:
        assert o["exit"]==0, f"Command {o['command']} failed: {o.get('stdout','')[:200]}"
    print(f"  Commands: {[o['command'] for o in outputs]}")
    print(f"  Plan checksum: {result.get('plan_checksum','N/A')[:16]}")
    evidence = result.get("evidence",[])
    assert len(evidence)>0
    for ev in evidence:
        print(f"  Evidence: {ev['evidenceId']} type={ev['evidenceType']} source={ev['source']}")
    assert not any("apply" in o.get("command","").lower() for o in outputs), "PLAN_ONLY must not apply"
    print("PASS: PLAN_ONLY real execution verified")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
