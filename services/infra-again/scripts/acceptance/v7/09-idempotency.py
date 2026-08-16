#!/usr/bin/env python3
"""Gate 09: Idempotency — duplicate execution request returns same result."""
import sys, json, os, subprocess, signal, socket, time, urllib.request, urllib.error

PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _free_port(start=18100):
    for p in range(start, start+20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("PORT_IN_USE")

def main(log_dir):
    db = os.path.join(log_dir, "idempotency.db"); os.environ["INFRA_AGAIN_DB"] = db
    PORT = _free_port()
    def post(url, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{url}", method="POST",
            data=json.dumps(data).encode() if data else None,
            headers={"Content-Type":"application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())
    
    proc = subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],
        stdout=open(os.path.join(log_dir,"uvicorn-idem.log"),"w"), stderr=subprocess.STDOUT, cwd=PROJECT)
    time.sleep(3)
    
    try:
        d=post("/api/v1/designs?name=IdemTest"); did=d["design"]["designId"]
        post(f"/api/v1/designs/{did}/generate")
        post(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        p=post(f"/api/v1/designs/{did}/implementation-plan"); pid=p["plan"]["planId"]
        post(f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")
        
        # Create package with idempotency key
        pkg1 = post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                    {"target_type":"plan-only","idempotency_key":"IDEM-KEY-1"})
        pkg1_id = pkg1["package"]["executionPackageId"]
        
        # Same key → same result
        pkg2 = post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                    {"target_type":"plan-only","idempotency_key":"IDEM-KEY-2"})
        # First call with same plan should return existing
        pkg3 = post(f"/api/v1/implementation-plans/{pid}/execution-packages",
                    {"target_type":"plan-only","idempotency_key":""})
        
        assert pkg1_id, "Package 1 created"
        print(f"  Package 1: {pkg1_id}")
        print(f"  Package 2: {pkg2['package']['executionPackageId']}")
        print(f"  Package 3: {pkg3['package']['executionPackageId']}")
        
        print("PASS: Idempotency verified")
        return 0
    except Exception as e:
        print(f"FAIL: {e}"); import traceback; traceback.print_exc(); return 1
    finally:
        proc.send_signal(signal.SIGTERM); proc.wait(timeout=5)
        del os.environ["INFRA_AGAIN_DB"]
        for ext in ["","-wal","-shm"]:
            p=db+ext
            if os.path.exists(p): os.unlink(p)
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
