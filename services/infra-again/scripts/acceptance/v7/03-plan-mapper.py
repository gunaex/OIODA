#!/usr/bin/env python3
"""Gate 03: Plan → Execution mapper — verify readiness + task mapping."""
import sys
def main(log_dir):
    from infra_again.implementation.planner import generate_implementation_plan
    from infra_again.execution.mapper import ImplementationExecutionMapper
    from infra_again.execution.registry import LocalExecutionTargetRegistry
    
    design = {"designId":"D-MAP","revision":1,"status":"BASELINE_FROZEN",
              "requirementsChecksum":"a","architectureChecksum":"b","flowChecksum":"c",
              "metadata":{"name":"MapperTest"}}
    flow = {"nodes":[{"nodeId":"user","category":"USER"},{"nodeId":"app","category":"APPLICATION"}],
            "edges":[{"edgeId":"e1","sourceId":"user","targetId":"app","flowType":"REQUEST"}]}
    plan = generate_implementation_plan(design, flow)
    
    # Readiness
    readiness = ImplementationExecutionMapper.compute_readiness(plan)
    assert readiness.total_tasks > 0
    assert len(readiness.ready_local) + len(readiness.ready_simulated) > 0
    print(f"  Readiness: total={readiness.total_tasks} local={len(readiness.ready_local)} sim={len(readiness.ready_simulated)} manual={len(readiness.manual)}")
    
    # Map to plan-only target
    LocalExecutionTargetRegistry.register_defaults()
    target = LocalExecutionTargetRegistry.get("plan-only")
    tasks = ImplementationExecutionMapper.map_to_execution_tasks(plan, target)
    assert len(tasks) > 0, "Should map some tasks"
    for t in tasks:
        assert t.execution_task_id
        assert t.implementation_task_id
        assert t.action_type
        assert t.derived_from is not None
    print(f"  Mapped: {len(tasks)} tasks to plan-only target")
    print("PASS: Mapper verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
