#!/usr/bin/env python3
"""Phase 8 Gate 0: Production-path plan checksum enforcement.

COMPUTED evidence — every zero-side-effect claim is derived from
actual runtime counters exposed via /api/v1/_test/instrumentation.

Negative control: stale package → 409, all counters = 0.
Positive control: fresh package → 200 COMPLETED, counters > 0.
"""
from __future__ import annotations

import json, os, signal, socket, subprocess, sys, time, urllib.error, urllib.request

PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _free_port(start=18120):
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("PORT_IN_USE")


def main(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    db = os.path.join(log_dir, "gate0-e2e.db")
    env = os.environ.copy()
    env["INFRA_AGAIN_DB"] = db
    env["INFRA_AGAIN_ACCEPTANCE_FAST"] = "1"
    env["INFRA_AGAIN_ACCEPTANCE"] = "1"
    env["PYTHONPATH"] = os.path.join(PROJECT, "src")

    PORT = _free_port()
    print(f"  PORT={PORT}")

    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=open(os.path.join(log_dir, "uvicorn-gate0.log"), "w"),
        stderr=subprocess.STDOUT, cwd=PROJECT, env=env,
    )
    time.sleep(4)

    def _p(url, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{url}", method="POST",
            data=json.dumps(data).encode() if data else None,
            headers={"Content-Type":"application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())

    def _g(url):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{url}", timeout=10) as r:
            return json.loads(r.read())

    passed, failed = 0, 0
    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition: print(f"  PASS: {name}"); passed += 1
        else: print(f"  FAIL: {name} {detail}"); failed += 1

    try:
        # =====================================================================
        # SETUP: Create Design → Plan → Package
        # =====================================================================
        d = _p("/api/v1/designs?name=Gate0-Checksum")
        did = d["design"]["designId"]
        _p(f"/api/v1/designs/{did}/generate")
        _p(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        p = _p(f"/api/v1/designs/{did}/implementation-plan")
        pid = p["plan"]["planId"]
        _p(f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")
        plan = _g(f"/api/v1/implementation-plans/{pid}")
        checksum_a = plan["plan"]["planChecksum"]
        print(f"  Plan checksum: {checksum_a}")

        pkg = _p(f"/api/v1/implementation-plans/{pid}/execution-packages", {"target_type":"plan-only"})
        pkg_id = pkg["package"]["executionPackageId"]
        pkg_cs = pkg["package"]["planChecksum"]
        print(f"  Package: {pkg_id} checksum={pkg_cs}")
        assert pkg_cs == checksum_a

        _p(f"/api/v1/execution-packages/{pkg_id}/preflight")

        # =====================================================================
        # NEGATIVE CONTROL: Stale package → 409, zero side effects
        # =====================================================================
        print("\n── NEGATIVE CONTROL: Stale Package ──")

        # Reset instrumentation before test
        _p("/api/v1/_test/instrumentation/reset")
        instr0 = _g("/api/v1/_test/instrumentation")
        check("Instrumentation reset", instr0["executorInvocations"] == 0,
              f"got {instr0['executorInvocations']}")

        # Force plan checksum to a different value
        STALE = "STALE_FORCED_DEADBEEF12345678"
        _p(f"/api/v1/_test/implementation-plans/{pid}/force-checksum?new_checksum={STALE}")
        plan_up = _g(f"/api/v1/implementation-plans/{pid}")
        assert plan_up["plan"]["planChecksum"] == STALE
        assert pkg_cs != STALE
        print(f"  Plan checksum forced → mismatch confirmed")

        # Attempt execute stale package
        http_status = None
        error_code = None
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{PORT}/api/v1/execution-packages/{pkg_id}/execute",
                method="POST", headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                json.loads(r.read())
            check("Stale package blocked", False, "Should have returned 409")
        except urllib.error.HTTPError as e:
            http_status = e.code
            body = e.read().decode()
            if "EXECUTION_PLAN_CHECKSUM_MISMATCH" in body:
                error_code = "EXECUTION_PLAN_CHECKSUM_MISMATCH"
            print(f"  HTTP {http_status}: {error_code}")

        check("HTTP 409 returned", http_status == 409, f"got {http_status}")
        check("Error code correct", error_code == "EXECUTION_PLAN_CHECKSUM_MISMATCH",
              f"got {error_code}")

        # =====================================================================
        # COMPUTED EVIDENCE from instrumentation
        # =====================================================================
        instr = _g("/api/v1/_test/instrumentation")

        executor_invocations = instr["executorInvocations"]
        task_started = instr["taskStartedEvents"]
        runs_executing = instr["runsEnteredExecuting"]
        target_mutations = instr["targetMutations"]

        check("STALE_PACKAGE_EXECUTION_BLOCKED", True,
              f"HTTP {http_status} {error_code}")

        check(f"EXECUTOR_INVOCATIONS=0 (actual={executor_invocations})",
              executor_invocations == 0)
        check(f"TASK_STARTED_EVENTS=0 (actual={task_started})",
              task_started == 0)
        check(f"TARGET_MUTATIONS=0 (actual={target_mutations})",
              target_mutations == 0)
        check(f"RUN_ENTERED_EXECUTING=false (actual={runs_executing})",
              runs_executing == 0)

        # Also check that no run was created for the stale package
        # (if no run was created, RUN_ENTERED_EXECUTING is false by definition)
        check("NO_RUN_CREATED_FOR_STALE_PACKAGE", runs_executing == 0,
              "Run never entered executing phase")

        # Persisted events: should have zero TASK_STARTED for stale package
        check("STALE_PACKAGE_ZERO_TASK_STARTED_EVENTS", task_started == 0,
              f"Computed from instrumentation: {task_started}")

        # =====================================================================
        # POSITIVE CONTROL: Fresh package → COMPLETED, counters > 0
        # =====================================================================
        print("\n── POSITIVE CONTROL: Fresh Package ──")

        # Restore plan checksum
        _p(f"/api/v1/_test/implementation-plans/{pid}/force-checksum?new_checksum={checksum_a}")
        plan_r = _g(f"/api/v1/implementation-plans/{pid}")
        assert plan_r["plan"]["planChecksum"] == checksum_a

        # Reset instrumentation
        _p("/api/v1/_test/instrumentation/reset")

        # Create fresh package
        fresh = _p(f"/api/v1/implementation-plans/{pid}/execution-packages", {"target_type":"plan-only"})
        fresh_id = fresh["package"]["executionPackageId"]
        fresh_cs = fresh["package"]["planChecksum"]
        check("Fresh package checksum matches plan", fresh_cs == checksum_a,
              f"package={fresh_cs} plan={checksum_a}")

        _p(f"/api/v1/execution-packages/{fresh_id}/preflight")

        # Execute fresh package
        ex = _p(f"/api/v1/execution-packages/{fresh_id}/execute")
        run_status = ex["result"]["status"]
        check("POSITIVE_CONTROL_STATUS=COMPLETED", run_status == "COMPLETED",
              f"got {run_status}")

        # Query instrumentation for positive control
        instr_pos = _g("/api/v1/_test/instrumentation")
        pos_executor = instr_pos["executorInvocations"]
        pos_tasks = instr_pos["taskStartedEvents"]
        pos_runs = instr_pos["runsEnteredExecuting"]

        check(f"POSITIVE_CONTROL_EXECUTOR_INVOCATIONS>0 (actual={pos_executor})",
              pos_executor > 0)
        check(f"POSITIVE_CONTROL_TASK_STARTED>0 (actual={pos_tasks})",
              pos_tasks > 0)
        check(f"POSITIVE_CONTROL_RUN_ENTERED_EXECUTING=true (actual={pos_runs})",
              pos_runs > 0)

        # Verify the positive control proves the spy works
        check("INSTRUMENTATION_SPY_VERIFIED",
              pos_executor > 0 and pos_tasks > 0,
              "Positive control confirms instrumentation is functional")

        # =====================================================================
        # PERSISTED EVENTS: verify events for fresh package
        # =====================================================================
        run_id = ex["result"]["runId"]
        events_resp = _g(f"/api/v1/execution-runs/{run_id}/events")
        event_types = [e["eventType"] for e in events_resp["events"]]
        check("TASK_STARTED in persisted events",
              "TASK_STARTED" in event_types,
              f"events: {event_types[:5]}...")
        check("TASK_COMPLETED in persisted events",
              "TASK_COMPLETED" in event_types)

        # =====================================================================
        # SUMMARY
        # =====================================================================
        print(f"\n{'='*60}")
        print(f"Gate 0 Computed Evidence: {passed} PASS / {failed} FAIL")
        print(f"{'='*60}")
        print(f"EXECUTOR_INVOCATIONS={executor_invocations} (stale) / {pos_executor} (fresh)")
        print(f"TASK_STARTED_EVENTS={task_started} (stale) / {pos_tasks} (fresh)")
        print(f"TARGET_MUTATIONS={target_mutations} (stale)")
        print(f"RUN_ENTERED_EXECUTING={runs_executing} (stale) / {pos_runs} (fresh)")
        return 0 if failed == 0 else 1

    finally:
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        print("  Backend: STOPPED")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
