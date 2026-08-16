#!/usr/bin/env python3
"""Gate 07: API runtime — real uvicorn, create/approve/handoff."""
import sys, time, json, os, subprocess, signal, socket, urllib.request, urllib.error
PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PORT = 18094

def _free_port(start=DEFAULT_PORT, end=DEFAULT_PORT+50):
    """Find a free localhost port, starting from start."""
    for p in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError(f"PORT_IN_USE: no free port in {start}-{end}")

def main(log_dir):
    db = os.path.join(log_dir, "api-impl.db")
    os.environ["INFRA_AGAIN_DB"] = db
    PORT = _free_port()
    def post(url): req=urllib.request.Request(f"http://127.0.0.1:{PORT}{url}",method="POST"); return _call(req)
    def get(url): req=urllib.request.Request(f"http://127.0.0.1:{PORT}{url}"); return _call(req)
    def _call(req):
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e: raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}")
    proc = subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],stdout=open(os.path.join(log_dir,"uvicorn.log"),"w"),stderr=subprocess.STDOUT,cwd=PROJECT)
    time.sleep(3)
    try:
        _,d=post("/api/v1/designs?name=ImplTest");did=d["design"]["designId"]
        post(f"/api/v1/designs/{did}/generate")
        post(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        _,p=post(f"/api/v1/designs/{did}/implementation-plan");pid=p["plan"]["planId"]
        print(f"  Plan created: {pid}")
        _,wp=get(f"/api/v1/implementation-plans/{pid}/work-packages");assert len(wp["workPackages"])>=4
        _,rd=get(f"/api/v1/implementation-plans/{pid}/readiness");assert rd["readiness"]=="PARTIALLY_READY"
        _,dep=get(f"/api/v1/implementation-plans/{pid}/dependencies");assert len(dep["dependencies"])>=5
        post(f"/api/v1/implementation-plans/{pid}/approve?approved_by=qa")
        _,pm=get(f"/api/v1/implementation-plans/{pid}/handoff/pm");assert pm["contractVersion"]=="1.0"
        _,qa=get(f"/api/v1/implementation-plans/{pid}/handoff/qa");assert len(qa["testItems"])>0
        proc.send_signal(signal.SIGTERM);proc.wait(timeout=5)
        # Restart
        proc2=subprocess.Popen([PYTHON,"-m","uvicorn","infra_again.api:app","--host","127.0.0.1","--port",str(PORT)],stdout=open(os.path.join(log_dir,"uvicorn2.log"),"w"),stderr=subprocess.STDOUT,cwd=PROJECT)
        time.sleep(3)
        try:
            _,r=get(f"/api/v1/implementation-plans/{pid}")
            assert r["plan"]["status"]=="APPROVED_FOR_EXECUTION"
            assert r["plan"]["planChecksum"]==p["plan"]["planChecksum"]
            print(f"  Restart: status preserved, checksum match")
        finally: proc2.send_signal(signal.SIGTERM);proc2.wait(timeout=5)
        print("PASS")
        return 0
    except Exception as e: print(f"FAIL: {e}"); import traceback; traceback.print_exc(); return 1
    finally:
        del os.environ["INFRA_AGAIN_DB"]
        for ext in ["","-wal","-shm"]:
            p=db+ext
            if os.path.exists(p): os.unlink(p)
if __name__=="__main__": sys.exit(main(sys.argv[1] if len(sys.argv)>1 else "/tmp"))
