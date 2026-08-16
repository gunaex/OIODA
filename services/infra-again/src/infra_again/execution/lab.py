"""
Local Lab Registry for INFRA-AGAIN.

Models all local/test execution targets with truthful capability probing.
Never claims support until verified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..core.domain import (
    ExecutionMode,
    ExecutionTarget,
    ExecutionTargetType,
    Platform,
    Provider,
    TruthStatus,
)


class LabTargetCategory(str, Enum):
    """Classification of local lab targets."""
    CLOUD_SIMULATOR = "CLOUD_SIMULATOR"
    CLOUD_EMULATOR = "CLOUD_EMULATOR"
    KUBERNETES_LOCAL = "KUBERNETES_LOCAL"
    OPENSHIFT_LOCAL = "OPENSHIFT_LOCAL"
    PRIVATE_CLOUD_LOCAL = "PRIVATE_CLOUD_LOCAL"
    VIRTUALIZATION_SIM = "VIRTUALIZATION_SIM"
    SUPPORTING_SERVICE = "SUPPORTING_SERVICE"


@dataclass
class LabTarget:
    """A registered local/test execution target."""
    target_type: ExecutionTargetType
    category: LabTargetCategory
    provider: Provider
    platform: Platform
    mode: ExecutionMode
    name: str
    description: str
    repository_url: str | None = None
    license_info: str | None = None
    host_requirements: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    fidelity_notes: dict[str, str] = field(default_factory=dict)
    status: TruthStatus = TruthStatus.NOT_INSTALLED
    install_command: str | None = None
    verify_command: str | None = None

    def to_execution_target(self) -> ExecutionTarget:
        return ExecutionTarget(
            mode=self.mode,
            provider=self.provider,
            platform=self.platform,
            target_type=self.target_type,
            fidelity_notes=self.fidelity_notes,
            safety_level=self._safety_level(),
        )

    def _safety_level(self) -> int:
        mapping = {
            ExecutionMode.PLAN_ONLY: 0,
            ExecutionMode.SIMULATED: 1,
            ExecutionMode.LOCAL_RUNTIME: 1,
            ExecutionMode.LOCAL_PRIVATE_CLOUD: 1,
            ExecutionMode.SANDBOX: 2,
            ExecutionMode.CONTROLLED_REAL: 3,
            ExecutionMode.PRODUCTION: 4,
        }
        return mapping.get(self.mode, 0)


# ---------------------------------------------------------------------------
# Local Lab Target Catalog
# ---------------------------------------------------------------------------

# These are modeled, not automatically installed.
# Status defaults to NOT_INSTALLED — probe truthfully.


AWS_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.FAKECLOUD,
        category=LabTargetCategory.CLOUD_SIMULATOR,
        provider=Provider.AWS,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.SIMULATED,
        name="fakecloud",
        description="AWS API simulator for local testing (S3 verified)",
        repository_url="https://github.com/faiscadev/fakecloud",
        license_info="AGPL-3.0",
        fidelity_notes={
            "AWS API Compatibility": "SIMULATED",
            "Real AWS Provisioning": "NOT_TESTED",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Simulator only — not real AWS",
            "May not support all AWS services",
            "No production credential equivalence",
        ],
        status=TruthStatus.READY,
        install_command="brew install fakecloud",
        verify_command="fakecloud --version && curl http://localhost:4566/_fakecloud/health",
    ),
    LabTarget(
        target_type=ExecutionTargetType.LOCALSTACK,
        category=LabTargetCategory.CLOUD_EMULATOR,
        provider=Provider.AWS,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.SIMULATED,
        name="LocalStack",
        description="AWS cloud emulator for local development",
        repository_url="https://github.com/localstack/localstack",
        fidelity_notes={
            "AWS API Compatibility": "EMULATED",
            "Real AWS Provisioning": "NOT_TESTED",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Community edition has service limits",
            "Not equivalent to real AWS",
        ],
        status=TruthStatus.NOT_INSTALLED,
        install_command="pip install localstack",
    ),
]

GCP_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.GCP_EMULATOR,
        category=LabTargetCategory.CLOUD_EMULATOR,
        provider=Provider.GCP,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.SIMULATED,
        name="GCP Emulators",
        description="Google Cloud emulators (Pub/Sub, Firestore, Spanner, Bigtable, Datastore)",
        fidelity_notes={
            "GCP API Compatibility": "EMULATED",
            "Real GCP Provisioning": "NOT_TESTED",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Individual service emulators only",
            "Not full GCP environment",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
    LabTarget(
        target_type=ExecutionTargetType.FAKE_GCS,
        category=LabTargetCategory.CLOUD_EMULATOR,
        provider=Provider.GCP,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.SIMULATED,
        name="fake-gcs-server",
        description="GCS-compatible local emulator",
        repository_url="https://github.com/fsouza/fake-gcs-server",
        fidelity_notes={
            "GCS API Compatibility": "EMULATED",
            "Real GCS Provisioning": "NOT_TESTED",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "GCS only — not full GCP",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
]

KUBERNETES_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.KIND,
        category=LabTargetCategory.KUBERNETES_LOCAL,
        provider=Provider.ON_PREM,
        platform=Platform.KUBERNETES,
        mode=ExecutionMode.LOCAL_RUNTIME,
        name="kind",
        description="Kubernetes in Docker — CI/automated testing target",
        fidelity_notes={
            "Kubernetes API": "REAL_LOCAL",
            "Multi-node": "SIMULATED",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Runs in Docker — not bare metal",
            "Limited to single host",
            "CI-optimized, not production",
        ],
        status=TruthStatus.NOT_INSTALLED,
        install_command="brew install kind",
    ),
    LabTarget(
        target_type=ExecutionTargetType.MINIKUBE,
        category=LabTargetCategory.KUBERNETES_LOCAL,
        provider=Provider.ON_PREM,
        platform=Platform.KUBERNETES,
        mode=ExecutionMode.LOCAL_RUNTIME,
        name="minikube",
        description="Richer local Kubernetes acceptance target",
        fidelity_notes={
            "Kubernetes API": "REAL_LOCAL",
            "Multi-node": "PARTIAL",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Single-node focus",
            "Addons may diverge from production",
        ],
        status=TruthStatus.NOT_INSTALLED,
        install_command="brew install minikube",
    ),
]

OPENSHIFT_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.CRC_OPENSHIFT,
        category=LabTargetCategory.OPENSHIFT_LOCAL,
        provider=Provider.ON_PREM,
        platform=Platform.OPENSHIFT_OCP,
        mode=ExecutionMode.LOCAL_RUNTIME,
        name="CRC (Red Hat OpenShift Local)",
        description="Local OpenShift Container Platform for development",
        fidelity_notes={
            "OpenShift API": "REAL_LOCAL",
            "Production OCP": "NOT_EQUIVALENT",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Requires significant resources (16GB+ RAM, 4+ vCPU)",
            "Single-node only",
            "Not production-grade",
            "CRC != production OCP",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
    LabTarget(
        target_type=ExecutionTargetType.CRC_OKD,
        category=LabTargetCategory.OPENSHIFT_LOCAL,
        provider=Provider.ON_PREM,
        platform=Platform.OPENSHIFT_OCP,
        mode=ExecutionMode.LOCAL_RUNTIME,
        name="CRC OKD",
        description="Local OKD (OpenShift Origin) for development",
        fidelity_notes={
            "OKD API": "REAL_LOCAL",
            "Production OCP": "NOT_EQUIVALENT",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "Community edition",
            "Not equivalent to Red Hat OpenShift",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
    LabTarget(
        target_type=ExecutionTargetType.MICROSHIFT,
        category=LabTargetCategory.OPENSHIFT_LOCAL,
        provider=Provider.ON_PREM,
        platform=Platform.OPENSHIFT_OCP,
        mode=ExecutionMode.LOCAL_RUNTIME,
        name="MicroShift",
        description="Lightweight OpenShift for edge/resource-constrained",
        fidelity_notes={
            "OpenShift API": "PARTIAL",
            "Production OCP": "NOT_EQUIVALENT",
        },
        limitations=[
            "Reduced feature set",
            "Edge-focused, not full OCP",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
]

PRIVATE_CLOUD_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.DEVSTACK,
        category=LabTargetCategory.PRIVATE_CLOUD_LOCAL,
        provider=Provider.PRIVATE_CLOUD,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.LOCAL_PRIVATE_CLOUD,
        name="DevStack",
        description="OpenStack development environment — real private cloud locally",
        fidelity_notes={
            "OpenStack API": "REAL_LOCAL",
            "Production OpenStack": "NOT_EQUIVALENT",
        },
        limitations=[
            "Development/CI only — not production",
            "Significant resource requirements",
            "Not a lightweight API mock",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
]

VIRTUALIZATION_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.VCSIM,
        category=LabTargetCategory.VIRTUALIZATION_SIM,
        provider=Provider.ON_PREM,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.SIMULATED,
        name="vcsim (govmomi)",
        description="VMware vSphere API simulator",
        fidelity_notes={
            "VMware API": "SIMULATED",
            "Real vSphere Provisioning": "NOT_TESTED",
            "Production Readiness": "NOT_VERIFIED",
        },
        limitations=[
            "API simulator only",
            "Does NOT prove real VMware provisioning",
        ],
        status=TruthStatus.NOT_INSTALLED,
    ),
]

SUPPORTING_TARGETS: list[LabTarget] = [
    LabTarget(
        target_type=ExecutionTargetType.LOCAL_DOCKER,
        category=LabTargetCategory.SUPPORTING_SERVICE,
        provider=Provider.ON_PREM,
        platform=Platform.NATIVE_VM,
        mode=ExecutionMode.LOCAL_RUNTIME,
        name="Docker",
        description="Container runtime for local testing",
        fidelity_notes={
            "Container Runtime": "REAL_LOCAL",
        },
        status=TruthStatus.NOT_INSTALLED,
    ),
]


def all_lab_targets() -> list[LabTarget]:
    """Return all registered lab targets."""
    return (
        AWS_TARGETS
        + GCP_TARGETS
        + KUBERNETES_TARGETS
        + OPENSHIFT_TARGETS
        + PRIVATE_CLOUD_TARGETS
        + VIRTUALIZATION_TARGETS
        + SUPPORTING_TARGETS
    )


def get_target(target_type: ExecutionTargetType) -> LabTarget | None:
    """Look up a lab target by type."""
    for t in all_lab_targets():
        if t.target_type == target_type:
            return t
    return None
