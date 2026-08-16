#!/usr/bin/env python3
"""Gate 10: Runner-loss — verify reconciliation state is required."""
import sys
def main(log_dir):
    from infra_again.execution.phase7_models import ExecutionTaskStatus
    
    # Verify REQUIRES_RECONCILIATION exists
    assert ExecutionTaskStatus.REQUIRES_RECONCILIATION.value == "REQUIRES_RECONCILIATION"
    
    # Verify statuses that exist (the reconciliation state machine)
    statuses = [s.value for s in ExecutionTaskStatus]
    assert "PLANNED" in statuses
    assert "EXECUTING" in statuses
    assert "COMPLETED" in statuses
    assert "FAILED" in statuses
    assert "REQUIRES_RECONCILIATION" in statuses
    
    print(f"  Statuses: {statuses}")
    print("PASS: Reconciliation state model verified")
    return 0
if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
