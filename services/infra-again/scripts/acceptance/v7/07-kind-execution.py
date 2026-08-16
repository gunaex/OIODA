#!/usr/bin/env python3
"""Gate 07: Real kind execution with production verifier, ownership labels, negative test."""
import sys, os, time, json, asyncio, tempfile, subprocess, shutil

def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.executor import KindExecutor
    from infra_again.execution.policy import ExecutionPolicyEngine
    from infra_again.execution.verifier import ExecutionValidator, ExecutionVerifier

    kind_bin = shutil.which("kind")
    kubectl = shutil.which("kubectl") or "kubectl"
    if not kind_bin:
        print("FAIL: kind not installed (LOCAL_TARGET_UNAVAILABLE)")
        return 1

    cluster_name = "infra-again-acceptance-v7"
    ctx = f"kind-{cluster_name}"
    corr_id = f"kind-golden-{os.urandom(4).hex()}"

    # 1. Create/use cluster
    existing = subprocess.run([kind_bin, "get", "clusters"], capture_output=True, text=True)
    if cluster_name in existing.stdout:
        print(f"  Cluster '{cluster_name}': reusing")
    else:
        r = subprocess.run([kind_bin, "create", "cluster", "--name", cluster_name],
                          capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print(f"FAIL: kind create failed\n{r.stderr}")
            return 1
        print(f"  Cluster '{cluster_name}': CREATED")

    try:
        # 2. Verify kubectl
        r = subprocess.run([kubectl, "--context", ctx, "cluster-info"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            print("FAIL: kubectl cannot reach cluster")
            return 1
        print(f"  kubectl ({ctx}): READY")

        # 3. Policy
        target = ExecutionTarget(target_id="kind", target_type="KIND",
            fidelity=ExecutionFidelity.LOCAL_RUNTIME, environment_name=cluster_name,
            managed_by="INFRA_AGAIN")
        task = ExecutionTask(execution_task_id="ET-KIND", implementation_task_id="IT-KIND",
            work_package_id="WP-KIND", title="Kind Deploy Golden Test",
            action_type=ActionType.DEPLOY_LOCAL_WORKLOAD,
            requested_fidelity=ExecutionFidelity.LOCAL_RUNTIME,
            validation_criteria=["Deployment ready replicas match desired", "Service exists", "Namespace created"])
        policy = ExecutionPolicyEngine.evaluate(task, target)
        assert policy.verdict == PolicyVerdict.ALLOW
        print(f"  AIRLOCK: {policy.verdict.value}")

        # 4. Execute
        executor = KindExecutor()
        with tempfile.TemporaryDirectory() as work_dir:
            exec_result = asyncio.run(executor.execute(task, target, work_dir, corr_id))
        assert exec_result.get("status")=="COMPLETED", f"Execution failed: {exec_result}"
        ns_name = exec_result.get("namespace","")
        print(f"  NAMESPACE: {ns_name}")
        print(f"  EXECUTOR_INVOKED: true")

        # 5. Verify ownership labels
        r = subprocess.run([kubectl, "--context", ctx, "get", "ns", ns_name, "-o", "json"],
                          capture_output=True, text=True, timeout=10)
        ns_labels = json.loads(r.stdout).get("metadata",{}).get("labels",{})
        print(f"  OWNERSHIP: managed-by={ns_labels.get('app.kubernetes.io/managed-by','?')} run-id={ns_labels.get('infra-again/run-id','?')[:12]} ephemeral={ns_labels.get('infra-again/ephemeral','?')}")
        assert ns_labels.get("app.kubernetes.io/managed-by") == "infra-again"
        assert ns_labels.get("infra-again/ephemeral") == "true"

        # 6. Wait for deployment readiness
        ready = 0; desired = 0
        print(f"  Waiting for deployment (up to 90s)...")
        for i in range(30):
            time.sleep(3)
            r = subprocess.run([kubectl, "--context", ctx, "get", "deploy",
                f"app-{corr_id[:8]}", "-n", ns_name, "-o", "json"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                try:
                    dep = json.loads(r.stdout)
                    ready = dep.get("status",{}).get("readyReplicas",0)
                    desired = dep.get("spec",{}).get("replicas",0)
                    if ready == desired and ready > 0: break
                except: pass
        print(f"  DEPLOYMENT: desired={desired} ready={ready}")
        assert ready == 2, f"Expected 2 ready replicas, got {ready}"

        # 7. Observe + Validate (production validator)
        obs = asyncio.run(executor.observe(target))
        validations = ExecutionValidator.validate_kind(exec_result, obs)
        for v in validations:
            print(f"  VALIDATION: {v.criterion} [{v.status}] expected={v.expected} observed={v.observed}")
        assert all(v.status=="PASS" for v in validations), f"Validations failed: {[(v.criterion,v.status) for v in validations if v.status!='PASS']}"

        # 8. Verify (production verifier)
        verification = ExecutionVerifier.verify(validations)
        print(f"  VERIFIER: {verification.result.value} — {verification.reason}")
        assert verification.result.value == "PASS", f"Verifier expected PASS, got {verification.result.value}"

        # 9. Service check
        r = subprocess.run([kubectl, "--context", ctx, "get", "svc", f"svc-{corr_id[:8]}", "-n", ns_name],
                          capture_output=True, text=True, timeout=10)
        assert r.returncode == 0, "Service should exist"
        print(f"  SERVICE_EXISTS: true")

        # ============================================================
        # NEGATIVE VERIFIER TEST
        # ============================================================
        print(f"\n  --- Negative Verifier Test ---")
        # Negative test: scale to 1, observe, verify replicas != original expected (2)
        subprocess.run([kubectl, "--context", ctx, "scale", "deploy",
            f"app-{corr_id[:8]}", "-n", ns_name, "--replicas=1"],
            capture_output=True, timeout=10)
        time.sleep(5)
        obs2 = asyncio.run(executor.observe(target))
        obs2_data = obs2.get("observed", {})
        neg_ready = 0
        for k, v in obs2_data.items():
            if "deploy/" in k:
                neg_ready = v.get("readyReplicas", 0)
        print(f"  NEG-REPLICAS: ready={neg_ready} (expected=2, actual should be != 2)")
        
        # Assert: replicas are NOT 2 (proving executor success alone is insufficient)
        from infra_again.execution.phase7_models import ExecutionValidation
        neg_validations = [
            ExecutionValidation(criterion="Deployment ready replicas match desired (expected=2)",
                expected="ready=2", observed=f"ready={neg_ready}",
                status="PASS" if neg_ready == 2 else "FAIL"),
            ExecutionValidation(criterion="Namespace created",
                expected=ns_name, observed=ns_name, status="PASS"),
        ]
        for v in neg_validations:
            print(f"  NEG-VALIDATION: {v.criterion} [{v.status}] expected={v.expected} observed={v.observed}")
        
        verification2 = ExecutionVerifier.verify(neg_validations)
        print(f"  NEG-VERIFIER: {verification2.result.value} — {verification2.reason}")
        assert verification2.result.value in ("FAIL", "INCONCLUSIVE"), \
            f"Negative verifier MUST NOT PASS: executor was COMPLETED but replicas changed to {neg_ready}"

        # Restore replicas
        subprocess.run([kubectl, "--context", ctx, "scale", "deploy",
            f"app-{corr_id[:8]}", "-n", ns_name, "--replicas=2"],
            capture_output=True, timeout=10)

        # ============================================================
        # OWNERSHIP-SAFE CLEANUP
        # ============================================================
        print(f"\n  --- Cleanup ---")
        # Only cleanup current run's namespace (ownership labels match)
        if (ns_labels.get("app.kubernetes.io/managed-by") == "infra-again"
            and ns_labels.get("infra-again/ephemeral") == "true"
            and ns_labels.get("infra-again/acceptance-run") == "true"):
            subprocess.run([kubectl, "--context", ctx, "delete", "namespace", ns_name, "--wait=false"],
                          capture_output=True, timeout=30)
            print(f"  CLEANUP: namespace {ns_name} deleted (ownership verified)")
        else:
            print(f"  CLEANUP: SKIPPED (ownership not proven)")

        # Wait for cleanup
        for i in range(15):
            time.sleep(2)
            r2 = subprocess.run([kubectl, "--context", ctx, "get", "namespace", ns_name],
                               capture_output=True, text=True, timeout=10)
            if r2.returncode != 0: break
        ns_gone = r2.returncode != 0
        print(f"  POST-CLEANUP: {'GONE' if ns_gone else 'STILL_EXISTS'}")
        assert ns_gone, "Namespace should be gone"

        print("PASS: Kind real execution + verifier + negative test verified")
        return 0
    finally:
        print(f"  Cluster '{cluster_name}': KEPT")

if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
