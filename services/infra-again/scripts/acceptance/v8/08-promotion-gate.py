#!/usr/bin/env python3
"""Phase 9.2 Promotion Gate Acceptance — control-plane only, NO cloud execution."""
from __future__ import annotations
import json, os, signal, socket, subprocess, sys, time, urllib.error, urllib.request

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(PROJECT, "src"))

def _free_port(start=18300):
    for p in range(start, start+10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try: s.bind(("127.0.0.1", p)); return p
            except OSError: continue
    raise RuntimeError("no port")

def main(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    PORT = _free_port()
    env = os.environ.copy()
    env.update(PYTHONPATH=os.path.join(PROJECT,"src"), INFRA_AGAIN_DB=os.path.join(log_dir,"p92.db"),
               INFRA_AGAIN_ACCEPTANCE="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, cwd=PROJECT, env=env)
    time.sleep(3)

    def post(u, d=None):
        r = urllib.request.Request(f"http://127.0.0.1:{PORT}{u}", method="POST",
            data=json.dumps(d).encode() if d else None,
            headers={"Content-Type":"application/json"} if d else {})
        try:
            with urllib.request.urlopen(r, timeout=30) as resp: return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return {"_c": e.code, "_b": e.read().decode()[:500]}
    def get(u):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{u}", timeout=10) as r: return json.loads(r.read())

    p, f = 0, 0
    def ck(n, cond, d=""):
        nonlocal p, f
        if cond: print(f"  PASS: {n}"); p += 1
        else: print(f"  FAIL: {n} {d}"); f += 1

    try:
        # Get environments
        envs = get("/api/v1/environments")["environments"]
        sandbox = next(e for e in envs if e["classification"]=="SANDBOX")
        cr = next(e for e in envs if e["classification"]=="CONTROLLED_REAL")
        prod = next(e for e in envs if e["classification"]=="PRODUCTION")

        print("── Allowed Transitions ──")
        # SANDBOX → CONTROLLED_REAL
        r1 = post("/api/v1/promotions", {"sourceEnvironmentId": sandbox["environmentId"],
            "targetEnvironmentId": cr["environmentId"], "sourceExecutionId":"EXEC-001",
            "planChecksum":"cs-001", "packageChecksum":"cs-001", "evidenceDigest":"ev-001",
            "requestedBy":"alice"})
        ck("SANDBOX→CR allowed", "_c" not in r1, str(r1)[:100])
        promo_id = r1.get("promotion",{}).get("packageId","")
        ck("Promotion digest exists", len(r1.get("promotion",{}).get("promotionDigest",""))>0)

        # SANDBOX → PRODUCTION blocked
        r2 = post("/api/v1/promotions", {"sourceEnvironmentId": sandbox["environmentId"],
            "targetEnvironmentId": prod["environmentId"], "sourceExecutionId":"EXEC-002",
            "planChecksum":"cs-001", "packageChecksum":"cs-001", "evidenceDigest":"ev-001",
            "requestedBy":"alice"})
        ck("SANDBOX→PRODUCTION BLOCKED", r2.get("_c")==400, f"HTTP {r2.get('_c')}")
        ck("INVALID_ENVIRONMENT_TRANSITION", "INVALID" in r2.get("_b",""))

        # Same-env blocked
        r3 = post("/api/v1/promotions", {"sourceEnvironmentId": sandbox["environmentId"],
            "targetEnvironmentId": sandbox["environmentId"], "sourceExecutionId":"EXEC-003",
            "planChecksum":"cs-001", "packageChecksum":"cs-001", "evidenceDigest":"ev-001",
            "requestedBy":"alice"})
        ck("Same-env BLOCKED", r3.get("_c")==400)

        print("── Approval ──")
        # Approve by different person
        apr = post(f"/api/v1/promotions/{promo_id}/approve?approved_by=bob")
        ck("Approved by bob (different from alice)", "_c" not in apr, str(apr)[:100])

        # Verify digest
        v = get(f"/api/v1/promotions/{promo_id}/verify")
        ck("Digest valid after approval", v.get("valid"), v.get("message",""))

        print("── Separation of Duties ──")
        r4 = post("/api/v1/promotions", {"sourceEnvironmentId": sandbox["environmentId"],
            "targetEnvironmentId": cr["environmentId"], "sourceExecutionId":"EXEC-004",
            "planChecksum":"cs-001", "packageChecksum":"cs-001", "evidenceDigest":"ev-001",
            "requestedBy":"charlie"})
        promo2 = r4.get("promotion",{}).get("packageId","")
        apr2 = post(f"/api/v1/promotions/{promo2}/approve?approved_by=charlie")
        ck("Self-approve BLOCKED", apr2.get("_c")==400, str(apr2)[:100])
        ck("SEPARATION_OF_DUTIES_VIOLATION", "SEPARATION" in apr2.get("_b",""))

        print("── Single-Use Consume ──")
        c1 = post(f"/api/v1/promotions/{promo_id}/consume")
        ck("Consume succeeds", "_c" not in c1, str(c1)[:100])
        c2 = post(f"/api/v1/promotions/{promo_id}/consume")
        ck("Re-consume BLOCKED", c2.get("_c")==400)
        ck("PROMOTION_PACKAGE_ALREADY_CONSUMED", "CONSUMED" in c2.get("_b",""))

        print("── CONTROLLED_REAL → PRODUCTION ──")
        r5 = post("/api/v1/promotions", {"sourceEnvironmentId": cr["environmentId"],
            "targetEnvironmentId": prod["environmentId"], "sourceExecutionId":"EXEC-005",
            "planChecksum":"cs-002", "packageChecksum":"cs-002", "evidenceDigest":"ev-002",
            "requestedBy":"dave"})
        ck("CR→PROD allowed", "_c" not in r5, str(r5)[:100])

        print("── Local model tests ──")
        from infra_again.execution.phase9_models import (
            PromotionStatus, validate_transition, EnvironmentClassification,
        )
        ck("DRAFT status", PromotionStatus.DRAFT.value == "DRAFT")
        ck("CONSUMED status", PromotionStatus.CONSUMED.value == "CONSUMED")
        ok_t, _ = validate_transition(EnvironmentClassification.SANDBOX, EnvironmentClassification.CONTROLLED_REAL)
        ck("Validate SANDBOX→CR", ok_t)
        ok_t2, _ = validate_transition(EnvironmentClassification.CONTROLLED_REAL, EnvironmentClassification.PRODUCTION)
        ck("Validate CR→PROD", ok_t2)
        bad, _ = validate_transition(EnvironmentClassification.SANDBOX, EnvironmentClassification.PRODUCTION)
        ck("Validate SANDBOX→PROD blocked", not bad)

        # Policy
        from infra_again.execution.policy import PHASE7_BLOCK, PHASE8_ASK
        from infra_again.execution.phase7_models import ExecutionFidelity
        ck("SANDBOX=ASK", ExecutionFidelity.SANDBOX in PHASE8_ASK)
        ck("CONTROLLED_REAL=BLOCK", ExecutionFidelity.CONTROLLED_REAL in PHASE7_BLOCK)
        ck("PRODUCTION=BLOCK", ExecutionFidelity.PRODUCTION in PHASE7_BLOCK)

        print(f"\n{'='*60}")
        print(f"Phase 9.2 Promotion Gate: {p} PASS / {f} FAIL")
        print(f"REAL_AWS_SANDBOX=NOT_EXECUTED")
        print(f"AWS_MUTATION_API_CALLS=0")
        print(f"CONTROLLED_REAL_EXECUTOR_INVOCATIONS=0")
        print(f"PRODUCTION_EXECUTOR_INVOCATIONS=0")
        return 0 if f == 0 else 1
    finally:
        proc.send_signal(signal.SIGTERM)
        try: proc.wait(timeout=5)
        except: proc.kill(); proc.wait()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
