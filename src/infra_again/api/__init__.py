"""INFRA-AGAIN Control API — FastAPI.

Exposes the Infrastructure OS through a REST API for:
- Health, capabilities, targets
- Run management (plan, apply, reconcile)
- Architecture visualization
- Evidence retrieval
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core.domain import (
    ExecutionMode, ExecutionState, ExecutionTarget, ExecutionTargetType,
    Platform, Provider, TruthStatus,
)
from ..core.persistence import RunStore
from ..registry import CapabilityRegistry
from ..execution.lab import all_lab_targets, get_target

app = FastAPI(title="INFRA-AGAIN Control API", version="3.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

store = RunStore()
registry = CapabilityRegistry()

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@app.get("/api/v1/capabilities")
async def get_capabilities(
    provider: str | None = None,
    platform: str | None = None,
    verified_only: bool = False,
):
    caps = registry.get_all()
    if provider:
        caps = [c for c in caps if c.provider == provider]
    if platform:
        caps = [c for c in caps if c.platform == platform]
    if verified_only:
        caps = [c for c in caps if c.lifecycle.value == "VERIFIED"]
    return {"capabilities": [c.to_dict() for c in caps], "count": len(caps)}


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@app.get("/api/v1/targets")
async def get_targets():
    targets = []
    for t in all_lab_targets():
        targets.append({
            "target_type": t.target_type.value,
            "name": t.name,
            "provider": t.provider.value,
            "platform": t.platform.value,
            "mode": t.mode.value,
            "status": t.status.value,
            "fidelity": t.fidelity_notes,
            "description": t.description,
        })
    return {"targets": targets, "count": len(targets)}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@app.get("/api/v1/runs")
async def list_runs(correlation_id: str | None = None):
    runs = store.list_runs(correlation_id)
    return {"runs": runs, "count": len(runs)}


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    transitions = store.get_transitions(run_id)
    evidence = store.get_evidence(run_id)
    resources = store.get_resources_for_run(run_id)
    return {
        "run": run,
        "transitions": transitions,
        "evidence_count": len(evidence),
        "resources": resources,
    }


@app.get("/api/v1/runs/{run_id}/architecture")
async def get_run_architecture(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    evidence_dir = Path(".ai/infra-runs") / run_id
    arch: dict[str, Any] = {}
    for fname in ["architecture-proposed.json", "architecture-planned.json",
                   "architecture-observed.json", "architecture-diff.json"]:
        fpath = evidence_dir / fname
        if fpath.exists():
            try:
                arch[fname.replace(".json", "").replace("architecture-", "")] = json.loads(fpath.read_text())
            except Exception:
                arch[fname] = {"error": "parse failed"}
    return {"run_id": run_id, "architecture": arch}


@app.get("/api/v1/runs/{run_id}/evidence")
async def get_run_evidence(run_id: str):
    evidence = store.get_evidence(run_id)
    return {"run_id": run_id, "evidence": evidence, "count": len(evidence)}


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    infrastructureRequestId: str
    correlationId: str
    workPackageId: str = ""
    engineeringResultId: str = ""
    provider: str = "AWS"
    platform: str = "NATIVE_VM"
    targetType: str = "FAKECLOUD"
    requirements: dict[str, Any] = {}


@app.post("/api/v1/plan")
async def create_plan(req: PlanRequest):
    from ..contracts import InfrastructureRequest, InfrastructureRequirements
    from ..execution.orchestrator import ExecutionOrchestrator
    from ..providers.aws.adapter import AwsProviderAdapter

    infra_req = InfrastructureRequest(
        infrastructureRequestId=req.infrastructureRequestId,
        correlationId=req.correlationId,
        workPackageId=req.workPackageId,
        engineeringResultId=req.engineeringResultId,
        requirements=InfrastructureRequirements(),
    )
    target = ExecutionTarget(
        mode=ExecutionMode.PLAN_ONLY,
        provider=Provider(req.provider),
        platform=Platform(req.platform),
        target_type=ExecutionTargetType(req.targetType) if req.targetType else None,
    )
    adapter = AwsProviderAdapter()
    orchestrator = ExecutionOrchestrator(provider_adapter=adapter, store=store)
    result = await orchestrator.process(infra_req, target)
    return {"result": result.model_dump(mode="json"), "run_id": orchestrator._ctx.run_id if orchestrator._ctx else ""}


@app.post("/api/v1/runs/{run_id}/apply")
async def apply_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404)
    state = run.get("state", "")
    if state not in (ExecutionState.PLAN_READY.value, ExecutionState.WAITING_FOR_APPROVAL.value):
        raise HTTPException(status_code=400, detail=f"Cannot apply run in state {state}")
    return {"run_id": run_id, "status": "apply_requested", "state": state,
            "note": "Apply in SIMULATED/LOCAL_RUNTIME only via API in this phase"}


@app.post("/api/v1/runs/{run_id}/reconcile")
async def reconcile_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404)
    if run.get("state") != ExecutionState.REQUIRES_RECONCILIATION.value:
        raise HTTPException(status_code=400, detail="Run is not in reconciliation state")
    return {"run_id": run_id, "status": "reconciliation_requested"}

# ===========================================================================
# Runner API (Phase 3.1)
# ===========================================================================

_runner_registry: dict[str, dict[str, Any]] = {}
_task_registry: dict[str, dict[str, Any]] = {}
_lease_registry: dict[str, dict[str, Any]] = {}
_RUNNER_AUTH_TOKEN = "runner-dev-token-change-in-production"  # nosec


def _verify_runner_auth(auth_header: str | None) -> bool:
    if not auth_header:
        return False
    return auth_header.replace("Bearer ", "") == _RUNNER_AUTH_TOKEN


class RunnerRegisterRequest(BaseModel):
    runnerId: str = ""
    name: str = ""
    version: str = ""
    os: str = ""
    arch: str = ""


@app.get("/api/v1/runners")
async def list_runners():
    return {"runners": list(_runner_registry.values()), "count": len(_runner_registry)}


@app.post("/api/v1/runners/register")
async def register_runner(req: RunnerRegisterRequest):
    rid = req.runnerId or f"runner-{len(_runner_registry)}"
    _runner_registry[rid] = {
        "runnerId": rid, "name": req.name, "version": req.version,
        "os": req.os, "arch": req.arch, "status": "ONLINE",
        "registeredAt": datetime.now(timezone.utc).isoformat(),
        "lastHeartbeat": datetime.now(timezone.utc).isoformat(),
    }
    return {"status": "registered", "runner": _runner_registry[rid]}


@app.post("/api/v1/runners/{runner_id}/heartbeat")
async def runner_heartbeat(runner_id: str, capabilities: dict[str, Any] | None = None):
    runner = _runner_registry.get(runner_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Runner not found")
    runner["lastHeartbeat"] = datetime.now(timezone.utc).isoformat()
    runner["status"] = "ONLINE"
    if capabilities:
        runner["capabilities"] = capabilities
    return {"status": "ok", "runnerId": runner_id}


class CreateTaskRequest(BaseModel):
    runId: str = ""
    correlationId: str = ""
    executionMode: str = "LOCAL_RUNTIME"
    provider: str = "ON_PREM"
    platform: str = "KUBERNETES"
    target: str = "KIND"
    action: str = "APPLY"


@app.post("/api/v1/runners/{runner_id}/tasks")
async def create_task(runner_id: str, req: CreateTaskRequest):
    from ..runner import ExecutionTask
    task = ExecutionTask(
        run_id=req.runId, correlation_id=req.correlationId,
        execution_mode=req.executionMode, provider=req.provider,
        platform=req.platform, target=req.target, action=req.action)
    _task_registry[task.task_id] = {
        "task": task.to_dict(), "state": "QUEUED", "runnerId": runner_id,
    }
    return {"task": task.to_dict(), "state": "QUEUED"}


@app.post("/api/v1/runners/{runner_id}/tasks/lease")
async def lease_task(runner_id: str):
    for tid, t in _task_registry.items():
        if t["state"] == "QUEUED":
            from ..runner import TaskLease
            now = datetime.now(timezone.utc)
            lease = TaskLease(
                task_id=tid, runner_id=runner_id,
                leased_at=now.isoformat(),
                expires_at=datetime.fromtimestamp(now.timestamp() + 3600, tz=timezone.utc).isoformat(),
            )
            t["state"] = "LEASED"
            _lease_registry[tid] = lease.to_dict()
            return {"lease": lease.to_dict(), "task": t["task"]}
    return {"status": "no_queued_tasks"}


@app.post("/api/v1/runners/{runner_id}/tasks/{task_id}/complete")
async def complete_task(runner_id: str, task_id: str, result: dict[str, Any] | None = None):
    t = _task_registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404)
    if t.get("runnerId") != runner_id:
        raise HTTPException(status_code=403, detail="Not your task")
    t["state"] = "COMPLETED"
    t["result"] = result or {}
    return {"status": "completed", "taskId": task_id}


@app.post("/api/v1/runners/{runner_id}/tasks/{task_id}/fail")
async def fail_task(runner_id: str, task_id: str, error: str = ""):
    t = _task_registry.get(task_id)
    if not t:
        raise HTTPException(status_code=404)
    t["state"] = "FAILED"
    t["error"] = error
    return {"status": "failed", "taskId": task_id, "error": error}

# ===========================================================================
# Provider Intelligence API (Phase 4)
# ===========================================================================

from ..intelligence.catalog import get_catalog


@app.get("/api/v1/providers")
async def list_providers():
    catalog = get_catalog()
    aws = catalog.get_snapshot("AWS")
    gcp = catalog.get_snapshot("GCP")
    return {"providers": [
        {"provider": "AWS", "services": aws.service_count if aws else 0,
         "verified": sum(1 for s in catalog.get_services("AWS") if s.lifecycle.value in ("VERIFIED","SUPPORTED")),
         "executable": sum(1 for s in catalog.get_services("AWS") if s.is_executable)},
        {"provider": "GCP", "services": gcp.service_count if gcp else 0,
         "verified": sum(1 for s in catalog.get_services("GCP") if s.lifecycle.value in ("VERIFIED","SUPPORTED")),
         "executable": sum(1 for s in catalog.get_services("GCP") if s.is_executable)},
    ]}


@app.get("/api/v1/providers/{provider}")
async def get_provider(provider: str):
    catalog = get_catalog()
    snap = catalog.get_snapshot(provider.upper())
    if not snap:
        raise HTTPException(status_code=404, detail=f"Provider {provider} not found")
    services = [s.to_dict() for s in catalog.get_services(provider.upper())]
    return {"provider": provider.upper(), "services": services, "snapshot": {
        "snapshotId": snap.snapshot_id, "serviceCount": snap.service_count,
        "checksum": snap.checksum, "freshness": snap.freshness.value,
    }}


@app.get("/api/v1/providers/{provider}/services")
async def get_provider_services(provider: str):
    catalog = get_catalog()
    return {"services": [s.to_dict() for s in catalog.get_services(provider.upper())]}


@app.get("/api/v1/intel/capabilities")
async def list_intel_capabilities():
    from ..intelligence.catalog import CapabilityCategory
    return {"capabilities": [{"id": c.value, "name": c.name.replace("_"," ").title()} for c in CapabilityCategory]}


@app.get("/api/v1/capabilities/{capability}")
async def get_capability(capability: str):
    catalog = get_catalog()
    mappings = catalog.get_mappings(capability=capability.upper())
    return {"capability": capability.upper(), "mappings": [m.to_dict() for m in mappings]}


class CompareRequest(BaseModel):
    capability: str = ""
    executionMode: str = ""


@app.post("/api/v1/capabilities/compare")
async def compare_capabilities(req: CompareRequest):
    catalog = get_catalog()
    results = catalog.compare(req.capability.upper(), req.executionMode)
    return {"capability": req.capability.upper(), "candidates": results}


@app.get("/api/v1/catalog/status")
async def catalog_status():
    catalog = get_catalog()
    snapshots = catalog.get_snapshots()
    return {"snapshots": [{"provider": s.provider, "snapshotId": s.snapshot_id,
        "serviceCount": s.service_count, "checksum": s.checksum,
        "freshness": s.freshness.value, "retrievedAt": s.retrieved_at} for s in snapshots]}


@app.post("/api/v1/catalog/sync")
async def sync_catalog(provider: str = "AWS", syncMode: str = "LOCAL_REFRESH"):
    from ..intelligence.catalog import SyncMode
    mode = SyncMode(syncMode) if syncMode in (SyncMode.LOCAL_REFRESH.value, SyncMode.LIVE_OFFICIAL_SYNC.value) else SyncMode.LOCAL_REFRESH

    catalog = get_catalog()
    if mode == SyncMode.LOCAL_REFRESH:
        snap = catalog.get_snapshot(provider.upper())
        if snap:
            snap.compute_checksum()
            catalog.persist()
            return {"status": "synced", "provider": provider.upper(),
                    "checksum": snap.checksum, "syncMode": mode.value,
                    "note": "LOCAL_REFRESH: recomputed local checksum only. LIVE_OFFICIAL_SYNC is NOT_IMPLEMENTED."}
        raise HTTPException(status_code=404, detail=f"No snapshot for {provider}")
    else:
        return {"status": "not_implemented", "syncMode": mode.value,
                "note": "LIVE_OFFICIAL_SYNC requires internet access to official provider APIs. NOT_IMPLEMENTED."}


@app.get("/api/v1/catalog/snapshots")
async def list_snapshots():
    catalog = get_catalog()
    return {"snapshots": [{"provider": s.provider, "snapshotId": s.snapshot_id,
        "serviceCount": s.service_count, "checksum": s.checksum,
        "freshness": s.freshness.value} for s in catalog.get_snapshots()]}

# ===========================================================================
# Infra Pulse + Design Review API (Phase 5)
# ===========================================================================
# Infra Pulse + Design Review API (Phase 5)
# ===========================================================================

from ..flow.api import register_flow_routes
register_flow_routes(app)

# ===========================================================================
# AGAINPILOT — AI Architecture Copilot (Phase C)
# ===========================================================================

from ..intelligence.againpilot_api import register_againpilot_routes
register_againpilot_routes(app)

# ===========================================================================
# Implementation Planning API (Phase 6)
# ===========================================================================

from ..implementation.api import register_impl_routes
register_impl_routes(app)

# ===========================================================================
# Execution API (Phase 7)
# ===========================================================================

from ..execution.api import register_execution_routes
register_execution_routes(app)

# ===========================================================================
# Sandbox API (Phase 8)
# ===========================================================================

from ..execution.sandbox_api import register_sandbox_routes
register_sandbox_routes(app)

# ===========================================================================
# Promotion API (Phase 9.2)
# ===========================================================================

from ..execution.phase9_api import register_promotion_routes
register_promotion_routes(app)
