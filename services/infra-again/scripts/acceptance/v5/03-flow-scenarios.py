#!/usr/bin/env python3
"""Gate 03: Flow scenarios — semantic assertions for all 7 scenarios."""
import sys, time

def main(log_dir: str) -> int:
    start = time.time()
    try:
        from infra_again.flow import (
            FlowSimulator, create_demo_flow, reduce_state, FlowNodeState, FlowEdgeState
        )

        flow = create_demo_flow()
        results = []

        def chk(scenario, assertions):
            sim = FlowSimulator(flow, scenario, seed=42)
            events = sim.simulate()
            state = reduce_state(flow, events, bottlenecks=sim.get_bottlenecks())
            for name, fn in assertions:
                ok, msg = fn(state, events, sim)
                if not ok:
                    return False, f"{scenario}: {name} FAILED: {msg}"
            return True, f"{scenario}: {len(events)} events OK"

        def ns(node_id): return lambda s, e, sim: s.node_states.get(node_id)
        def blocked(nid): return lambda s, e, sim: (ns(nid)(s,e,sim) == FlowNodeState.BLOCKED, f"{nid} not BLOCKED (got {ns(nid)(s,e,sim)})")
        def not_reached(*nids): return lambda s, e, sim: (all(ns(n)(s,e,sim) == FlowNodeState.NOT_REACHED for n in nids), f"Expected NOT_REACHED for {nids}")
        def degraded(nid): return lambda s, e, sim: (ns(nid)(s,e,sim) == FlowNodeState.DEGRADED, f"{nid} not DEGRADED")
        def completed(nid): return lambda s, e, sim: (ns(nid)(s,e,sim) in (FlowNodeState.PASS, FlowNodeState.COMPLETED), f"{nid} not completed")
        def no_blocked(): return lambda s, e, sim: (not any(v == FlowNodeState.BLOCKED for v in s.node_states.values()), "Unexpected BLOCKED")
        def event_exists(etype): return lambda s, e, sim: (any(ev.event_type.value == etype for ev in e), f"No {etype} event")
        def bottleneck_is(nid): return lambda s, e, sim: (any(b.node_id == nid and (b.score or 0) > 0 for b in s.bottlenecks), f"No bottleneck for {nid}")

        results.append(chk("HAPPY_PATH", [
            ("no-blocked", no_blocked()),
            ("user-completed", completed("user")),
        ]))
        results.append(chk("AUTH_FAILURE", [
            ("credential-blocked", blocked("credential-gate")),
            ("downstream-not-reached", not_reached("waf","firewall","api-gateway","application-service","postgresql","approval-gate")),
        ]))
        results.append(chk("FIREWALL_BLOCK", [
            ("firewall-blocked", blocked("firewall")),
            ("api-not-reached", not_reached("api-gateway","application-service","postgresql","approval-gate")),
        ]))
        results.append(chk("DATABASE_SLOW", [
            ("postgresql-degraded", degraded("postgresql")),
            ("bottleneck-exists", bottleneck_is("postgresql")),
            ("no-blocked", no_blocked()),
        ]))
        results.append(chk("API_TIMEOUT", [
            ("api-failed", lambda s, e, sim: (ns("api-gateway")(s,e,sim) == FlowNodeState.FAILED, "api-gateway not FAILED")),
            ("downstream-not-reached", not_reached("application-service","postgresql","approval-gate")),
        ]))
        results.append(chk("APPROVAL_WAIT", [
            ("approval-requested", event_exists("APPROVAL_REQUESTED")),
            ("approval-granted", event_exists("APPROVAL_GRANTED")),
        ]))
        results.append(chk("RETRY_RECOVERY", [
            ("retry-started", event_exists("RETRY_START")),
            ("retry-ended", event_exists("RETRY_END")),
            ("node-pass-after-retry", lambda s, e, sim: (
                any(ev.event_type.value == "NODE_PASS" and ev.node_id == "application-service" for ev in e),
                "application-service never passed")),
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
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    sys.exit(main(log_dir))
