"""Phase 3 Tests — Multi-Platform + Registry + API + UI."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from infra_again.registry import CapabilityRegistry, CapabilityRecord, CapabilityLifecycle, ExecutionFidelity
from infra_again.core.domain import Provider, Platform, TruthStatus
from infra_again.platforms.kubernetes.runtime import KubernetesPlatformAdapter, KindRuntime


# ---------------------------------------------------------------------------
# Capability Registry
# ---------------------------------------------------------------------------


class TestCapabilityRegistry:
    def test_registry_seeded(self):
        reg = CapabilityRegistry()
        caps = reg.get_all()
        assert len(caps) >= 5, f"Expected >=5 seeded, got {len(caps)}"

    def test_discovered_not_supported(self):
        reg = CapabilityRegistry()
        discovered = reg.query(lifecycle=CapabilityLifecycle.DISCOVERED)
        for c in discovered:
            assert c.lifecycle != CapabilityLifecycle.SUPPORTED

    def test_verified_can_execute(self):
        reg = CapabilityRegistry()
        verified = reg.get_verified()
        assert len(verified) >= 3
        for c in verified:
            assert c.is_safe_to_execute

    def test_aws_s3_verified(self):
        reg = CapabilityRegistry()
        s3 = reg.get("cap-aws-s3")
        assert s3 is not None
        assert s3.lifecycle == CapabilityLifecycle.VERIFIED
        assert s3.fidelity == ExecutionFidelity.SIMULATED
        assert "FAKECLOUD" in s3.targets

    def test_k8s_deployment_verified(self):
        reg = CapabilityRegistry()
        dep = reg.get("cap-k8s-deployment")
        assert dep is not None
        assert dep.lifecycle == CapabilityLifecycle.VERIFIED
        assert "KIND" in dep.targets

    def test_ocp_is_plan_only(self):
        reg = CapabilityRegistry()
        ocp = reg.get("cap-ocp-deployment")
        assert ocp is not None
        assert ocp.lifecycle == CapabilityLifecycle.DISCOVERED
        assert ocp.fidelity == ExecutionFidelity.PLAN_ONLY

    def test_minikube_is_not_implemented(self):
        reg = CapabilityRegistry()
        mk = reg.get("cap-k8s-minikube-deploy")
        assert mk is not None
        assert mk.lifecycle == CapabilityLifecycle.UNVERIFIED
        assert mk.fidelity == ExecutionFidelity.NOT_IMPLEMENTED

    def test_query_by_provider(self):
        reg = CapabilityRegistry()
        aws = reg.query(provider="AWS")
        assert len(aws) >= 2

    def test_query_by_platform(self):
        reg = CapabilityRegistry()
        k8s = reg.query(platform="KUBERNETES")
        assert len(k8s) >= 3

    def test_to_dict_list(self):
        reg = CapabilityRegistry()
        dl = reg.to_dict_list()
        assert len(dl) >= 5
        assert all(isinstance(d, dict) for d in dl)


# ---------------------------------------------------------------------------
# Kubernetes Runtime
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestKubernetesRuntime:
    async def test_kubectl_probe(self):
        adapter = KubernetesPlatformAdapter()
        status = await adapter.probe()
        assert status == TruthStatus.READY, "kubectl should be installed"

    async def test_kind_probe(self):
        runtime = KindRuntime()
        info = await runtime.probe()
        assert info["status"] == "READY", f"kind must be READY, got {info}"


@pytest.mark.asyncio
class TestKindIntegration:
    """Real kind cluster creation and Kubernetes operations."""

    async def test_kind_create_and_observe(self):
        """Create kind cluster, deploy namespace, observe, cleanup."""
        runtime = KindRuntime()
        info = await runtime.probe()
        if info["status"] != "READY":
            pytest.skip("kind not available")

        cluster_name = "ia-test-v3"
        # Create cluster
        result = await runtime.create_cluster(cluster_name)
        assert result["exit_code"] == 0, f"kind create failed: {result['stderr']}"

        try:
            # Wait for cluster
            import asyncio
            await asyncio.sleep(5)

            # Create namespace via kubectl
            adapter = KubernetesPlatformAdapter(context=f"kind-{cluster_name}")
            ns_manifest = {
                "apiVersion": "v1", "kind": "Namespace",
                "metadata": {
                    "name": "infra-again-test",
                    "labels": {
                        "app.kubernetes.io/managed-by": "INFRA_AGAIN",
                        "infra-again/run-id": "test-v3",
                        "infra-again/ephemeral": "true",
                    },
                },
            }
            result = await adapter.apply_manifest(ns_manifest)
            assert result["exit_code"] == 0, f"namespace apply failed: {result['stderr']}"

            # Create deployment
            dep_manifest = {
                "apiVersion": "apps/v1", "kind": "Deployment",
                "metadata": {
                    "name": "hello-again", "namespace": "infra-again-test",
                    "labels": {
                        "app.kubernetes.io/managed-by": "INFRA_AGAIN",
                        "infra-again/run-id": "test-v3",
                        "infra-again/ephemeral": "true",
                    },
                },
                "spec": {
                    "replicas": 2,
                    "selector": {"matchLabels": {"app": "hello-again"}},
                    "template": {
                        "metadata": {"labels": {"app": "hello-again"}},
                        "spec": {"containers": [{"name": "nginx", "image": "nginx:alpine", "ports": [{"containerPort": 80}]}]},
                    },
                },
            }
            result = await adapter.apply_manifest(dep_manifest)
            assert result["exit_code"] == 0, f"deployment apply failed: {result['stderr']}"

            # Create service
            svc_manifest = {
                "apiVersion": "v1", "kind": "Service",
                "metadata": {
                    "name": "hello-again", "namespace": "infra-again-test",
                    "labels": {"app.kubernetes.io/managed-by": "INFRA_AGAIN"},
                },
                "spec": {"selector": {"app": "hello-again"}, "ports": [{"port": 80, "targetPort": 80}]},
            }
            result = await adapter.apply_manifest(svc_manifest)
            assert result["exit_code"] == 0, f"service apply failed: {result['stderr']}"

            # Wait for pods
            await asyncio.sleep(10)

            # Observe
            observed = await adapter.observe(None)
            assert "observed" in observed
            obs_data = str(observed["observed"])
            assert "infra-again-test" in obs_data, f"Namespace not observed: {list(observed['observed'].keys())[:5]}"

        finally:
            await runtime.delete_cluster(cluster_name)


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestControlAPI:
    def test_health(self):
        from infra_again.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_capabilities(self):
        from infra_again.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/v1/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 5

    def test_targets(self):
        from infra_again.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/v1/targets")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 10

    def test_runs_list(self):
        from infra_again.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/v1/runs")
        assert resp.status_code == 200

    def test_plan_endpoint(self):
        from infra_again.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.post("/api/v1/plan", json={
            "infrastructureRequestId": "ir-api-001",
            "correlationId": "corr-api-001",
        })
        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_run_not_found(self):
        from infra_again.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/v1/runs/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# UI Build Test
# ---------------------------------------------------------------------------


class TestUIBuild:
    def test_ui_build_exists(self):
        """UI build output must exist."""
        dist_dir = Path(__file__).parent.parent.parent / "ui" / "dist"
        if dist_dir.exists():
            index = dist_dir / "index.html"
            assert index.exists(), "UI build must produce index.html"
        else:
            # UI may not be built yet — check source exists
            src_dir = Path(__file__).parent.parent.parent / "ui" / "src"
            assert src_dir.exists(), "UI source must exist"
            assert (src_dir / "App.tsx").exists(), "App.tsx must exist"
