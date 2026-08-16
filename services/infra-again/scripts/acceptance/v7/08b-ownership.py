#!/usr/bin/env python3
"""Gate 08b: Ownership-safe cleanup — current run deleted, other run survives."""
import sys, os, time, json, subprocess, shutil

def main(log_dir):
    kubectl = shutil.which("kubectl") or "kubectl"
    kind_bin = shutil.which("kind")
    if not kind_bin or not shutil.which("kubectl"):
        print("FAIL: kind/kubectl not installed")
        return 1

    cluster_name = "infra-again-acceptance-v7"
    ctx = f"kind-{cluster_name}"
    current_run = f"ownership-test-{os.urandom(4).hex()}"
    other_run = f"other-run-{os.urandom(4).hex()}"

    # Ensure cluster exists
    existing = subprocess.run([kind_bin, "get", "clusters"], capture_output=True, text=True)
    if cluster_name not in existing.stdout:
        r = subprocess.run([kind_bin, "create", "cluster", "--name", cluster_name],
                          capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"FAIL: kind create failed"); return 1

    try:
        # Create namespace A (current run — SHOULD be cleaned up)
        ns_a = f"infra-again-own-a-{os.urandom(4).hex()}"
        subprocess.run([kubectl, "--context", ctx, "create", "ns", ns_a], capture_output=True, timeout=10)
        subprocess.run([kubectl, "--context", ctx, "label", "ns", ns_a,
            f"app.kubernetes.io/managed-by=infra-again",
            f"infra-again/run-id={current_run}",
            f"infra-again/ephemeral=true",
            f"infra-again/acceptance-run=true",
        ], capture_output=True, timeout=10)
        print(f"  Namespace A: {ns_a} run-id={current_run[:16]}")

        # Create namespace B (other run — MUST survive cleanup)
        ns_b = f"infra-again-own-b-{os.urandom(4).hex()}"
        subprocess.run([kubectl, "--context", ctx, "create", "ns", ns_b], capture_output=True, timeout=10)
        subprocess.run([kubectl, "--context", ctx, "label", "ns", ns_b,
            f"app.kubernetes.io/managed-by=infra-again",
            f"infra-again/run-id={other_run}",
            f"infra-again/ephemeral=true",
            f"infra-again/acceptance-run=true",
        ], capture_output=True, timeout=10)
        print(f"  Namespace B: {ns_b} run-id={other_run[:16]} (different run)")

        # Import production ownership check
        from infra_again.execution.verifier import can_auto_cleanup

        # Verify A can be cleaned
        r = subprocess.run([kubectl, "--context", ctx, "get", "ns", ns_a, "-o", "json"],
                          capture_output=True, text=True, timeout=10)
        ns_a_labels = json.loads(r.stdout).get("metadata",{}).get("labels",{})
        a_meta = {"managed_by": ns_a_labels.get("app.kubernetes.io/managed-by",""),
                  "run_id": ns_a_labels.get("infra-again/run-id",""),
                  "ephemeral": ns_a_labels.get("infra-again/ephemeral",""),
                  "acceptance_run": ns_a_labels.get("infra-again/acceptance-run","")}
        assert can_auto_cleanup(a_meta, current_run), "A should be auto-cleanable"
        print(f"  can_auto_cleanup(A, currentRun): true")

        # Verify B CANNOT be cleaned
        r = subprocess.run([kubectl, "--context", ctx, "get", "ns", ns_b, "-o", "json"],
                          capture_output=True, text=True, timeout=10)
        ns_b_labels = json.loads(r.stdout).get("metadata",{}).get("labels",{})
        b_meta = {"managed_by": ns_b_labels.get("app.kubernetes.io/managed-by",""),
                  "run_id": ns_b_labels.get("infra-again/run-id",""),
                  "ephemeral": ns_b_labels.get("infra-again/ephemeral",""),
                  "acceptance_run": ns_b_labels.get("infra-again/acceptance-run","")}
        assert not can_auto_cleanup(b_meta, current_run), "B should NOT be auto-cleanable with current run"
        print(f"  can_auto_cleanup(B, currentRun): false (different runId)")

        # Perform cleanup for current_run only
        if can_auto_cleanup(a_meta, current_run):
            subprocess.run([kubectl, "--context", ctx, "delete", "ns", ns_a, "--wait=false"],
                          capture_output=True, timeout=30)
        if can_auto_cleanup(b_meta, current_run):
            subprocess.run([kubectl, "--context", ctx, "delete", "ns", ns_b, "--wait=false"],
                          capture_output=True, timeout=30)

        time.sleep(5)

        # Verify A is gone (with retry)
        a_gone = False
        for _ in range(10):
            time.sleep(2)
            r = subprocess.run([kubectl, "--context", ctx, "get", "ns", ns_a],
                              capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                a_gone = True
                break
        print(f"  A deleted: {a_gone}")
        assert a_gone, "Namespace A (current run) should be deleted"

        # Verify B survives
        r = subprocess.run([kubectl, "--context", ctx, "get", "ns", ns_b],
                          capture_output=True, text=True, timeout=10)
        b_survives = r.returncode == 0
        print(f"  B survives: {b_survives}")
        assert b_survives, "Namespace B (other run) MUST survive — different runId"

        # Clean up B explicitly (test-owned teardown, not AUTO cleanup)
        subprocess.run([kubectl, "--context", ctx, "delete", "ns", ns_b, "--wait=false"],
                      capture_output=True, timeout=30)
        print(f"  B: explicitly deleted (test teardown)")

        print("PASS: Ownership cleanup — current deleted, other survived")
        print(f"  OWNERSHIP_OTHER_RUN_SURVIVED=true")
        return 0
    finally:
        print(f"  Cluster '{cluster_name}': KEPT")

if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
