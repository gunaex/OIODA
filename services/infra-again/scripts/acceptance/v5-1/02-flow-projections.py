#!/usr/bin/env python3
"""Gate 02: Flow projections — HIGH_LEVEL, DETAILED, SECURITY, DATA."""
import sys, time

def main(log_dir: str) -> int:
    start = time.time()
    try:
        from infra_again.flow import (
            create_demo_flow, project_high_level, project_detailed,
            project_security, project_data,
        )
        flow = create_demo_flow()

        # HIGH_LEVEL
        hl = project_high_level(flow)
        assert len(hl.nodes) > 2, f"High-level too few nodes: {len(hl.nodes)}"
        assert len(hl.nodes) < len(flow.nodes), "High-level should have fewer nodes"
        print(f"  HIGH_LEVEL: {len(hl.nodes)} nodes, {len(hl.edges)} edges")

        # DETAILED
        dl = project_detailed(flow)
        assert len(dl.nodes) == len(flow.nodes)
        assert len(dl.edges) == len(flow.edges)
        print(f"  DETAILED: {len(dl.nodes)} nodes, {len(dl.edges)} edges")

        # SECURITY
        sec = project_security(flow)
        sec_nodes = [n for n in sec.nodes if n.metadata.get("emphasis") == "SECURITY"]
        assert len(sec_nodes) >= 4, f"Expected >=4 security-emphasized nodes, got {len(sec_nodes)}"
        print(f"  SECURITY: {len(sec_nodes)} emphasized nodes")

        # DATA
        dat = project_data(flow)
        data_edges = [e for e in dat.edges if e.metadata.get("emphasis") == "DATA"]
        assert len(data_edges) >= 1, f"Expected >=1 data edge, got {len(data_edges)}"
        print(f"  DATA: {len(data_edges)} data edges")

        # Verify all projections serialize
        for name, proj in [("HIGH_LEVEL", hl), ("DETAILED", dl), ("SECURITY", sec), ("DATA", dat)]:
            d = proj.to_dict()
            assert "nodes" in d and "edges" in d
        print(f"  Serialization: all 4 projections OK")

        elapsed = time.time() - start
        print(f"PASS {elapsed:.1f}s")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
