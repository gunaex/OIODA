"""
Unit tests for provider-neutral domain model.
"""

import pytest

from infra_again.core.domain import (
    CapabilityCategory,
    CapabilityRequirement,
    ChangeAction,
    ChangeItem,
    ChangeSet,
    ExecutionMode,
    ExecutionState,
    ExecutionTarget,
    ExecutionTargetType,
    InfrastructurePlan,
    Platform,
    Provider,
    TruthStatus,
    ValidationResult,
)
from infra_again.execution.lab import (
    AWS_TARGETS,
    all_lab_targets,
    get_target,
    LabTarget,
)
from infra_again.execution.orchestrator import ActionPolicy, PolicyEngine


# ---------------------------------------------------------------------------
# Provider × Platform separation
# ---------------------------------------------------------------------------


class TestProviderPlatformSeparation:
    """Provider and Platform must be independent dimensions."""

    def test_provider_not_platform(self):
        """Provider values are not platform values."""
        providers = {p.value for p in Provider}
        platforms = {p.value for p in Platform}
        assert "AWS" in providers
        assert "KUBERNETES" in platforms
        assert "OPENSHIFT_OCP" in platforms
        # OCP is platform, not provider
        assert "OPENSHIFT_OCP" not in providers

    def test_valid_combinations(self):
        """Any valid Provider × Platform combination should work."""
        target = ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY,
            provider=Provider.AWS,
            platform=Platform.OPENSHIFT_OCP,
            target_type=ExecutionTargetType.CRC_OPENSHIFT,
        )
        assert target.provider == Provider.AWS
        assert target.platform == Platform.OPENSHIFT_OCP
        # AWS + OCP is valid
        assert target.provider != target.platform


# ---------------------------------------------------------------------------
# Execution Mode & Safety
# ---------------------------------------------------------------------------


class TestExecutionModeSafety:
    """Safety ladder enforcement."""

    def test_plan_only_is_safe(self):
        target = ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
        )
        assert target.is_safe is True

    def test_production_is_not_safe(self):
        target = ExecutionTarget(
            mode=ExecutionMode.PRODUCTION,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.AWS_PRODUCTION,
        )
        assert target.is_safe is False

    def test_simulated_is_safe(self):
        target = ExecutionTarget(
            mode=ExecutionMode.SIMULATED,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
        )
        assert target.is_safe is True

    def test_fidelity_description(self):
        target = ExecutionTarget(
            mode=ExecutionMode.SIMULATED,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
            fidelity_notes={
                "AWS API Compatibility": "SIMULATED",
                "Real AWS Provisioning": "NOT_TESTED",
            },
        )
        desc = target.fidelity_description()
        assert "SIMULATED" in desc
        assert "NOT_TESTED" in desc


# ---------------------------------------------------------------------------
# Capability Lifecycle
# ---------------------------------------------------------------------------


class TestCapabilityLifecycle:
    """Capability lifecycle states."""

    def test_capability_requirement(self):
        req = CapabilityRequirement(
            category=CapabilityCategory.DATABASE,
            name="database",
            properties={"engine": "postgresql", "availability": "production"},
        )
        assert req.category == CapabilityCategory.DATABASE
        assert req.properties["engine"] == "postgresql"

    def test_capability_not_hardcoded_aws(self):
        """Capability requirements must not contain AWS-specific terms."""
        req = CapabilityRequirement(
            category=CapabilityCategory.DATABASE,
            name="database",
            properties={"engine": "postgresql"},
        )
        # Properties should be provider-neutral
        assert "RDS" not in str(req.properties)
        assert "db.r6g" not in str(req.properties)


# ---------------------------------------------------------------------------
# Truth Status
# ---------------------------------------------------------------------------


class TestTruthStatus:
    """Truthful runtime states — no fake success."""

    def test_default_is_not_ready(self):
        assert TruthStatus.NOT_CONFIGURED != TruthStatus.READY

    def test_no_implicit_online(self):
        """The system must not assume providers are online."""
        statuses = [s.value for s in TruthStatus]
        assert "ONLINE" not in statuses
        assert TruthStatus.NOT_CONFIGURED.value == "NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# Change Set
# ---------------------------------------------------------------------------


class TestChangeSet:
    """Change set safety checks."""

    def test_destructive_detection(self):
        changes = [
            ChangeItem(
                action=ChangeAction.CREATE,
                resource_type="AWS::S3::Bucket",
                resource_id="bucket-1",
            ),
            ChangeItem(
                action=ChangeAction.DELETE,
                resource_type="AWS::RDS::DBInstance",
                resource_id="db-1",
                is_destructive=True,
            ),
        ]
        cs = ChangeSet(changes=changes, provider=Provider.AWS)
        assert cs.has_destructive_changes is True

    def test_safe_changeset(self):
        changes = [
            ChangeItem(
                action=ChangeAction.CREATE,
                resource_type="AWS::S3::Bucket",
                resource_id="bucket-1",
            ),
        ]
        cs = ChangeSet(changes=changes)
        assert cs.has_destructive_changes is False

    def test_summary(self):
        changes = [
            ChangeItem(action=ChangeAction.CREATE, resource_type="T1", resource_id="r1"),
            ChangeItem(action=ChangeAction.CREATE, resource_type="T1", resource_id="r2"),
            ChangeItem(action=ChangeAction.UPDATE, resource_type="T1", resource_id="r3"),
        ]
        cs = ChangeSet(changes=changes)
        assert "Create=2" in cs.summary
        assert "Update=1" in cs.summary


# ---------------------------------------------------------------------------
# Policy / AIRLOCK
# ---------------------------------------------------------------------------


class TestPolicyEngine:
    """Safety policy enforcement."""

    def test_plan_is_auto(self):
        target = ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
        )
        decision = PolicyEngine.evaluate("plan", target)
        assert decision.policy == ActionPolicy.AUTO
        assert decision.requires_approval is False

    def test_destroy_is_blocked_outside_simulated(self):
        """Destroy without ownership context defaults to ASK outside simulated."""
        target = ExecutionTarget(
            mode=ExecutionMode.CONTROLLED_REAL,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.AWS_SANDBOX,
        )
        decision = PolicyEngine.evaluate("destroy", target)
        # Without ownership context, destroy requires ASK or BLOCK
        assert decision.policy in (ActionPolicy.ASK, ActionPolicy.BLOCK)
        assert decision.requires_approval is True

    def test_destroy_is_auto_for_owned_isolated(self):
        """AUTO destroy allowed for owned, ephemeral, ISOLATED resource."""
        from infra_again.core.domain import ResourceOwnership, TargetScope

        target = ExecutionTarget(
            mode=ExecutionMode.SIMULATED,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
        )
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN",
            created_by_run_id="run-123",
            ephemeral=True,
            target_scope=TargetScope.ISOLATED,
        )
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "bucket-1",
            "ownership": ownership,
            "current_run_id": "run-123",
        })
        assert decision.policy == ActionPolicy.AUTO
        assert decision.requires_approval is False

    def test_destroy_is_ask_for_non_owned(self):
        """ASK required for non-owned or shared resources."""
        from infra_again.core.domain import ResourceOwnership, TargetScope

        target = ExecutionTarget(
            mode=ExecutionMode.SIMULATED,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
        )
        ownership = ResourceOwnership(
            managed_by="INFRA_AGAIN",
            created_by_run_id="run-other",
            ephemeral=True,
            target_scope=TargetScope.ISOLATED,
        )
        decision = PolicyEngine.evaluate("destroy", target, context={
            "resource_id": "bucket-1",
            "ownership": ownership,
            "current_run_id": "run-123",
        })
        assert decision.policy == ActionPolicy.ASK
        assert decision.requires_approval is True

    def test_production_apply_blocked(self):
        target = ExecutionTarget(
            mode=ExecutionMode.PRODUCTION,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.AWS_PRODUCTION,
        )
        decision = PolicyEngine.evaluate("apply", target)
        assert decision.policy == ActionPolicy.BLOCK

    def test_hidden_fallback_blocked(self):
        target = ExecutionTarget(
            mode=ExecutionMode.PLAN_ONLY,
            provider=Provider.AWS,
            platform=Platform.NATIVE_VM,
            target_type=ExecutionTargetType.FAKECLOUD,
        )
        decision = PolicyEngine.evaluate("plan", target, context={"fallback_provider": True})
        assert decision.policy == ActionPolicy.BLOCK


# ---------------------------------------------------------------------------
# Local Lab Registry
# ---------------------------------------------------------------------------


class TestLocalLab:
    """Local lab target catalog."""

    def test_fakecloud_registered(self):
        target = get_target(ExecutionTargetType.FAKECLOUD)
        assert target is not None
        assert target.provider == Provider.AWS
        assert target.mode == ExecutionMode.SIMULATED
        assert "Production Readiness" in target.fidelity_notes

    def test_fakecloud_not_production(self):
        target = get_target(ExecutionTargetType.FAKECLOUD)
        assert target is not None
        assert target.fidelity_notes.get("Production Readiness") == "NOT_VERIFIED"
        assert "Real AWS Provisioning" in target.fidelity_notes

    def test_crc_is_platform_not_provider(self):
        target = get_target(ExecutionTargetType.CRC_OPENSHIFT)
        assert target is not None
        assert target.platform == Platform.OPENSHIFT_OCP
        assert target.provider != Provider.AWS  # OCP is not a cloud provider

    def test_all_targets_default_not_installed(self):
        """Most targets default to NOT_INSTALLED; fakecloud may be READY if installed."""
        for target in all_lab_targets():
            if target.target_type == ExecutionTargetType.FAKECLOUD:
                # fakecloud may be installed — just verify it's a valid status
                assert target.status in (TruthStatus.NOT_INSTALLED, TruthStatus.READY)
            else:
                assert target.status == TruthStatus.NOT_INSTALLED, \
                    f"{target.name} should default to NOT_INSTALLED"

    def test_vcsim_not_real_vmware(self):
        target = get_target(ExecutionTargetType.VCSIM)
        assert target is not None
        assert target.mode == ExecutionMode.SIMULATED
        assert "Real vSphere Provisioning" in target.fidelity_notes


# ---------------------------------------------------------------------------
# Execution State Machine
# ---------------------------------------------------------------------------


class TestExecutionStateMachine:
    """Explicit persisted states."""

    def test_all_states_defined(self):
        states = [s.value for s in ExecutionState]
        assert "DRAFT" in states
        assert "COMPLETED" in states
        assert "FAILED" in states
        assert "BLOCKED" in states
        assert "CANCELLED" in states

    def test_state_not_inferred_from_logs(self):
        """States must be explicit, not inferred."""
        state = ExecutionState.DRAFT
        assert state == ExecutionState.DRAFT
        assert state != ExecutionState.COMPLETED
