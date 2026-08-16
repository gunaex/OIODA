#!/usr/bin/env python3
"""Gate 06: Real fakecloud execution with production verifier + negative test."""
import sys, os, time, json, asyncio, tempfile, subprocess, shutil, signal, socket, urllib.request

def main(log_dir):
    from infra_again.execution.phase7_models import (
        ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType, PolicyVerdict,
    )
    from infra_again.execution.executor import FakecloudExecutor
    from infra_again.execution.policy import ExecutionPolicyEngine
    from infra_again.execution.verifier import ExecutionValidator, ExecutionVerifier

    fc_bin = shutil.which("fakecloud")
    if not fc_bin:
        print("FAIL: fakecloud not installed")
        return 1

    # Port check
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if s.connect_ex(("127.0.0.1", 4566)) == 0:
        s.close(); print("FAIL: Port 4566 occupied"); return 1
    s.close()

    # Start fakecloud
    fc_log = os.path.join(log_dir, "fakecloud.log")
    fc_proc = subprocess.Popen([fc_bin], stdout=open(fc_log,"w"), stderr=subprocess.STDOUT)
    print(f"  fakecloud PID: {fc_proc.pid}")
    for i in range(30):
        try:
            if urllib.request.urlopen("http://localhost:4566/_fakecloud/health", timeout=2).status == 200:
                break
        except: time.sleep(1)
    else:
        fc_proc.kill(); fc_proc.wait(); print("FAIL: fakecloud not healthy"); return 1
    print("  fakecloud: HEALTHY")

    try:
        corr_id = f"fc-golden-{os.urandom(4).hex()}"
        import boto3
        s3 = boto3.client("s3", endpoint_url="http://localhost:4566",
            aws_access_key_id="test", aws_secret_access_key="test", region_name="us-east-1")
        pre = [b["Name"] for b in s3.list_buckets().get("Buckets",[])]
        print(f"  PRE_EXISTED: {len(pre)} buckets")

        task = ExecutionTask(execution_task_id="ET-FC", implementation_task_id="IT-FC",
            work_package_id="WP-FC", title="Fakecloud S3 Golden Test",
            action_type=ActionType.APPLY_LOCAL_IAC,
            requested_fidelity=ExecutionFidelity.SIMULATED,
            validation_criteria=["Bucket exists", "Bucket accessible via provider API"])
        target = ExecutionTarget(target_id="fakecloud", target_type="FAKECLOUD",
            fidelity=ExecutionFidelity.SIMULATED, endpoint_reference="http://localhost:4566")

        policy = ExecutionPolicyEngine.evaluate(task, target)
        assert policy.verdict == PolicyVerdict.ALLOW
        print(f"  AIRLOCK: {policy.verdict.value}")

        # Execute
        executor = FakecloudExecutor()
        with tempfile.TemporaryDirectory() as work_dir:
            exec_result = asyncio.run(executor.execute(task, target, work_dir, corr_id))
        assert exec_result.get("status")=="COMPLETED", f"Execution failed: {exec_result}"
        print(f"  EXECUTOR_INVOKED: true status={exec_result['status']}")

        # Observe
        obs = asyncio.run(executor.observe(target))
        buckets_after = obs.get("observed",{}).get("buckets",[])
        bucket_name = [b for b in buckets_after if "infra-again" in b and corr_id[:8] in b]
        print(f"  OBSERVED: {len(buckets_after)} buckets, ours={'FOUND' if bucket_name else 'NOT_FOUND'}")
        assert bucket_name, "Bucket not observed"
        bn = bucket_name[0]

        # Production validator
        validations = ExecutionValidator.validate_fakecloud(obs)
        for v in validations:
            print(f"  VALIDATION: {v.criterion} [{v.status}]")
        assert all(v.status=="PASS" for v in validations)

        # Production verifier
        verification = ExecutionVerifier.verify(validations)
        print(f"  VERIFIER: {verification.result.value} — {verification.reason}")
        assert verification.result.value == "PASS"

        # ============================================================
        # NEGATIVE VERIFIER TEST
        # ============================================================
        print(f"\n  --- Negative Verifier Test ---")
        s3.delete_bucket(Bucket=bn)
        time.sleep(2)
        obs2 = asyncio.run(executor.observe(target))
        buckets2 = obs2.get("observed",{}).get("buckets",[])
        bucket_still_there = bn in buckets2

        validations2 = ExecutionValidator.validate_fakecloud(obs2)
        for v in validations2:
            print(f"  NEG-VALIDATION: {v.criterion} [{v.status}]")

        verification2 = ExecutionVerifier.verify(validations2)
        print(f"  NEG-VERIFIER: {verification2.result.value} — {verification2.reason}")
        assert verification2.result.value in ("FAIL", "INCONCLUSIVE"), \
            f"Negative verifier MUST NOT PASS (executor=COMPLETED, bucket_gone={not bucket_still_there})"

        # Cleanup (bucket already deleted)
        post = [b["Name"] for b in s3.list_buckets().get("Buckets",[])]
        print(f"  POST-CLEANUP: {len(post)} buckets, ours_gone={bn not in post}")
        assert bn not in post, "Bucket should be gone"

        print("PASS: Fakecloud real execution + verifier + negative test verified")
        return 0
    finally:
        fc_proc.kill(); fc_proc.wait()
        print("  fakecloud: STOPPED")

if __name__ == "__main__": sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp"))
