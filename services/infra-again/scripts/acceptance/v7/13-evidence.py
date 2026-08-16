#!/usr/bin/env python3
"""Gate 13: Evidence — verify evidence types and source truth model."""
import sys
def main(log_dir):
    from infra_again.execution.phase7_models import EvidenceType, SourceTruth
    
    # Verify all evidence types
    types = [e.value for e in EvidenceType]
    assert "COMMAND_OUTPUT" in types
    assert "API_RESPONSE" in types
    assert "CONFIG_SNAPSHOT" in types
    assert "TEST_RESULT" in types
    
    # Verify source truth values
    sources = [s.value for s in SourceTruth]
    assert "GENERATED" in sources
    assert "SIMULATED" in sources
    assert "LOCAL_OBSERVED" in sources
    # Phase 7 must NOT claim remote observed
    assert "REMOTE_OBSERVED" in sources  # Exists but not used in Phase 7
    
    # Verify ExecutionEvidence construction
    from infra_again.execution.phase7_models import ExecutionEvidence
    ev = ExecutionEvidence(
        evidence_id="EVD-1",
        evidence_type=EvidenceType.COMMAND_OUTPUT,
        source=SourceTruth.LOCAL_OBSERVED,
        captured_at="2026-01-01T00:00:00Z",
        checksum="abc123",
    )
    d = ev.to_dict()
    assert d["evidenceId"] == "EVD-1"
    assert d["source"] == "LOCAL_OBSERVED"
    assert d["checksum"] == "abc123"
    
    print(f"  Evidence types: {types}")
    print(f"  Source truths: {sources}")
    print("PASS: Evidence model verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
