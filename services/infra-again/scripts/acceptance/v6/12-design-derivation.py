#!/usr/bin/env python3
"""Gate 12: Design derivation regression — negative tests for truly design-derived planner."""
import sys, os

def main(log_dir):
    from infra_again.implementation.planner import generate_implementation_plan

    # --- Design A: User → Application (no DB, no WAF, no Firewall) ---
    design_a = {
        "designId": "A", "revision": 1, "status": "BASELINE_FROZEN",
        "requirementsChecksum": "a1", "architectureChecksum": "a2", "flowChecksum": "a3",
        "metadata": {"name": "Design A — minimal"},
    }
    flow_a = {
        "nodes": [
            {"nodeId": "user", "category": "USER"},
            {"nodeId": "app", "category": "APPLICATION"},
        ],
        "edges": [{"edgeId": "e1", "sourceId": "user", "targetId": "app", "flowType": "REQUEST"}],
    }
    plan_a = generate_implementation_plan(design_a, flow_a)
    wp_types_a = {wp.package_type.value for wp in plan_a.work_packages}
    
    errors = []
    # Must have APPLICATION
    if "APPLICATION" not in wp_types_a:
        errors.append("Design A: missing APPLICATION package")
    # Must NOT have DATABASE
    if "DATABASE" in wp_types_a:
        errors.append("Design A: should NOT have DATABASE package (no DB node)")
    # Must NOT have SECURITY
    if "SECURITY" in wp_types_a:
        errors.append("Design A: should NOT have SECURITY package (no WAF/firewall)")
    
    # All tasks must have non-empty derivedFrom
    for wp in plan_a.work_packages:
        for t in wp.tasks:
            if len(t.derived_from) == 0:
                errors.append(f"Design A: task {t.task_id} has empty derivedFrom")
    
    print(f"  Design A: packages={wp_types_a}")
    
    # --- Design B: User → WAF → App → PostgreSQL ---
    design_b = {
        "designId": "B", "revision": 1, "status": "BASELINE_FROZEN",
        "requirementsChecksum": "b1", "architectureChecksum": "b2", "flowChecksum": "b3",
        "metadata": {"name": "Design B — standard web app"},
    }
    flow_b = {
        "nodes": [
            {"nodeId": "user", "category": "USER"},
            {"nodeId": "waf", "category": "SECURITY"},
            {"nodeId": "app", "category": "APPLICATION"},
            {"nodeId": "pg", "category": "DATABASE"},
        ],
        "edges": [
            {"edgeId": "e1", "sourceId": "user", "targetId": "waf", "flowType": "REQUEST"},
            {"edgeId": "e2", "sourceId": "waf", "targetId": "app", "flowType": "REQUEST"},
            {"edgeId": "e3", "sourceId": "app", "targetId": "pg", "flowType": "DATA"},
        ],
    }
    plan_b = generate_implementation_plan(design_b, flow_b)
    wp_types_b = {wp.package_type.value for wp in plan_b.work_packages}
    
    if "SECURITY" not in wp_types_b:
        errors.append("Design B: missing SECURITY package (has WAF)")
    if "APPLICATION" not in wp_types_b:
        errors.append("Design B: missing APPLICATION package")
    if "DATABASE" not in wp_types_b:
        errors.append("Design B: missing DATABASE package (has PostgreSQL)")
    
    print(f"  Design B: packages={wp_types_b}")
    
    # --- Design C: App → Object Storage ---
    flow_c = {
        "nodes": [
            {"nodeId": "app", "category": "APPLICATION"},
            {"nodeId": "storage", "category": "STORAGE"},
        ],
        "edges": [
            {"edgeId": "e1", "sourceId": "app", "targetId": "storage", "flowType": "DATA"},
        ],
    }
    plan_c = generate_implementation_plan(design_b, flow_c)  # reuse design_b metadata
    wp_types_c = {wp.package_type.value for wp in plan_c.work_packages}
    
    if "DATA" not in wp_types_c:
        errors.append("Design C: missing DATA package (has object storage)")
    if "DATABASE" in wp_types_c:
        errors.append("Design C: should NOT have DATABASE package (no PostgreSQL)")
    
    print(f"  Design C: packages={wp_types_c}")
    
    if errors:
        print(f"FAIL: {len(errors)} derivation violations:")
        for e in errors:
            print(f"  - {e}")
        return 1
    
    print("PASS: All 3 negative derivation tests passed")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
