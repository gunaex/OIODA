#!/usr/bin/env python3
"""Gate 04: Design Review lifecycle truth."""
import sys, time, json, os

def main(log_dir: str) -> int:
    start = time.time()
    db_path = os.path.join(log_dir, "review-test.db")
    try:
        from infra_again.flow import DesignBaseline, DesignStatus
        from infra_again.flow.api import _persist_design, _load_design

        design = DesignBaseline(design_id="DESIGN-R01")
        design.metadata = {"name": "Review Test", "description": "QA"}

        # State 1: REVIEW_READY
        design.status = DesignStatus.REVIEW_READY
        assert design.status == DesignStatus.REVIEW_READY
        print("  REVIEW_READY: OK")

        # State 2: Accept → BASELINE_FROZEN
        design.accept("qa-user")
        assert design.status == DesignStatus.BASELINE_FROZEN
        assert design.accepted_by == "qa-user"
        assert design.accepted_at
        assert design.revision == 1
        print(f"  BASELINE_FROZEN: rev={design.revision} by={design.accepted_by}")

        # Persist
        os.environ["INFRA_AGAIN_DB"] = db_path
        _persist_design(design)
        loaded = _load_design("DESIGN-R01")
        assert loaded.status == DesignStatus.BASELINE_FROZEN
        assert loaded.revision == 1
        assert loaded.accepted_by == "qa-user"
        del os.environ["INFRA_AGAIN_DB"]
        print("  Persisted frozen state: OK")

        # State 3: Request Change
        design.request_change("Add encryption layer", "api-gateway", "HIGH")
        assert design.status == DesignStatus.CHANGE_REQUESTED
        assert len(design.change_requests) == 1
        cr = design.change_requests[0]
        assert cr["comment"] == "Add encryption layer"
        assert cr["nodeId"] == "api-gateway"
        print(f"  CHANGE_REQUESTED: comment='{cr['comment']}' area={cr['nodeId']}")

        # Persist change
        os.environ["INFRA_AGAIN_DB"] = db_path
        _persist_design(design)
        loaded2 = _load_design("DESIGN-R01")
        assert loaded2.status == DesignStatus.CHANGE_REQUESTED
        assert len(loaded2.change_requests) == 1
        del os.environ["INFRA_AGAIN_DB"]
        print("  Change request persisted: OK")

        # State 4: New revision (re-review)
        design2 = DesignBaseline(
            design_id="DESIGN-R01", revision=loaded2.revision + 1,
            status=DesignStatus.REVIEW_READY,
            requirements_checksum="abc123",
            architecture_checksum="def456",
            flow_checksum="ghi789",
        )
        os.environ["INFRA_AGAIN_DB"] = db_path
        _persist_design(design2)
        loaded3 = _load_design("DESIGN-R01")
        assert loaded3.revision == 2
        assert loaded3.status == DesignStatus.REVIEW_READY
        del os.environ["INFRA_AGAIN_DB"]
        print(f"  Revision history: rev=2 status=REVIEW_READY")

        # Cleanup
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
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
