"""Architecture Feasibility / Executability — Phase N2.

Architecture Quality != Executability. A quality-passing, complete
architecture can still be NOT_EXECUTABLE if Provider Intelligence has no
executor/observer/validator/verifier for one of its services, or only has
one at a fidelity nobody requested.

Everything here is derived — never trusted — from ProviderServiceResolver.
No field on an incoming node dict is ever read as a verdict; the LLM/
frontend can only influence WHICH service a node names, never whether the
resulting architecture is executable (see LLM_CANNOT_SET_EXECUTABILITY /
FRONTEND_CANNOT_SET_EXECUTABILITY acceptance in the N2 spec).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .provider_resolver import ALL_FIDELITIES, FidelityCapability, ProviderServiceResolver, get_resolver

# Categories that are never implementation targets — same exclusion used by
# provider_resolver.enrich_nodes_with_provider_intelligence, so "required
# executable nodes" and "enriched nodes" always agree on scope.
_NON_EXECUTABLE_CATEGORIES = {"USER", "EXTERNAL"}

# Fidelities where schema validation is treated as mandatory for execution
# readiness — SANDBOX and above touch real or real-adjacent infrastructure,
# so an unvalidated schema is a blocking gap there, not just a warning.
_SCHEMA_MANDATORY_FIDELITIES = {"SANDBOX", "CONTROLLED_REAL", "PRODUCTION"}


@dataclass
class NodeFeasibility:
    node_id: str = ""
    name: str = ""
    provider: str = ""
    canonical_service_id: str = ""
    runtime_mode: str = ""
    execution_mode: str = ""  # platform, e.g. KUBERNETES/NATIVE_VM
    requested_fidelity: str = ""

    provider_lifecycle_state: str = "UNRESOLVED"
    execution_support_state: str = "UNRESOLVED"

    executor_available: bool = False
    observer_available: bool = False
    validator_available: bool = False
    verifier_available: bool = False
    verified_success_available: bool = False

    schema_validated: bool = False

    # Per-fidelity capability for all 7 fidelities — the fidelity matrix
    # (N2 section 3), keyed by fidelity name.
    fidelity: dict[str, FidelityCapability] = field(default_factory=dict)

    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id, "name": self.name, "provider": self.provider,
            "canonicalServiceId": self.canonical_service_id, "runtimeMode": self.runtime_mode,
            "executionMode": self.execution_mode, "requestedFidelity": self.requested_fidelity,
            "providerLifecycleState": self.provider_lifecycle_state,
            "executionSupportState": self.execution_support_state,
            "executorAvailable": self.executor_available,
            "observerAvailable": self.observer_available,
            "validatorAvailable": self.validator_available,
            "verifierAvailable": self.verifier_available,
            "verifiedSuccessAvailable": self.verified_success_available,
            "schemaValidated": self.schema_validated,
            "fidelity": {k: v.to_dict() for k, v in self.fidelity.items()},
            "blockingIssues": self.blocking_issues,
            "warnings": self.warnings,
        }


@dataclass
class ArchitectureFeasibilityAssessment:
    architecture_id: str = ""
    architecture_revision: str = ""
    provider: str = ""
    platform: str = ""
    requested_fidelity: str = "SIMULATED"

    total_services: int = 0
    supported_count: int = 0
    verified_count: int = 0
    known_unverified_count: int = 0
    unsupported_count: int = 0
    unknown_count: int = 0

    required_executable_nodes: int = 0
    executable_nodes: int = 0
    observable_nodes: int = 0
    validatable_nodes: int = 0
    verifiable_nodes: int = 0

    executor_coverage: float = 0.0
    observer_coverage: float = 0.0
    validator_coverage: float = 0.0
    verifier_coverage: float = 0.0
    schema_coverage: float = 0.0
    implementation_coverage: float = 0.0

    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    plan_only_ready: bool = False
    simulated_ready: bool = False
    local_runtime_ready: bool = False
    local_private_cloud_ready: bool = False
    sandbox_ready: bool = False
    controlled_real_ready: bool = False
    production_ready: bool = False

    # EXECUTABLE | PARTIALLY_EXECUTABLE | NOT_EXECUTABLE | UNKNOWN
    overall_executability: str = "UNKNOWN"

    node_feasibility: list[NodeFeasibility] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "architectureId": self.architecture_id, "architectureRevision": self.architecture_revision,
            "provider": self.provider, "platform": self.platform,
            "requestedFidelity": self.requested_fidelity,
            "totalServices": self.total_services,
            "supportedCount": self.supported_count, "verifiedCount": self.verified_count,
            "knownUnverifiedCount": self.known_unverified_count,
            "unsupportedCount": self.unsupported_count, "unknownCount": self.unknown_count,
            "requiredExecutableNodes": self.required_executable_nodes,
            "executableNodes": self.executable_nodes, "observableNodes": self.observable_nodes,
            "validatableNodes": self.validatable_nodes, "verifiableNodes": self.verifiable_nodes,
            "executorCoverage": self.executor_coverage, "observerCoverage": self.observer_coverage,
            "validatorCoverage": self.validator_coverage, "verifierCoverage": self.verifier_coverage,
            "schemaCoverage": self.schema_coverage, "implementationCoverage": self.implementation_coverage,
            "blockingIssues": self.blocking_issues, "warnings": self.warnings,
            "planOnlyReady": self.plan_only_ready, "simulatedReady": self.simulated_ready,
            "localRuntimeReady": self.local_runtime_ready,
            "localPrivateCloudReady": self.local_private_cloud_ready,
            "sandboxReady": self.sandbox_ready, "controlledRealReady": self.controlled_real_ready,
            "productionReady": self.production_ready,
            "overallExecutability": self.overall_executability,
            "nodeFeasibility": [n.to_dict() for n in self.node_feasibility],
        }


def _is_required_node(node: dict[str, Any]) -> bool:
    return node.get("category") not in _NON_EXECUTABLE_CATEGORIES and bool(node.get("nativeService"))


def _assess_node(resolver: ProviderServiceResolver, node: dict[str, Any], requested_fidelity: str) -> NodeFeasibility:
    node_id = node.get("nodeId", "") or "?"
    native = node.get("nativeService", "")
    provider = node.get("provider", "")
    platform = node.get("platform", "")

    result = resolver.resolve(provider=provider, native_service=native, platform=platform)

    fidelity_map = {fid: resolver.resolve_fidelity(provider, native, fid, platform) for fid in ALL_FIDELITIES}
    req = fidelity_map.get(requested_fidelity.upper())

    schema_validated = result.schema_validation_state == "VALIDATED"

    blocking: list[str] = []
    warnings: list[str] = list(result.warnings)

    if result.provider_lifecycle_state == "UNKNOWN_SERVICE":
        blocking.append(f"{node_id}: unknown provider service '{native}' — cannot assess executability")
    elif req is not None and not req.ready and requested_fidelity.upper() != "PLAN_ONLY":
        # Known service, but no executor at the requested fidelity. PLAN_ONLY
        # itself never blocks on this — a plan can exist with no executor.
        blocking.append(
            f"{node_id}: {result.display_name or native} has no {requested_fidelity} execution "
            f"support — PLAN_ONLY may remain available"
        )

    if req is not None and req.executor_available and not req.observer_available:
        warnings.append(f"{node_id}: executor available without an observer — VERIFIED SUCCESS not possible")
    if req is not None and req.executor_available and not req.validator_available:
        warnings.append(f"{node_id}: validator unavailable — VERIFIED SUCCESS not possible")
    if req is not None and req.executor_available and not req.verifier_available:
        warnings.append(f"{node_id}: independent verifier unavailable — final verification not possible")

    if not schema_validated and result.provider_lifecycle_state != "UNKNOWN_SERVICE":
        msg = f"{node_id}: schema not independently validated for {native}"
        if requested_fidelity.upper() in _SCHEMA_MANDATORY_FIDELITIES:
            blocking.append(msg + f" — mandatory at {requested_fidelity}")
        else:
            warnings.append(msg)

    verified_success_available = bool(
        req and req.executor_available and req.observer_available
        and req.validator_available and req.verifier_available
    )

    return NodeFeasibility(
        node_id=node_id, name=node.get("name", ""), provider=result.provider,
        canonical_service_id=result.canonical_service_id, runtime_mode=result.runtime_mode,
        execution_mode=platform, requested_fidelity=requested_fidelity.upper(),
        provider_lifecycle_state=result.provider_lifecycle_state,
        execution_support_state=result.execution_support_state,
        executor_available=bool(req and req.executor_available),
        observer_available=bool(req and req.observer_available),
        validator_available=bool(req and req.validator_available),
        verifier_available=bool(req and req.verifier_available),
        verified_success_available=verified_success_available,
        schema_validated=schema_validated,
        fidelity=fidelity_map,
        blocking_issues=blocking, warnings=warnings,
    )


def assess_architecture_feasibility(
    nodes: list[dict[str, Any]],
    architecture_id: str = "",
    architecture_revision: str = "",
    provider: str = "",
    platform: str = "",
    requested_fidelity: str = "SIMULATED",
    resolver: ProviderServiceResolver | None = None,
) -> ArchitectureFeasibilityAssessment:
    """The ONE place feasibility/executability is computed. Always recomputed
    fresh from Provider Intelligence — any providerLifecycleState/
    executionSupportState already present on an incoming node dict (e.g.
    from N1 enrichment) is ignored, so neither the LLM nor the frontend can
    ever set executability by embedding a claim in the node payload."""
    resolver = resolver or get_resolver()
    requested_fidelity = (requested_fidelity or "SIMULATED").upper()

    required = [n for n in nodes if _is_required_node(n)]
    node_results = [_assess_node(resolver, n, requested_fidelity) for n in required]

    total = len(node_results)
    unknown = sum(1 for r in node_results if r.provider_lifecycle_state == "UNKNOWN_SERVICE")
    verified = sum(1 for r in node_results if r.provider_lifecycle_state in ("VERIFIED", "SUPPORTED"))
    unsupported = sum(
        1 for r in node_results
        if r.provider_lifecycle_state != "UNKNOWN_SERVICE" and r.execution_support_state == "UNSUPPORTED"
    )
    known_unverified = total - unknown - verified - unsupported
    known_unverified = max(known_unverified, 0)
    supported = total - unknown - unsupported

    executable_nodes = sum(1 for r in node_results if r.executor_available)
    observable_nodes = sum(1 for r in node_results if r.observer_available)
    validatable_nodes = sum(1 for r in node_results if r.validator_available)
    verifiable_nodes = sum(1 for r in node_results if r.verifier_available)
    schema_ok_nodes = sum(1 for r in node_results if r.schema_validated)
    implementable_nodes = sum(1 for r in node_results if r.provider_lifecycle_state != "UNKNOWN_SERVICE")

    def _cov(n: int) -> float:
        return round(n / total, 4) if total else 0.0

    blocking_issues: list[str] = []
    warnings: list[str] = []
    for r in node_results:
        blocking_issues.extend(r.blocking_issues)
        warnings.extend(r.warnings)

    # Fidelity readiness matrix — the WHOLE required node set must be ready
    # at a fidelity for the architecture to be ready there. One unready
    # node blocks readiness at that fidelity regardless of how high overall
    # coverage looks (BLOCKER_OVERRIDES_PERCENTAGE).
    fidelity_ready: dict[str, bool] = {}
    for fid in ALL_FIDELITIES:
        if total == 0:
            fidelity_ready[fid] = False
            continue
        fidelity_ready[fid] = all(r.fidelity[fid].ready for r in node_results)

    if total == 0:
        overall = "UNKNOWN"
    elif unknown > 0:
        overall = "NOT_EXECUTABLE"
    elif executable_nodes == 0:
        overall = "NOT_EXECUTABLE"
    elif executable_nodes < total:
        overall = "PARTIALLY_EXECUTABLE"
    else:
        overall = "EXECUTABLE"

    return ArchitectureFeasibilityAssessment(
        architecture_id=architecture_id, architecture_revision=architecture_revision,
        provider=provider, platform=platform, requested_fidelity=requested_fidelity,
        total_services=total,
        supported_count=supported, verified_count=verified,
        known_unverified_count=known_unverified, unsupported_count=unsupported, unknown_count=unknown,
        required_executable_nodes=total,
        executable_nodes=executable_nodes, observable_nodes=observable_nodes,
        validatable_nodes=validatable_nodes, verifiable_nodes=verifiable_nodes,
        executor_coverage=_cov(executable_nodes), observer_coverage=_cov(observable_nodes),
        validator_coverage=_cov(validatable_nodes), verifier_coverage=_cov(verifiable_nodes),
        schema_coverage=_cov(schema_ok_nodes), implementation_coverage=_cov(implementable_nodes),
        blocking_issues=blocking_issues, warnings=warnings,
        plan_only_ready=fidelity_ready.get("PLAN_ONLY", False),
        simulated_ready=fidelity_ready.get("SIMULATED", False),
        local_runtime_ready=fidelity_ready.get("LOCAL_RUNTIME", False),
        local_private_cloud_ready=fidelity_ready.get("LOCAL_PRIVATE_CLOUD", False),
        sandbox_ready=fidelity_ready.get("SANDBOX", False),
        controlled_real_ready=fidelity_ready.get("CONTROLLED_REAL", False),
        production_ready=fidelity_ready.get("PRODUCTION", False),
        overall_executability=overall,
        node_feasibility=node_results,
    )


def feasibility_digest(assessment: ArchitectureFeasibilityAssessment) -> str:
    """Phase N3 — deterministic digest of the feasibility EVIDENCE used to
    produce a plan (not the whole assessment object, just the parts that
    would change what's plannable). Lets a plan detect "the same
    architecture now resolves differently" (e.g. a service's
    executionSupportState changed) without re-deriving feasibility itself —
    N3 binds this digest, it never recomputes feasibility and calls the
    result the same plan."""
    import hashlib
    import json

    data = {
        "overallExecutability": assessment.overall_executability,
        "requestedFidelity": assessment.requested_fidelity,
        "nodes": sorted(
            [
                {
                    "nodeId": n.node_id,
                    "providerLifecycleState": n.provider_lifecycle_state,
                    "executionSupportState": n.execution_support_state,
                    "executorAvailable": n.executor_available,
                    "observerAvailable": n.observer_available,
                    "validatorAvailable": n.validator_available,
                    "verifierAvailable": n.verifier_available,
                }
                for n in assessment.node_feasibility
            ],
            key=lambda x: x["nodeId"],
        ),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
