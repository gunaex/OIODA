"""
Execution Orchestrator for INFRA-AGAIN — Phase 2A.1 HARDENED.

Full pipeline with SQLite persistence, ownership tracking,
explicit state machine, evidence persistence, and restart/resume.

Fixes from 2A.1:
- Idempotency: EXECUTING/OBSERVING/VALIDATING do NOT return SUCCESS
- Persisted final InfrastructureResult for exact idempotent retrieval
- Destroy bypass removed: only explicit ownership allows AUTO destroy
- Missing/unknown ownership → ASK (never AUTO)
- Restart from EXECUTING → REQUIRES_RECONCILIATION
- Validation failure → FAILED run state (not partial success)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..contracts import (
    EvidenceItem,
    EvidenceType,
    InfrastructureRequest,
    InfrastructureResult,
    InfrastructureStatus,
)
from ..core.domain import (
    ChangeAction,
    ChangeSet,
    Evidence,
    ExecutionMode,
    ExecutionState,
    ExecutionTarget,
    ExecutionTargetType,
    InfrastructurePlan,
    OwnedResource,
    Platform,
    Provider,
    ResourceOwnership,
    TargetScope,
    ValidationResult,
    can_transition,
    VALID_TRANSITIONS,
)
from ..core.persistence import RunStore
from ..providers.interface import ProviderAdapter
from ..platforms.interface import PlatformAdapter
from ..iac.engine import IaCEngine, IaCStage, sha256_file, short_checksum
from ..iac.opentofu import OpenTofuEngine, extract_plan_info
from ..iac.renderer import render_tofu_config
from ..visualization.graph import ArchitectureGraph, GraphType
from ..visualization.renderer import (
    build_proposed_graph, build_planned_graph, build_observed_graph,
    build_diff, render_mermaid_before_after,
)


class ActionPolicy(str, Enum):
    AUTO = "AUTO"
    ASK = "ASK"
    BLOCK = "BLOCK"


class IdempotencyStatus:
    """Truthful idempotent response status — never fakes SUCCESS."""

    ACTIVE_STATES = {
        ExecutionState.EXECUTING.value,
        ExecutionState.OBSERVING.value,
        ExecutionState.VALIDATING.value,
        ExecutionState.REQUIRES_RECONCILIATION.value,
    }
    TERMINAL_GOOD = {ExecutionState.COMPLETED.value}
    TERMINAL_BAD = {
        ExecutionState.FAILED.value,
        ExecutionState.BLOCKED.value,
        ExecutionState.CANCELLED.value,
    }

    @staticmethod
    def classify(state: str) -> str:
        if state in IdempotencyStatus.TERMINAL_GOOD:
            return "COMPLETED"
        if state in IdempotencyStatus.TERMINAL_BAD:
            return "TERMINAL_NON_SUCCESS"
        if state in IdempotencyStatus.ACTIVE_STATES:
            return "IN_PROGRESS"
        return "OTHER"


@dataclass
class PolicyDecision:
    action: str
    policy: ActionPolicy
    reason: str
    requires_approval: bool
    approval_id: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PolicyEngine:
    """AIRLOCK policy engine — ownership-aware, no shortcuts."""

    @staticmethod
    def evaluate(
        action: str,
        target: ExecutionTarget,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        ctx = context or {}

        if target.mode == ExecutionMode.PRODUCTION:
            if action in ("apply", "destroy", "modify"):
                return PolicyDecision(
                    action=action, policy=ActionPolicy.BLOCK,
                    reason="Production mutation requires explicit approval gate",
                    requires_approval=True)

        if ctx.get("fallback_provider"):
            return PolicyDecision(action=action, policy=ActionPolicy.BLOCK,
                                  reason="Hidden provider fallback is blocked", requires_approval=True)

        if action == "unrestricted_admin":
            return PolicyDecision(action=action, policy=ActionPolicy.BLOCK,
                                  reason="Unrestricted cloud admin is blocked", requires_approval=True)

        if action == "destroy":
            return PolicyEngine._evaluate_destroy(target, ctx)

        if action == "apply":
            if target.mode in (ExecutionMode.SANDBOX, ExecutionMode.CONTROLLED_REAL):
                return PolicyDecision(action=action, policy=ActionPolicy.ASK,
                                      reason=f"Apply to {target.mode.value} requires approval",
                                      requires_approval=True)

        if action in ("read", "plan", "inspect", "plan_only", "validate_schema", "discover"):
            return PolicyDecision(action=action, policy=ActionPolicy.AUTO,
                                  reason=f"'{action}' is safe — AUTO", requires_approval=False)

        if action == "apply" and target.mode == ExecutionMode.SIMULATED and target.is_safe:
            return PolicyDecision(action=action, policy=ActionPolicy.AUTO,
                                  reason="SIMULATED apply on safe target — AUTO",
                                  requires_approval=False)

        if action == "local_lab_execute" and target.is_safe:
            return PolicyDecision(action=action, policy=ActionPolicy.AUTO,
                                  reason="Local lab execution AUTO within safe targets",
                                  requires_approval=False)

        return PolicyDecision(action=action, policy=ActionPolicy.ASK,
                              reason=f"Action '{action}' requires approval by default",
                              requires_approval=True)

    @staticmethod
    def _evaluate_destroy(target: ExecutionTarget, ctx: dict[str, Any]) -> PolicyDecision:
        """Ownership-only destroy evaluation — no bypass shortcuts."""
        resource_id = ctx.get("resource_id", "unknown")
        ownership = ctx.get("ownership")
        current_run_id = ctx.get("current_run_id", "")

        # Production: always BLOCK
        if target.mode == ExecutionMode.PRODUCTION:
            return PolicyDecision(action="destroy", policy=ActionPolicy.BLOCK,
                                  reason="Production destroy requires explicit approval",
                                  requires_approval=True)

        # Ownership present: strict rule
        if ownership is not None:
            if ownership.is_auto_destroy_allowed(current_run_id):
                return PolicyDecision(action="destroy", policy=ActionPolicy.AUTO,
                                      reason=f"AUTO destroy: owned ephemeral ISOLATED {resource_id}",
                                      requires_approval=False)
            reasons = []
            if ownership.managed_by != "INFRA_AGAIN":
                reasons.append(f"managed_by={ownership.managed_by}")
            if ownership.created_by_run_id != current_run_id:
                reasons.append("not owned by current run")
            if not ownership.ephemeral:
                reasons.append("not ephemeral")
            if ownership.target_scope != TargetScope.ISOLATED:
                reasons.append(f"scope={ownership.target_scope.value}")
            return PolicyDecision(action="destroy", policy=ActionPolicy.ASK,
                                  reason=f"Destroy requires approval: {'; '.join(reasons)}",
                                  requires_approval=True)

        # No ownership → ASK (never AUTO, regardless of target mode)
        return PolicyDecision(action="destroy", policy=ActionPolicy.ASK,
                              reason="Destroy requires ownership verification — ownership unknown",
                              requires_approval=True)


EVIDENCE_DIR = ".ai/infra-runs"


@dataclass
class OrchestrationContext:
    run_id: str = field(default_factory=lambda: f"run-{uuid4().hex[:8]}")
    request: InfrastructureRequest | None = None
    state: ExecutionState = ExecutionState.DRAFT
    plan: InfrastructurePlan | None = None
    target: ExecutionTarget | None = None
    change_set: ChangeSet | None = None
    evidence: Evidence = field(default_factory=Evidence)
    policy_decisions: list[PolicyDecision] = field(default_factory=list)
    owned_resources: list[OwnedResource] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionOrchestrator:
    """Orchestrator with SQLite persistence, ownership, state machine, IaC engine."""

    def __init__(
        self,
        provider_adapter: ProviderAdapter | None = None,
        platform_adapter: PlatformAdapter | None = None,
        store: RunStore | None = None,
        iac_engine: IaCEngine | None = None,
    ):
        self.provider_adapter = provider_adapter
        self.platform_adapter = platform_adapter
        self.policy_engine = PolicyEngine()
        self.store = store or RunStore()
        self.iac_engine = iac_engine
        self._ctx: OrchestrationContext | None = None

    # ------------------------------------------------------------------
    # Main Pipeline
    # ------------------------------------------------------------------

    async def process(
        self,
        request: InfrastructureRequest,
        target: ExecutionTarget | None = None,
        idempotency_key: str | None = None,
    ) -> InfrastructureResult:
        # Idempotency: check for existing run
        if idempotency_key:
            existing = self.store.get_run_by_idempotency(idempotency_key)
            if existing:
                return self._handle_idempotent(existing)

        ctx = OrchestrationContext(request=request, target=target)
        ctx.started_at = datetime.now(timezone.utc)
        self._ctx = ctx

        self.store.create_run(
            run_id=ctx.run_id, correlation_id=request.correlationId,
            work_package_id=request.workPackageId,
            infrastructure_request_id=request.infrastructureRequestId,
            idempotency_key=idempotency_key)

        # Persist full canonical request for restart reconstruction
        self.store.persist_request(ctx.run_id, request.model_dump_json())
        self._persist_file(ctx, "request.json", request.model_dump(mode="json"))

        try:
            await self._transition(ctx, ExecutionState.NORMALIZING)
            normalized = self._normalize_intent(request)
            self._persist_file(ctx, "normalized-intent.json", normalized)

            if target is None:
                target = self._resolve_target(request)
                ctx.target = target
            self._persist_target(ctx, target)

            decision = self.policy_engine.evaluate("plan", target)
            ctx.policy_decisions.append(decision)
            if decision.policy == ActionPolicy.BLOCK:
                await self._transition(ctx, ExecutionState.BLOCKED, decision.reason)
                return self._finalize(ctx, InfrastructureStatus.FAILED,
                    extra_evidence=[EvidenceItem(type=EvidenceType.PLAN_APPROVAL,
                        source="infrastructure-again", reference="airlock",
                        summary=f"BLOCKED: {decision.reason}",
                        timestamp=datetime.now(timezone.utc))])

            await self._transition(ctx, ExecutionState.PLANNING)
            # Phase 4.1: Query Provider Intelligence before planning
            provider_intel = self._query_provider_intelligence(normalized, target)
            self._persist_file(ctx, "provider-intel.json", provider_intel)

            if self.provider_adapter:
                capabilities = self._to_capability_requirements(normalized)
                ctx.plan = await self.provider_adapter.plan(capabilities, target)
            else:
                ctx.plan = self._generate_plan_only(request, target)
            ctx.plan.correlation_id = request.correlationId
            ctx.plan.request_id = request.infrastructureRequestId
            self._persist_plan(ctx)

            # Phase 2B: Generate proposed + planned architecture graphs
            proposed_graph = build_proposed_graph(ctx.plan)
            planned_graph = build_planned_graph(ctx.plan, target.mode)
            self._persist_file(ctx, "architecture-proposed.json", proposed_graph.to_dict())
            self._persist_file(ctx, "architecture-planned.json", planned_graph.to_dict())

            await self._transition(ctx, ExecutionState.PLAN_READY)

            if self.provider_adapter:
                warnings = await self.provider_adapter.validate_plan(ctx.plan)
                if warnings:
                    ctx.errors.extend(warnings)

            if target.mode == ExecutionMode.PLAN_ONLY:
                await self._transition(ctx, ExecutionState.COMPLETED, "PLAN_ONLY — no mutation")
                ctx.evidence.plan = ctx.plan
                ctx.evidence.limitations.append("PLAN_ONLY mode — no infrastructure mutation")
                return self._finalize(ctx, InfrastructureStatus.SUCCESS)

            await self._transition(ctx, ExecutionState.WAITING_FOR_APPROVAL)
            exec_decision = self.policy_engine.evaluate("apply", target)
            ctx.policy_decisions.append(exec_decision)
            self._persist_file(ctx, "policy.json", {
                "action": "apply", "policy": exec_decision.policy.value,
                "reason": exec_decision.reason})

            if exec_decision.policy in (ActionPolicy.BLOCK, ActionPolicy.ASK):
                await self._transition(ctx, ExecutionState.BLOCKED, exec_decision.reason)
                return self._finalize(ctx, InfrastructureStatus.PARTIAL,
                    extra_evidence=[EvidenceItem(type=EvidenceType.PLAN_APPROVAL,
                        source="infrastructure-again", reference="policy-gate",
                        summary=f"Requires approval: {exec_decision.reason}",
                        timestamp=datetime.now(timezone.utc))])

            await self._transition(ctx, ExecutionState.EXECUTING)

            # Phase 2B: OpenTofu IaC pipeline
            if self.iac_engine and target.mode == ExecutionMode.SIMULATED:
                await self._run_iac_pipeline(ctx, target)
            elif self.provider_adapter:
                ctx.change_set = await self.provider_adapter.apply(ctx.plan, target)
                for change in (ctx.change_set.changes if ctx.change_set else []):
                    if change.action == ChangeAction.CREATE:
                        resource = OwnedResource(
                            resource_id=change.resource_id, resource_type=change.resource_type,
                            provider=target.provider.value,
                            ownership=ResourceOwnership(
                                managed_by="INFRA_AGAIN", created_by_run_id=ctx.run_id,
                                ephemeral=True, target_scope=TargetScope.ISOLATED))
                        ctx.owned_resources.append(resource)
                        self.store.register_resource(resource)
            self._persist_file(ctx, "execution.json", {
                "target": target.mode.value,
                "change_summary": ctx.change_set.summary if ctx.change_set else "N/A",
                "iac_stage": self.store.get_run(ctx.run_id).get("iac_stage", "") if self.store.get_run(ctx.run_id) else "",
            })

            await self._transition(ctx, ExecutionState.OBSERVING)
            if self.provider_adapter:
                observed = await self.provider_adapter.observe(target)
                ctx.evidence.observed_resources.append(observed)
                self._persist_file(ctx, "observed-state.json", observed)
                for resource in ctx.owned_resources:
                    r_obs = observed.get(resource.resource_id)
                    if r_obs:
                        self.store.update_resource_observed(resource.resource_id, {resource.resource_id: r_obs})
                        self.store.update_resource_state(resource.resource_id, r_obs)

            await self._transition(ctx, ExecutionState.VALIDATING)
            validation_failed = False
            if self.provider_adapter and ctx.plan:
                desired = self._plan_to_desired_state(ctx.plan)
                obs = ctx.evidence.observed_resources[-1] if ctx.evidence.observed_resources else {}
                validations = await self.provider_adapter.validate(desired, obs)
                ctx.evidence.validation_results = validations
                self._persist_file(ctx, "validation.json", {
                    "results": [{"resource_id": v.resource_id, "matches": v.matches,
                                 "drift_detected": v.drift_detected} for v in validations]})
                all_match = all(v.matches for v in validations if v.matches is not None)
                if not all_match:
                    validation_failed = True
                    ctx.errors.append("VALIDATION FAIL: desired != observed")

            # Phase 2B: Generate observed graph, diff, and Mermaid visualization
            if ctx.plan:
                obs_state = ctx.evidence.observed_resources[-1] if ctx.evidence.observed_resources else {}
                obs_graph = build_observed_graph(
                    obs_state, ctx.plan, ctx.evidence.validation_results,
                    target.mode, target.endpoint or "")
                planned_for_diff = build_planned_graph(ctx.plan, target.mode)
                diff_result = build_diff(planned_for_diff, obs_graph)
                self._persist_file(ctx, "architecture-observed.json", obs_graph.to_dict())
                self._persist_file(ctx, "architecture-diff.json", diff_result.to_dict())

                mermaid = render_mermaid_before_after(
                    planned_for_diff, obs_graph, diff_result,
                    run_id=ctx.run_id,
                    correlation_id=ctx.request.correlationId if ctx.request else "")
                # Persist Mermaid as evidence text file
                evidence_path = Path(EVIDENCE_DIR) / ctx.run_id
                evidence_path.mkdir(parents=True, exist_ok=True)
                (evidence_path / "architecture-before-after.md").write_text(mermaid)
                self.store.add_evidence(run_id=ctx.run_id, evidence_type="FILE",
                    source="infrastructure-again",
                    reference=str(evidence_path / "architecture-before-after.md"),
                    summary="Before/After architecture visualization",
                    data={"format": "mermaid"})

            # Validation failure → FAILED state, not SUCCESS
            if validation_failed or ctx.errors:
                await self._transition(ctx, ExecutionState.FAILED,
                    "; ".join(ctx.errors) if ctx.errors else "Validation failed")
                return self._finalize(ctx, InfrastructureStatus.FAILED)

            await self._transition(ctx, ExecutionState.COMPLETED)
            status = InfrastructureStatus.SUCCESS

        except Exception as e:
            try:
                await self._transition(ctx, ExecutionState.FAILED, str(e))
            except RuntimeError:
                pass
            ctx.errors.append(str(e))
            status = InfrastructureStatus.FAILED

        return self._finalize(ctx, status)

    # ------------------------------------------------------------------
    # Idempotency handling
    # ------------------------------------------------------------------

    def _handle_idempotent(self, existing: dict[str, Any]) -> InfrastructureResult:
        """Handle duplicate idempotency key truthfully."""
        state = existing["state"]
        run_id = existing["run_id"]
        classification = IdempotencyStatus.classify(state)

        if classification == "COMPLETED":
            # Return the EXACT persisted result
            persisted = self.store.get_final_result(run_id)
            if persisted:
                try:
                    return InfrastructureResult.model_validate_json(persisted)
                except Exception:
                    pass
            # Fallback: reconstruct from context
            ctx = self._load_context(run_id)
            if ctx:
                self._ctx = ctx
                return self._build_result(ctx, InfrastructureStatus.SUCCESS)

        if classification == "TERMINAL_NON_SUCCESS":
            persisted = self.store.get_final_result(run_id)
            if persisted:
                try:
                    return InfrastructureResult.model_validate_json(persisted)
                except Exception:
                    pass
            ctx = self._load_context(run_id)
            if ctx:
                self._ctx = ctx
                return self._build_result(ctx, InfrastructureStatus.FAILED)

        # IN_PROGRESS (EXECUTING, OBSERVING, VALIDATING, REQUIRES_RECONCILIATION)
        # Do NOT return SUCCESS — return truthful status
        ctx = self._load_context(run_id)
        if ctx:
            self._ctx = ctx
            if state == ExecutionState.REQUIRES_RECONCILIATION.value:
                return self._build_result(ctx, InfrastructureStatus.FAILED, extra_evidence=[
                    EvidenceItem(type=EvidenceType.PLAN_APPROVAL, source="infrastructure-again",
                                 reference=f"run-{run_id}",
                                 summary=f"Run requires reconciliation — state={state}",
                                 timestamp=datetime.now(timezone.utc))])
            return self._build_result(ctx, InfrastructureStatus.PARTIAL, extra_evidence=[
                EvidenceItem(type=EvidenceType.PLAN_APPROVAL, source="infrastructure-again",
                             reference=f"run-{run_id}",
                             summary=f"Run in progress — state={state}",
                             timestamp=datetime.now(timezone.utc))])

        # OTHER / fallback
        return InfrastructureResult(
            correlationId=existing.get("correlation_id", ""),
            workPackageId=existing.get("work_package_id", ""),
            infrastructureRequestId=existing.get("infrastructure_request_id", ""),
            status=InfrastructureStatus.PARTIAL,
            provider=existing.get("provider", Provider.AWS.value),
            platform=existing.get("platform", Platform.NATIVE_VM.value),
            evidence=[EvidenceItem(type=EvidenceType.PLAN_APPROVAL,
                source="infrastructure-again", reference=f"run-{run_id}",
                summary=f"Idempotent — state={state}",
                timestamp=datetime.now(timezone.utc))],
            completedAt=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Restart / Resume
    # ------------------------------------------------------------------

    def load_run(self, run_id: str) -> OrchestrationContext | None:
        ctx = self._load_context(run_id)
        if ctx:
            run = self.store.get_run(run_id) or {}
            iac_stage = run.get("iac_stage", "")
            # Safety: restart during IaC apply → reconciliation
            if ctx.state == ExecutionState.EXECUTING:
                self.store.transition_state(
                    run_id, ExecutionState.REQUIRES_RECONCILIATION,
                    "Restarted while EXECUTING — manual reconciliation required")
                ctx.state = ExecutionState.REQUIRES_RECONCILIATION
            elif iac_stage == IaCStage.IAC_APPLYING.value:
                self.store.transition_state(
                    run_id, ExecutionState.REQUIRES_RECONCILIATION,
                    "Restarted during IAC_APPLYING — manual reconciliation required")
                ctx.state = ExecutionState.REQUIRES_RECONCILIATION
            # Safety: if request cannot be reconstructed, require reconciliation
            if ctx.request is None and ctx.state not in (
                ExecutionState.COMPLETED, ExecutionState.FAILED,
                ExecutionState.CANCELLED, ExecutionState.BLOCKED,
            ):
                self.store.transition_state(
                    run_id, ExecutionState.REQUIRES_RECONCILIATION,
                    "Cannot reconstruct InfrastructureRequest — reconciliation required")
                ctx.state = ExecutionState.REQUIRES_RECONCILIATION
        return ctx

    def _load_context(self, run_id: str) -> OrchestrationContext | None:
        run = self.store.get_run(run_id)
        if run is None:
            return None
        ctx = OrchestrationContext(run_id=run_id)
        ctx.state = ExecutionState(run["state"])

        # Reconstruct canonical request
        request_json = self.store.get_request(run_id)
        if request_json:
            try:
                ctx.request = InfrastructureRequest.model_validate_json(request_json)
            except Exception:
                # Cannot reconstruct request → truthfully mark for reconciliation
                pass

        # Reconstruct target
        if run.get("execution_target_type"):
            ctx.target = ExecutionTarget(
                mode=ExecutionMode(run["execution_mode"]) if run.get("execution_mode") else ExecutionMode.PLAN_ONLY,
                provider=Provider(run["provider"]) if run.get("provider") else Provider.AWS,
                platform=Platform(run["platform"]) if run.get("platform") else Platform.NATIVE_VM,
                target_type=ExecutionTargetType(run["execution_target_type"]),
                endpoint=run.get("execution_target_endpoint"))

        # Reconstruct plan
        if run.get("plan"):
            try:
                plan_data = json.loads(run["plan"])
                ctx.plan = InfrastructurePlan(
                    plan_id=plan_data.get("plan_id", ""),
                    correlation_id=run.get("correlation_id", ""),
                    request_id=run.get("infrastructure_request_id", ""),
                    provider=Provider(run["provider"]) if run.get("provider") else None,
                    platform=Platform(run["platform"]) if run.get("platform") else None,
                    execution_target=ctx.target,
                    risk_assessment=plan_data.get("risk_assessment", ""))
            except Exception:
                pass

        # Reconstruct owned resources
        for r in self.store.get_resources_for_run(run_id):
            ctx.owned_resources.append(OwnedResource(
                resource_id=r["resource_id"], resource_type=r["resource_type"],
                provider=r["provider"],
                ownership=ResourceOwnership(
                    managed_by=r["managed_by"], created_by_run_id=r["created_by_run_id"],
                    ephemeral=bool(r["ephemeral"]),
                    target_scope=TargetScope(r["target_scope"]))))

        # Reconstruct policy decisions from evidence
        for ev in self.store.get_evidence(run_id):
            if ev.get("summary") and "policy" in ev.get("summary", "").lower():
                ctx.policy_decisions.append(PolicyDecision(
                    action="recorded", policy=ActionPolicy.ASK,
                    reason=ev.get("summary", ""), requires_approval=True))

        return ctx

    # ------------------------------------------------------------------
    # Destroy (ownership-aware)
    # ------------------------------------------------------------------

    async def destroy_resource(
        self, run_id: str, resource_id: str, target: ExecutionTarget,
    ) -> tuple[bool, str]:
        """Destroy a resource — ownership-gated."""
        ownership = ResourceOwnership()
        resource = self.store.get_resource(resource_id)
        if resource:
            ownership = ResourceOwnership(
                managed_by=resource["managed_by"], created_by_run_id=resource["created_by_run_id"],
                ephemeral=bool(resource["ephemeral"]),
                target_scope=TargetScope(resource["target_scope"]))

        decision = self.policy_engine.evaluate("destroy", target, context={
            "resource_id": resource_id, "ownership": ownership if resource else None,
            "current_run_id": run_id})

        if decision.policy == ActionPolicy.BLOCK:
            return False, f"BLOCKED: {decision.reason}"
        if decision.policy == ActionPolicy.ASK:
            return False, f"ASK: {decision.reason}"

        # AUTO only
        if self.provider_adapter:
            cs = await self.provider_adapter.destroy(target, [resource_id])
            self.store.log_apply(run_id=run_id, resource_id=resource_id,
                                 operation="DESTROY", endpoint=target.endpoint or "unknown",
                                 response_data={"change_summary": cs.summary})
            return True, f"Destroyed {resource_id}: {cs.summary}"
        return False, "No provider adapter"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def _transition(self, ctx: OrchestrationContext, to: ExecutionState, reason: str = ""):
        if not can_transition(ctx.state, to):
            raise RuntimeError(
                f"Illegal transition: {ctx.state.value} → {to.value}. "
                f"Valid: {[s.value for s in VALID_TRANSITIONS.get(ctx.state, set())]}")
        ctx.state = to
        self.store.transition_state(ctx.run_id, to, reason)

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------

    def _finalize(
        self, ctx: OrchestrationContext, status: InfrastructureStatus,
        extra_evidence: list[EvidenceItem] | None = None,
    ) -> InfrastructureResult:
        ctx.completed_at = datetime.now(timezone.utc)
        result = self._build_result(ctx, status, extra_evidence)

        # Persist the exact result for idempotent retrieval
        result_json = result.model_dump_json()
        self.store.persist_final_result(ctx.run_id, result_json)
        self._persist_file(ctx, "final-result.json", json.loads(result_json))

        return result

    # ------------------------------------------------------------------
    # IaC Pipeline (Phase 2B)
    # ------------------------------------------------------------------

    async def _run_iac_pipeline(self, ctx: OrchestrationContext, target: ExecutionTarget) -> None:
        """Run the full OpenTofu pipeline: render → fmt → init → validate → plan → apply."""
        if not self.iac_engine or not ctx.plan:
            return

        run = self.store.get_run(ctx.run_id) or {}
        engine = self.iac_engine
        iac_dir = Path(EVIDENCE_DIR) / ctx.run_id / "iac"
        iac_dir.mkdir(parents=True, exist_ok=True)

        # Record engine info
        version = await engine.probe()
        self.store.update_run(ctx.run_id, iac_engine=engine.engine_name, iac_version=version or "",
                              iac_working_dir=str(iac_dir))

        # 1. Render HCL
        endpoint = target.endpoint or "http://localhost:4566"
        checksum = render_tofu_config(ctx.plan, iac_dir, run_id=ctx.run_id,
                                       correlation_id=ctx.request.correlationId if ctx.request else "",
                                       endpoint=endpoint)
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.IAC_RENDERED.value, iac_checksum=checksum)
        # Persist generated file contents (not Path objects)
        for tf_file in iac_dir.glob("*.tf"):
            self._persist_file(ctx, f"iac/{tf_file.name}", {"content": tf_file.read_text()})

        # 2. tofu fmt (auto-format)
        fmt_result = await engine.fmt(iac_dir)
        self._persist_file(ctx, "tofu-fmt.json", {"exit_code": fmt_result.exit_code, "stderr": fmt_result.stderr})

        # 3. tofu init
        init_result = await engine.init(iac_dir)
        if not init_result.success:
            ctx.errors.append(f"tofu init failed: {init_result.stderr}")
            await self._transition(ctx, ExecutionState.FAILED, "tofu init failed")
            return
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.IAC_INITIALIZED.value)
        self._persist_file(ctx, "tofu-init.json", {"exit_code": init_result.exit_code, "stdout": init_result.stdout[:500]})

        # 4. tofu validate
        val_result = await engine.validate(iac_dir)
        if not val_result.success:
            ctx.errors.append(f"tofu validate failed: {val_result.stderr}")
            await self._transition(ctx, ExecutionState.FAILED, "tofu validate failed")
            return
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.IAC_VALIDATED.value)
        self._persist_file(ctx, "tofu-validate.json", {"exit_code": val_result.exit_code})

        # 5. tofu plan
        plan_path = iac_dir / "tfplan"
        plan_result = await engine.plan(iac_dir, plan_path)
        if not plan_result.success:
            ctx.errors.append(f"tofu plan failed: {plan_result.stderr}")
            await self._transition(ctx, ExecutionState.FAILED, "tofu plan failed")
            return

        # 5a. Compute full SHA-256 of the plan artifact
        if plan_path.exists():
            plan_sha256 = sha256_file(plan_path)
        else:
            ctx.errors.append("Plan artifact not found after tofu plan")
            await self._transition(ctx, ExecutionState.FAILED, "plan artifact missing")
            return

        # 5b. Extract plan info
        plan_json = await engine.show(plan_path)
        plan_info = extract_plan_info(plan_json)
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.IAC_PLANNED.value,
                              iac_plan_checksum=plan_info.plan_checksum,
                              iac_plan_sha256=plan_sha256,
                              iac_plan_artifact_path=str(plan_path))
        self._persist_file(ctx, "tofu-plan.json", plan_json or {})
        self._persist_file(ctx, "tofu-plan.txt", {"stdout": plan_result.stdout[:2000]})

        # 6. Policy gate before apply — persist approved checksum
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.WAITING_FOR_APPROVAL.value)
        plan_decision = self.policy_engine.evaluate("apply", target)
        if plan_decision.policy in (ActionPolicy.BLOCK, ActionPolicy.ASK):
            await self._transition(ctx, ExecutionState.BLOCKED, plan_decision.reason)
            return
        # Record approved plan checksum
        self.store.update_run(ctx.run_id, iac_approved_plan_sha256=plan_sha256)
        self._persist_file(ctx, "plan-integrity.json", {
            "plan_sha256": plan_sha256,
            "approved_plan_sha256": plan_sha256,
            "plan_artifact_path": str(plan_path),
            "configuration_checksum": checksum,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        })

        # 7. tofu apply — with plan path containment and checksum verification
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.IAC_APPLYING.value)

        # 7a. Verify plan path belongs to this run
        expected_prefix = str(iac_dir.resolve())
        actual_path = str(plan_path.resolve())
        if not actual_path.startswith(expected_prefix):
            ctx.errors.append(f"Plan path not in run workspace: {actual_path}")
            await self._transition(ctx, ExecutionState.FAILED, "plan path outside run workspace")
            return

        # 7b. Verify approved checksum matches current plan file
        current_plan_sha256 = sha256_file(plan_path)
        approved = self.store.get_run(ctx.run_id).get("iac_approved_plan_sha256", "")
        if approved and current_plan_sha256 != approved:
            ctx.errors.append(
                f"PLAN CHECKSUM MISMATCH: approved={short_checksum(approved)} "
                f"current={short_checksum(current_plan_sha256)}")
            await self._transition(ctx, ExecutionState.BLOCKED, "plan checksum mismatch")
            return
        self.store.update_run(ctx.run_id, iac_applied_plan_sha256=current_plan_sha256)

        # 7c. Apply the saved plan only
        apply_result = await engine.apply(iac_dir, plan_path)
        if not apply_result.success:
            ctx.errors.append(f"tofu apply failed (exit={apply_result.exit_code}): {apply_result.stderr[:500]}")
            await self._transition(ctx, ExecutionState.FAILED, "tofu apply failed")
            return
        self.store.update_run(ctx.run_id, iac_stage=IaCStage.IAC_APPLIED.value)
        self._persist_file(ctx, "tofu-apply.json", {"exit_code": apply_result.exit_code, "stdout": apply_result.stdout[:500]})

        # 8. Persist state reference
        state_ref = engine.state_reference(iac_dir)
        self.store.update_run(ctx.run_id, iac_state_reference=state_ref)

        # 9. Register owned resources from plan
        for change in plan_info.resource_changes:
            if "create" in change.get("change", {}).get("actions", []):
                addr = change.get("address", "unknown")
                rtype = change.get("type", "unknown")
                resource = OwnedResource(
                    resource_id=addr, resource_type=rtype, provider=target.provider.value,
                    ownership=ResourceOwnership(
                        managed_by="INFRA_AGAIN", created_by_run_id=ctx.run_id,
                        ephemeral=True, target_scope=TargetScope.ISOLATED))
                ctx.owned_resources.append(resource)
                self.store.register_resource(resource)

        # 10. Build change set from plan
        from ..core.domain import ChangeAction, ChangeItem
        changes = []
        for c in plan_info.resource_changes:
            actions = c.get("change", {}).get("actions", [])
            if "create" in actions:
                changes.append(ChangeItem(action=ChangeAction.CREATE,
                    resource_type=c.get("type", ""), resource_id=c.get("address", "")))
            elif "delete" in actions:
                changes.append(ChangeItem(action=ChangeAction.DELETE,
                    resource_type=c.get("type", ""), resource_id=c.get("address", ""), is_destructive=True))
        ctx.change_set = ChangeSet(changes=changes, provider=target.provider, platform=target.platform, iac_tool="OPENTOFU")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_target(self, ctx: OrchestrationContext, target: ExecutionTarget):
        self.store.update_run(ctx.run_id,
                              provider=target.provider.value, platform=target.platform.value,
                              execution_mode=target.mode.value,
                              execution_target_type=target.target_type.value if target.target_type else None,
                              execution_target_endpoint=target.endpoint)

    def _persist_plan(self, ctx: OrchestrationContext):
        if ctx.plan:
            data = {"plan_id": ctx.plan.plan_id,
                    "provider": ctx.plan.provider.value if ctx.plan.provider else None,
                    "platform": ctx.plan.platform.value if ctx.plan.platform else None,
                    "risk_assessment": ctx.plan.risk_assessment}
            self.store.update_run(ctx.run_id, plan=json.dumps(data))
            self._persist_file(ctx, "plan.json", data)

    def _persist_file(self, ctx: OrchestrationContext, filename: str, data: Any):
        evidence_path = Path(EVIDENCE_DIR) / ctx.run_id
        evidence_path.mkdir(parents=True, exist_ok=True)
        with open(evidence_path / filename, "w") as f:
            json.dump(data, f, default=str, indent=2)
        self.store.add_evidence(run_id=ctx.run_id, evidence_type="FILE",
                                source="infrastructure-again",
                                reference=str(evidence_path / filename),
                                summary=filename, data={"filename": filename})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Provider Intelligence integration (Phase 4.1)
    # ------------------------------------------------------------------

    def _query_provider_intelligence(
        self, normalized: dict[str, Any], target: ExecutionTarget
    ) -> dict[str, Any]:
        """Query the Provider Intelligence catalog for capability→provider mapping."""
        from ..intelligence.catalog import get_catalog, evaluate_freshness, FreshnessStatus

        catalog = get_catalog()
        capability = normalized.get("capability", "").upper() or "OBJECT_STORAGE"
        provider_hint = (target.provider.value if target.provider.value else ""
                         ) or normalized.get("provider_hint", "")

        mappings = catalog.get_mappings(capability=capability, provider=provider_hint)
        if not mappings:
            mappings = catalog.get_mappings(capability=capability)

        candidates = []
        warnings: list[str] = []
        for m in mappings:
            svc = catalog.get_service(m.provider, m.service_id)
            is_executable = any(
                s not in ("NONE", "PLAN_ONLY", "NOT_TESTED", "NOT_IMPLEMENTED")
                for s in m.execution_support
            )
            # Check deprecated status from actual service
            deprecated = svc.deprecated if svc else False
            candidate = {
                "provider": m.provider,
                "serviceId": m.service_id,
                "resourceType": m.resource_type,
                "confidence": m.confidence,
                "selectionReason": m.selection_reason,
                "lifecycle": m.lifecycle.value,
                "executionSupport": m.execution_support,
                "isExecutable": is_executable and not deprecated,
                "deprecated": deprecated,
                "mappedCapability": capability,
            }
            candidates.append(candidate)

        # Evaluate catalog freshness
        snap = catalog.get_snapshot(provider_hint) if provider_hint else None
        catalog_freshness = FreshnessStatus.UNKNOWN
        if snap:
            catalog_freshness = evaluate_freshness(snap.retrieved_at)
            if catalog_freshness == FreshnessStatus.STALE:
                warnings.append(f"Catalog snapshot for {snap.provider} is STALE (retrieved {snap.retrieved_at})")

        # If provider_hint specified but no executable support for that mode
        if provider_hint and candidates:
            target_mode = target.mode.value
            matching = [c for c in candidates if target_mode in c.get("executionSupport", []) and not c.get("deprecated")]
            if not matching:
                # Check if there was a match that was deprecated
                deprecated_matches = [c for c in candidates
                                       if target_mode in c.get("executionSupport", []) and c.get("deprecated")]
                if deprecated_matches:
                    return {
                        "capability": capability,
                        "providerHint": provider_hint,
                        "requestedMode": target_mode,
                        "result": "DEPRECATED_RESOURCE",
                        "reason": f"Provider {provider_hint} has matching service but it is DEPRECATED",
                        "candidates": candidates,
                        "warnings": warnings + [f"Deprecated: {c['provider']} {c['serviceId']}" for c in deprecated_matches],
                    }
                return {
                    "capability": capability,
                    "providerHint": provider_hint,
                    "requestedMode": target_mode,
                    "result": "EXECUTION_NOT_SUPPORTED",
                    "reason": f"Provider {provider_hint} does not support {target_mode} for {capability}",
                    "candidates": candidates,
                    "warnings": warnings,
                }

        # Pick best candidate (exclude deprecated for executable selection)
        selected = None
        if candidates:
            non_deprecated = [c for c in candidates if not c.get("deprecated")]
            executable = [c for c in non_deprecated if c["isExecutable"]]
            if executable:
                selected = executable[0]
            elif non_deprecated:
                selected = non_deprecated[0]
            else:
                # All candidates deprecated — still show in comparison but note it
                warnings.append("All matching candidates are DEPRECATED")

        result = "SUPPORTED" if selected and selected.get("isExecutable") else "PLAN_ONLY"

        # Add freshness warning to selection
        if selected and catalog_freshness == FreshnessStatus.STALE:
            warnings.append(f"Catalog freshness: STALE (snapshot age may affect accuracy)")
            selected = dict(selected)  # copy
            selected["catalogFreshness"] = "STALE"

        return {
            "capability": capability,
            "providerHint": provider_hint,
            "candidates": candidates,
            "selected": selected,
            "result": result,
            "catalogFreshness": catalog_freshness.value,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------

    def _normalize_intent(self, request: InfrastructureRequest) -> dict[str, Any]:
        req = request.requirements
        intent: dict[str, Any] = {}
        if req.database:
            intent["database"] = {
                "engine": req.database.engine, "version": req.database.version,
                "availability": req.database.availability.value if req.database.availability else None,
                "backup_required": req.database.backup.required if req.database.backup else False,
                "encryption_required": bool(req.database.encryption and (req.database.encryption.atRest or req.database.encryption.inTransit)),
                "storage": req.database.storage}
        if req.applicationRuntime:
            intent["application_runtime"] = {
                "containerized": req.applicationRuntime.containerized,
                "replicas": req.applicationRuntime.replicas,
                "https": req.applicationRuntime.https, "port": req.applicationRuntime.port}
        if req.networking:
            intent["networking"] = {"public": req.networking.public,
                                    "https_only": req.networking.httpsOnly,
                                    "domain": req.networking.domain}
        intent["provider_hint"] = req.providerHint.value if req.providerHint else None
        return intent

    def _to_capability_requirements(self, normalized: dict[str, Any]) -> list[Any]:
        from ..core.domain import CapabilityCategory, CapabilityRequirement
        caps: list[CapabilityRequirement] = []
        if "database" in normalized:
            caps.append(CapabilityRequirement(category=CapabilityCategory.DATABASE, name="database", properties=normalized["database"]))
        if "application_runtime" in normalized:
            caps.append(CapabilityRequirement(category=CapabilityCategory.COMPUTE, name="application_runtime", properties=normalized["application_runtime"]))
        if "networking" in normalized:
            caps.append(CapabilityRequirement(category=CapabilityCategory.NETWORKING, name="networking", properties=normalized["networking"]))
        return caps

    def _resolve_target(self, request: InfrastructureRequest) -> ExecutionTarget:
        hint = request.requirements.providerHint
        provider = Provider(hint.value) if hint else Provider.AWS
        return ExecutionTarget(mode=ExecutionMode.PLAN_ONLY, provider=provider,
                               platform=Platform.NATIVE_VM, target_type=None,
                               fidelity_notes={"Execution": "PLAN_ONLY", "Real Provisioning": "NOT_TESTED"})

    def _generate_plan_only(self, request: InfrastructureRequest, target: ExecutionTarget) -> InfrastructurePlan:
        return InfrastructurePlan(request_id=request.infrastructureRequestId,
                                  correlation_id=request.correlationId,
                                  provider=target.provider, platform=target.platform,
                                  execution_target=target)

    def _plan_to_desired_state(self, plan: InfrastructurePlan) -> dict[str, Any]:
        desired: dict[str, Any] = {}
        for m in plan.capability_mappings:
            desired[m.resource_type] = m.resource_properties
        return desired

    def _build_result(self, ctx: OrchestrationContext, status: InfrastructureStatus,
                      extra_evidence: list[EvidenceItem] | None = None) -> InfrastructureResult:
        target = ctx.target or ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY, provider=Provider.AWS,
            platform=Platform.NATIVE_VM, target_type=None)

        # Use ctx.request if available, otherwise try to reconstruct IDs from store
        if ctx.request:
            corr_id = ctx.request.correlationId
            wp_id = ctx.request.workPackageId
            ir_id = ctx.request.infrastructureRequestId
        else:
            run = self.store.get_run(ctx.run_id) or {}
            corr_id = run.get("correlation_id", "")
            wp_id = run.get("work_package_id", "")
            ir_id = run.get("infrastructure_request_id", "")

        evidence_items = ctx.evidence.to_canonical_evidence_items()
        if extra_evidence:
            evidence_items.extend([{
                "type": e.type.value, "source": e.source, "reference": e.reference,
                "summary": e.summary,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None} for e in extra_evidence])

        return InfrastructureResult(
            correlationId=corr_id,
            workPackageId=wp_id,
            infrastructureRequestId=ir_id,
            status=status,
            provider=target.provider.value,
            platform=target.platform.value,
            evidence=[EvidenceItem(
                type=EvidenceType.ARCHITECTURE_PLAN, source="infrastructure-again",
                reference=item.get("reference", ""), summary=item.get("summary", ""),
                timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None)
                for item in evidence_items if item.get("type")],
            completedAt=ctx.completed_at or datetime.now(timezone.utc))
