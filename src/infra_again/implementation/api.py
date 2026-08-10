"""Implementation Planning API routes."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from .models import ImplementationPlan, PlanStatus
from .planner import generate_implementation_plan, detect_cycles
from .persistence import persist_plan, load_plan, load_plans_for_design
from .handoff import generate_pm_handoff, generate_qa_handoff

_plans: dict[str, ImplementationPlan] = {}


def _load_persisted() -> None:
    """Load persisted plans into memory cache."""
    # Plans are loaded on demand via load_plan()


def register_impl_routes(app: FastAPI) -> None:
    """Register implementation planning routes."""

    @app.post("/api/v1/designs/{design_id}/implementation-plan")
    async def create_implementation_plan(design_id: str):
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

        plan = generate_implementation_plan(
            design.to_dict(),
            flow=flow_dict,
        )
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

    @app.post("/api/v1/implementation-plans/{plan_id}/approve")
    async def approve_plan(plan_id: str, approved_by: str = ""):
        plan = _plans.get(plan_id) or load_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404)
        if plan.status != PlanStatus.REVIEW_READY:
            raise HTTPException(status_code=400, detail=f"Cannot approve plan in status {plan.status.value}")
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
