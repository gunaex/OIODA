#!/usr/bin/env python3
"""Gate 02: Plan models — import, blocked design, cycle detection."""
import sys
def main(log_dir):
    from infra_again.flow import create_demo_flow
    from infra_again.implementation import generate_implementation_plan, detect_cycles
    from infra_again.implementation.models import ImplementationWorkPackage, ImplementationDependency
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN','requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi','metadata':{'name':'Test'}}
    flow = create_demo_flow().to_dict()
    plan = generate_implementation_plan(design, flow=flow)
    assert len(plan.work_packages) >= 5
    assert sum(len(w.tasks) for w in plan.work_packages) >= 15
    try: generate_implementation_plan({'designId':'X','status':'DRAFT'}); assert False
    except ValueError: pass
    w1=ImplementationWorkPackage(package_id='A');w2=ImplementationWorkPackage(package_id='B');w3=ImplementationWorkPackage(package_id='C')
    deps=[ImplementationDependency(from_package='A',to_package='B'),ImplementationDependency(from_package='B',to_package='C'),ImplementationDependency(from_package='C',to_package='A')]
    cycles=detect_cycles([w1,w2,w3],deps)
    assert len(cycles)>0
    print(f"PASS: {len(plan.work_packages)} packages, {sum(len(w.tasks) for w in plan.work_packages)} tasks")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
