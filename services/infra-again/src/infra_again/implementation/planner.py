"""Deterministic Implementation Planner — PHASE 6.0.1

Derives ImplementationPlan from accepted BASELINE_FROZEN design.
Every task is traceable to actual design truth.
No LLM — rule-based derivation from design.
"""

from __future__ import annotations

from typing import Any

from .models import (
    ImplementationPlan, ImplementationWorkPackage, ImplementationTask,
    ImplementationDependency, ImplementationMilestone, ImplementationGate,
    ImplementationRisk, ImplementationBlocker,
    WorkPackageType, TaskStatus, AutomationEligibility, RiskSeverity,
    ReadinessState, GateState, PlanStatus,
    ImplementationEstimate, EffortUnit, EstimateSource,
    DeliveryStage, RiskCategory,
)


def generate_implementation_plan(
    design: dict[str, Any],
    flow: dict[str, Any] | None = None,
    architecture: dict[str, Any] | None = None,
) -> ImplementationPlan:
    """Generate an implementation plan from an accepted BASELINE_FROZEN design.

    Args:
        design: DesignBaseline.to_dict()
        flow: FlowDefinition.to_dict() — the accepted flow
        architecture: Optional architecture graph dict
    """
    if design.get("status") != "BASELINE_FROZEN":
        raise ValueError("IMPLEMENTATION_PLAN_NOT_ALLOWED: Design must be BASELINE_FROZEN")

    plan = ImplementationPlan(
        design_id=design["designId"],
        design_revision=design["revision"],
        status=PlanStatus.GENERATED,
        baseline_checksums={
            "requirements": design.get("requirementsChecksum", ""),
            "architecture": design.get("architectureChecksum", ""),
            "flow": design.get("flowChecksum", ""),
        },
        summary=f"Implementation plan for {design.get('metadata', {}).get('name', design['designId'])} rev {design['revision']}",
    )

    # Extract design truth from flow nodes — use CATEGORIES, not hard-coded IDs
    flow_nodes: dict[str, dict] = {}
    flow_edges: list[dict] = []
    if flow:
        flow_nodes = {n.get("nodeId", ""): n for n in flow.get("nodes", [])}
        flow_edges = flow.get("edges", [])

    def node_has_category(cat: str) -> bool:
        return any(n.get("category", "").upper() == cat.upper() for n in flow_nodes.values())

    def node_has_id(partial_id: str) -> bool:
        return any(partial_id.lower() in nid.lower() for nid in flow_nodes)

    has_user = node_has_id("user")
    has_auth = node_has_id("credential") or node_has_category("IDENTITY")
    has_waf = node_has_id("waf")
    has_firewall = node_has_id("firewall")
    has_api = node_has_id("gateway") or node_has_id("api")
    has_app = node_has_category("APPLICATION") or node_has_id("application") or node_has_id("app")
    has_db = node_has_category("DATABASE") or node_has_id("postgres") or node_has_id("db")
    has_approval = node_has_id("approval") or node_has_category("APPROVAL")
    has_storage = node_has_category("STORAGE") or node_has_id("storage") or node_has_id("s3")

    has_any_security = has_auth or has_waf or has_firewall
    has_any_data = has_db or has_storage

    pkg_counter = [0]
    task_counter = [0]

    def next_pkg_id(prefix: str) -> str:
        pkg_counter[0] += 1
        return f"WP-{prefix}-{pkg_counter[0]:03d}"

    def next_task_id() -> str:
        task_counter[0] += 1
        return f"T-{task_counter[0]:03d}"

    def derived_from(*sources: str) -> list[dict]:
        result = []
        for s in sources:
            if ":" in s:
                typ, val = s.split(":", 1)
            else:
                typ, val = "RULE", s
            result.append({"type": typ, "id": val})
        return result

    # =====================================================================
    # Only create packages for design elements that actually exist
    # =====================================================================
    packages: list[ImplementationWorkPackage] = []
    all_deps: list[ImplementationDependency] = []

    # --- SECURITY (if any security nodes exist) ---
    if has_any_security:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("SEC"), plan_id=plan.plan_id,
            title="Security Foundation",
            description="Authentication, authorization, and security baseline derived from accepted design.",
            package_type=WorkPackageType.SECURITY,
            estimated_effort=ImplementationEstimate(3.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.8),
        )
        if has_auth:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Configure credential and identity provider",
                "Set up authentication for user access", WorkPackageType.SECURITY,
                derived_from("FLOW_NODE:credential-gate"), local=True))
        if has_waf:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Configure WAF rules", "Define web application firewall policies",
                WorkPackageType.SECURITY, derived_from("FLOW_NODE:waf"), local=True))
        if has_firewall:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Configure firewall policies", "Define network-level access rules",
                WorkPackageType.SECURITY, derived_from("FLOW_NODE:firewall"), local=True))
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Validate firewall blocking", "Verify unauthorized traffic is blocked before reaching protected services",
                WorkPackageType.TESTING, derived_from("FLOW_NODE:firewall", "FLOW_SCENARIO:FIREWALL_BLOCK"), local=True))
        if has_auth:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Validate credential validation", "Verify invalid credentials do not reach protected services",
                WorkPackageType.TESTING, derived_from("FLOW_NODE:credential-gate", "FLOW_SCENARIO:AUTH_FAILURE"), local=True))
        packages.append(wp)

    # --- APPLICATION (if app exists) ---
    if has_app or has_api:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("APP"), plan_id=plan.plan_id,
            title="Application Runtime",
            description="Provision and configure the application runtime environment.",
            package_type=WorkPackageType.APPLICATION,
            parallel_group="PG-02",
            estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.7),
        )
        if has_app:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Provision application host", "Configure compute/storage for application",
                WorkPackageType.APPLICATION, derived_from("FLOW_NODE:application-service"), local=True))
        if has_api:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Configure API gateway", "Set up API routing and authentication integration",
                WorkPackageType.APPLICATION, derived_from("FLOW_NODE:api-gateway"), local=True))
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Validate application health", "Verify application responds correctly",
            WorkPackageType.TESTING, derived_from("FLOW_NODE:application-service", "FLOW_SCENARIO:HAPPY_PATH"), local=True))
        if has_app:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Validate timeout handling", "Verify timeout behavior propagates correctly",
                WorkPackageType.TESTING, derived_from("FLOW_NODE:api-gateway", "FLOW_SCENARIO:API_TIMEOUT"), local=True))
        packages.append(wp)

    # --- DATABASE (if DB exists) ---
    if has_db:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("DATA"), plan_id=plan.plan_id,
            title="PostgreSQL Database",
            description="Provision and configure relational database.",
            package_type=WorkPackageType.DATABASE,
            parallel_group="PG-02",
            estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.7),
        )
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Provision database instance", "Create managed PostgreSQL instance",
            WorkPackageType.DATABASE, derived_from("FLOW_NODE:postgresql"), local=False))
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Configure database access", "Set up network access, credentials, encryption",
            WorkPackageType.DATABASE, derived_from("FLOW_NODE:postgresql"), local=False))
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Validate database connectivity", "Verify application can reach database",
            WorkPackageType.TESTING, derived_from("FLOW_NODE:postgresql"), local=False))
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Simulate database degradation", "Verify latency degradation is detected",
            WorkPackageType.TESTING, derived_from("FLOW_NODE:postgresql", "FLOW_SCENARIO:DATABASE_SLOW"), local=True))
        packages.append(wp)

    # --- STORAGE (if object storage exists) ---
    if has_storage and not has_db:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("STORE"), plan_id=plan.plan_id,
            title="Object Storage",
            description="Provision and configure object storage.",
            package_type=WorkPackageType.DATA,
            parallel_group="PG-02",
            estimated_effort=ImplementationEstimate(1.5, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.6),
        )
        storage_nodes = [n for n in flow_nodes.values() if "storage" in n.get("nodeId", "").lower()]
        for sn in storage_nodes[:1]:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                f"Provision {sn.get('label', 'Storage')}", "Create object storage bucket/container",
                WorkPackageType.DATA, derived_from(f"FLOW_NODE:{sn.get('nodeId','')}"), local=False))
        packages.append(wp)

    # --- APPROVAL (if approval gate exists) ---
    if has_approval:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("APPR"), plan_id=plan.plan_id,
            title="Approval Workflow",
            description="Configure approval gate and workflow.",
            package_type=WorkPackageType.APPLICATION,
            estimated_effort=ImplementationEstimate(1.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.6),
        )
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Configure approval gate", "Set up human approval checkpoint",
            WorkPackageType.APPLICATION, derived_from("FLOW_NODE:approval-gate"), local=True))
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Validate approval flow", "Verify approval gate pauses and continues correctly",
            WorkPackageType.TESTING, derived_from("FLOW_NODE:approval-gate", "FLOW_SCENARIO:APPROVAL_WAIT"), local=True))
        packages.append(wp)

    # --- INTEGRATION (if multiple packages need integration) ---
    if len(packages) >= 2:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("INT"), plan_id=plan.plan_id,
            title="Application Integration",
            description="Integrate application, database, and external dependencies.",
            package_type=WorkPackageType.INTEGRATION,
            estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.6),
        )
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Configure application-to-database connectivity",
            "Ensure secure authenticated path between app and data stores",
            WorkPackageType.INTEGRATION,
            derived_from("RULE:integration-required"), local=False))
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Validate end-to-end flow", "Confirm request path through all components",
            WorkPackageType.INTEGRATION,
            derived_from("FLOW_SCENARIO:HAPPY_PATH"), local=False))
        if has_app:
            wp.tasks.append(_task(next_task_id(), wp.package_id,
                "Validate retry recovery", "Verify transient failure recovery succeeds",
                WorkPackageType.TESTING,
                derived_from("FLOW_SCENARIO:RETRY_RECOVERY"), local=True))
        packages.append(wp)

    # --- TESTING (always needed if there are tasks to test) ---
    total_tasks = sum(len(w.tasks) for w in packages)
    if total_tasks >= 3:
        wp = ImplementationWorkPackage(
            package_id=next_pkg_id("TEST"), plan_id=plan.plan_id,
            title="Integration & Flow Testing",
            description="Validate system flows including applicable failure scenarios.",
            package_type=WorkPackageType.TESTING,
            estimated_effort=ImplementationEstimate(2.0, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.5),
        )
        wp.tasks.append(_task(next_task_id(), wp.package_id,
            "Run happy-path validation", "Verify complete request path succeeds",
            WorkPackageType.TESTING, derived_from("FLOW_SCENARIO:HAPPY_PATH"), local=True))
        packages.append(wp)

    # --- DEPLOYMENT (always) ---
    wp = ImplementationWorkPackage(
        package_id=next_pkg_id("DEP"), plan_id=plan.plan_id,
        title="Deployment Readiness",
        description="Prepare for controlled deployment. No real production deploy in this phase.",
        package_type=WorkPackageType.DEPLOYMENT,
        estimated_effort=ImplementationEstimate(1.5, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.5),
    )
    wp.tasks.append(_task(next_task_id(), wp.package_id,
        "Validate deployment configuration", "Review all IaC templates and configuration",
        WorkPackageType.DEPLOYMENT, derived_from("RULE:deployment-required"), local=True))
    wp.tasks.append(_task(next_task_id(), wp.package_id,
        "Create deployment runbook", "Document step-by-step deployment procedure",
        WorkPackageType.DOCUMENTATION, derived_from("RULE:deployment-required"), local=True,
        automation=AutomationEligibility.MANUAL))
    wp.tasks.append(_task(next_task_id(), wp.package_id,
        "Verify rollback plan", "Ensure all changes can be reversed",
        WorkPackageType.DEPLOYMENT, derived_from("RULE:deployment-required"), local=True))
    packages.append(wp)

    plan.work_packages = packages

    # --- Build dependencies between packages ---
    deps: list[ImplementationDependency] = []
    sec_pkg = next((w for w in packages if w.package_type == WorkPackageType.SECURITY), None)
    app_pkg = next((w for w in packages if w.package_type == WorkPackageType.APPLICATION and "Approval" not in w.title), None)
    data_pkg = next((w for w in packages if w.package_type in (WorkPackageType.DATABASE, WorkPackageType.DATA)), None)
    int_pkg = next((w for w in packages if w.package_type == WorkPackageType.INTEGRATION), None)
    test_pkg = next((w for w in packages if w.package_type == WorkPackageType.TESTING), None)
    dep_pkg = next((w for w in packages if w.package_type == WorkPackageType.DEPLOYMENT), None)

    dep_id = 0
    def add_dep(frm: ImplementationWorkPackage | None, to: ImplementationWorkPackage | None, desc: str) -> None:
        nonlocal dep_id
        if frm and to and frm.package_id != to.package_id:
            dep_id += 1
            deps.append(ImplementationDependency(dep_id=f"DEP-{dep_id:03d}", from_package=frm.package_id, to_package=to.package_id, description=desc))

    if sec_pkg:
        if app_pkg: add_dep(sec_pkg, app_pkg, "Security before application")
        if data_pkg: add_dep(sec_pkg, data_pkg, "Security before data")
    if app_pkg and data_pkg and int_pkg:
        add_dep(app_pkg, int_pkg, "App before integration")
        add_dep(data_pkg, int_pkg, "Data before integration")
    if int_pkg and test_pkg:
        add_dep(int_pkg, test_pkg, "Integration before testing")
    if test_pkg and dep_pkg:
        add_dep(test_pkg, dep_pkg, "Testing before deployment")
    if not test_pkg and int_pkg and dep_pkg:
        add_dep(int_pkg, dep_pkg, "Integration before deployment")

    plan.dependencies = deps

    # Critical path: longest chain
    plan.critical_path = compute_critical_path(packages, deps)

    # Milestones
    milestones: list[ImplementationMilestone] = [
        ImplementationMilestone(milestone_id="M1", name="Design Baseline Frozen", description="Design accepted and frozen", completed=True),
    ]
    if sec_pkg:
        milestones.append(ImplementationMilestone(milestone_id="M2", name="Infra Foundation Ready", depends_on=[sec_pkg.package_id]))
    if app_pkg or data_pkg:
        milestones.append(ImplementationMilestone(milestone_id="M3", name="Application Runtime Ready", depends_on=[w.package_id for w in [app_pkg, data_pkg] if w]))
    if int_pkg:
        milestones.append(ImplementationMilestone(milestone_id="M4", name="Integration Ready", depends_on=[int_pkg.package_id]))
    if test_pkg:
        milestones.append(ImplementationMilestone(milestone_id="M5", name="IFT Ready", depends_on=[test_pkg.package_id]))
        milestones.append(ImplementationMilestone(milestone_id="M6", name="UAT Ready", depends_on=[test_pkg.package_id]))
    if dep_pkg:
        milestones.append(ImplementationMilestone(milestone_id="M7", name="Production Readiness", depends_on=[dep_pkg.package_id]))
    plan.milestones = milestones

    # Risks
    plan.risks = []
    if has_db:
        plan.risks.append(ImplementationRisk(risk_id="RISK-001", title="Database provisioning delay",
            description="Managed database creation may be blocked by provider quotas",
            severity=RiskSeverity.MEDIUM, category=RiskCategory.DATA))
    plan.risks.append(ImplementationRisk(risk_id="RISK-002", title="Integration dependency",
        description="Multiple packages must coordinate for integration testing",
        severity=RiskSeverity.MEDIUM, category=RiskCategory.INTEGRATION))

    # Gates
    plan.gates = [
        ImplementationGate(gate_id="GATE-001", name="DESIGN_ACCEPTED", state=GateState.PASS, description="Design is frozen"),
        ImplementationGate(gate_id="GATE-002", name="CREDENTIALS_READY", state=GateState.PENDING, description="Cloud credentials required for real execution"),
        ImplementationGate(gate_id="GATE-003", name="SECURITY_APPROVED", state=GateState.PENDING, description="Security review required before deployment"),
    ]

    # Blockers
    plan.blockers = [
        ImplementationBlocker(blocker_id="BLOCK-001", severity=RiskSeverity.HIGH,
            description="No cloud provider credentials configured",
            resolution_required="Obtain cloud account credentials"),
    ]
    if has_db:
        plan.blockers.append(ImplementationBlocker(blocker_id="BLOCK-002", severity=RiskSeverity.MEDIUM,
            description="Production region not yet selected",
            resolution_required="Select region for production deployment"))

    plan.open_questions = [
        "Which cloud account will host the solution?",
        "What production region is approved?",
    ]
    if has_db:
        plan.open_questions.append("Is database migration required from existing systems?")

    plan.readiness = ReadinessState.PARTIALLY_READY if plan.blockers else ReadinessState.READY_FOR_LOCAL_IMPLEMENTATION
    plan.compute_checksum()
    plan.status = PlanStatus.REVIEW_READY
    return plan


def _task(
    task_id: str, wp_id: str, title: str, description: str,
    category: WorkPackageType,
    derived_from: list[dict] | None = None,
    local: bool = True,
    automation: AutomationEligibility = AutomationEligibility.AUTO,
) -> ImplementationTask:
    return ImplementationTask(
        task_id=task_id, work_package_id=wp_id,
        title=title, description=description,
        category=category, status=TaskStatus.PLANNED,
        priority=5,
        execution_mode="LOCAL_RUNTIME" if local else "PLAN_ONLY",
        acceptance_criteria=[f"{title} completed and verified"],
        risk_level=RiskSeverity.LOW,
        estimated_effort=ImplementationEstimate(0.5, EffortUnit.PERSON_DAYS, EstimateSource.RULE_BASED, 0.7),
        owner_role="Infrastructure Engineer",
        automation=automation,
        derived_from=derived_from or [{"type": "RULE", "id": "planner"}],
        delivery_stage=DeliveryStage.PU,
        local_validatable=local,
    )


def compute_critical_path(
    packages: list[ImplementationWorkPackage],
    dependencies: list[ImplementationDependency],
) -> list[str]:
    """Deterministic critical path via topological sort."""
    incoming: dict[str, list[str]] = {w.package_id: [] for w in packages}
    for d in dependencies:
        if d.to_package not in incoming:
            incoming[d.to_package] = []
        incoming[d.to_package].append(d.from_package)

    result: list[str] = []
    visited: set[str] = set()
    temp: set[str] = set()

    def visit(node: str) -> None:
        if node in temp:
            raise ValueError(f"IMPLEMENTATION_DEPENDENCY_CYCLE: cycle detected at {node}")
        if node not in visited:
            temp.add(node)
            for pred in incoming.get(node, []):
                if pred in [w.package_id for w in packages]:
                    visit(pred)
            temp.discard(node)
            visited.add(node)
            result.append(node)

    start_nodes = set(w.package_id for w in packages)
    for d in dependencies:
        start_nodes.discard(d.from_package)
    if not start_nodes:
        start_nodes = {packages[-1].package_id} if packages else set()

    for node in start_nodes:
        visit(node)
    result.reverse()
    return result


def detect_cycles(
    packages: list[ImplementationWorkPackage],
    dependencies: list[ImplementationDependency],
) -> list[list[str]]:
    try:
        compute_critical_path(packages, dependencies)
        return []
    except ValueError as e:
        if "CYCLE" in str(e):
            return [["cycle-detected"]]
        raise
