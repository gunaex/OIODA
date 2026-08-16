"""Phase 7 Executors — PlanOnly, Fakecloud, Kind."""

from __future__ import annotations

import asyncio
import json
import os
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from .registry import ExecutionAdapter
from .phase7_models import (
    ExecutionTask, ExecutionTarget, ExecutionFidelity, ActionType,
    ExecutionEvidence, EvidenceType, SourceTruth,
)


# ===========================================================================
# PlanOnlyExecutor
# ===========================================================================

class PlanOnlyExecutor(ExecutionAdapter):
    """Generate and validate IaC without applying."""

    @property
    def supported_action_types(self) -> list[ActionType]:
        return [ActionType.GENERATE_IAC, ActionType.VALIDATE_IAC, ActionType.PLAN_IAC]

    @property
    def supported_fidelity(self) -> ExecutionFidelity:
        return ExecutionFidelity.PLAN_ONLY

    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        """Generate HCL, validate, plan — no apply."""
        import shutil
        result: dict[str, Any] = {"status": "COMPLETED", "outputs": [], "evidence": [], "artifacts": []}

        work_path = Path(work_dir)
        work_path.mkdir(parents=True, exist_ok=True)

        tofu = shutil.which("tofu")
        # Fast mode for acceptance: generate HCL only, skip tofu calls
        fast_mode = os.environ.get("INFRA_AGAIN_ACCEPTANCE_FAST", "") == "1"
        
        # Generate main.tf
        main_tf = work_path / "main.tf"
        main_tf.write_text(PlanOnlyExecutor._generate_hcl(task, correlation_id))
        result["artifacts"].append(str(main_tf))

        if fast_mode:
            result["outputs"].append({"command": "hcl-generated", "exit": 0, "stdout": "fast mode"})
            result["evidence"].append({
                "evidenceId": f"EVD-{uuid.uuid4().hex[:8].upper()}",
                "evidenceType": "CONFIG_SNAPSHOT",
                "source": "GENERATED",
                "checksum": hashlib.sha256(main_tf.read_bytes()).hexdigest(),
                "pathRef": str(main_tf),
            })
            return result

        if not tofu:
            return {"status": "FAILED", "reason": "tofu not installed"}

        result["artifacts"].append(str(main_tf))

        # tofu fmt
        proc = await asyncio.create_subprocess_exec(
            tofu, "fmt", str(main_tf),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        result["outputs"].append({"command": "fmt", "exit": proc.returncode, "stdout": stdout.decode(errors="replace")})

        # tofu init
        proc = await asyncio.create_subprocess_exec(
            tofu, "init",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
            env={**os.environ, "AWS_ENDPOINT_URL_S3": "http://localhost:4566"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        result["outputs"].append({"command": "init", "exit": proc.returncode, "stdout": stdout.decode(errors="replace")})

        # tofu validate
        proc = await asyncio.create_subprocess_exec(
            tofu, "validate",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        result["outputs"].append({"command": "validate", "exit": proc.returncode, "stdout": stdout.decode(errors="replace")})

        if proc.returncode != 0:
            result["status"] = "FAILED"
            result["error"] = stderr.decode(errors="replace")
            result["reason"] = f"tofu init failed: {stderr.decode(errors='replace')[:200]}"
            return result

        # tofu plan
        plan_file = work_path / "plan.tfplan"
        proc = await asyncio.create_subprocess_exec(
            tofu, "plan", "-out", str(plan_file),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=str(work_path),
            env={**os.environ, "AWS_ENDPOINT_URL_S3": "http://localhost:4566"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        plan_output = stdout.decode(errors="replace")
        result["outputs"].append({"command": "plan", "exit": proc.returncode, "stdout": plan_output})

        # Compute plan checksum
        if plan_file.exists():
            plan_checksum = hashlib.sha256(plan_file.read_bytes()).hexdigest()
            result["plan_checksum"] = plan_checksum
            result["evidence"].append({
                "evidenceId": f"EVD-{uuid.uuid4().hex[:8].upper()}",
                "evidenceType": "CONFIG_SNAPSHOT",
                "source": "GENERATED",
                "checksum": plan_checksum,
                "pathRef": str(plan_file),
            })

        result["status"] = "COMPLETED" if proc.returncode == 0 else "FAILED"
        return result

    @staticmethod
    def _generate_hcl(task: ExecutionTask, correlation_id: str) -> str:
        return f"""# INFRA-AGAIN Phase 7 — PLAN_ONLY
# Task: {task.title}
# Correlation: {correlation_id}

terraform {{
  required_version = ">= 1.0"
}}

provider "aws" {{
  region = "us-east-1"
  endpoints {{
    s3 = "http://localhost:4566"
  }}
  s3_use_path_style = true
  access_key = "test"
  secret_key = "test"
  skip_credentials_validation = true
  skip_requesting_account_id = true
}}

resource "aws_s3_bucket" "main" {{
  bucket = "infra-again-{correlation_id[:8]}-{task.execution_task_id.lower()}"
  tags = {{
    Name        = "{task.title}"
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        # PLAN_ONLY: observe artifacts on disk
        return {"observed": {"artifacts": "plan-only-execution"}, "observed_at": time.time()}

    async def destroy(self, task: ExecutionTask, target: ExecutionTarget, correlation_id: str) -> dict[str, Any]:
        # PLAN_ONLY never mutates anything — nothing exists to destroy.
        return {"status": "COMPLETED", "note": "PLAN_ONLY performed zero mutation — nothing to destroy"}


# ===========================================================================
# FakecloudExecutor
# ===========================================================================

class FakecloudExecutor(ExecutionAdapter):
    """Execute against local fakecloud (simulated AWS). S3 was the original
    (Phase 7) resource type; Phase N6 added ELB(v2)/Lambda/CloudWatch Logs —
    the minimum set needed to genuinely back AGAINPILOT's unconditionally-
    required EDGE_INGRESS/APPLICATION_ENTRY/OBSERVABILITY completeness
    roles at SIMULATED fidelity, each independently verified against a
    real running fakecloud (see catalog.py's notes on each entry)."""

    FAKECLOUD_ENDPOINT = "http://localhost:4566"

    @property
    def supported_action_types(self) -> list[ActionType]:
        return [ActionType.APPLY_LOCAL_IAC, ActionType.OBSERVE_RESOURCE,
                ActionType.VALIDATE_RESOURCE, ActionType.DESTROY_RUN_OWNED_RESOURCE]

    @property
    def supported_fidelity(self) -> ExecutionFidelity:
        return ExecutionFidelity.SIMULATED

    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        """Apply local IaC to fakecloud, observe, validate."""
        import shutil
        result: dict[str, Any] = {"status": "EXECUTING", "outputs": [], "evidence": []}

        tofu = shutil.which("tofu")
        if not tofu:
            return {"status": "FAILED", "reason": "tofu not installed"}

        work_path = Path(work_dir)
        work_path.mkdir(parents=True, exist_ok=True)

        # Generate and apply
        main_tf = work_path / "main.tf"
        main_tf.write_text(FakecloudExecutor._generate_hcl(task, correlation_id, work_path))

        env = {**os.environ, "AWS_ENDPOINT_URL_S3": "http://localhost:4566"}

        # init
        proc = await asyncio.create_subprocess_exec(tofu, "init", cwd=str(work_path),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        await asyncio.wait_for(proc.communicate(), timeout=60)

        # apply
        proc = await asyncio.create_subprocess_exec(tofu, "apply", "-auto-approve",
            cwd=str(work_path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=150)
        apply_output = stdout.decode(errors="replace")
        result["outputs"].append({"command": "apply", "exit": proc.returncode, "stdout": apply_output})

        if proc.returncode != 0:
            result["status"] = "FAILED"
            result["error"] = stderr.decode(errors="replace")
            return result

        result["status"] = "COMPLETED"
        return result

    @staticmethod
    def _bucket_name(task: ExecutionTask, correlation_id: str) -> str:
        bucket_name = f"infra-again-{correlation_id[:8]}-{task.execution_task_id.lower()}"
        return bucket_name.lower().replace("_", "-")  # S3 requires lowercase

    @staticmethod
    def _alb_name(task: ExecutionTask, correlation_id: str) -> str:
        # ALB names: <=32 chars, alphanumeric/hyphens only.
        return f"ia-{correlation_id[:8]}-{task.execution_task_id[-6:]}".lower().replace("_", "-")

    @staticmethod
    def _lambda_name(task: ExecutionTask, correlation_id: str) -> str:
        return f"infra-again-{correlation_id[:8]}-{task.execution_task_id.lower()}".replace("_", "-")

    @staticmethod
    def _lambda_role_name(task: ExecutionTask, correlation_id: str) -> str:
        return f"ia-lambda-{correlation_id[:8]}-{task.execution_task_id[-6:]}".lower().replace("_", "-")

    @staticmethod
    def _log_group_name(task: ExecutionTask, correlation_id: str) -> str:
        return f"/infra-again/{correlation_id[:8]}/{task.execution_task_id.lower()}"

    @staticmethod
    def resource_name(task: ExecutionTask, correlation_id: str) -> str:
        """The exact (never prefix/wildcard) resource identity this task
        owns — execute() and destroy() must derive it identically for
        whichever service this task represents, or a destroy could miss
        the real resource or, worse, match a different one."""
        svc = (task.canonical_service_id or "").lower()
        if svc == "elb":
            return FakecloudExecutor._alb_name(task, correlation_id)
        if svc == "lambda":
            return FakecloudExecutor._lambda_name(task, correlation_id)
        if svc == "cloudwatch":
            return FakecloudExecutor._log_group_name(task, correlation_id)
        return FakecloudExecutor._bucket_name(task, correlation_id)  # default/fallback: s3

    @staticmethod
    def _generate_hcl(task: ExecutionTask, correlation_id: str, work_path: Path) -> str:
        svc = (task.canonical_service_id or "").lower()
        provider_block = """provider "aws" {
  region = "us-east-1"
  endpoints {
    s3 = "http://localhost:4566"
    elbv2 = "http://localhost:4566"
    lambda = "http://localhost:4566"
    iam = "http://localhost:4566"
    cloudwatchlogs = "http://localhost:4566"
    ec2 = "http://localhost:4566"
  }
  s3_use_path_style = true
  access_key = "test"
  secret_key = "test"
  skip_credentials_validation = true
  skip_requesting_account_id = true
}
"""
        header = f'# INFRA-AGAIN — FAKECLOUD SIMULATED ({svc or "s3"})\nterraform {{\n  required_version = ">= 1.0"\n}}\n\n{provider_block}\n'

        if svc == "elb":
            name = FakecloudExecutor._alb_name(task, correlation_id)
            return header + f"""
data "aws_vpc" "default" {{}}

data "aws_subnets" "default" {{
  filter {{
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }}
}}

resource "aws_lb" "main" {{
  name               = "{name}"
  internal           = true
  load_balancer_type = "application"
  subnets            = data.aws_subnets.default.ids
  tags = {{
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""
        if svc == "lambda":
            name = FakecloudExecutor._lambda_name(task, correlation_id)
            role_name = FakecloudExecutor._lambda_role_name(task, correlation_id)
            zip_path = work_path / "lambda.zip"
            import zipfile
            with zipfile.ZipFile(zip_path, "w") as z:
                z.writestr("index.py", "def handler(event, context):\n    return {'statusCode': 200}\n")
            return header + f"""
resource "aws_iam_role" "lambda_exec" {{
  name = "{role_name}"
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {{ Service = "lambda.amazonaws.com" }}
    }}]
  }})
  tags = {{
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}

resource "aws_lambda_function" "main" {{
  function_name = "{name}"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "index.handler"
  runtime       = "python3.12"
  filename      = "lambda.zip"
  tags = {{
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""
        if svc == "cloudwatch":
            name = FakecloudExecutor._log_group_name(task, correlation_id)
            return header + f"""
resource "aws_cloudwatch_log_group" "main" {{
  name = "{name}"
  tags = {{
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""
        # default: s3
        bucket_name = FakecloudExecutor._bucket_name(task, correlation_id)
        return header + f"""
resource "aws_s3_bucket" "main" {{
  bucket = "{bucket_name}"
  tags = {{
    managed_by  = "INFRA_AGAIN"
    correlation = "{correlation_id}"
  }}
}}
"""

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        """Observe fakecloud via boto3 — independently of any executor
        return value. Queries every resource type this executor can create;
        cheap, real, local calls."""
        observed: dict[str, Any] = {}
        errors: list[str] = []
        common = dict(endpoint_url=self.FAKECLOUD_ENDPOINT, aws_access_key_id="test",
                      aws_secret_access_key="test", region_name="us-east-1")
        try:
            import boto3
            s3 = boto3.client("s3", **common)
            observed["buckets"] = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        except Exception as e:
            errors.append(f"s3: {e}")
        try:
            import boto3
            elbv2 = boto3.client("elbv2", **common)
            observed["loadBalancers"] = [lb["LoadBalancerName"] for lb in elbv2.describe_load_balancers().get("LoadBalancers", [])]
        except Exception as e:
            errors.append(f"elbv2: {e}")
        try:
            import boto3
            lam = boto3.client("lambda", **common)
            observed["functions"] = [f["FunctionName"] for f in lam.list_functions().get("Functions", [])]
        except Exception as e:
            errors.append(f"lambda: {e}")
        try:
            import boto3
            logs = boto3.client("logs", **common)
            observed["logGroups"] = [g["logGroupName"] for g in logs.describe_log_groups().get("logGroups", [])]
        except Exception as e:
            errors.append(f"logs: {e}")

        result = {"observed": observed, "observed_at": time.time()}
        if errors:
            result["error"] = "; ".join(errors)
        return result

    @staticmethod
    def observed_ids_for(task: ExecutionTask, observation: dict[str, Any]) -> list[str]:
        """The observed-resource-id list relevant to THIS task's service —
        used by the drift classifier so 'expected s3 bucket' is never
        compared against the load-balancer list, etc."""
        svc = (task.canonical_service_id or "").lower()
        observed = observation.get("observed", {})
        if svc == "elb":
            return observed.get("loadBalancers", [])
        if svc == "lambda":
            return observed.get("functions", [])
        if svc == "cloudwatch":
            return observed.get("logGroups", [])
        return observed.get("buckets", [])

    async def destroy(self, task: ExecutionTask, target: ExecutionTarget, correlation_id: str) -> dict[str, Any]:
        """Exact-ownership destroy — deletes ONLY the exact resource this
        task created (same derivation _generate_hcl/resource_name use),
        dispatched by service type. Never a prefix or wildcard match."""
        svc = (task.canonical_service_id or "").lower()
        name = FakecloudExecutor.resource_name(task, correlation_id)
        common = dict(endpoint_url=self.FAKECLOUD_ENDPOINT, aws_access_key_id="test",
                      aws_secret_access_key="test", region_name="us-east-1")
        try:
            import boto3
            if svc == "elb":
                elbv2 = boto3.client("elbv2", **common)
                lbs = elbv2.describe_load_balancers().get("LoadBalancers", [])
                match = next((lb for lb in lbs if lb["LoadBalancerName"] == name), None)
                if not match:
                    return {"status": "COMPLETED", "destroyed": name, "note": "already absent"}
                elbv2.delete_load_balancer(LoadBalancerArn=match["LoadBalancerArn"])
                return {"status": "COMPLETED", "destroyed": name}
            if svc == "lambda":
                lam = boto3.client("lambda", **common)
                lam.delete_function(FunctionName=name)
                try:
                    iam = boto3.client("iam", **common)
                    iam.delete_role(RoleName=FakecloudExecutor._lambda_role_name(task, correlation_id))
                except Exception:
                    pass  # role cleanup is best-effort; function deletion is the primary resource
                return {"status": "COMPLETED", "destroyed": name}
            if svc == "cloudwatch":
                logs = boto3.client("logs", **common)
                logs.delete_log_group(logGroupName=name)
                return {"status": "COMPLETED", "destroyed": name}
            # default: s3
            s3 = boto3.client("s3", **common)
            s3.delete_bucket(Bucket=name)
            return {"status": "COMPLETED", "destroyed": name}
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("NoSuchBucket", "ResourceNotFoundException", "404", "not found")):
                return {"status": "COMPLETED", "destroyed": name, "note": "already absent"}
            return {"status": "FAILED", "error": err, "attemptedTarget": name}


# ===========================================================================
# KindExecutor
# ===========================================================================

class KindExecutor(ExecutionAdapter):
    """Execute against local kind Kubernetes cluster."""

    @staticmethod
    def _namespace_name(correlation_id: str) -> str:
        """The exact (never prefix/wildcard) namespace this run owns —
        execute() and destroy() must derive it identically."""
        return f"infra-again-{correlation_id[:8]}".lower()

    @property
    def supported_action_types(self) -> list[ActionType]:
        return [ActionType.CREATE_LOCAL_NAMESPACE, ActionType.DEPLOY_LOCAL_WORKLOAD,
                ActionType.OBSERVE_RESOURCE, ActionType.VALIDATE_RESOURCE,
                ActionType.DESTROY_RUN_OWNED_RESOURCE]

    @property
    def supported_fidelity(self) -> ExecutionFidelity:
        return ExecutionFidelity.LOCAL_RUNTIME

    async def execute(self, task: ExecutionTask, target: ExecutionTarget,
                      work_dir: str, correlation_id: str) -> dict[str, Any]:
        """Deploy workload to kind cluster."""
        import shutil
        result: dict[str, Any] = {"status": "EXECUTING", "outputs": [], "evidence": []}

        kubectl = shutil.which("kubectl") or "kubectl"
        # Use explicit context if available, fall back to default
        ctx = target.environment_name or ""
        ctx_args = ["--context", f"kind-{ctx}"] if ctx else []
        ns_name = KindExecutor._namespace_name(correlation_id)
        deploy_name = f"app-{correlation_id[:8]}".lower()
        svc_name = f"svc-{correlation_id[:8]}".lower()

        async def _kubectl(args: list[str], stdin_data: str = "") -> tuple[int, str, str]:
            proc = await asyncio.create_subprocess_exec(
                kubectl, *args,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin_data.encode() if stdin_data else None), timeout=30)
            return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")

        # Create namespace with ownership labels
        ns_manifest = json.dumps({
            "apiVersion": "v1", "kind": "Namespace",
            "metadata": {
                "name": ns_name,
                "labels": {
                    "app.kubernetes.io/managed-by": "infra-again",
                    "infra-again/run-id": correlation_id,
                    "infra-again/ephemeral": "true",
                    "infra-again/acceptance-run": "true",
                    "correlation": correlation_id,
                },
            },
        })
        exit_code, stdout, stderr = await _kubectl(ctx_args + ["apply", "-f", "-"], ns_manifest)
        result["outputs"].append({"command": "apply-namespace", "exit": exit_code, "stdout": stdout})
        if exit_code != 0:
            result["status"] = "FAILED"; result["error"] = stderr; return result

        # Create deployment
        deploy_manifest = json.dumps({
            "apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {
                "name": deploy_name, "namespace": ns_name,
                "labels": {"app.kubernetes.io/managed-by": "infra-again", "infra-again/run-id": correlation_id, "infra-again/ephemeral": "true", "correlation": correlation_id},
            },
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": deploy_name}},
                "template": {
                    "metadata": {"labels": {"app": deploy_name, "app.kubernetes.io/managed-by": "infra-again", "infra-again/run-id": correlation_id}},
                    "spec": {"containers": [{"name": "nginx", "image": "nginx:alpine", "ports": [{"containerPort": 80}]}]},
                },
            },
        })
        exit_code, stdout, stderr = await _kubectl(ctx_args + ["apply", "-f", "-"], deploy_manifest)
        result["outputs"].append({"command": "apply-deployment", "exit": exit_code, "stdout": stdout})
        if exit_code != 0:
            result["status"] = "FAILED"; result["error"] = stderr; return result

        # Create service
        svc_manifest = json.dumps({
            "apiVersion": "v1", "kind": "Service",
            "metadata": {
                "name": svc_name, "namespace": ns_name,
                "labels": {"app.kubernetes.io/managed-by": "infra-again", "infra-again/run-id": correlation_id, "correlation": correlation_id},
            },
            "spec": {
                "selector": {"app": deploy_name},
                "ports": [{"port": 80, "targetPort": 80}],
            },
        })
        exit_code, stdout, stderr = await _kubectl(ctx_args + ["apply", "-f", "-"], svc_manifest)
        result["outputs"].append({"command": "apply-service", "exit": exit_code, "stdout": stdout})
        if exit_code != 0:
            result["status"] = "FAILED"; result["error"] = stderr; return result

        result["status"] = "COMPLETED"
        result["namespace"] = ns_name
        return result

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        """Observe kind cluster via kubectl."""
        import shutil
        kubectl = shutil.which("kubectl") or "kubectl"
        ctx = target.environment_name or ""
        ctx_args = ["--context", f"kind-{ctx}"] if ctx else []
        observed: dict[str, Any] = {}

        try:
            proc = await asyncio.create_subprocess_exec(
                kubectl, *ctx_args, "get", "deployments", "--all-namespaces", "-o", "json",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                dep_data = json.loads(stdout)
                for item in dep_data.get("items", []):
                    labels = item["metadata"].get("labels", {})
                    if labels.get("app.kubernetes.io/managed-by") in ("INFRA_AGAIN", "infra-again"):
                        name = item["metadata"]["name"]
                        ns = item["metadata"]["namespace"]
                        ready = item.get("status", {}).get("readyReplicas", 0)
                        desired = item.get("spec", {}).get("replicas", 0)
                        observed[f"deploy/{ns}/{name}"] = {
                            "readyReplicas": ready, "desiredReplicas": desired,
                        }
        except Exception as e:
            observed["error"] = str(e)

        return {"observed": observed, "observed_at": time.time()}

    async def destroy(self, task: ExecutionTask, target: ExecutionTarget, correlation_id: str) -> dict[str, Any]:
        """Exact-ownership destroy — deletes ONLY the exact namespace this
        run created (same derivation execute() uses). Deleting the
        namespace takes its deployment/service with it; no other
        namespace is ever touched, so a foreign/unrelated namespace with a
        similar name is never at risk."""
        import shutil
        kubectl = shutil.which("kubectl") or "kubectl"
        ctx = target.environment_name or ""
        ctx_args = ["--context", f"kind-{ctx}"] if ctx else []
        ns_name = KindExecutor._namespace_name(correlation_id)
        try:
            proc = await asyncio.create_subprocess_exec(
                kubectl, *ctx_args, "delete", "namespace", ns_name, "--ignore-not-found=true",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode != 0:
                return {"status": "FAILED", "error": stderr.decode(errors="replace"), "attemptedTarget": ns_name}
            return {"status": "COMPLETED", "destroyed": ns_name, "output": stdout.decode(errors="replace")}
        except Exception as e:
            return {"status": "FAILED", "error": str(e), "attemptedTarget": ns_name}
