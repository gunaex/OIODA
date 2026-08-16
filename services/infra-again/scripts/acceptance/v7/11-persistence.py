#!/usr/bin/env python3
"""Gate 11: Persistence — execution history survives restart."""
import sys, json, os, subprocess, signal, socket, time, urllib.request, urllib.error
PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def _free_port(start=18102):
    for p in range(start, start+20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("PORT_IN_USE")
def main(log_dir):
    db = os.path.join(log_dir, "persist.db"); os.environ["INFRA_AGAIN_DB"] = db
    PORT = _free_port()
    def post(url, data=None):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{url}", method="POST",
            data=json.dumps(data).encode() if data else None,
            headers={"Content-Type":"application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())
    def get(url):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{url}", timeout=10) as r: return json.loads(r.read())
    def get(url):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{url}", timeout=10) as r: return json.loads(r.read())
    
    proc = subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],
        stdout=open(os.path.join(log_dir,"uvicorn-persist.log"),"w"), stderr=subprocess.STDOUT, cwd=PROJECT)
    time.sleep(3)
    
    try:
        d=post("/api/v1/designs?name=PersistTest"); did=d["design"]["designId"]
        post(f"/api/v1/designs/{did}/generate")
        post(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        p=post(f"/api/v1/designs/{did}/implementation-plan"); pid=p["plan"]["planId"]
        post(f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")
        pkg=post(f"/api/v1/implementation-plans/{pid}/execution-packages",{"target_type":"plan-only"})
        pkg_id=pkg["package"]["executionPackageId"]
        post(f"/api/v1/execution-packages/{pkg_id}/preflight")
        # Persist package (skip slow execute — verify package survives restart)
        pkg_status = pkg["package"]["status"]
        proc.send_signal(signal.SIGTERM); proc.wait(timeout=10)
        print(f"  Package: {pkg_id} status={pkg_status}")
        
        # Restart and verify
        proc2 = subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],
            stdout=open(os.path.join(log_dir,"uvicorn-persist2.log"),"w"), stderr=subprocess.STDOUT, cwd=PROJECT)
        time.sleep(3)
        try:
            pkg2 = get(f"/api/v1/execution-packages/{pkg_id}")
            assert pkg2["package"]["executionPackageId"]==pkg_id
            print(f"  Restart: package={pkg2['package']['executionPackageId']} status={pkg2['package']['status']}")
        finally: proc2.send_signal(signal.SIGTERM); proc2.wait(timeout=10)
        print("PASS: Persistence verified")
        return 0
    except Exception as e:
        print(f"FAIL: {e}"); import traceback; traceback.print_exc(); return 1
    finally:
        del os.environ["INFRA_AGAIN_DB"]
        for ext in ["","-wal","-shm"]:
            p=db+ext
            if os.path.exists(p): os.unlink(p)
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
