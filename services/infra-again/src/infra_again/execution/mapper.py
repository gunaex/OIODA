"""Phase 7 Implementation → Execution Mapper.

Converts ImplementationPlan tasks into executable ExecutionTasks.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..implementation.models import (
    ImplementationPlan, ImplementationTask, WorkPackageType,
    TaskStatus as ImplTaskStatus,
)
from .phase7_models import (
    ExecutionTask, ExecutionTarget, ExecutionFidelity,
    ExecutionPackage, ExecutionPackageStatus, ExecutionReadiness,
    TaskReadiness, ActionType, ExecutionTaskStatus,
)
from .registry import LocalExecutionTargetRegistry

# Implementation task category → execution action mapping
CATEGORY_ACTION_MAP: dict[str, ActionType] = {
    "SECURITY": ActionType.VALIDATE_RESOURCE,
    "APPLICATION": ActionType.DEPLOY_LOCAL_WORKLOAD,
    "DATABASE": ActionType.DEPLOY_LOCAL_WORKLOAD,
    "STORAGE": ActionType.APPLY_LOCAL_IAC,
    "INTEGRATION": ActionType.VALIDATE_RESOURCE,
    "TESTING": ActionType.VALIDATE_RESOURCE,
    "DEPLOYMENT": ActionType.APPLY_LOCAL_IAC,
    "DOCUMENTATION": None,  # MANUAL
}

# WorkPackage type → fidelity mapping
WP_FIDELITY_MAP: dict[str, ExecutionFidelity] = {
    "SECURITY": ExecutionFidelity.LOCAL_RUNTIME,
    "APPLICATION": ExecutionFidelity.LOCAL_RUNTIME,
    "DATABASE": ExecutionFidelity.LOCAL_RUNTIME,
    "STORAGE": ExecutionFidelity.SIMULATED,
    "INTEGRATION": ExecutionFidelity.LOCAL_RUNTIME,
    "TESTING": ExecutionFidelity.LOCAL_RUNTIME,
    "DEPLOYMENT": ExecutionFidelity.PLAN_ONLY,
    "DOCUMENTATION": ExecutionFidelity.PLAN_ONLY,
}


class ImplementationExecutionMapper:
    """Maps ImplementationPlan tasks to executable ExecutionTasks."""

    @staticmethod
    def compute_readiness(plan: ImplementationPlan) -> ExecutionReadiness:
        """Compute execution readiness for all tasks in a plan."""
        readiness = ExecutionReadiness(
            plan_id=plan.plan_id,
            plan_status=plan.status.value,
            total_tasks=sum(len(wp.tasks) for wp in plan.work_packages),
        )

        for wp in plan.work_packages:
            for task in wp.tasks:
                task_info = {
                    "taskId": task.task_id,
                    "workPackageId": wp.package_id,
                    "title": task.title,
                    "category": task.category,
                    "executionMode": task.execution_mode.value if hasattr(task.execution_mode, 'value') else str(task.execution_mode),
                    "automation": task.automation.value if hasattr(task.automation, 'value') else str(task.automation),
                    "localValidatable": task.local_validatable,
                }
                readiness = ImplementationExecutionMapper._classify(readiness, task, task_info)

        return readiness

    @staticmethod
    def _classify(readiness: ExecutionReadiness, task: ImplementationTask, info: dict) -> ExecutionReadiness:
        cat = task.category
        auto = task.automation.value if hasattr(task.automation, 'value') else str(task.automation)
        mode = task.execution_mode.value if hasattr(task.execution_mode, 'value') else str(task.execution_mode)

        # MANUAL tasks
        if auto == "MANUAL" or cat in ("DOCUMENTATION",):
            readiness.manual.append(info)
            return readiness

        # REAL_CLOUD → future
        if mode == "REAL_CLOUD":
            readiness.future_real.append(info)
            return readiness

        # PLAN_ONLY → ready simulated
        if mode == "PLAN_ONLY":
            readiness.ready_simulated.append(info)
            return readiness

        # LOCAL_RUNTIME → ready local
        if mode == "LOCAL_RUNTIME" or mode == "SIMULATED":
            if task.local_validatable:
                readiness.ready_local.append(info)
            else:
                readiness.ready_simulated.append(info)
            return readiness

        # Fallback
        readiness.blocked.append(info)
        return readiness

    @staticmethod
    def map_to_execution_tasks(plan: ImplementationPlan, target: ExecutionTarget) -> list[ExecutionTask]:
        """Convert eligible ImplementationTasks to ExecutionTasks."""
        exec_tasks: list[ExecutionTask] = []
        readiness = ImplementationExecutionMapper.compute_readiness(plan)

        for wp in plan.work_packages:
            for task in wp.tasks:
                action = ImplementationExecutionMapper._determine_action(task)
                if action is None:
                    continue  # Skip manual/documentation tasks

                fid = ImplementationExecutionMapper._determine_fidelity(task, target)

                # Skip tasks incompatible with target fidelity
                if not ImplementationExecutionMapper._is_compatible(action, fid):
                    continue

                exec_task = ExecutionTask(
                    execution_task_id=f"ET-{uuid.uuid4().hex[:8].upper()}",
                    implementation_task_id=task.task_id,
                    work_package_id=wp.package_id,
                    title=task.title,
                    action_type=action,
                    target_capability=task.category,
                    requested_fidelity=fid,
                    effective_fidelity=fid,
                    preconditions=task.inputs or [],
                    expected_outputs=task.outputs or [],
                    validation_criteria=[ac for ac in (task.acceptance_criteria or [])],
                    evidence_requirements=task.evidence_requirements or [],
                    status=ExecutionTaskStatus.PLANNED,
                    derived_from=task.derived_from if hasattr(task, 'derived_from') else [],
                    canonical_service_id=getattr(task, 'canonical_service_id', '') or '',
                    provider=getattr(task, 'provider', '') or '',
                )
                exec_tasks.append(exec_task)

        return exec_tasks

    @staticmethod
    def _determine_action(task: ImplementationTask) -> ActionType | None:
        cat = task.category
        auto = task.automation.value if hasattr(task.automation, 'value') else str(task.automation)
        # BLOCKED (N3 execution_classification=BLOCKED — CONTROLLED_REAL/
        # PRODUCTION targets) must never become an executable task, same as
        # MANUAL. Without this, a policy-blocked task would still leak into
        # the ExecutionPackage the AIRLOCK evaluates.
        if auto in ("MANUAL", "BLOCKED") or cat == "DOCUMENTATION":
            return None

        # Check task description for action hints
        desc = (task.description or "").lower()
        title = (task.title or "").lower()

        if "deploy" in title or "provision" in title:
            return ActionType.DEPLOY_LOCAL_WORKLOAD
        if "configure" in title or "validate" in title:
            return ActionType.VALIDATE_RESOURCE
        if "simulate" in title or "degrad" in title:
            return ActionType.VALIDATE_RESOURCE
        if "destroy" in title or "cleanup" in title:
            return ActionType.DESTROY_RUN_OWNED_RESOURCE

        return CATEGORY_ACTION_MAP.get(cat, ActionType.VALIDATE_RESOURCE)

    @staticmethod
    def _determine_fidelity(task: ImplementationTask, target: ExecutionTarget) -> ExecutionFidelity:
        mode = task.execution_mode.value if hasattr(task.execution_mode, 'value') else str(task.execution_mode)
        if mode in ("LOCAL_RUNTIME",):
            return target.fidelity
        if mode in ("PLAN_ONLY",):
            return ExecutionFidelity.PLAN_ONLY
        if mode in ("SIMULATED",):
            return ExecutionFidelity.SIMULATED
        return target.fidelity

    @staticmethod
    def _is_compatible(action: ActionType, fidelity: ExecutionFidelity) -> bool:
        """Check if an action is compatible with a fidelity."""
        PLAN_ONLY_ACTIONS = {ActionType.GENERATE_IAC, ActionType.VALIDATE_IAC,
                             ActionType.PLAN_IAC, ActionType.OBSERVE_RESOURCE,
                             ActionType.VALIDATE_RESOURCE}
        LOCAL_ACTIONS = {ActionType.DEPLOY_LOCAL_WORKLOAD, ActionType.CREATE_LOCAL_NAMESPACE,
                         ActionType.APPLY_LOCAL_IAC, ActionType.OBSERVE_RESOURCE,
                         ActionType.VALIDATE_RESOURCE, ActionType.DESTROY_RUN_OWNED_RESOURCE}
        if fidelity == ExecutionFidelity.PLAN_ONLY:
            return action in PLAN_ONLY_ACTIONS
        if fidelity in (ExecutionFidelity.SIMULATED, ExecutionFidelity.LOCAL_RUNTIME):
            return action in LOCAL_ACTIONS or action in PLAN_ONLY_ACTIONS
        return True
