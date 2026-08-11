"""Implementation persistence — SQLite storage for plans."""
from __future__ import annotations
import json, sqlite3, os
from pathlib import Path
from .models import ImplementationPlan, PlanStatus, ReadinessState

DB_PATH = os.environ.get("INFRA_AGAIN_DB", str(Path(".ai/infra-again.db").resolve()))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS impl_plans (
            plan_id TEXT PRIMARY KEY, design_id TEXT, design_revision INTEGER,
            status TEXT, created_at TEXT, updated_at TEXT,
            summary TEXT, plan_json TEXT, plan_checksum TEXT,
            readiness TEXT, approved_by TEXT, approved_at TEXT,
            critical_path TEXT, critical_path_duration TEXT
        )
    """)
    conn.commit()


def persist_plan(plan: ImplementationPlan) -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO impl_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            plan.plan_id, plan.design_id, plan.design_revision,
            plan.status.value, plan.created_at, plan.updated_at or "",
            plan.summary, json.dumps(plan.to_dict()), plan.plan_checksum,
            plan.readiness.value, plan.approved_by, plan.approved_at,
            json.dumps(plan.critical_path), plan.critical_path_duration,
        ))
        conn.commit()
    finally:
        conn.close()


def load_plan(plan_id: str) -> ImplementationPlan | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM impl_plans WHERE plan_id=?", (plan_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["plan_json"])
        return _reconstruct_plan(data)
    finally:
        conn.close()


def load_plans_for_design(design_id: str) -> list[ImplementationPlan]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT plan_json FROM impl_plans WHERE design_id=? ORDER BY created_at DESC", (design_id,)
        ).fetchall()
        return [_reconstruct_plan(json.loads(r["plan_json"])) for r in rows]
    finally:
        conn.close()


def _reconstruct_plan(data: dict) -> ImplementationPlan:
    from .models import (
        ImplementationWorkPackage, ImplementationTask, ImplementationDependency,
        ImplementationMilestone, ImplementationGate, ImplementationRisk,
        ImplementationBlocker, EvidenceRequirement, ImplementationEstimate,
        WorkPackageType, TaskStatus, AutomationEligibility, RiskSeverity,
        ReadinessState, GateState, EvidenceType, EstimateSource, EffortUnit,
        DeliveryStage, RiskCategory, PlanStatus,
        TaskExecutionClassification, RollbackCapability,
    )
    plan = ImplementationPlan(
        plan_id=data.get("planId", ""), design_id=data.get("designId", ""),
        design_revision=data.get("designRevision", 1),
        status=PlanStatus(data["status"]) if data.get("status") else PlanStatus.DRAFT,
        created_at=data.get("createdAt", ""), updated_at=data.get("updatedAt", ""),
        summary=data.get("summary", ""), plan_checksum=data.get("planChecksum", ""),
        readiness=ReadinessState(data.get("readiness", "NOT_READY")),
        approved_by=data.get("approvedBy", ""), approved_at=data.get("approvedAt", ""),
        critical_path=data.get("criticalPath", []),
        critical_path_duration=data.get("criticalPathDuration", ""),
        baseline_checksums=data.get("baselineChecksums", {}),
        architecture_id=data.get("architectureId", ""),
        architecture_revision=data.get("architectureRevision", 0),
        plan_version=data.get("planVersion", 1),
        plan_digest=data.get("planDigest", ""),
        approved_plan_digest=data.get("approvedPlanDigest", ""),
        provider_intelligence_version=data.get("providerIntelligenceVersion", ""),
        feasibility_digest=data.get("feasibilityDigest", ""),
        feasibility_assessment_id=data.get("feasibilityAssessmentId", ""),
        target_fidelity=data.get("targetFidelity", ""),
        correlation_id=data.get("correlationId", ""),
        created_by=data.get("createdBy", ""),
        generation_method=data.get("generationMethod", "LEGACY_FLOW_HEURISTIC"),
        stale=data.get("stale", False), stale_reason=data.get("staleReason", ""),
        superseded_by=data.get("supersededBy", ""),
        dependency_cycle_detected=data.get("dependencyCycleDetected", False),
        cycle_nodes=data.get("cycleNodes", []),
    )
    # Reconstruct work packages
    for wp_data in data.get("workPackages", []):
        wp = ImplementationWorkPackage(
            package_id=wp_data.get("packageId", ""), plan_id=plan.plan_id,
            title=wp_data.get("title", ""), description=wp_data.get("description", ""),
            package_type=WorkPackageType(wp_data["packageType"]) if wp_data.get("packageType") else WorkPackageType.INFRASTRUCTURE,
            dependencies=wp_data.get("dependencies", []),
            parallel_group=wp_data.get("parallelGroup", ""),
            status=TaskStatus(wp_data["status"]) if wp_data.get("status") else TaskStatus.PLANNED,
            execution_readiness=wp_data.get("executionReadiness", "UNKNOWN"),
            blocking_issues=wp_data.get("blockingIssues", []),
            estimated_cost=wp_data.get("estimatedCost", "UNKNOWN"),
            blast_radius=wp_data.get("blastRadius", "UNKNOWN"),
        )
        for t_data in wp_data.get("tasks", []):
            task = ImplementationTask(
                task_id=t_data.get("taskId", ""), work_package_id=wp.package_id,
                title=t_data.get("title", ""), description=t_data.get("description", ""),
                category=WorkPackageType(t_data["category"]) if t_data.get("category") else WorkPackageType.INFRASTRUCTURE,
                status=TaskStatus.PLANNED, priority=t_data.get("priority", 5),
                execution_mode=t_data.get("executionMode", "PLAN_ONLY"),
                dependencies=t_data.get("dependencies", []),
                acceptance_criteria=t_data.get("acceptanceCriteria", []),
                risk_level=RiskSeverity(t_data["riskLevel"]) if t_data.get("riskLevel") else RiskSeverity.LOW,
                automation=AutomationEligibility(t_data["automation"]) if t_data.get("automation") else AutomationEligibility.MANUAL,
                derived_from=t_data.get("derivedFrom", []),
                local_validatable=t_data.get("localValidatable", False),
                source_node_ids=t_data.get("sourceNodeIds", []),
                source_edge_ids=t_data.get("sourceEdgeIds", []),
                provider=t_data.get("provider", ""),
                canonical_service_id=t_data.get("canonicalServiceId", ""),
                runtime_mode=t_data.get("runtimeMode", ""),
                requirement_refs=t_data.get("requirementRefs", []),
                decision_refs=t_data.get("decisionRefs", []),
                provider_intelligence_ref=t_data.get("providerIntelligenceRef", ""),
                provider_intelligence_version=t_data.get("providerIntelligenceVersion", ""),
                target_fidelity=t_data.get("targetFidelity", ""),
                execution_classification=TaskExecutionClassification(t_data["executionClassification"])
                    if t_data.get("executionClassification") else TaskExecutionClassification.UNKNOWN,
                blocking_issues=t_data.get("blockingIssues", []),
                estimated_cost=t_data.get("estimatedCost", "UNKNOWN"),
                blast_radius=t_data.get("blastRadius", "UNKNOWN"),
                rollback_capability=RollbackCapability(t_data["rollbackCapability"])
                    if t_data.get("rollbackCapability") else RollbackCapability.NOT_APPLICABLE,
            )
            wp.tasks.append(task)
        plan.work_packages.append(wp)
    # Dependencies
    for d_data in data.get("dependencies", []):
        plan.dependencies.append(ImplementationDependency(
            dep_id=d_data.get("depId", ""), from_package=d_data.get("fromPackage", ""),
            to_package=d_data.get("toPackage", ""), description=d_data.get("description", ""),
        ))
    # Milestones, risks, gates, blockers
    for m_data in data.get("milestones", []):
        plan.milestones.append(ImplementationMilestone(
            milestone_id=m_data.get("milestoneId", ""), name=m_data.get("name", ""),
            description=m_data.get("description", ""), depends_on=m_data.get("dependsOn", []),
            completed=m_data.get("completed", False),
        ))
    for r_data in data.get("risks", []):
        plan.risks.append(ImplementationRisk(
            risk_id=r_data.get("riskId", ""), title=r_data.get("title", ""),
            description=r_data.get("description", ""),
            severity=RiskSeverity(r_data["severity"]) if r_data.get("severity") else RiskSeverity.MEDIUM,
            category=RiskCategory(r_data["category"]) if r_data.get("category") else RiskCategory.INTEGRATION,
            affected_tasks=r_data.get("affectedTasks", []),
        ))
    for g_data in data.get("gates", []):
        plan.gates.append(ImplementationGate(
            gate_id=g_data.get("gateId", ""), name=g_data.get("name", ""),
            state=GateState(g_data["state"]) if g_data.get("state") else GateState.PENDING,
            description=g_data.get("description", ""),
        ))
    for b_data in data.get("blockers", []):
        plan.blockers.append(ImplementationBlocker(
            blocker_id=b_data.get("blockerId", ""),
            severity=RiskSeverity(b_data["severity"]) if b_data.get("severity") else RiskSeverity.HIGH,
            description=b_data.get("description", ""),
            affected_tasks=b_data.get("affectedTasks", []),
            resolution_required=b_data.get("resolutionRequired", ""),
        ))
    plan.open_questions = data.get("openQuestions", [])
    return plan
