"""Kubernetes platform adapter — kind/minikube runtime."""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.domain import (
    ExecutionTarget, ExecutionTargetType, Platform, Provider, TruthStatus,
    ValidationResult, OwnedResource, ResourceOwnership, TargetScope,
    ChangeAction, ChangeItem, ChangeSet, InfrastructurePlan,
    CapabilityRequirement, CapabilityCategory,
    ExecutionMode,
)


@dataclass
class K8sResource:
    """A Kubernetes resource manifest with ownership."""
    kind: str
    name: str
    namespace: str
    manifest: dict[str, Any]
    ownership: ResourceOwnership = field(default_factory=ResourceOwnership)


class KubernetesPlatformAdapter:
    """Kubernetes platform adapter with kind/minikube support."""

    def __init__(self, kubeconfig: str | None = None, context: str | None = None):
        self._kubeconfig = kubeconfig
        self._context = context
        self._kubectl = shutil.which("kubectl") or "kubectl"

    @property
    def platform(self) -> Platform:
        return Platform.KUBERNETES

    async def probe(self) -> TruthStatus:
        if not shutil.which("kubectl"):
            return TruthStatus.NOT_INSTALLED
        try:
            result = await self._kubectl_run(["version", "--client"], timeout=10)
            if result["exit_code"] == 0:
                return TruthStatus.READY
        except Exception:
            pass
        return TruthStatus.NOT_CONFIGURED

    async def probe_cluster(self, context: str | None = None) -> dict[str, Any]:
        ctx = context or self._context
        args = ["cluster-info"]
        if ctx:
            args.extend(["--context", ctx])
        result = await self._kubectl_run(args, timeout=15)
        return {"ready": result["exit_code"] == 0, "output": result["stdout"], "error": result["stderr"]}

    async def apply_manifest(self, manifest: dict[str, Any], namespace: str = "") -> dict[str, Any]:
        """Apply a Kubernetes manifest. Namespace extracted from manifest metadata if not provided."""
        ns = namespace or manifest.get("metadata", {}).get("namespace", "default")
        # For cluster-scoped resources (Namespace), don't pass -n
        kind = manifest.get("kind", "")
        if kind == "Namespace":
            args = [self._kubectl, "apply", "-f", "-"]
        else:
            args = [self._kubectl, "apply", "-n", ns, "-f", "-"]
        manifest_json = json.dumps(manifest)
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(manifest_json.encode()), timeout=60)
        return {
            "exit_code": proc.returncode or 0,
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
        }

    async def observe(self, target: ExecutionTarget, resource_ids: list[str] | None = None) -> dict[str, Any]:
        """Observe actual Kubernetes state."""
        observed: dict[str, Any] = {"observed": {}, "observed_at": time.time()}

        try:
            ns_result = await self._kubectl_run(["get", "namespaces", "-o", "json"], timeout=15)
            if ns_result["exit_code"] == 0:
                ns_data = json.loads(ns_result["stdout"])
                for item in ns_data.get("items", []):
                    name = item["metadata"]["name"]
                    if "infra-again" in name:
                        observed["observed"][f"ns/{name}"] = {
                            "kind": "Namespace", "name": name,
                            "status": item.get("status", {}).get("phase", "Active"),
                        }

            deploy_result = await self._kubectl_run(["get", "deployments", "--all-namespaces", "-o", "json"], timeout=15)
            if deploy_result["exit_code"] == 0:
                dep_data = json.loads(deploy_result["stdout"])
                for item in dep_data.get("items", []):
                    labels = item["metadata"].get("labels", {})
                    if labels.get("app.kubernetes.io/managed-by") in ("INFRA_AGAIN", "infra-again"):
                        name = item["metadata"]["name"]
                        ns = item["metadata"]["namespace"]
                        ready = item.get("status", {}).get("readyReplicas", 0)
                        desired = item.get("spec", {}).get("replicas", 0)
                        observed["observed"][f"deploy/{ns}/{name}"] = {
                            "kind": "Deployment", "name": name, "namespace": ns,
                            "ready_replicas": ready, "desired_replicas": desired,
                        }

            svc_result = await self._kubectl_run(["get", "services", "--all-namespaces", "-o", "json"], timeout=15)
            if svc_result["exit_code"] == 0:
                svc_data = json.loads(svc_result["stdout"])
                for item in svc_data.get("items", []):
                    labels = item["metadata"].get("labels", {})
                    if labels.get("app.kubernetes.io/managed-by") in ("INFRA_AGAIN", "infra-again"):
                        name = item["metadata"]["name"]
                        ns = item["metadata"]["namespace"]
                        observed["observed"][f"svc/{ns}/{name}"] = {
                            "kind": "Service", "name": name, "namespace": ns,
                            "cluster_ip": item.get("spec", {}).get("clusterIP", ""),
                        }
        except Exception as e:
            observed["error"] = str(e)

        return observed

    async def validate(self, desired: dict[str, Any], observed: dict[str, Any]) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        obs_data = observed.get("observed", {})

        for key, desired_state in desired.items():
            obs_state = obs_data.get(key)
            if obs_state:
                matches = self._compare_state(desired_state, obs_state)
                results.append(ValidationResult(
                    resource_id=key,
                    desired_state=desired_state if isinstance(desired_state, dict) else {},
                    observed_state=obs_state,
                    matches=matches,
                    drift_detected=not matches,
                    drift_details="" if matches else f"Mismatch for {key}",
                ))
            else:
                results.append(ValidationResult(
                    resource_id=key,
                    desired_state=desired_state if isinstance(desired_state, dict) else {},
                    observed_state=None, matches=False, drift_detected=True,
                    drift_details=f"Resource {key} not observed",
                ))
        return results

    def _compare_state(self, desired: Any, observed: Any) -> bool:
        if isinstance(desired, dict) and isinstance(observed, dict):
            # Check replicas match
            d_rep = desired.get("replicas") or desired.get("desired_replicas")
            o_rep = observed.get("ready_replicas") or observed.get("desired_replicas")
            if d_rep is not None and o_rep is not None:
                return d_rep == o_rep
            return desired.get("name") == observed.get("name")
        return desired == observed

    async def destroy_namespace(self, namespace: str) -> dict[str, Any]:
        result = await self._kubectl_run(["delete", "namespace", namespace, "--wait=false"], timeout=30)
        return {"exit_code": result["exit_code"], "stdout": result["stdout"], "stderr": result["stderr"]}

    async def destroy_resource(self, kind: str, name: str, namespace: str) -> dict[str, Any]:
        result = await self._kubectl_run(["delete", kind, name, "-n", namespace, "--wait=false"], timeout=30)
        return {"exit_code": result["exit_code"], "stdout": result["stdout"], "stderr": result["stderr"]}

    async def _kubectl_run(self, args: list[str], timeout: int = 30) -> dict[str, Any]:
        full_args = [self._kubectl] + args
        if self._kubeconfig:
            full_args.extend(["--kubeconfig", self._kubeconfig])
        try:
            proc = await asyncio.create_subprocess_exec(
                *full_args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "exit_code": proc.returncode or 0,
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
            }
        except asyncio.TimeoutError:
            return {"exit_code": -1, "stdout": "", "stderr": "timeout"}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}


class KindRuntime:
    """kind cluster lifecycle manager."""

    def __init__(self):
        self._kind = shutil.which("kind") or "kind"

    async def probe(self) -> dict[str, Any]:
        """Probe kind availability and version."""
        if not shutil.which(self._kind):
            return {"status": "NOT_INSTALLED", "version": ""}
        try:
            proc = await asyncio.create_subprocess_exec(
                self._kind, "version", stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            return {"status": "READY", "version": stdout.decode().strip().split("\n")[0]}
        except Exception as e:
            return {"status": "UNAVAILABLE", "error": str(e)}

    async def create_cluster(self, name: str) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            self._kind, "create", "cluster", "--name", name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        return {"exit_code": proc.returncode or 0, "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace")}

    async def delete_cluster(self, name: str) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            self._kind, "delete", "cluster", "--name", name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        return {"exit_code": proc.returncode or 0, "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace")}

    async def get_kubeconfig_path(self, name: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            self._kind, "get", "kubeconfig", "--name", name,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        # kind get kubeconfig prints the path — if fails, construct default
        path = stdout.decode().strip()
        if path:
            return path
        return str(Path.home() / ".kube" / "config")
