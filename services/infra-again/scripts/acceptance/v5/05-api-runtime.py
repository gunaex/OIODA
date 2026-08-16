#!/usr/bin/env python3
"""Gate 05: API runtime — real uvicorn processes, design RESTART durability."""
import sys, time, json, subprocess, signal, os, urllib.request, urllib.error, tempfile

PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def main(log_dir: str) -> int:
    start = time.time()
    db_path = os.path.join(log_dir, "api-test.db")
    os.environ["INFRA_AGAIN_DB"] = db_path

    def post(url, timeout=10):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{url}", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            raise RuntimeError(f"POST {url} → {e.code}: {body[:500]}")

    def get(url, timeout=10):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{url}", timeout=timeout) as r:
            return r.status, json.loads(r.read())

    def start_backend(p):
        proc = subprocess.Popen(
            [PYTHON, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(p)],
            stdout=open(os.path.join(log_dir, f"uvicorn-{p}.log"), "w"),
            stderr=subprocess.STDOUT,
            cwd=PROJECT,
        )
        # Wait for health
        for _ in range(30):
            time.sleep(0.3)
            try:
                code, _ = get("/health")
                if code == 200:
                    return proc
            except Exception:
                pass
        proc.kill()
        raise RuntimeError(f"Backend on port {p} did not become healthy")

    def stop_backend(proc):
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    try:
        port = 18092

        # --- Process A: create, generate, accept ---
        proc_a = start_backend(port)
        print(f"  Backend A started (PID={proc_a.pid})")

        _, d = post("/api/v1/designs?name=APITest")
        design_id = d["design"]["designId"]
        print(f"  Created: {design_id}")

        _, g = post(f"/api/v1/designs/{design_id}/generate")
        assert g["design"]["status"] == "REVIEW_READY"
        print(f"  Generated: {g['design']['status']}")

        _, sim = post(f"/api/v1/designs/{design_id}/simulate?scenario=HAPPY_PATH")
        assert len(sim["events"]) > 0
        print(f"  Simulated: {len(sim['events'])} events")

        _, acc = post(f"/api/v1/designs/{design_id}/accept?accepted_by=qa")
        assert acc["design"]["status"] == "BASELINE_FROZEN"
        acc_rev = acc["design"]["revision"]
        acc_req = acc["design"]["requirementsChecksum"]
        acc_arch = acc["design"]["architectureChecksum"]
        acc_flow = acc["design"]["flowChecksum"]
        acc_by = acc["design"]["acceptedBy"]
        acc_at = acc["design"]["acceptedAt"]
        print(f"  Accepted: {acc['design']['status']} rev={acc_rev} by={acc_by}")

        stop_backend(proc_a)
        print("  Backend A stopped")

        # --- Process B: verify restart durability ---
        proc_b = start_backend(port)
        print(f"  Backend B started (PID={proc_b.pid})")

        _, rd = get(f"/api/v1/designs/{design_id}")
        assert rd["design"]["status"] == "BASELINE_FROZEN", f"Status: {rd['design']['status']}"
        assert rd["design"]["revision"] == acc_rev
        assert rd["design"]["requirementsChecksum"] == acc_req
        assert rd["design"]["architectureChecksum"] == acc_arch
        assert rd["design"]["flowChecksum"] == acc_flow
        assert rd["design"]["acceptedBy"] == acc_by
        print(f"  Restart: all checksums + revision preserved")

        # Request change
        _, ch = post(f"/api/v1/designs/{design_id}/request-change?comment=Needs+TLS")
        assert ch["design"]["status"] == "CHANGE_REQUESTED"
        print(f"  Change requested: {ch['design']['status']}")

        stop_backend(proc_b)
        print("  Backend B stopped")

        # --- Process C: change survives restart ---
        proc_c = start_backend(port)
        print(f"  Backend C started (PID={proc_c.pid})")

        _, rd3 = get(f"/api/v1/designs/{design_id}")
        assert rd3["design"]["status"] == "CHANGE_REQUESTED"
        assert len(rd3["design"]["changeRequests"]) == 1
        print(f"  Restart 2: {rd3['design']['status']} preserved")

        stop_backend(proc_c)
        print("  Backend C stopped")

        elapsed = time.time() - start
        print(f"PASS {elapsed:.1f}s")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return 1
    finally:
        # Cleanup
        del os.environ["INFRA_AGAIN_DB"]
        for ext in ["", "-wal", "-shm"]:
            p = db_path + ext
            if os.path.exists(p):
                os.unlink(p)

if __name__ == "__main__":
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
    sys.exit(main(log_dir))
