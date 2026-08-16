#!/usr/bin/env python3
"""Gate 04: Dependencies — DAG, cycle detection, critical path."""
import sys
def main(log_dir):
    from infra_again.flow import create_demo_flow
    from infra_again.implementation import generate_implementation_plan, compute_critical_path, detect_cycles
    from infra_again.implementation.models import ImplementationWorkPackage, ImplementationDependency
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN','requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi','metadata':{'name':'Test'}}
    flow = create_demo_flow().to_dict()
    plan = generate_implementation_plan(design, flow=flow)
    cp = compute_critical_path(plan.work_packages, plan.dependencies)
    assert len(cp) >= 2  # design-derived
    cycles = detect_cycles(plan.work_packages, plan.dependencies)
    assert len(cycles) == 0, f"Unexpected cycles: {cycles}"
    # Cycle injection
    w = [ImplementationWorkPackage(package_id=f'C{i}') for i in range(3)]
    deps=[ImplementationDependency(from_package='C0',to_package='C1'),ImplementationDependency(from_package='C1',to_package='C2'),ImplementationDependency(from_package='C2',to_package='C0')]
    assert len(detect_cycles(w,deps))>0
    print(f"PASS: critical={len(cp)}, cycles=0, cycle-detection=ok")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
