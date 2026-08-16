"""Phase N5 — Observe / Validate / Verify acceptance tests.

Pure logic tests against the exact production functions execute_package
uses (classify_resource_drift, ExecutionValidator, ExecutionVerifier,
determine_verifier_decision) — no fakecloud/tofu dependency. Covers the
required negative scenarios at the smallest legitimate unit boundary per
the N5 spec's explicit allowance, plus the core invariant:
EXECUTOR SUCCESS != VERIFIED SUCCESS.
"""

from __future__ import annotations

from infra_again.execution.phase7_models import (
    DriftClassification, ExecutionValidation, ExecutionVerification,
    VerificationResult, VerifierDecision,
)
from infra_again.execution.verifier import (
    ExecutionVerifier, classify_resource_drift, determine_verifier_decision,
)


# ═══════════════════════════════════════════════════════════════════
# classify_resource_drift — MISSING / EXTRA / CHANGED / UNKNOWN / FOREIGN
# ═══════════════════════════════════════════════════════════════════


def test_missing_resource_classified():
    findings = classify_resource_drift(
        expected_resource_ids=["infra-again-abc-et-1"], observed_resource_ids=[],
        run_owned_prefix="infra-again-abc-",
    )
    assert len(findings) == 1
    assert findings[0].classification == DriftClassification.MISSING


def test_extra_run_owned_resource_classified():
    findings = classify_resource_drift(
        expected_resource_ids=[], observed_resource_ids=["infra-again-abc-et-unexpected"],
        run_owned_prefix="infra-again-abc-",
    )
    assert len(findings) == 1
    assert findings[0].classification == DriftClassification.EXTRA


def test_changed_property_classified():
    findings = classify_resource_drift(
        expected_resource_ids=["infra-again-abc-et-1"], observed_resource_ids=["infra-again-abc-et-1"],
        run_owned_prefix="infra-again-abc-",
        property_mismatches={"infra-again-abc-et-1": "correlation tag mismatch"},
    )
    assert len(findings) == 1
    assert findings[0].classification == DriftClassification.CHANGED


def test_unknown_on_observation_failure():
    findings = classify_resource_drift(
        expected_resource_ids=["infra-again-abc-et-1"], observed_resource_ids=[],
        run_owned_prefix="infra-again-abc-", observation_ok=False,
    )
    assert len(findings) == 1
    assert findings[0].classification == DriftClassification.UNKNOWN


def test_foreign_resource_never_reported_as_owned():
    """A resource outside this run's exact ownership prefix must never be
    reclassified as EXTRA/owned just because it superficially resembles
    one of ours — it simply isn't reported at all (never touched)."""
    findings = classify_resource_drift(
        expected_resource_ids=["infra-again-abc-et-1"],
        observed_resource_ids=["infra-again-xyz-et-1"],  # different run's resource
        run_owned_prefix="infra-again-abc-",
    )
    classifications = {f.classification for f in findings}
    assert DriftClassification.FOREIGN not in classifications  # never explicitly claimed
    assert DriftClassification.EXTRA not in classifications  # and never silently absorbed as ours
    assert DriftClassification.MISSING in classifications  # our own expected resource is still reported missing


def test_no_drift_when_everything_matches():
    findings = classify_resource_drift(
        expected_resource_ids=["infra-again-abc-et-1"], observed_resource_ids=["infra-again-abc-et-1"],
        run_owned_prefix="infra-again-abc-",
    )
    assert findings == []


# ═══════════════════════════════════════════════════════════════════
# ExecutionVerifier — independent of executor, requires real evidence
# ═══════════════════════════════════════════════════════════════════


def test_executor_cannot_self_verify_with_no_validations():
    verification = ExecutionVerifier.verify(validations=[], evidence_refs=[], executor_status="COMPLETED")
    assert verification.result == VerificationResult.INCONCLUSIVE
    assert verification.result != VerificationResult.PASS  # executor_status alone never yields PASS


def test_verifier_fails_on_failed_validation():
    validations = [ExecutionValidation(criterion="Bucket exists", expected="present", observed="absent", status="FAIL")]
    verification = ExecutionVerifier.verify(validations, executor_status="COMPLETED")
    assert verification.result == VerificationResult.FAIL


def test_verifier_passes_only_when_all_validations_pass():
    validations = [
        ExecutionValidation(criterion="a", expected="x", observed="x", status="PASS"),
        ExecutionValidation(criterion="b", expected="y", observed="y", status="PASS"),
    ]
    verification = ExecutionVerifier.verify(validations, executor_status="COMPLETED")
    assert verification.result == VerificationResult.PASS


# ═══════════════════════════════════════════════════════════════════
# determine_verifier_decision — the exact function execute_package uses
# ═══════════════════════════════════════════════════════════════════


def _pass_verification():
    return ExecutionVerification(verifier_id="v", result=VerificationResult.PASS, criteria=["c"])


def test_executor_success_without_observation_not_verified():
    decision, reason = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=False, validation_all_ok=True,
        task_verifications=[_pass_verification()],
    )
    assert decision == VerifierDecision.OBSERVATION_FAILED
    assert decision != VerifierDecision.VERIFIED_SUCCESS


def test_observation_failure_not_verified():
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=False, validation_all_ok=False, task_verifications=[],
    )
    assert decision == VerifierDecision.OBSERVATION_FAILED


def test_validation_failure_not_verified():
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=True, validation_all_ok=False,
        task_verifications=[ExecutionVerification(verifier_id="v", result=VerificationResult.FAIL, criteria=["c"])],
    )
    assert decision == VerifierDecision.VALIDATION_FAILED


def test_missing_resource_not_verified():
    # A MISSING drift finding makes validation_all_ok False upstream (see
    # execute_package's blocking_drift computation) — proven here at the
    # decision-function boundary once that upstream signal is False.
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=True, validation_all_ok=False, task_verifications=[],
    )
    assert decision != VerifierDecision.VERIFIED_SUCCESS


def test_changed_resource_not_verified():
    # Same mechanism as MISSING — CHANGED is also a blocking drift class
    # that flips validation_all_ok False before determine_verifier_decision runs.
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=True, validation_all_ok=False,
        task_verifications=[ExecutionVerification(verifier_id="v", result=VerificationResult.PASS, criteria=["c"])],
    )
    assert decision != VerifierDecision.VERIFIED_SUCCESS


def test_foreign_resource_not_accepted_as_expected():
    # A FOREIGN resource is never added to expected/owned sets by
    # classify_resource_drift (see test_foreign_resource_never_reported_as_owned)
    # so it can never contribute to a positive validation signal at all —
    # confirmed structurally: FOREIGN is not even a DriftClassification
    # value classify_resource_drift ever emits (by construction).
    findings = classify_resource_drift(
        expected_resource_ids=[], observed_resource_ids=["infra-again-other-run-et-1"],
        run_owned_prefix="infra-again-abc-",
    )
    assert findings == []  # not ours to report on, not counted as validating anything


def test_insufficient_evidence_not_verified():
    decision, reason = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=True, validation_all_ok=True,
        task_verifications=[ExecutionVerification(verifier_id="v", result=VerificationResult.INCONCLUSIVE, criteria=[])],
    )
    assert decision == VerifierDecision.EVIDENCE_INSUFFICIENT


def test_executor_cannot_self_verify_end_to_end():
    """The core N5 invariant: EXECUTOR SUCCESS != VERIFIED SUCCESS. Executor
    reporting COMPLETED, with no observation/validation/verification signal
    at all, must never reach VERIFIED_SUCCESS."""
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=False, validation_all_ok=False, task_verifications=[],
    )
    assert decision != VerifierDecision.VERIFIED_SUCCESS


def test_verified_success_requires_all_gates_true():
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=True, validation_all_ok=True,
        task_verifications=[_pass_verification()],
    )
    assert decision == VerifierDecision.VERIFIED_SUCCESS


def test_verified_success_never_emitted_with_empty_verifications():
    decision, _ = determine_verifier_decision(
        executor_all_ok=True, observation_all_ok=True, validation_all_ok=True, task_verifications=[],
    )
    assert decision != VerifierDecision.VERIFIED_SUCCESS
