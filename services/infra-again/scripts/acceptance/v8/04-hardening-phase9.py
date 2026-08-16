#!/usr/bin/env python3
"""Phase 8.2-9 Consolidated Acceptance: Hardening + Controlled Real Readiness.

Tests (local, no real AWS required):
  8.2A: Idempotency
  8.2D: Approval Immutability
  8.2E: Cost Safety
  8.2F: Account Mismatch
  8.2G: Ownership Negative
  8.2B/C: Reconciliation
  9.x:  Promotion model, gates, blast radius, UAT, rollback, separation of duties
"""
from __future__ import annotations

import json, sys, os

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(PROJECT, "src"))


def main(log_dir: str) -> int:
    from infra_again.execution.sandbox_hardening import run_all_hardening_tests
    from infra_again.execution.phase9_models import (
        PromotionPackage, EnvironmentTarget, EnvironmentClassification,
        BlastRadius, PromotionGate, PromotionGateState,
        UATState, RollbackPlan, MaintenanceWindow,
        PHASE9_POLICY, REQUIRED_PROMOTION_GATES,
        create_sandbox_environment, create_controlled_real_target,
    )

    passed, failed = 0, 0
    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition: print(f"  PASS: {name}"); passed += 1
        else: print(f"  FAIL: {name} {detail}"); failed += 1

    # =========================================================================
    # Phase 8.2: Sandbox Hardening
    # =========================================================================
    print("── Phase 8.2: Sandbox Hardening ──")
    hw = run_all_hardening_tests()

    # Idempotency
    idem = hw["results"]["idempotency"]
    check("8.2A: First execution allowed", idem["firstAllowed"])
    check("8.2A: Duplicate key blocked", idem["secondBlocked"])
    check("8.2A: Different key allowed", idem["differentKeyAllowed"])

    # Approval Immutability
    appr = hw["results"]["approvalImmutability"]
    check("8.2D: Approval immutability all pass", appr["allPass"])
    check("8.2D: SANDBOX_APPROVAL_INVALIDATED on mismatch",
          appr["SANDBOX_APPROVAL_INVALIDATED_on_mismatch"])

    # Cost Safety
    cost = hw["results"]["costSafety"]
    check("8.2E: Within ceiling allowed", cost["withinCeilingAllowed"])
    check("8.2E: Exceeds ceiling blocked", cost["exceedsCeilingBlocked"])
    check("8.2E: SANDBOX_COST_LIMIT_EXCEEDED code",
          cost["SANDBOX_COST_LIMIT_EXCEEDED_on_overage"])

    # Account Mismatch
    acct = hw["results"]["accountMismatch"]
    check("8.2F: Matching account allowed", acct["matchAllowed"])
    check("8.2F: Mismatched account blocked", acct["mismatchBlocked"])
    check("8.2F: SANDBOX_ACCOUNT_MISMATCH detected",
          acct["SANDBOX_ACCOUNT_MISMATCH_detected"])

    # Ownership Negative
    own = hw["results"]["ownershipNegative"]
    check("8.2G: Correct ownership proven", own["correctOwnershipProven"])
    check("8.2G: All negatives blocked", own["allNegativesBlocked"])

    # Reconciliation
    rec = hw["results"]["reconciliation"]
    check("8.2B/C: Reconciliation logic exists",
          rec["REQUIRES_RECONCILIATION_on_ambiguous"])

    # =========================================================================
    # Phase 9: Controlled Real Readiness
    # =========================================================================
    print("\n── Phase 9: Controlled Real Readiness ──")

    # Environment model
    sandbox_env = create_sandbox_environment("123456789012", "us-east-1")
    check("9.1: SANDBOX environment created",
          sandbox_env.classification == EnvironmentClassification.SANDBOX)
    check("9.1: SANDBOX blast radius LOW",
          sandbox_env.blast_radius == BlastRadius.LOW)
    check("9.1: SANDBOX production=false", not sandbox_env.production)

    cr_env = create_controlled_real_target("123456789012", "us-east-1")
    check("9.1: CONTROLLED_REAL created",
          cr_env.classification == EnvironmentClassification.CONTROLLED_REAL)
    check("9.1: CONTROLLED_REAL blast radius UNKNOWN",
          cr_env.blast_radius == BlastRadius.UNKNOWN)

    # Promotion gates
    check("9.3: Required gates defined", len(REQUIRED_PROMOTION_GATES) >= 10,
          f"got {len(REQUIRED_PROMOTION_GATES)}")
    gate_ids = [g["id"] for g in REQUIRED_PROMOTION_GATES]
    for req_gate in ["SANDBOX_VERIFIED", "DESIGN_VALID", "PLAN_VALID",
                      "QA_EVIDENCE", "ROLLBACK_DEFINED", "APPROVERS_DEFINED",
                      "SEPARATION_OF_DUTIES", "BLAST_RADIUS"]:
        check(f"9.3: Gate {req_gate} exists", req_gate in gate_ids)

    # Promotion package with missing requirements → blocked
    pkg = PromotionPackage(
        target_environment=cr_env,
        change_set={"type": "s3_bucket", "name": "test"},
    )
    ready, blockers = pkg.check_readiness()
    check("9.3: Promotion blocked (no rollback/UAT/approvers)",
          not ready, f"blockers: {blockers[:3]}...")
    check("9.3: CONTROLLED_REAL_BLOCKED in blockers",
          any("CONTROLLED_REAL_BLOCKED" in b for b in blockers))

    # UAT gate
    check("9.8: UAT state model exists", UATState.NOT_EXECUTED.value == "NOT_EXECUTED")
    check("9.8: UAT NOT_EXECUTED by default",
          pkg.uat_state == UATState.NOT_EXECUTED)

    # Rollback plan
    rbp = RollbackPlan(
        description="Delete bucket and recreate",
        steps=["1. Delete bucket", "2. Create new bucket", "3. Verify"],
        failure_owner="platform-team",
    )
    check("9.7: Rollback plan defined", rbp.is_defined)

    rbp_empty = RollbackPlan()
    check("9.7: Empty rollback NOT defined", not rbp_empty.is_defined)

    # Maintenance window
    mw = MaintenanceWindow(
        start_time="2026-08-11T02:00:00Z",
        end_time="2026-08-11T04:00:00Z",
    )
    check("9.6: Maintenance window model exists",
          mw.window_type.value == "MAINTENANCE")
    check("9.6: Window not active (different time)",
          not mw.is_active())

    # Blast radius
    check("9.5: Blast radius UNKNOWN exists",
          BlastRadius.UNKNOWN.value == "UNKNOWN")
    check("9.5: Blast radius CRITICAL exists",
          BlastRadius.CRITICAL.value == "CRITICAL")

    # Separation of duties (use SANDBOX env to avoid early CONTROLLED_REAL block)
    sep_pkg = PromotionPackage(
        executor="alice", approvers=["alice"],
        target_environment=create_sandbox_environment("123456789012", "us-east-1"),
        rollback_plan=RollbackPlan(description="test", steps=["s1"], failure_owner="team"),
        maintenance_window=MaintenanceWindow(start_time="2026-08-11T02:00:00Z", end_time="2026-08-11T04:00:00Z"),
    )
    check("9.4: EXECUTOR cannot self-approve",
          any("EXECUTOR_CANNOT_SELF_APPROVE" in b for b in sep_pkg.check_readiness()[1]))

    # Phase 9 policy
    check("9.9: SANDBOX=ASK in Phase 9",
          PHASE9_POLICY["SANDBOX"] == "ASK")
    check("9.9: CONTROLLED_REAL=BLOCK in Phase 9",
          PHASE9_POLICY["CONTROLLED_REAL"] == "BLOCK")
    check("9.9: PRODUCTION=BLOCK in Phase 9",
          PHASE9_POLICY["PRODUCTION"] == "BLOCK")

    # =========================================================================
    # Summary
    # =========================================================================
    print(f"\n{'='*60}")
    print(f"Phase 8.2-9 Hardening + Readiness: {passed} PASS / {failed} FAIL")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
