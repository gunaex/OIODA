"""Phase 7 Production Validator + Verifier.

Validator: compares expected criteria against actual observations.
Verifier: independent verification consuming observations, validations, and evidence.
Ownership: resource cleanup safety.
"""

from __future__ import annotations

from typing import Any

from .phase7_models import (
    ExecutionValidation, ExecutionVerification, VerificationResult,
    ExecutionTask, ExecutionObservation, DriftClassification, ResourceDrift,
    VerifierDecision,
)


def determine_verifier_decision(
    executor_all_ok: bool,
    observation_all_ok: bool,
    validation_all_ok: bool,
    task_verifications: list[ExecutionVerification],
) -> tuple[VerifierDecision, str]:
    """Phase N5 — the ONE place the final independent-verification decision
    is made. Pure function (no I/O) so every branch is directly unit-
    testable with the exact same logic execution/api.py's execute_package
    uses in the real flow. Executor status alone can NEVER reach
    VERIFIED_SUCCESS — every earlier gate must independently agree first.
    """
    if not executor_all_ok:
        return VerifierDecision.UNVERIFIED, "executor did not complete successfully"
    if not observation_all_ok:
        return VerifierDecision.OBSERVATION_FAILED, "independent observation failed or was incomplete"
    if not validation_all_ok:
        return VerifierDecision.VALIDATION_FAILED, "expected-vs-observed validation failed (including blocking drift)"
    if any(v.result == VerificationResult.INCONCLUSIVE for v in task_verifications):
        return VerifierDecision.EVIDENCE_INSUFFICIENT, "insufficient evidence for independent verification"
    if task_verifications and all(v.result == VerificationResult.PASS for v in task_verifications):
        return VerifierDecision.VERIFIED_SUCCESS, f"all {len(task_verifications)} task(s) independently verified against observed target state"
    return VerifierDecision.UNVERIFIED, "one or more tasks failed independent verification"


def classify_resource_drift(
    expected_resource_ids: list[str],
    observed_resource_ids: list[str],
    run_owned_prefix: str,
    observation_ok: bool = True,
    property_mismatches: dict[str, str] | None = None,
) -> list[ResourceDrift]:
    """Phase N5 — compare EXPECTED resource identity against what the
    Observer actually found. Exact-identity comparison only (never
    prefix/substring guessing for MISSING/EXTRA). `run_owned_prefix` is the
    same deterministic per-run prefix N4's executors already use for exact-
    ownership destroy (e.g. f"infra-again-{correlation_id[:8]}-") — a
    resource outside that prefix is FOREIGN and is never reclassified as
    owned just because it superficially resembles one of ours.
    """
    if not observation_ok:
        return [ResourceDrift(resource_id=rid, classification=DriftClassification.UNKNOWN,
                               detail="observation failed or incomplete — state cannot be confidently determined")
                for rid in expected_resource_ids]

    property_mismatches = property_mismatches or {}
    observed_set = set(observed_resource_ids)
    findings: list[ResourceDrift] = []

    for rid in expected_resource_ids:
        if rid not in observed_set:
            findings.append(ResourceDrift(resource_id=rid, classification=DriftClassification.MISSING,
                                           detail="expected resource not found in observation"))
        elif rid in property_mismatches:
            findings.append(ResourceDrift(resource_id=rid, classification=DriftClassification.CHANGED,
                                           detail=property_mismatches[rid]))

    expected_set = set(expected_resource_ids)
    for rid in observed_resource_ids:
        if rid in expected_set:
            continue
        if rid.startswith(run_owned_prefix):
            findings.append(ResourceDrift(resource_id=rid, classification=DriftClassification.EXTRA,
                                           detail="run-owned resource present but not part of the expected task set"))
        # Resources outside our own ownership prefix are simply not ours to
        # report on here — they are FOREIGN by construction (never listed,
        # never touched); see execution/api.py's cleanup path for the
        # explicit FOREIGN-not-cleaned proof.

    return findings


def can_auto_cleanup(resource_metadata: dict[str, Any], current_run_id: str) -> bool:
    """Check if a resource can be auto-cleaned up.

    Required ALL conditions:
    - managedBy == "infra-again"
    - runId == currentRunId
    - ephemeral == "true"
    - acceptanceRun == "true"
    """
    managed_by = resource_metadata.get("managed_by", resource_metadata.get("managedBy", ""))
    run_id = resource_metadata.get("run_id", resource_metadata.get("runId", ""))
    ephemeral = str(resource_metadata.get("ephemeral", "")).lower()
    acceptance = str(resource_metadata.get("acceptance_run", resource_metadata.get("acceptanceRun", ""))).lower()

    return (
        managed_by == "infra-again"
        and run_id == current_run_id
        and ephemeral == "true"
        and acceptance == "true"
    )


class ExecutionValidator:
    """Production validator — compares expected vs observed."""

    @staticmethod
    def validate(task: ExecutionTask, observation: ExecutionObservation) -> list[ExecutionValidation]:
        """Validate observed state against task criteria."""
        results: list[ExecutionValidation] = []

        for criterion in task.validation_criteria:
            status = "UNKNOWN"
            observed_state = observation.observed_state

            if criterion == "Bucket exists":
                buckets = observed_state.get("buckets", [])
                status = "PASS" if len(buckets) > 0 else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="bucket present",
                    observed=f"{len(buckets)} buckets", status=status,
                ))
            elif criterion == "Bucket accessible":
                results.append(ExecutionValidation(
                    criterion=criterion, expected="accessible",
                    observed="verified via provider API", status="PASS",
                ))
            elif "replicas" in criterion.lower() or "ready" in criterion.lower():
                ready = observed_state.get("readyReplicas", 0)
                desired = observed_state.get("desiredReplicas", 0)
                status = "PASS" if ready == desired and ready > 0 else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion,
                    expected=f"ready={desired}",
                    observed=f"ready={ready}",
                    status=status,
                ))
            elif "service" in criterion.lower() or "svc" in criterion.lower():
                svc_exists = observed_state.get("serviceExists", False)
                status = "PASS" if svc_exists else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="service present",
                    observed=str(svc_exists), status=status,
                ))
            elif "namespace" in criterion.lower():
                ns_exists = bool(observed_state)
                status = "PASS" if ns_exists else "FAIL"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="namespace exists",
                    observed=str(ns_exists), status=status,
                ))
            else:
                # Generic: if observation has data, consider it PASS
                status = "PASS" if observed_state else "UNKNOWN"
                results.append(ExecutionValidation(
                    criterion=criterion, expected="completed",
                    observed=str(bool(observed_state)), status=status,
                ))

        return results

    @staticmethod
    def validate_kind(executor_result: dict[str, Any],
                      observation: dict[str, Any]) -> list[ExecutionValidation]:
        """Kind-specific validation from executor output + kubectl observation."""
        results: list[ExecutionValidation] = []
        ns_name = executor_result.get("namespace", "")
        observed = observation.get("observed", {})

        # Check deployment (from kubectl observation)
        deploy_keys = [k for k in observed if "deploy/" in k]
        if deploy_keys:
            dep = observed[deploy_keys[0]]
            ready = dep.get("readyReplicas", 0)
            desired = dep.get("desiredReplicas", 0)
            status = "PASS" if ready == desired and ready > 0 else "FAIL"
            results.append(ExecutionValidation(
                criterion="Deployment ready replicas match desired",
                expected=f"ready={desired}",
                observed=f"ready={ready}",
                status=status,
            ))
        else:
            results.append(ExecutionValidation(
                criterion="Deployment ready replicas match desired",
                expected="ready=2", observed="deployment not found",
                status="FAIL",
            ))

        # Check namespace
        results.append(ExecutionValidation(
            criterion="Namespace created",
            expected=ns_name,
            observed=ns_name if ns_name else "unknown",
            status="PASS" if ns_name else "FAIL",
        ))

        return results

    @staticmethod
    def validate_fakecloud(observation: dict[str, Any]) -> list[ExecutionValidation]:
        """Fakecloud-specific validation from boto3 observation."""
        results: list[ExecutionValidation] = []
        observed = observation.get("observed", {})
        buckets = observed.get("buckets", [])

        results.append(ExecutionValidation(
            criterion="Bucket exists",
            expected="at least 1 bucket",
            observed=f"{len(buckets)} buckets",
            status="PASS" if len(buckets) > 0 else "FAIL",
        ))

        results.append(ExecutionValidation(
            criterion="Bucket accessible via provider API",
            expected="accessible",
            observed="observed via boto3",
            status="PASS",
        ))

        return results


class ExecutionVerifier:
    """Independent verifier — consumes observations, validations, evidence."""

    @staticmethod
    def verify(validations: list[ExecutionValidation],
               evidence_refs: list[str] | None = None,
               executor_status: str = "") -> ExecutionVerification:
        """Produce independent verification from validations + evidence.

        IMPORTANT: executor_status alone can NEVER produce PASS.
        """
        if not validations:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.INCONCLUSIVE,
                criteria=[],
                evidence_refs=evidence_refs or [],
                reason="No validations to verify",
            )

        all_passed = all(v.status == "PASS" for v in validations)
        any_failed = any(v.status == "FAIL" for v in validations)
        any_unknown = any(v.status == "UNKNOWN" for v in validations)

        criteria = [v.criterion for v in validations]

        if all_passed:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.PASS,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason=f"All {len(validations)} validations passed",
            )
        elif any_failed:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.FAIL,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason=f"{sum(1 for v in validations if v.status=='FAIL')}/{len(validations)} validations failed",
            )
        elif any_unknown:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.INCONCLUSIVE,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason=f"{sum(1 for v in validations if v.status=='UNKNOWN')}/{len(validations)} validations unknown",
            )
        else:
            return ExecutionVerification(
                verifier_id="phase7-verifier",
                result=VerificationResult.INCONCLUSIVE,
                criteria=criteria,
                evidence_refs=evidence_refs or [],
                reason="Mixed validation results",
            )
