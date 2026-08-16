#!/usr/bin/env python3
"""Gate 05: Large graph — 100 nodes, 200 edges, projections, serialization."""
import sys, time

def main(log_dir: str) -> int:
    start = time.time()
    try:
        from infra_again.flow import (
            generate_large_graph, project_high_level, project_detailed,
            project_security, project_data,
        )
        g = generate_large_graph(100, 200)
        assert len(g.nodes) == 100, f"Expected 100 nodes, got {len(g.nodes)}"
        assert len(g.edges) >= 190, f"Expected ~200 edges, got {len(g.edges)}"
        print(f"  Generated: {len(g.nodes)} nodes, {len(g.edges)} edges")

        # Serialization
        d = g.to_dict()
        assert len(d["nodes"]) == 100
        assert len(d["edges"]) == len(g.edges)
        print(f"  Serialized: {len(d['nodes'])} nodes, {len(d['edges'])} edges")

        # Projections
        hl = project_high_level(g)
        dl = project_detailed(g)
        sec = project_security(g)
        dat = project_data(g)
        for name, proj in [("HIGH_LEVEL", hl), ("DETAILED", dl), ("SECURITY", sec), ("DATA", dat)]:
            pd = proj.to_dict()
            assert "nodes" in pd and "edges" in pd
            print(f"  {name}: {len(pd['nodes'])} nodes, {len(pd['edges'])} edges")

        elapsed = time.time() - start
        print(f"PASS {elapsed:.1f}s")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
