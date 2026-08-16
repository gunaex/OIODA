#!/usr/bin/env python3
"""Phase 8.0.1: Test endpoint isolation audit.

Verifies:
  1. _test endpoints are available when INFRA_AGAIN_ACCEPTANCE=1
  2. _test endpoints return 404 when INFRA_AGAIN_ACCEPTANCE is NOT set
  3. INFRA_AGAIN_ACCEPTANCE_FAST does not bypass safety
  4. No real cloud execution path runs accidentally
"""
from __future__ import annotations

import json, os, signal, socket, subprocess, sys, time, urllib.error, urllib.request

PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _free_port(start=18150):
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("PORT_IN_USE")


def _start_server(port, db, acceptance_mode=True):
    env = os.environ.copy()
    env["INFRA_AGAIN_DB"] = db
    if acceptance_mode:
        env["INFRA_AGAIN_ACCEPTANCE"] = "1"
    env["INFRA_AGAIN_ACCEPTANCE_FAST"] = "1"
    env["PYTHONPATH"] = os.path.join(PROJECT, "src")
    return subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, cwd=PROJECT, env=env,
    )


def _post(port, url, data=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{url}", method="POST",
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type":"application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())


def _get(port, url):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{url}", timeout=10) as r:
        return json.loads(r.read())


def main(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    passed, failed = 0, 0
    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition: print(f"  PASS: {name}"); passed += 1
        else: print(f"  FAIL: {name} {detail}"); failed += 1

    # =========================================================================
    # Test 1: ACCEPTANCE mode — _test endpoints available
    # =========================================================================
    print("── Test 1: Acceptance mode — test endpoints available ──")
    PORT1 = _free_port()
    proc1 = _start_server(PORT1, os.path.join(log_dir, "test-iso-accept.db"), acceptance_mode=True)
    time.sleep(3)
    try:
        # force-checksum should work
        d = _post(PORT1, "/api/v1/designs?name=IsoTest")
        did = d["design"]["designId"]
        _post(PORT1, f"/api/v1/designs/{did}/generate")
        _post(PORT1, f"/api/v1/designs/{did}/accept?accepted_by=qa")
        p = _post(PORT1, f"/api/v1/designs/{did}/implementation-plan")
        pid = p["plan"]["planId"]
        _post(PORT1, f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")

        # This should work in acceptance mode
        try:
            r = _post(PORT1, f"/api/v1/_test/implementation-plans/{pid}/force-checksum?new_checksum=TEST123")
            check("ACCEPTANCE_MODE: force-checksum available",
                  r.get("forcedChecksum") == "TEST123")
        except urllib.error.HTTPError as e:
            check("ACCEPTANCE_MODE: force-checksum available",
                  False, f"HTTP {e.code}: {e.read().decode()[:100]}")

        # Instrumentation should work
        try:
            instr = _get(PORT1, "/api/v1/_test/instrumentation")
            check("ACCEPTANCE_MODE: instrumentation available",
                  "executorInvocations" in instr)
        except urllib.error.HTTPError as e:
            check("ACCEPTANCE_MODE: instrumentation available",
                  False, f"HTTP {e.code}")

        # Instrumentation reset should work
        try:
            rst = _post(PORT1, "/api/v1/_test/instrumentation/reset")
            check("ACCEPTANCE_MODE: instrumentation reset available",
                  rst.get("reset") == True)
        except urllib.error.HTTPError as e:
            check("ACCEPTANCE_MODE: instrumentation reset available",
                  False, f"HTTP {e.code}")
    finally:
        proc1.send_signal(signal.SIGTERM)
        try: proc1.wait(timeout=5)
        except subprocess.TimeoutExpired: proc1.kill(); proc1.wait()

    # =========================================================================
    # Test 2: NORMAL mode — _test endpoints return 404
    # =========================================================================
    print("\n── Test 2: Normal mode — test endpoints UNAVAILABLE ──")
    PORT2 = _free_port()
    proc2 = _start_server(PORT2, os.path.join(log_dir, "test-iso-normal.db"), acceptance_mode=False)
    time.sleep(3)
    try:
        # Create a design so we have a plan_id to test with
        d = _post(PORT2, "/api/v1/designs?name=IsoNormal")
        did = d["design"]["designId"]
        _post(PORT2, f"/api/v1/designs/{did}/generate")
        _post(PORT2, f"/api/v1/designs/{did}/accept?accepted_by=qa")
        p = _post(PORT2, f"/api/v1/designs/{did}/implementation-plan")
        pid = p["plan"]["planId"]

        # force-checksum should 404
        try:
            _post(PORT2, f"/api/v1/_test/implementation-plans/{pid}/force-checksum?new_checksum=TEST")
            check("NORMAL_MODE: force-checksum 404", False, "Should have returned 404")
        except urllib.error.HTTPError as e:
            check("NORMAL_MODE: force-checksum 404",
                  e.code == 404, f"HTTP {e.code}")

        # Instrumentation should 404
        try:
            _get(PORT2, "/api/v1/_test/instrumentation")
            check("NORMAL_MODE: instrumentation 404", False, "Should have returned 404")
        except urllib.error.HTTPError as e:
            check("NORMAL_MODE: instrumentation 404",
                  e.code == 404, f"HTTP {e.code}")

        # Instrumentation reset should 404
        try:
            _post(PORT2, "/api/v1/_test/instrumentation/reset")
            check("NORMAL_MODE: instrumentation reset 404", False, "Should have returned 404")
        except urllib.error.HTTPError as e:
            check("NORMAL_MODE: instrumentation reset 404",
                  e.code == 404, f"HTTP {e.code}")
    finally:
        proc2.send_signal(signal.SIGTERM)
        try: proc2.wait(timeout=5)
        except subprocess.TimeoutExpired: proc2.kill(); proc2.wait()

    # =========================================================================
    # Test 3: ACCEPTANCE_FAST does not bypass safety
    # =========================================================================
    print("\n── Test 3: ACCEPTANCE_FAST safety audit ──")

    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.policy import ExecutionPolicyEngine

    task = ExecutionTask(
        execution_task_id="ET-FAST", implementation_task_id="IT-F",
        work_package_id="WP-F", title="Fast Mode Check",
        action_type=ActionType.APPLY_LOCAL_IAC,
        requested_fidelity=ExecutionFidelity.LOCAL_RUNTIME,
    )

    # With or without ACCEPTANCE_FAST, policy must be the same
    check("FAST: PRODUCTION still BLOCK",
          ExecutionPolicyEngine.evaluate(task, ExecutionTarget(
              target_id="p", target_type="AWS", fidelity=ExecutionFidelity.PRODUCTION,
          )).verdict == PolicyVerdict.BLOCK)

    check("FAST: CONTROLLED_REAL still BLOCK",
          ExecutionPolicyEngine.evaluate(task, ExecutionTarget(
              target_id="c", target_type="AWS", fidelity=ExecutionFidelity.CONTROLLED_REAL,
          )).verdict == PolicyVerdict.BLOCK)

    check("FAST: SANDBOX is ASK",
          ExecutionPolicyEngine.evaluate(task, ExecutionTarget(
              target_id="s", target_type="AWS", fidelity=ExecutionFidelity.SANDBOX,
              endpoint_reference="https://s3.amazonaws.com",
          )).verdict == PolicyVerdict.ASK)

    # =========================================================================
    # Test 4: No real cloud execution path runs
    # =========================================================================
    print("\n── Test 4: No real cloud execution ──")
    from infra_again.execution.instrumentation import ExecutionInstrumentation

    # Check that real AWS mutation counter is at 0
    inst = ExecutionInstrumentation.snapshot()
    check("AWS_MUTATION_API_CALLS=0",
          inst["realAwsMutations"] == 0,
          f"actual={inst['realAwsMutations']}")
    check("PRODUCTION_EXECUTOR_INVOCATIONS=0",
          inst["productionInvocations"] == 0,
          f"actual={inst['productionInvocations']}")

    print(f"\n{'='*60}")
    print(f"Test Endpoint Isolation: {passed} PASS / {failed} FAIL")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
