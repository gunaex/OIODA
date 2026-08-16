#!/usr/bin/env python3
"""Gate 08: Handoff contracts."""
import sys
def main(log_dir):
    from infra_again.flow import create_demo_flow
    from infra_again.implementation import generate_implementation_plan, generate_pm_handoff, generate_qa_handoff
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN','requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi','metadata':{'name':'Test'}}
    flow = create_demo_flow().to_dict()
    plan = generate_implementation_plan(design, flow=flow)
    pm = generate_pm_handoff(plan)
    assert pm["contractVersion"]=="1.0"
    assert len(pm["workPackages"])>=4
    qa = generate_qa_handoff(plan)
    assert qa["contractVersion"]=="1.0"
    assert len(qa["testItems"])>0
    print(f"PASS: PM={len(pm['workPackages'])} pkgs, QA={len(qa['testItems'])} test items")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
