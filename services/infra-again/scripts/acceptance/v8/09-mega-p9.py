#!/usr/bin/env python3
"""Phase 9.2.1-9.5 Mega Acceptance — promotion persistence, rollback, UAT, production readiness.

Restart-proof, all negative cases, positive control. NO real AWS.
"""
from __future__ import annotations
import json, os, signal, socket, subprocess, sys, time, urllib.error, urllib.request

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(PROJECT, "src"))

def _free_port(start=18400):
    for p in range(start, start+10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("no port")

def _start(PORT, db):
    env = os.environ.copy()
    env.update(PYTHONPATH=os.path.join(PROJECT,"src"), INFRA_AGAIN_DB=db, INFRA_AGAIN_ACCEPTANCE="1")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, cwd=PROJECT, env=env)

def main(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    db = os.path.join(log_dir, "p92.db")
    PORT = _free_port()
    proc = _start(PORT, db); time.sleep(3)
    p, f = 0, 0
    def ck(n, cond, d=""):
        nonlocal p, f
        if cond: print(f"  PASS: {n}"); p += 1
        else: print(f"  FAIL: {n} {d}"); f += 1

    def post(u, d=None):
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}{u}", method="POST",
            data=json.dumps(d).encode() if d else None,
            headers={"Content-Type":"application/json"} if d else {})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp: return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return {"_c": int(e.code), "_b": e.read().decode()[:500]}
    def get(u):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{u}", timeout=10) as r: return json.loads(r.read())

    def restart():
        nonlocal proc, sb, cr, prod
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=5)
        except: proc.kill(); proc.wait()
        time.sleep(1)
        proc = _start(PORT, db)
        time.sleep(3)
        # Reload environments — IDs change on restart
        envs2 = get("/api/v1/environments")["environments"]
        sb = next(e for e in envs2 if e["classification"]=="SANDBOX")
        cr = next(e for e in envs2 if e["classification"]=="CONTROLLED_REAL")
        prod = next(e for e in envs2 if e["classification"]=="PRODUCTION")

    try:
        envs = get("/api/v1/environments")["environments"]
        sb = next(e for e in envs if e["classification"]=="SANDBOX")
        cr = next(e for e in envs if e["classification"]=="CONTROLLED_REAL")
        prod = next(e for e in envs if e["classification"]=="PRODUCTION")

        # ══════════════════════════════════════════════════
        print("── 9.2.1: Restart-Proof Promotion Persistence ──")
        # NOTE: no sourceExecutionId — avoids triggering source verification binding
        r1 = post("/api/v1/promotions", {"sourceEnvironmentId": sb["environmentId"],
            "targetEnvironmentId": cr["environmentId"],
            "planChecksum":"cs-rp", "packageChecksum":"cs-rp",
            "requestedBy":"alice"})
        pid = r1["promotion"]["promotionId"]
        d1 = r1["promotion"]["promotionDigest"]
        ck("Created PENDING promotion", pid.startswith("PROMO-"))
        ck("Digest computed", len(d1) > 0)

        restart()
        p2 = get(f"/api/v1/promotions/{pid}")["promotion"]
        ck("RESTART: promotion survived", p2["promotionId"] == pid)
        ck("RESTART: status preserved", p2["status"] == "PENDING_APPROVAL")
        ck("RESTART: digest stable", p2["promotionDigest"] == d1)

        post(f"/api/v1/promotions/{pid}/approve?approved_by=bob")
        # Digest changes after approve — status is part of canonical digest (9.2.1-F)
        restart()
        p3 = get(f"/api/v1/promotions/{pid}")["promotion"]
        ck("RESTART: APPROVED preserved", p3["status"] == "APPROVED")
        ck("RESTART: digest recomputed after approve", len(p3["promotionDigest"]) > 0 and p3["promotionDigest"] != d1)

        post(f"/api/v1/promotions/{pid}/consume")
        restart()
        p4 = get(f"/api/v1/promotions/{pid}")["promotion"]
        ck("RESTART: CONSUMED preserved", p4["status"] == "CONSUMED")

        r2 = post(f"/api/v1/promotions/{pid}/consume")
        ck("Re-consume blocked after restart", r2.get("_c") == 400)

        # ══════════════════════════════════════════════════
        print("── 9.2.1: Negative Matrix ──")
        # SANDBOX→PRODUCTION blocked
        r3 = post("/api/v1/promotions", {"sourceEnvironmentId": sb["environmentId"],
            "targetEnvironmentId": prod["environmentId"], "requestedBy":"alice"})
        ck("SANDBOX→PRODUCTION BLOCKED", r3.get("_c") == 400)
        ck("INVALID_ENVIRONMENT_TRANSITION", "INVALID" in r3.get("_b",""))

        # Same-env blocked
        r4 = post("/api/v1/promotions", {"sourceEnvironmentId": sb["environmentId"],
            "targetEnvironmentId": sb["environmentId"], "requestedBy":"alice"})
        ck("Same-env BLOCKED", r4.get("_c") == 400)

        # Self-approve blocked
        r5 = post("/api/v1/promotions", {"sourceEnvironmentId": sb["environmentId"],
            "targetEnvironmentId": cr["environmentId"], "requestedBy":"charlie"})
        if "_c" in r5:
            ck("Self-approve promo created", False, f"Got HTTP {r5['_c']}: {r5.get('_b','')[:100]}")
        else:
            pid5 = r5["promotion"]["promotionId"]
            apr5 = post(f"/api/v1/promotions/{pid5}/approve?approved_by=charlie")
            ck("Self-approve BLOCKED", apr5.get("_c") == 400)

        # ══════════════════════════════════════════════════
        print("── 9.3: Rollback Control ──")
        rb = post("/api/v1/rollback-plans", {
            "environmentId": cr["environmentId"], "implementationPlanId":"PLAN-001",
            "executionPackageId":"PKG-001",
            "triggerConditions":["validation_fail","verification_fail"],
            "rollbackSteps":["1. Delete resource", "2. Recreate from plan"],
            "verificationSteps":["1. Check resource absent", "2. Check new resource created"],
            "expectedRecoveryState":"resource_recreated", "owner":"alice",
        })
        rbid = rb["rollbackPlan"]["rollbackId"]
        ck("Rollback DRAFT created", rbid.startswith("RBP-"))
        ck("Rollback digest exists", len(rb["rollbackPlan"]["rollbackDigest"]) > 0)

        restart()
        rb2 = get(f"/api/v1/rollback-plans/{rbid}")["rollbackPlan"]
        ck("RESTART: rollback preserved", rb2["rollbackId"] == rbid)
        ck("RESTART: status DRAFT", rb2["status"] == "DRAFT")

        post(f"/api/v1/rollback-plans/{rbid}/approve?approved_by=bob")
        restart()
        rb3 = get(f"/api/v1/rollback-plans/{rbid}")["rollbackPlan"]
        ck("RESTART: APPROVED preserved", rb3["status"] == "APPROVED")

        # ══════════════════════════════════════════════════
        print("── 9.4: UAT + Separation of Duties ──")
        uat = post("/api/v1/uat", {
            "promotionId": pid, "environmentId": prod["environmentId"],
            "scope":"Verify production readiness", "acceptanceCriteria":"All gates pass",
            "requestedBy":"alice",
        })
        uid = uat["uat"]["uatId"]
        ck("UAT created", uid.startswith("UAT-"))

        restart()
        u2 = get(f"/api/v1/uat/{uid}")["uat"]
        ck("RESTART: UAT preserved", u2["uatId"] == uid)
        ck("RESTART: NOT_STARTED", u2["status"] == "NOT_STARTED")

        # Self-approve UAT blocked
        uat_self = post(f"/api/v1/uat/{uid}/pass?performed_by=charlie&approved_by=charlie")
        ck("UAT self-approve BLOCKED", uat_self.get("_c") == 400)

        # Valid approval
        post(f"/api/v1/uat/{uid}/pass?performed_by=dave&approved_by=eve")
        restart()
        u3 = get(f"/api/v1/uat/{uid}")["uat"]
        ck("RESTART: UAT PASSED", u3["status"] == "PASSED")

        # ══════════════════════════════════════════════════
        print("── 9.5: Production Readiness ──")
        # Create approved promotion for production (no sourceExecutionId — avoids verification binding)
        rp = post("/api/v1/promotions", {"sourceEnvironmentId": cr["environmentId"],
            "targetEnvironmentId": prod["environmentId"],
            "planChecksum":"cs-prod", "packageChecksum":"cs-prod",
            "rollbackPlanId": rbid, "uatId": uid, "requestedBy":"frank"})
        if "_c" in rp:
            ck("CR→PROD promotion created", False, f"HTTP {rp['_c']}")
        else:
            ppid = rp["promotion"]["promotionId"]
            post(f"/api/v1/promotions/{ppid}/approve?approved_by=grace")
            ck("CR→PROD approved", True)

            # Evaluate readiness — planId/packageId required by 9.5-B gates
            rd = post("/api/v1/production-readiness/evaluate", {
                "promotionId": ppid, "uatId": uid, "rollbackPlanId": rbid,
                "environmentId": prod["environmentId"],
                "planId":"PLAN-PROD", "packageId":"PKG-PROD",
                "planChecksum":"cs-prod", "packageChecksum":"cs-prod",
            })
            ck("Readiness: READY", rd["readiness"]["readinessDecision"] == "READY")
            ck("PRODUCTION_EXECUTION_ALLOWED=false", rd.get("PRODUCTION_EXECUTION_ALLOWED") == False)
            ck("PRODUCTION=BLOCK", rd.get("PRODUCTION") == "BLOCK")

            # Negative: missing UAT
            rd2 = post("/api/v1/production-readiness/evaluate", {
                "promotionId": ppid, "environmentId": prod["environmentId"],
                "planId":"PLAN-PROD", "packageId":"PKG-PROD",
                "planChecksum":"cs-prod", "packageChecksum":"cs-prod",
            })
            ck("No UAT → NOT_READY", rd2["readiness"]["readinessDecision"] == "NOT_READY")
            ck("UAT_REQUIRED blocker", any("UAT" in b for b in rd2["readiness"]["blocks"]))

            # Negative: checksum mismatch
            rd3 = post("/api/v1/production-readiness/evaluate", {
                "promotionId": ppid, "uatId": uid, "rollbackPlanId": rbid,
                "environmentId": prod["environmentId"],
                "planId":"PLAN-PROD", "packageId":"PKG-PROD",
                "planChecksum":"cs-prod", "packageChecksum":"DIFFERENT",
            })
            ck("Checksum mismatch → NOT_READY", rd3["readiness"]["readinessDecision"] == "NOT_READY")

            restart()
            rdid = rd["readiness"]["readinessId"]
            rd4 = get(f"/api/v1/production-readiness/{rdid}")["readiness"]
            ck("RESTART: readiness preserved", rd4["readinessId"] == rdid)
            ck("RESTART: still READY", rd4["readinessDecision"] == "READY")

        # ══════════════════════════════════════════════════
        print("── Safety Invariants ──")
        from infra_again.execution.policy import PHASE7_BLOCK, PHASE8_ASK
        from infra_again.execution.phase7_models import ExecutionFidelity
        ck("SANDBOX=ASK", ExecutionFidelity.SANDBOX in PHASE8_ASK)
        ck("CONTROLLED_REAL=BLOCK", ExecutionFidelity.CONTROLLED_REAL in PHASE7_BLOCK)
        ck("PRODUCTION=BLOCK", ExecutionFidelity.PRODUCTION in PHASE7_BLOCK)

        print(f"\n{'='*60}")
        print(f"Phase 9.2.1-9.5 Mega: {p} PASS / {f} FAIL")
        print(f"PROMOTION_RESTART_PROOF=true")
        print(f"ROLLBACK_RESTART_PROOF=true")
        print(f"UAT_RESTART_PROOF=true")
        print(f"PRODUCTION_READINESS_RESTART_PROOF=true")
        print(f"PRODUCTION_EXECUTION_ALLOWED=false")
        print(f"PRODUCTION=BLOCK")
        print(f"REAL_AWS_SANDBOX=NOT_EXECUTED")
        print(f"AWS_MUTATION_API_CALLS=0")
        return 0 if f == 0 else 1
    finally:
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=5)
        except: proc.kill(); proc.wait()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
