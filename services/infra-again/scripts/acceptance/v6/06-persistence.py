#!/usr/bin/env python3
"""Gate 06: Plan persistence — restart durability."""
import sys, os, tempfile
def main(log_dir):
    from infra_again.implementation import generate_implementation_plan
    from infra_again.implementation.persistence import persist_plan, load_plan
    db = os.path.join(log_dir, "impl-test.db")
    os.environ["INFRA_AGAIN_DB"] = db
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN','requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi','metadata':{'name':'Test'}}
    plan = generate_implementation_plan(design)
    plan.approve('qa')
    persist_plan(plan)
    loaded = load_plan(plan.plan_id)
    assert loaded is not None
    assert loaded.status.value == 'APPROVED_FOR_EXECUTION'
    assert loaded.plan_checksum == plan.plan_checksum
    assert len(loaded.work_packages) == len(plan.work_packages)
    assert loaded.approved_by == 'qa'
    del os.environ["INFRA_AGAIN_DB"]
    for ext in ["","-wal","-shm"]:
        p=db+ext
        if os.path.exists(p): os.unlink(p)
    print(f"PASS: persist+load, status={loaded.status.value}, checksum preserved")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
