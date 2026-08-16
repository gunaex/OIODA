#!/usr/bin/env python3
"""Gate 11: API/UI contract test — verify frontend model maps correctly to API response."""
import sys, json, os, subprocess, time, signal, socket, urllib.request, urllib.error

PYTHON = sys.executable
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _free_port(start=18096, end=18120):
    for p in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("PORT_IN_USE: no free port")

REQUIRED_FIELDS = [
    "planId", "designId", "designRevision", "status",
    "summary", "workPackages", "dependencies", "milestones",
    "risks", "blockers", "gates", "openQuestions",
    "baselineChecksums", "planChecksum", "criticalPath",
    "criticalPathDuration", "readiness", "approvedBy", "approvedAt",
]

WORK_PACKAGE_FIELDS = [
    "packageId", "planId", "title", "description", "packageType",
    "tasks", "dependencies", "parallelGroup", "status", "estimatedEffort",
]

TASK_FIELDS = [
    "taskId", "workPackageId", "title", "description", "category",
    "status", "priority", "executionMode", "dependencies",
    "inputs", "outputs", "acceptanceCriteria", "evidenceRequirements",
    "riskLevel", "estimatedEffort", "ownerRole", "automation",
    "derivedFrom", "deliveryStage", "localValidatable",
]

def main(log_dir):
    db = os.path.join(log_dir, "api-ui-contract.db")
    os.environ["INFRA_AGAIN_DB"] = db
    PORT = _free_port()

    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "infra_again.api:app", "--host", "127.0.0.1", "--port", str(PORT)],
        stdout=open(os.path.join(log_dir, "uvicorn-contract.log"), "w"),
        stderr=subprocess.STDOUT, cwd=PROJECT,
    )
    time.sleep(3)

    def post(url):
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}{url}", method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())

    errors = []
    try:
        # Create design, generate, accept, create plan
        _, d = post("/api/v1/designs?name=ContractTest")
        did = d["design"]["designId"]
        post(f"/api/v1/designs/{did}/generate")
        post(f"/api/v1/designs/{did}/accept?accepted_by=qa")
        _, p = post(f"/api/v1/designs/{did}/implementation-plan")
        plan = p["plan"]

        # Verify top-level fields
        for field in REQUIRED_FIELDS:
            if field not in plan:
                errors.append(f"plan.{field} missing")

        # Verify work package fields
        if plan.get("workPackages"):
            wp = plan["workPackages"][0]
            for field in WORK_PACKAGE_FIELDS:
                if field not in wp:
                    errors.append(f"workPackage.{field} missing")

            # Verify task fields
            if wp.get("tasks"):
                task = wp["tasks"][0]
                for field in TASK_FIELDS:
                    if field not in task:
                        errors.append(f"task.{field} missing")

                # derivedFrom must be non-empty
                df = task.get("derivedFrom", [])
                if len(df) == 0:
                    errors.append("task.derivedFrom is empty")
                else:
                    for item in df:
                        if "type" not in item or "id" not in item:
                            errors.append(f"derivedFrom item missing type/id: {item}")

        # Verify critical path
        cp = plan.get("criticalPath", [])
        if len(cp) == 0:
            errors.append("criticalPath is empty")

        # Verify planChecksum is non-empty
        if not plan.get("planChecksum"):
            errors.append("planChecksum is empty")

        if errors:
            print(f"FAIL: {len(errors)} contract violations:")
            for e in errors:
                print(f"  - {e}")
            return 1

        print(f"PASS: All {len(REQUIRED_FIELDS)} top-level + {len(WORK_PACKAGE_FIELDS)} WP + {len(TASK_FIELDS)} task fields verified")
        return 0

    except Exception as e:
        print(f"FAIL: {e}")
        import traceback; traceback.print_exc()
        return 1
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
        del os.environ["INFRA_AGAIN_DB"]
        for ext in ["", "-wal", "-shm"]:
            p = db + ext
            if os.path.exists(p): os.unlink(p)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
