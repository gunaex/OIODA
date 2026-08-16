#!/usr/bin/env python3
"""Gate 04: Design persistence — SQLite durability without uvicorn."""
import sys, time, json, tempfile, os

def main(log_dir: str) -> int:
    start = time.time()
    try:
        from infra_again.flow.models import DesignBaseline, DesignStatus
        from infra_again.flow.api import _persist_design, _load_design
        from infra_again.flow.simulator import create_demo_flow

        # Use temp DB
        db_path = os.path.join(log_dir, "test-design.db")

        # Phase 1: Create, generate, accept, persist
        design = DesignBaseline(design_id="DESIGN-T01")
        flow = create_demo_flow()
        flow.architecture_graph_id = design.design_id

        import hashlib
        design.requirements_checksum = hashlib.sha256(b"req-v1").hexdigest()[:16]
        design.architecture_checksum = hashlib.sha256(b"arch-v1").hexdigest()[:16]
        design.flow_checksum = hashlib.sha256(b"flow-v1").hexdigest()[:16]
        design.status = DesignStatus.REVIEW_READY
        design.accept("qa")

        # Persist using the same DB path
        os.environ["INFRA_AGAIN_DB"] = db_path
        _persist_design(design, flow)
        del os.environ["INFRA_AGAIN_DB"]

        # Record values for restart comparison
        acc_rev = design.revision
        acc_req = design.requirements_checksum
        acc_arch = design.architecture_checksum
        acc_flow = design.flow_checksum
        acc_at = design.accepted_at
        acc_by = design.accepted_by
        print(f"  Accepted: rev={acc_rev} by={acc_by} at={acc_at[:19]}")

        # Phase 2: New store — load and verify
        loaded = _load_design("DESIGN-T01")
        assert loaded is not None, "Design not found after persist"
        assert loaded.status == DesignStatus.BASELINE_FROZEN, f"Status: {loaded.status}"
        assert loaded.revision == acc_rev, f"Revision: {loaded.revision} != {acc_rev}"
        assert loaded.requirements_checksum == acc_req
        assert loaded.architecture_checksum == acc_arch
        assert loaded.flow_checksum == acc_flow
        assert loaded.accepted_at == acc_at
        assert loaded.accepted_by == acc_by
        print(f"  Restart: status={loaded.status.value} checksums preserved")

        # Phase 3: Request change, persist, reload
        loaded.request_change("Needs encryption")
        _persist_design(loaded, flow)

        loaded2 = _load_design("DESIGN-T01")
        assert loaded2 is not None
        assert loaded2.status == DesignStatus.CHANGE_REQUESTED
        assert len(loaded2.change_requests) == 1
        assert "encryption" in loaded2.change_requests[0]["comment"]
        print(f"  Change request: {loaded2.status.value} survives reload")

        # Phase 4: Material change creates new revision
        new_design = DesignBaseline(
            design_id="DESIGN-T01",
            revision=loaded2.revision + 1,
            status=DesignStatus.REVIEW_READY,
            requirements_checksum=hashlib.sha256(b"req-v2").hexdigest()[:16],
            architecture_checksum=loaded2.architecture_checksum,
            flow_checksum=hashlib.sha256(b"flow-v2").hexdigest()[:16],
        )
        assert new_design.revision == 2
        assert new_design.requirements_checksum != acc_req
        _persist_design(new_design, flow)
        loaded3 = _load_design("DESIGN-T01")
        assert loaded3.revision == 2
        assert loaded3.status == DesignStatus.REVIEW_READY
        print(f"  Material change: rev={loaded3.revision} status={loaded3.status.value}")

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
        for ext in ["", "-wal", "-shm"]:
            p = db_path + ext
            if os.path.exists(p):
                os.unlink(p)

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
