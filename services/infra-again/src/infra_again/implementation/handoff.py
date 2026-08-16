"""Implementation handoff — PM and QA contract generation."""
from __future__ import annotations
from .models import ImplementationPlan


def generate_pm_handoff(plan: ImplementationPlan) -> dict:
    """Generate portable PM work-package contract."""
    return {
        "contractVersion": "1.0",
        "planId": plan.plan_id,
        "designId": plan.design_id,
        "designRevision": plan.design_revision,
        "status": plan.status.value,
        "workPackages": [
            {
                "packageId": w.package_id, "title": w.title,
                "description": w.description, "packageType": w.package_type.value,
                "taskCount": len(w.tasks), "dependencies": w.dependencies,
                "estimatedEffort": w.estimated_effort.to_dict(),
                "status": w.status.value,
            }
            for w in plan.work_packages
        ],
        "milestones": [m.to_dict() for m in plan.milestones],
        "risks": [r.to_dict() for r in plan.risks],
        "criticalPath": plan.critical_path,
        "readiness": plan.readiness.value,
        "generatedAt": plan.created_at,
    }


def generate_qa_handoff(plan: ImplementationPlan) -> dict:
    """Generate portable QA testing contract with flow scenario references."""
    return {
        "contractVersion": "1.0",
        "planId": plan.plan_id,
        "designId": plan.design_id,
        "designRevision": plan.design_revision,
        "testItems": [
            {
                "taskId": t.task_id,
                "workPackageId": t.work_package_id,
                "title": t.title,
                "acceptanceCriteria": t.acceptance_criteria,
                "evidenceRequirements": [e.to_dict() for e in t.evidence_requirements],
                "riskLevel": t.risk_level.value,
                "executionMode": t.execution_mode,
                "scenarioReferences": [d.get("id", "") for d in t.derived_from if "scenario" in d.get("type", "").lower() or "flow" in d.get("type", "").lower()],
            }
            for w in plan.work_packages
            for t in w.tasks
            if t.category.value == "TESTING" or t.evidence_requirements
        ],
        "generatedAt": plan.created_at,
    }
