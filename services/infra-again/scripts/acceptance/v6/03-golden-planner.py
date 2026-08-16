#!/usr/bin/env python3
"""Gate 03: Golden planner — design-derived, negative tests, traceability."""
import sys
def main(log_dir):
    from infra_again.flow import create_demo_flow
    from infra_again.implementation import generate_implementation_plan

    flow = create_demo_flow()
    flow_dict = flow.to_dict()
    design = {'designId':'D-001','revision':1,'status':'BASELINE_FROZEN',
        'requirementsChecksum':'abc','architectureChecksum':'def','flowChecksum':'ghi',
        'metadata':{'name':'Customer API Service'}}

    # Golden: full demo flow (has security, app, db)
    plan_full = generate_implementation_plan(design, flow=flow_dict)
    pkgs = [w.package_type.value for w in plan_full.work_packages]
    assert 'SECURITY' in pkgs, f"Missing SECURITY in {pkgs}"
    assert 'APPLICATION' in pkgs
    assert 'DATABASE' in pkgs
    assert 'INTEGRATION' in pkgs
    assert 'DEPLOYMENT' in pkgs
    # Traceability check
    all_derived = []
    for w in plan_full.work_packages:
        for t in w.tasks:
            all_derived.extend(t.derived_from)
    flow_derived = [d for d in all_derived if d['type'].startswith('FLOW_')]
    assert len(flow_derived) >= 5, f"Only {len(flow_derived)} flow-derived tasks"

    # Negative A: user→app only (no db, no firewall, no waf)
    simple_flow = {'nodes':[
        {'nodeId':'user','label':'User','category':'USER'},
        {'nodeId':'app','label':'App','category':'APPLICATION'},
    ],'edges':[{'edgeId':'e1','sourceId':'user','targetId':'app'}]}
    plan_simple = generate_implementation_plan(design, flow=simple_flow)
    sp_types = [w.package_type.value for w in plan_simple.work_packages]
    assert 'DATABASE' not in sp_types, f"Should not have DATABASE: {sp_types}"
    assert 'SECURITY' not in sp_types, f"Should not have SECURITY: {sp_types}"
    assert 'APPLICATION' in sp_types
    print(f"  Design A (user→app): {len(plan_simple.work_packages)} pkgs, no DB, no security")

    # Negative B: user→waf→app→db
    sec_flow = {'nodes':[
        {'nodeId':'user','label':'User','category':'USER'},
        {'nodeId':'waf','label':'WAF','category':'SECURITY'},
        {'nodeId':'app','label':'App','category':'APPLICATION'},
        {'nodeId':'db','label':'PostgreSQL','category':'DATABASE'},
    ],'edges':[
        {'edgeId':'e1','sourceId':'user','targetId':'waf'},
        {'edgeId':'e2','sourceId':'waf','targetId':'app'},
        {'edgeId':'e3','sourceId':'app','targetId':'db'},
    ]}
    plan_sec = generate_implementation_plan(design, flow=sec_flow)
    sp2 = [w.package_type.value for w in plan_sec.work_packages]
    assert 'SECURITY' in sp2, f"Should have SECURITY: {sp2}"
    assert 'DATABASE' in sp2, f"Should have DATABASE: {sp2}"
    print(f"  Design B (user→waf→app→db): {len(plan_sec.work_packages)} pkgs, SECURITY+DATABASE")

    # Negative C: app→storage only
    store_flow = {'nodes':[
        {'nodeId':'app','label':'App','category':'APPLICATION'},
        {'nodeId':'storage','label':'Object Storage','category':'STORAGE'},
    ],'edges':[{'edgeId':'e1','sourceId':'app','targetId':'storage','flowType':'DATA'}]}
    plan_store = generate_implementation_plan(design, flow=store_flow)
    sp3 = [w.package_type.value for w in plan_store.work_packages]
    assert 'DATA' in sp3 or any(w.package_type.value=='DATA' for w in plan_store.work_packages), f"Should have DATA: {sp3}"
    assert 'DATABASE' not in sp3, f"Should not have DATABASE: {sp3}"
    print(f"  Design C (app→storage): {len(plan_store.work_packages)} pkgs, DATA but no DATABASE")

    # Approval + invalidation
    plan_full.approve('qa')
    assert plan_full.status.value == 'APPROVED_FOR_EXECUTION'
    old = plan_full.plan_checksum
    from infra_again.implementation.models import ImplementationTask
    plan_full.work_packages[0].tasks.append(ImplementationTask(task_id='NEW',work_package_id=plan_full.work_packages[0].package_id,title='X'))
    assert plan_full.check_changed_after_approval()
    print(f"  Approval + invalidation: OK")

    print(f"PASS: design-derived planner verified (3 negative tests)")
    return 0
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
