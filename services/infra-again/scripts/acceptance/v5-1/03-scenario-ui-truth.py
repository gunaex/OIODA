#!/usr/bin/env python3
"""Gate 03: Scenario visual-state mapping truth for all 7 scenarios."""
import sys, time

def main(log_dir: str) -> int:
    start = time.time()
    try:
        from infra_again.flow import (
            FlowSimulator, create_demo_flow, reduce_state, FlowNodeState, FlowEdgeState, ScenarioId
        )
        flow = create_demo_flow()
        results = []

        def check(scenario, assertions):
            sim = FlowSimulator(flow, scenario, seed=42)
            events = sim.simulate()
            state = reduce_state(flow, events, bottlenecks=sim.get_bottlenecks())
            for name, fn in assertions:
                ok, msg = fn(state, events, sim)
                if not ok:
                    return False, f"{scenario}: {name} FAILED: {msg}"
            return True, f"{scenario} OK"

        def ns(nid): return lambda s, e, sim: s.node_states.get(nid)
        def is_state(nid, st): return lambda s, e, sim: (ns(nid)(s,e,sim) == st, f"{nid} expected {st}, got {ns(nid)(s,e,sim)}")
        def no_blocked(): return lambda s, e, sim: (not any(v == FlowNodeState.BLOCKED for v in s.node_states.values()), "Unexpected BLOCKED")
        def has_degraded(nid): return lambda s, e, sim: (ns(nid)(s,e,sim) == FlowNodeState.DEGRADED, f"{nid} not DEGRADED")
        def has_bottleneck(nid): return lambda s, e, sim: (any(b.node_id==nid and (b.score or 0)>0 for b in s.bottlenecks), f"No bottleneck at {nid}")
        def has_event(etype): return lambda s, e, sim: (any(ev.event_type.value==etype for ev in e), f"No {etype} event")

        # HAPPY_PATH
        results.append(check("HAPPY_PATH", [
            ("no-blocked", no_blocked()),
            ("user-completed", is_state("user", FlowNodeState.COMPLETED)),
            ("postgresql-completed", is_state("postgresql", FlowNodeState.COMPLETED)),
        ]))
        # AUTH_FAILURE
        results.append(check("AUTH_FAILURE", [
            ("cred-blocked", is_state("credential-gate", FlowNodeState.BLOCKED)),
            ("waf-not-reached", is_state("waf", FlowNodeState.NOT_REACHED)),
            ("postgresql-not-reached", is_state("postgresql", FlowNodeState.NOT_REACHED)),
        ]))
        # FIREWALL_BLOCK
        results.append(check("FIREWALL_BLOCK", [
            ("firewall-blocked", is_state("firewall", FlowNodeState.BLOCKED)),
            ("api-not-reached", is_state("api-gateway", FlowNodeState.NOT_REACHED)),
            ("app-not-reached", is_state("application-service", FlowNodeState.NOT_REACHED)),
            ("db-not-reached", is_state("postgresql", FlowNodeState.NOT_REACHED)),
        ]))
        # DATABASE_SLOW
        results.append(check("DATABASE_SLOW", [
            ("db-degraded", has_degraded("postgresql")),
            ("bottleneck-exists", has_bottleneck("postgresql")),
            ("no-blocked", no_blocked()),
        ]))
        # API_TIMEOUT
        results.append(check("API_TIMEOUT", [
            ("api-failed", is_state("api-gateway", FlowNodeState.FAILED)),
            ("app-not-reached", is_state("application-service", FlowNodeState.NOT_REACHED)),
            ("db-not-reached", is_state("postgresql", FlowNodeState.NOT_REACHED)),
        ]))
        # APPROVAL_WAIT
        results.append(check("APPROVAL_WAIT", [
            ("approval-requested", has_event("APPROVAL_REQUESTED")),
            ("approval-granted", has_event("APPROVAL_GRANTED")),
        ]))
        # RETRY_RECOVERY
        results.append(check("RETRY_RECOVERY", [
            ("retry-started", has_event("RETRY_START")),
            ("retry-ended", has_event("RETRY_END")),
        ]))

        for ok, msg in results:
            if not ok:
                print(f"  {msg}")
                return 1
            print(f"  {msg}")

        elapsed = time.time() - start
        print(f"PASS {elapsed:.1f}s")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
