"""Implementation Planning API routes."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from .models import ImplementationPlan, PlanStatus
from .planner import generate_implementation_plan, detect_cycles
from .architecture_planner import generate_implementation_plan_from_architecture, check_plan_freshness
from .persistence import persist_plan, load_plan, load_plans_for_design
from .handoff import generate_pm_handoff, generate_qa_handoff

_plans: dict[str, ImplementationPlan] = {}


def _load_persisted() -> None:
    """Load persisted plans into memory cache."""
    # Plans are loaded on demand via load_plan()


def _has_canonical_service_data(flow_dict: dict | None) -> bool:
    """True when the flow's nodes carry real N1-enrichable service data
    (nativeService), i.e. it was authored by AGAINPILOT rather than being a
    legacy hand-built flow with only generic nodeId/category."""
    if not flow_dict:
        return False
    return any(n.get("nativeService") for n in flow_dict.get("nodes", []))


def register_impl_routes(app: FastAPI) -> None:
    """Register implementation planning routes."""

    @app.post("/api/v1/designs/{design_id}/implementation-plan")
    async def create_implementation_plan(design_id: str, targetFidelity: str = "SIMULATED"):
        from ..flow.api import _designs, _flows, _get_conn
        import json
        design = _designs.get(design_id)
        if not design:
            raise HTTPException(status_code=404, detail="Design not found")
        if design.status.value != "BASELINE_FROZEN":
            raise HTTPException(status_code=400,
                detail="IMPLEMENTATION_PLAN_NOT_ALLOWED: Design must be BASELINE_FROZEN")

        # Load flow from DB (flow_json column) — canonical model
        flow_dict = None
        conn = _get_conn()
        try:
            row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (design_id,)).fetchone()
            if row and row["flow_json"]:
                flow_dict = json.loads(row["flow_json"])
        finally:
            conn.close()

        # Also check in-memory flows
        if not flow_dict:
            flow = next((f for f in _flows.values() if f.architecture_graph_id == design_id), None)
            flow_dict = flow.to_dict() if flow else None

        # Phase N3: prefer the architecture-aware generator (traceable to
        # real Provider Intelligence / N2 feasibility) whenever the flow
        # actually carries canonical service data. Falls back to the
        # legacy flow-nodeId-heuristic generator otherwise — never a
        # silent behavior change for designs that predate AGAINPILOT.
        if _has_canonical_service_data(flow_dict):
            nodes = flow_dict.get("nodes", [])
            edges = flow_dict.get("edges", [])
            provider = next((n.get("provider", "") for n in nodes if n.get("provider") not in ("", "EXTERNAL")), "")
            plan = generate_implementation_plan_from_architecture(
                nodes, edges, architecture_id=design_id, architecture_revision=design.revision,
                provider=provider, platform=flow_dict.get("platform", ""),
                target_fidelity=targetFidelity,
            )
        else:
            plan = generate_implementation_plan(design.to_dict(), flow=flow_dict)

        _plans[plan.plan_id] = plan
        persist_plan(plan)
        return {"plan": plan.to_dict()}

    @app.get("/api/v1/implementation-plans/{plan_id}")
    async def get_implementation_plan(plan_id: str):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if plan_id not in _plans:
            _plans[plan_id] = plan
        return {"plan": plan.to_dict()}

    @app.get("/api/v1/implementation-plans/{plan_id}/work-packages")
    async def get_work_packages(plan_id: str):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        return {"planId": plan_id, "workPackages": [w.to_dict() for w in plan.work_packages]}

    @app.get("/api/v1/implementation-plans/{plan_id}/dependencies")
    async def get_dependencies(plan_id: str):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        return {
            "planId": plan_id,
            "dependencies": [d.to_dict() for d in plan.dependencies],
            "criticalPath": plan.critical_path,
            "cycles": detect_cycles(plan.work_packages, plan.dependencies),
        }

    @app.get("/api/v1/implementation-plans/{plan_id}/readiness")
    async def get_readiness(plan_id: str):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        return {
            "planId": plan_id, "readiness": plan.readiness.value,
            "blockers": [b.to_dict() for b in plan.blockers],
            "gates": [g.to_dict() for g in plan.gates],
            "risks": [r.to_dict() for r in plan.risks],
            "openQuestions": plan.open_questions,
        }

    @app.get("/api/v1/implementation-plans/{plan_id}/status")
    async def get_plan_status(plan_id: str):
        """Phase N3 — freshness-aware plan status. Recomputes CURRENT
        architecture revision / Provider Intelligence version / feasibility
        digest and compares against what the plan is bound to. If the plan
        is APPROVED_FOR_EXECUTION and has drifted, its status is
        transitioned to BASELINE_INVALIDATED (existing domain vocabulary)
        and persisted — the plan's CONTENT is never rewritten, only its
        status/staleness metadata."""
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        freshness = {"stale": False, "reasons": []}
        if plan.generation_method == "ARCHITECTURE_AWARE":
            from ..flow.api import _designs, _get_conn
            from ..intelligence.catalog import get_catalog
            from ..intelligence.feasibility import assess_architecture_feasibility, feasibility_digest
            import json

            design = _designs.get(plan.design_id)
            current_rev = design.revision if design else plan.architecture_revision
            current_pi_version = get_catalog().version()
            conn = _get_conn()
            try:
                row = conn.execute("SELECT flow_json FROM flow_designs WHERE design_id=?", (plan.design_id,)).fetchone()
            finally:
                conn.close()
            flow_data = json.loads(row["flow_json"]) if row and row["flow_json"] else {}
            current_assessment = assess_architecture_feasibility(
                flow_data.get("nodes", []), architecture_id=plan.design_id,
                architecture_revision=str(current_rev), requested_fidelity=plan.target_fidelity,
            )
            current_digest = feasibility_digest(current_assessment)

            freshness = check_plan_freshness(plan, current_rev, current_pi_version, current_digest)
            if freshness["stale"]:
                plan.stale = True
                plan.stale_reason = "; ".join(freshness["reasons"])
                if plan.status == PlanStatus.APPROVED_FOR_EXECUTION:
                    plan.status = PlanStatus.BASELINE_INVALIDATED
                    _plans[plan_id] = plan
                    persist_plan(plan)

        total_tasks = sum(len(w.tasks) for w in plan.work_packages)
        by_class: dict[str, int] = {}
        for w in plan.work_packages:
            for t in w.tasks:
                by_class[t.execution_classification.value] = by_class.get(t.execution_classification.value, 0) + 1

        return {
            "planId": plan.plan_id, "status": plan.status.value,
            "architectureRevision": plan.architecture_revision or plan.design_revision,
            "targetFidelity": plan.target_fidelity,
            "providerIntelligenceVersion": plan.provider_intelligence_version,
            "feasibilityDigest": plan.feasibility_digest,
            "planDigest": plan.plan_digest,
            "stale": freshness["stale"], "staleReasons": freshness["reasons"],
            "totalTasks": total_tasks, "tasksByClassification": by_class,
            "dependencyCycleDetected": plan.dependency_cycle_detected,
            "blockers": [b.to_dict() for b in plan.blockers],
        }

    @app.post("/api/v1/implementation-plans/{plan_id}/approve")
    async def approve_plan(plan_id: str, approved_by: str = ""):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        if plan.status != PlanStatus.REVIEW_READY:
            raise HTTPException(status_code=400, detail=f"Cannot approve plan in status {plan.status.value}")
        if plan.dependency_cycle_detected:
            raise HTTPException(status_code=400, detail={
                "error": "DEPENDENCY_CYCLE_BLOCKS_APPROVAL",
                "cycleNodes": plan.cycle_nodes,
            })
        plan.approve(approved_by)
        _plans[plan_id] = plan
        persist_plan(plan)
        return {"plan": plan.to_dict(), "note": "No infrastructure will be created by this action."}

    @app.post("/api/v1/implementation-plans/{plan_id}/request-change")
    async def request_change_plan(plan_id: str, comment: str = ""):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        plan.status = PlanStatus.CHANGE_REQUESTED
        _plans[plan_id] = plan
        persist_plan(plan)
        return {"plan": plan.to_dict(), "comment": comment}

    @app.get("/api/v1/implementation-plans/{plan_id}/handoff/pm")
    async def get_pm_handoff(plan_id: str):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        return generate_pm_handoff(plan)

    @app.get("/api/v1/implementation-plans/{plan_id}/handoff/qa")
    async def get_qa_handoff(plan_id: str):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        return generate_qa_handoff(plan)
