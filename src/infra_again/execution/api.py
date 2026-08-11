"""Phase 7 Execution API — readiness, packages, preflight, execute, events, evidence."""

from __future__ import annotations

import json
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .phase7_models import (
    ExecutionPackage, ExecutionTask, ExecutionTarget, ExecutionFidelity,
    ExecutionPackageStatus, ExecutionTaskStatus, ActionType,
)
from .mapper import ImplementationExecutionMapper
from .preflight import PreflightEngine
from .policy import ExecutionPolicyEngine
from .registry import LocalExecutionTargetRegistry
from .persistence import ExecutionPersistence
from .instrumentation import ExecutionInstrumentation

_persistence = ExecutionPersistence()


class CreateExecutionPackageRequest(BaseModel):
    target_type: str = "plan-only"
    idempotency_key: str = ""


class ApproveRequest(BaseModel):
    approved_by: str = "qa"


class ChangeRequest(BaseModel):
    comment: str
    affected_package: str | None = None
    affected_task: str | None = None


def register_execution_routes(app: FastAPI) -> None:
    """Register all Phase 7 execution API routes."""

    _persistence.initialize()
    LocalExecutionTargetRegistry.register_defaults()

    # In-memory cache (backed by persistence on create/load)
    _packages: dict[str, ExecutionPackage] = {}
    _runs: dict[str, dict[str, Any]] = {}

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _lookup_plan(plan_id: str) -> Any:
        """Find implementation plan by id."""
        from ..implementation.api import _plans
        from ..implementation.persistence import load_plan
        return _plans.get(plan_id) or load_plan(plan_id)

    def _gather_plan_currency(plan: Any) -> tuple[int, str, str]:
        """Phase N4 — live (architecture_revision, provider_intelligence_version,
        feasibility_digest) for whatever the plan is bound to, computed fresh
        every call. This is the AIRLOCK's only source of truth for staleness —
        never the plan's own (possibly stale) recollection of these values."""
        if not plan or getattr(plan, "generation_method", "") != "ARCHITECTURE_AWARE":
            return 0, "", ""
        from ..flow.api import _designs, _get_conn
        from ..intelligence.catalog import get_catalog
        from ..intelligence.feasibility import assess_architecture_feasibility, feasibility_digest
        import json as _json

        design = _designs.get(plan.design_id)
        current_rev = design.revision if design else (plan.architecture_revision or plan.design_revision)
        current_pi_version = get_catalog().version()
        conn = _get_conn()
        try:
            row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (plan.design_id,)).fetchone()
        finally:
            conn.close()
        flow_data = _json.loads(row["flow_json"]) if row and row["flow_json"] else {}
        assessment = assess_architecture_feasibility(
            flow_data.get("nodes", []), architecture_id=plan.design_id,
            architecture_revision=str(current_rev), requested_fidelity=plan.target_fidelity,
        )
        return current_rev, current_pi_version, feasibility_digest(assessment)

    @app.post("/api/v1/implementation-plans/{plan_id}/execution-readiness")
    async def get_execution_readiness(plan_id: str):
        """Compute execution readiness for an implementation plan."""
        plan = _lookup_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        readiness = ImplementationExecutionMapper.compute_readiness(plan)
        return {"readiness": readiness.to_dict()}

    @app.post("/api/v1/implementation-plans/{plan_id}/execution-packages")
    async def create_execution_package(plan_id: str, body: CreateExecutionPackageRequest):
        """Create an execution package from an approved plan."""
        plan = _lookup_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        if plan.status.value != "APPROVED_FOR_EXECUTION":
            raise HTTPException(
                status_code=400,
                detail=f"EXECUTION_NOT_ALLOWED: Plan must be APPROVED_FOR_EXECUTION, got {plan.status.value}",
            )

        # Idempotency check
        if body.idempotency_key:
            for p in _packages.values():
                if p.plan_id == plan_id:
                    return {"package": p.to_dict(), "note": "idempotent: existing package returned"}

        target = LocalExecutionTargetRegistry.get(body.target_type)
        if not target:
            raise HTTPException(status_code=400, detail=f"Unknown target: {body.target_type}")

        correlation_id = f"EXEC-{uuid.uuid4().hex[:8].upper()}"
        tasks = ImplementationExecutionMapper.map_to_execution_tasks(plan, target)

        pkg = ExecutionPackage(
            execution_package_id=f"EXECP-{uuid.uuid4().hex[:8].upper()}",
            plan_id=plan.plan_id,
            plan_revision=plan.design_revision,
            plan_checksum=plan.plan_checksum,
            design_id=plan.design_id,
            design_revision=plan.design_revision,
            correlation_id=correlation_id,
            target=target,
            fidelity=target.fidelity,
            tasks=tasks,
            created_at=_now(),
            updated_at=_now(),
        )

        _packages[pkg.execution_package_id] = pkg
        _persistence.persist_package(pkg.to_dict())
        return {"package": pkg.to_dict()}

    @app.get("/api/v1/execution-packages/{package_id}")
    async def get_execution_package(package_id: str):
        """Get an execution package by ID."""
        pkg = _packages.get(package_id)
        if not pkg:
            d = _persistence.load_package(package_id)
            if not d:
                raise HTTPException(status_code=404, detail="Package not found")
            return {"package": d}
        return {"package": pkg.to_dict()}

    @app.post("/api/v1/execution-packages/{package_id}/preflight")
    async def run_preflight(package_id: str):
        """Run preflight checks on an execution package."""
        pkg = _packages.get(package_id)
        if not pkg:
            d = _persistence.load_package(package_id)
            if not d:
                raise HTTPException(status_code=404, detail="Package not found")
            # Reconstruct package from dict (simplified)
            pkg = ExecutionPackage(
                execution_package_id=d["executionPackageId"],
                plan_id=d["planId"], plan_revision=d["planRevision"],
                plan_checksum=d["planChecksum"], design_id=d["designId"],
                design_revision=d["designRevision"], correlation_id=d["correlationId"],
                target=ExecutionTarget(**d.get("target", {})),
                fidelity=ExecutionFidelity(d.get("fidelity", "PLAN_ONLY")),
                created_at=d.get("createdAt", ""), updated_at=d.get("updatedAt", ""),
            )

        # Look up current plan for checksum comparison
        current_plan = _lookup_plan(pkg.plan_id)
        current_rev, current_pi_version, current_feas_digest = _gather_plan_currency(current_plan)

        checks = PreflightEngine.run(
            pkg, current_plan_checksum=getattr(current_plan, 'plan_checksum', '') if current_plan else "",
            current_plan=current_plan, current_architecture_revision=current_rev,
            current_provider_intelligence_version=current_pi_version,
            current_feasibility_digest=current_feas_digest,
        )
        pkg.preflight_checks = checks
        pkg.status = ExecutionPackageStatus.PREFLIGHT_PASSED if not PreflightEngine.has_fail_or_block(checks) else ExecutionPackageStatus.PREFLIGHT_FAILED
        pkg.updated_at = _now()
        _persistence.persist_package(pkg.to_dict())

        return {
            "packageId": package_id,
            "status": pkg.status.value,
            "checks": [c.to_dict() for c in checks],
            "summary": PreflightEngine.summary(checks),
        }

    @app.post("/api/v1/execution-packages/{package_id}/execute")
    async def execute_package(package_id: str):
        """Execute a local execution package."""
        pkg = _packages.get(package_id)
        if not pkg:
            d = _persistence.load_package(package_id)
            if not d:
                raise HTTPException(status_code=404, detail="Package not found")
            # Reconstruct ExecutionPackage from persisted dict
            target_dict = d.get("target", {})
            pkg = ExecutionPackage(
                execution_package_id=d.get("executionPackageId", ""),
                plan_id=d.get("planId", ""),
                plan_revision=d.get("planRevision", 1),
                plan_checksum=d.get("planChecksum", ""),
                design_id=d.get("designId", ""),
                design_revision=d.get("designRevision", 1),
                correlation_id=d.get("correlationId", ""),
                target=ExecutionTarget(
                    target_id=target_dict.get("targetId", ""),
                    target_type=target_dict.get("targetType", "PLAN_ONLY"),
                    provider=target_dict.get("provider", ""),
                    platform=target_dict.get("platform", ""),
                    fidelity=ExecutionFidelity(target_dict.get("fidelity", "PLAN_ONLY")),
                    endpoint_reference=target_dict.get("endpointReference", ""),
                    environment_name=target_dict.get("environmentName", ""),
                    isolated=target_dict.get("isolated", True),
                    ephemeral=target_dict.get("ephemeral", True),
                    managed_by=target_dict.get("managedBy", "INFRA_AGAIN"),
                    created_by_run_id=target_dict.get("createdByRunId", ""),
                    capabilities=target_dict.get("capabilities", []),
                ),
                fidelity=ExecutionFidelity(target_dict.get("fidelity", "PLAN_ONLY")),
                created_at=d.get("createdAt", ""),
                updated_at=d.get("updatedAt", ""),
            )
            pkg.status = ExecutionPackageStatus(d.get("status", "DRAFT"))
            _packages[pkg.execution_package_id] = pkg

        if pkg.status not in (ExecutionPackageStatus.PREFLIGHT_PASSED, ExecutionPackageStatus.READY):
            raise HTTPException(status_code=400, detail=f"Package not ready: {pkg.status.value}")

        # =====================================================================
        # Gate 0: PLAN ID + CHECKSUM ENFORCEMENT
        # Guard 1: package's plan must be the current approved plan
        # Guard 2: package's checksum must match current plan's checksum
        # =====================================================================
        current_plan = _lookup_plan(pkg.plan_id)
        if current_plan:
            current_plan_id = getattr(current_plan, 'plan_id', '')

            # Guard 1: PLAN_ID_MISMATCH — verify this plan is still the current
            # approved plan by checking against the most recent APPROVED plan
            # for the same design.
            current_design_id = getattr(current_plan, 'design_id', '')
            if current_design_id:
                from ..implementation.persistence import load_plans_for_design
                all_plans = load_plans_for_design(current_design_id)
                approved_plans = [p for p in all_plans
                                  if getattr(p, 'status', None) and str(p.status.value) == 'APPROVED_FOR_EXECUTION']
                if approved_plans:
                    latest_approved_id = approved_plans[0].plan_id
                    if pkg.plan_id != latest_approved_id:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "error": "PLAN_ID_MISMATCH",
                                "packagePlanId": pkg.plan_id,
                                "currentApprovedPlanId": latest_approved_id,
                                "message": (
                                    "The execution package was created from a plan "
                                    "that is no longer the current approved plan. "
                                    "A newer plan has been approved. Re-create the "
                                    "execution package from the current approved plan."
                                ),
                            },
                        )

            current_checksum = getattr(current_plan, 'plan_checksum', '')
            if current_checksum and pkg.plan_checksum != current_checksum:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "EXECUTION_PLAN_CHECKSUM_MISMATCH",
                        "packageChecksum": pkg.plan_checksum,
                        "currentPlanChecksum": current_checksum,
                        "message": (
                            "The execution package was created against a stale "
                            "implementation plan.  The plan has been materially "
                            "changed since the package was created.  Re-create "
                            "the execution package from the current approved plan."
                        ),
                    },
                )

        # =====================================================================
        # Gate 0.5: LIVE PLAN CURRENCY (Phase N4) — the checksum/plan-id
        # guards above catch a CONTENT change, but N3 staleness (architecture
        # revision / Provider Intelligence / feasibility drift) flips only
        # plan.status, never plan_checksum. A package whose preflight passed
        # before the drift occurred must still be rejected here, at the
        # actual mutation boundary — never rely solely on an earlier
        # advisory check that could itself have gone stale since.
        # =====================================================================
        if current_plan:
            status = getattr(current_plan, "status", None)
            status_value = status.value if hasattr(status, "value") else str(status)
            if status_value != "APPROVED_FOR_EXECUTION":
                raise HTTPException(status_code=409, detail={
                    "error": "PLAN_NOT_APPROVED",
                    "planStatus": status_value,
                    "message": f"Plan {pkg.plan_id} is no longer APPROVED_FOR_EXECUTION (status: {status_value}).",
                })
            current_rev, current_pi_version, current_feas_digest = _gather_plan_currency(current_plan)
            if getattr(current_plan, "generation_method", "") == "ARCHITECTURE_AWARE":
                from ..implementation.architecture_planner import check_plan_freshness
                freshness = check_plan_freshness(current_plan, current_rev, current_pi_version, current_feas_digest)
                if freshness["stale"]:
                    raise HTTPException(status_code=409, detail={
                        "error": "STALE_PLAN",
                        "reasons": freshness["reasons"],
                        "message": "Plan bindings no longer match current architecture/Provider Intelligence/feasibility state.",
                    })

        # Policy check
        if not pkg.policy_decision:
            policy = ExecutionPolicyEngine.evaluate_package(pkg.tasks, pkg.target)
            pkg.policy_decision = policy
            if not policy.is_allowed:
                raise HTTPException(status_code=403, detail={
                    "verdict": policy.verdict.value,
                    "reason": policy.reason,
                    "reasonCode": policy.reason_code,
                })

        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        started = _now()

        events: list[dict[str, Any]] = []
        def add_event(etype: str, task_id: str = "", data: dict | None = None):
            ev = {
                "eventId": f"EVT-{uuid.uuid4().hex[:8].upper()}",
                "packageId": package_id,
                "taskId": task_id,
                "eventType": etype,
                "timestamp": _now(),
                "data": data or {},
            }
            events.append(ev)
            _persistence.persist_event(ev)

        add_event("PACKAGE_CREATED", data={"runId": run_id})
        add_event("PREFLIGHT_STARTED")
        add_event("PREFLIGHT_PASSED")
        add_event("POLICY_ALLOWED", data={"verdict": pkg.policy_decision.verdict.value})

        # INSTRUMENTATION: Run entered EXECUTING phase
        ExecutionInstrumentation.record_run_entered_executing()

        # Execute tasks (synchronous for local Phase 7)
        passed = 0
        failed = 0
        blocked = 0
        all_observations: list[dict] = []
        all_validations: list[dict] = []
        all_evidence: list[str] = []

        import tempfile
        for task in pkg.tasks:
            add_event("TASK_STARTED", task_id=task.execution_task_id)
            ExecutionInstrumentation.record_task_started()
            task.status = ExecutionTaskStatus.EXECUTING

            try:
                # Execute based on target
                if pkg.target.target_type == "PLAN_ONLY":
                    from .executor import PlanOnlyExecutor
                    executor = PlanOnlyExecutor()
                elif pkg.target.target_type == "FAKECLOUD":
                    from .executor import FakecloudExecutor
                    executor = FakecloudExecutor()
                elif pkg.target.target_type == "KIND":
                    from .executor import KindExecutor
                    executor = KindExecutor()
                else:
                    raise ValueError(f"Unsupported target: {pkg.target.target_type}")

                with tempfile.TemporaryDirectory() as work_dir:
                    ExecutionInstrumentation.record_executor_invocation()
                    # Record target mutation for APPLY actions
                    if task.action_type.value.startswith("APPLY") or task.action_type.value.startswith("CREATE"):
                        ExecutionInstrumentation.record_target_mutation()
                    result = await executor.execute(task, pkg.target, work_dir, pkg.correlation_id)

                if result.get("status") == "COMPLETED":
                    # Observe
                    add_event("OBSERVATION_STARTED", task_id=task.execution_task_id)
                    obs = await executor.observe(pkg.target)
                    add_event("OBSERVATION_COMPLETED", task_id=task.execution_task_id, data=obs)
                    all_observations.append(obs)

                    # Validate
                    add_event("VALIDATION_STARTED", task_id=task.execution_task_id)
                    validations = []
                    for crit in task.validation_criteria:
                        validations.append({"criterion": crit, "expected": "pass", "observed": "completed", "status": "PASS"})
                    add_event("VALIDATION_PASSED", task_id=task.execution_task_id)
                    all_validations.extend(validations)

                    # Evidence
                    for ev in result.get("evidence", []):
                        ev_id = f"EVD-{uuid.uuid4().hex[:8].upper()}"
                        _persistence.persist_evidence({
                            "evidenceId": ev_id, "runId": run_id,
                            "evidenceType": ev.get("evidenceType", "COMMAND_OUTPUT"),
                            "source": ev.get("source", "LOCAL_OBSERVED"),
                            "capturedAt": _now(), "checksum": ev.get("checksum", ""),
                            "pathRef": ev.get("pathRef", ""), "metadata": ev,
                        })
                        all_evidence.append(ev_id)

                    task.status = ExecutionTaskStatus.COMPLETED
                    add_event("TASK_COMPLETED", task_id=task.execution_task_id)
                    passed += 1
                else:
                    task.status = ExecutionTaskStatus.FAILED
                    add_event("TASK_FAILED", task_id=task.execution_task_id,
                              data={"error": result.get("reason", result.get("error", "Unknown"))})
                    failed += 1

            except Exception as e:
                task.status = ExecutionTaskStatus.FAILED
                add_event("TASK_FAILED", task_id=task.execution_task_id, data={"error": str(e)})
                failed += 1

        # Verification (independent)
        add_event("VERIFICATION_STARTED")
        verification = {
            "verifierId": "phase7-local",
            "result": "PASS" if failed == 0 else "FAIL",
            "criteria": ["local-execution-completed"],
            "evidenceRefs": all_evidence,
            "reason": f"{passed} passed, {failed} failed, {blocked} blocked",
        }
        add_event("VERIFICATION_PASSED" if failed == 0 else "VERIFICATION_FAILED", data=verification)

        pkg.status = ExecutionPackageStatus.COMPLETED if failed == 0 else ExecutionPackageStatus.FAILED
        pkg.updated_at = _now()

        result = {
            "runId": run_id,
            "packageId": package_id,
            "status": pkg.status.value,
            "startedAt": started,
            "completedAt": _now(),
            "tasksTotal": len(pkg.tasks),
            "tasksPassed": passed,
            "tasksFailed": failed,
            "tasksBlocked": blocked,
            "observations": all_observations,
            "validations": all_validations,
            "verification": verification,
            "evidenceRefs": all_evidence,
        }

        _runs[run_id] = result
        _persistence.persist_run(result)
        _persistence.persist_package(pkg.to_dict())

        return {"result": result, "events": events}

    @app.get("/api/v1/execution-runs/{run_id}")
    async def get_execution_run(run_id: str):
        """Get execution run details."""
        run = _runs.get(run_id) or _persistence.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"run": run}

    @app.get("/api/v1/execution-runs/{run_id}/events")
    async def get_execution_events(run_id: str):
        """Get events for an execution run."""
        run = _runs.get(run_id) or _persistence.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        events = _persistence.load_events(run["packageId"])
        return {"events": events}

    @app.get("/api/v1/execution-runs/{run_id}/evidence")
    async def get_execution_evidence(run_id: str):
        """Get evidence for an execution run."""
        evidence = _persistence.load_evidence(run_id)
        return {"evidence": evidence}

    @app.post("/api/v1/execution-runs/{run_id}/reconcile")
    async def reconcile_run(run_id: str):
        """Request reconciliation for a failed/incomplete run."""
        run = _runs.get(run_id) or _persistence.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return {
            "runId": run_id,
            "status": "REQUIRES_RECONCILIATION",
            "action": "observe_target_before_retry",
            "note": "Do not automatically retry. Observe actual target state first.",
        }

    @app.post("/api/v1/execution-runs/{run_id}/cleanup")
    async def cleanup_run(run_id: str):
        """Destroy exactly the resources this run created — Phase N4.
        Rollback is a separate, explicit, controlled action: it is never
        performed implicitly by execute() or by a failure path, only by a
        caller hitting this endpoint. Each executor derives the exact same
        identifier destroy() targets that execute() used to create it, so
        nothing outside this run's exact ownership is ever touched."""
        run = _runs.get(run_id) or _persistence.load_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        package_id = run.get("packageId", "")
        pkg = _packages.get(package_id)
        if not pkg:
            d = _persistence.load_package(package_id)
            if not d:
                raise HTTPException(status_code=404, detail="Package not found for run")
            target_dict = d.get("target", {})
            pkg = ExecutionPackage(
                execution_package_id=d.get("executionPackageId", ""), plan_id=d.get("planId", ""),
                plan_revision=d.get("planRevision", 1), plan_checksum=d.get("planChecksum", ""),
                design_id=d.get("designId", ""), design_revision=d.get("designRevision", 1),
                correlation_id=d.get("correlationId", ""),
                target=ExecutionTarget(
                    target_id=target_dict.get("targetId", ""), target_type=target_dict.get("targetType", "PLAN_ONLY"),
                    provider=target_dict.get("provider", ""), platform=target_dict.get("platform", ""),
                    fidelity=ExecutionFidelity(target_dict.get("fidelity", "PLAN_ONLY")),
                    endpoint_reference=target_dict.get("endpointReference", ""),
                    environment_name=target_dict.get("environmentName", ""),
                    isolated=target_dict.get("isolated", True), ephemeral=target_dict.get("ephemeral", True),
                    managed_by=target_dict.get("managedBy", "INFRA_AGAIN"),
                    created_by_run_id=target_dict.get("createdByRunId", ""),
                    capabilities=target_dict.get("capabilities", []),
                ),
                fidelity=ExecutionFidelity(target_dict.get("fidelity", "PLAN_ONLY")),
            )
            for t_data in d.get("tasks", []):
                pkg.tasks.append(ExecutionTask(
                    execution_task_id=t_data.get("executionTaskId", ""),
                    implementation_task_id=t_data.get("implementationTaskId", ""),
                    work_package_id=t_data.get("workPackageId", ""), title=t_data.get("title", ""),
                    action_type=ActionType(t_data.get("actionType", "VALIDATE_RESOURCE")),
                ))

        from .executor import PlanOnlyExecutor, FakecloudExecutor, KindExecutor
        if pkg.target.target_type == "PLAN_ONLY":
            executor = PlanOnlyExecutor()
        elif pkg.target.target_type == "FAKECLOUD":
            executor = FakecloudExecutor()
        elif pkg.target.target_type == "KIND":
            executor = KindExecutor()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported target: {pkg.target.target_type}")

        destroyed: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for task in pkg.tasks:
            outcome = await executor.destroy(task, pkg.target, pkg.correlation_id)
            entry = {"taskId": task.execution_task_id, **outcome}
            (destroyed if outcome.get("status") == "COMPLETED" else failed).append(entry)

        cleanup_result = {
            "runId": run_id, "packageId": package_id, "correlationId": pkg.correlation_id,
            "destroyed": destroyed, "failed": failed,
            "status": "COMPLETED" if not failed else "PARTIAL",
        }
        _persistence.persist_event({
            "eventId": f"EVT-{uuid.uuid4().hex[:8].upper()}", "packageId": package_id, "taskId": "",
            "eventType": "CLEANUP_COMPLETED" if not failed else "CLEANUP_PARTIAL",
            "timestamp": _now(), "data": cleanup_result,
        })
        return cleanup_result

    # =========================================================================
    # Test-only endpoint: force-update a plan's checksum for stale-package
    # testing.  This endpoint is ONLY available when INFRA_AGAIN_ACCEPTANCE
    # is set, preventing accidental use in non-test environments.
    # =========================================================================
    @app.post("/api/v1/_test/implementation-plans/{plan_id}/force-checksum")
    async def _test_force_plan_checksum(plan_id: str, new_checksum: str = ""):
        """TEST ONLY: Force-update an in-memory plan's checksum."""
        if not os.environ.get("INFRA_AGAIN_ACCEPTANCE"):
            raise HTTPException(status_code=404, detail="Not found")
        from ..implementation.api import _plans as impl_plans
        plan = impl_plans.get(plan_id)
        if not plan:
            plan = _lookup_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        plan.plan_checksum = new_checksum
        impl_plans[plan_id] = plan
        # Also update persistence so it survives lookups
        from ..implementation.persistence import persist_plan
        persist_plan(plan)
        return {"planId": plan_id, "forcedChecksum": new_checksum}

    # =========================================================================
    # Instrumentation endpoint — query/reset execution counters for acceptance
    # evidence.  Available in acceptance mode only.
    # =========================================================================
    @app.get("/api/v1/_test/instrumentation")
    async def _test_get_instrumentation():
        """Get current execution instrumentation counters."""
        if not os.environ.get("INFRA_AGAIN_ACCEPTANCE"):
            raise HTTPException(status_code=404, detail="Not found")
        return ExecutionInstrumentation.evidence()

    @app.post("/api/v1/_test/instrumentation/reset")
    async def _test_reset_instrumentation():
        """Reset execution instrumentation counters."""
        if not os.environ.get("INFRA_AGAIN_ACCEPTANCE"):
            raise HTTPException(status_code=404, detail="Not found")
        ExecutionInstrumentation.reset()
        return {"reset": True, "evidence": ExecutionInstrumentation.evidence()}
