#!/usr/bin/env python3
"""Gate 02: Flow domain — import, deterministic events, reducer, bottleneck."""
import sys, time, json

def main(log_dir: str) -> int:
    start = time.time()
    try:
        from infra_again.flow import (
            FlowSimulator, create_demo_flow, reduce_state, FlowNodeState,
            DesignBaseline, analyze_bottlenecks,
        )

        # 1. Deterministic event stream
        flow = create_demo_flow()
        e1 = FlowSimulator(flow, "HAPPY_PATH", seed=42).simulate()
        e2 = FlowSimulator(flow, "HAPPY_PATH", seed=42).simulate()
        d1 = [ev.to_dict() for ev in e1]
        d2 = [ev.to_dict() for ev in e2]
        assert d1 == d2, "Same seed gave different events"
        for ev in e1:
            assert "evt-" in ev.event_id and "-42-" in ev.event_id, f"Bad event_id: {ev.event_id}"
        print(f"  Deterministic: {len(e1)} events, 0 ignored fields")

        # 2. Reducer
        state = reduce_state(flow, e1)
        assert len(state.node_states) == len(flow.nodes)
        assert len(state.edge_states) == len(flow.edges)
        print(f"  Reducer: {len(state.node_states)} nodes, {len(state.edge_states)} edges")

        # 3. Bottleneck engine
        from infra_again.flow import FlowMetric, MetricSource
        metrics = {
            "db": [FlowMetric(name="latency", value=650, source=MetricSource.SIMULATED)]
        }
        bots = analyze_bottlenecks(state, metrics)
        assert len(bots) >= 1
        assert bots[0].score and bots[0].score > 0
        print(f"  Bottleneck: {bots[0].node_id} score={bots[0].score}")

        # 4. DesignBaseline lifecycle
        db = DesignBaseline(design_id="D-TEST")
        db.accept("qa")
        assert db.status.value == "BASELINE_FROZEN"
        inv = db.check_acceptance_invalidated("new", db.architecture_checksum, db.flow_checksum)
        assert inv
        db.request_change("test")
        assert db.status.value == "CHANGE_REQUESTED"
        print("  DesignBaseline: accept, invalidate, change OK")

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
