#!/usr/bin/env python3
"""Gate 12: API runtime — real /execute, events, evidence, restart proof."""
import sys, json, os, subprocess, signal, socket, time, urllib.request, urllib.error
PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _free_port(start=18104):
    for p in range(start, start+20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("PORT_IN_USE")
def main(log_dir):
    db = os.path.join(log_dir, "api-e2e.db"); os.environ["INFRA_AGAIN_DB"] = db
    os.environ["INFRA_AGAIN_ACCEPTANCE_FAST"] = "1"  # Fast mode for plan-only executor
    PORT = _free_port()
    def post(url, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{url}", method="POST",
            data=json.dumps(data).encode() if data else None,
            headers={"Content-Type":"application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())
    def get(url):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{url}", timeout=10) as r: return json.loads(r.read())

    proc = subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],
        stdout=open(os.path.join(log_dir,"uvicorn-api.log"),"w"), stderr=subprocess.STDOUT, cwd=PROJECT)
    time.sleep(3)

    try:
        # Create design, plan, approve
        d=post("/api/v1/designs?name=APIE2E"); did=d["design"]["designId"]
        post(f"/api/v1/designs/{did}/generate")
        post(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        p=post(f"/api/v1/designs/{did}/implementation-plan"); pid=p["plan"]["planId"]
        post(f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")

        # Execution readiness
        rd=post(f"/api/v1/implementation-plans/{pid}/execution-readiness")
        assert rd["readiness"]["totalTasks"] > 0
        print(f"  Readiness: {rd['readiness']['totalTasks']} tasks")

        # Create package
        pkg=post(f"/api/v1/implementation-plans/{pid}/execution-packages",{"target_type":"plan-only"})
        pkg_id=pkg["package"]["executionPackageId"]
        plan_cs = pkg["package"]["planChecksum"]
        print(f"  Package: {pkg_id} checksum={plan_cs[:12]}")

        # Preflight
        pf=post(f"/api/v1/execution-packages/{pkg_id}/preflight")
        assert pf["status"] in ("PREFLIGHT_PASSED","PREFLIGHT_FAILED")
        print(f"  Preflight: {pf['status']}")

        # ACTUAL /execute (PLAN_ONLY — fast, no mutation)
        ex=post(f"/api/v1/execution-packages/{pkg_id}/execute")
        run_id=ex["result"]["runId"]
        run_status=ex["result"]["status"]
        assert run_status == "COMPLETED", f"Expected COMPLETED, got {run_status}"
        print(f"  API_EXECUTE_INVOKED=true")
        print(f"  Run: {run_id} status={run_status} passed={ex['result']['tasksPassed']} failed={ex['result']['tasksFailed']}")

        # Events from production persistence
        ev=get(f"/api/v1/execution-runs/{run_id}/events")
        event_types = [e["eventType"] for e in ev["events"]]
        print(f"  Events: {len(ev['events'])}")
        required_events = ["PREFLIGHT_STARTED","PREFLIGHT_PASSED","POLICY_ALLOWED",
                          "TASK_STARTED","TASK_COMPLETED","OBSERVATION_STARTED",
                          "OBSERVATION_COMPLETED","VALIDATION_STARTED","VALIDATION_PASSED",
                          "VERIFICATION_STARTED","VERIFICATION_PASSED"]
        for re in required_events:
            assert re in event_types, f"Missing event: {re}"
        print(f"  API_FINAL_STATUS=COMPLETED")

        # Evidence
        evd=get(f"/api/v1/execution-runs/{run_id}/evidence")
        evd_count = len(evd["evidence"])
        print(f"  Evidence: {evd_count} items")
        assert evd_count > 0, "Expected evidence"
        print(f"  API_EVIDENCE_COUNT={evd_count}")

        # Restart proof
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        print(f"  Backend: STOPPED")

        proc2 = subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],
            stdout=open(os.path.join(log_dir,"uvicorn-api2.log"),"w"), stderr=subprocess.STDOUT, cwd=PROJECT)
        time.sleep(3)
        try:
            r2 = get(f"/api/v1/execution-runs/{run_id}")
            assert r2["run"]["runId"] == run_id
            assert r2["run"]["status"] == "COMPLETED"
            print(f"  API_RESTART_RUN_PRESERVED=true (runId={run_id} status=COMPLETED)")

            ev2 = get(f"/api/v1/execution-runs/{run_id}/events")
            assert len(ev2["events"]) == len(ev["events"]), "Events should survive restart"
            print(f"  Restart events: {len(ev2['events'])} (match)")

            evd2 = get(f"/api/v1/execution-runs/{run_id}/evidence")
            assert len(evd2["evidence"]) == evd_count, "Evidence should survive restart"
            print(f"  Restart evidence: {len(evd2['evidence'])} (match)")
        finally:
            proc2.send_signal(signal.SIGTERM)
            try: proc2.wait(timeout=10)
            except subprocess.TimeoutExpired: proc2.kill(); proc2.wait()

        print("PASS: API /execute E2E + restart verified")
        return 0
    except Exception as e:
        print(f"FAIL: {e}"); import traceback; traceback.print_exc(); return 1
    finally:
        del os.environ["INFRA_AGAIN_DB"]
        del os.environ["INFRA_AGAIN_ACCEPTANCE_FAST"]
        for ext in ["","-wal","-shm"]:
            p=db+ext
            if os.path.exists(p): os.unlink(p)
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
