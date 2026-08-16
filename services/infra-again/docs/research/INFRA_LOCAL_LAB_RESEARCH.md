# Infrastructure Local Lab Research

**Date:** 2026-08-09
**Status:** Research — Phase 0/1

## Purpose

Research all local/test execution targets for the INFRA-AGAIN Local Lab.
Every target is cataloged but NOT automatically installed.
Support is claimed only after truthful verification.

## AWS Targets

### fakecloud
- **URL:** https://github.com/faiscadev/fakecloud
- **Type:** SIMULATOR (not authoritative AWS catalog)
- **Classification:** `AWS_SIMULATED_TARGET`
- **Modeled as:** `ExecutionTargetType.FAKECLOUD`
- **Status:** NOT_INSTALLED
- **Fidelity:**
  - AWS API Compatibility: SIMULATED
  - Real AWS Provisioning: NOT_TESTED
  - Production Readiness: NOT_VERIFIED

### LocalStack
- **URL:** https://github.com/localstack/localstack
- **Type:** EMULATOR
- **Classification:** `AWS_SIMULATED_TARGET`
- **Modeled as:** `ExecutionTargetType.LOCALSTACK`
- **Status:** NOT_INSTALLED

## GCP Targets

### GCP Service Emulators
- **Source:** Google Cloud SDK (official)
- **Services:** Pub/Sub, Firestore, Spanner, Bigtable, Datastore
- **Type:** EMULATOR (official, but limited)
- **Modeled as:** `ExecutionTargetType.GCP_EMULATOR`
- **Status:** NOT_INSTALLED

### fake-gcs-server
- **URL:** https://github.com/fsouza/fake-gcs-server
- **Type:** GCS-COMPATIBLE EMULATOR
- **Classification:** `GCS_LOCAL_TARGET`
- **Modeled as:** `ExecutionTargetType.FAKE_GCS`
- **Status:** NOT_INSTALLED
- **Note:** NOT authoritative GCP catalog

## Kubernetes Targets

### kind
- **URL:** https://kind.sigs.k8s.io/
- **Type:** LOCAL_RUNTIME (real Kubernetes in Docker)
- **Classification:** CI/Automation Kubernetes target
- **Modeled as:** `ExecutionTargetType.KIND`
- **Status:** NOT_INSTALLED

### minikube
- **URL:** https://minikube.sigs.k8s.io/
- **Type:** LOCAL_RUNTIME (real Kubernetes locally)
- **Classification:** Richer local acceptance target
- **Modeled as:** `ExecutionTargetType.MINIKUBE`
- **Status:** NOT_INSTALLED

## OpenShift/OCP Targets

### CRC (Red Hat OpenShift Local)
- **URL:** https://developers.redhat.com/products/openshift-local/
- **Type:** LOCAL_RUNTIME
- **Platform:** OPENSHIFT_OCP
- **Modeled as:** `ExecutionTargetType.CRC_OPENSHIFT`
- **Host Requirements:** 16GB+ RAM, 4+ vCPU
- **Status:** NOT_INSTALLED
- **Note:** CRC != production OCP

### CRC OKD
- **Type:** LOCAL_RUNTIME
- **Platform:** OPENSHIFT_OCP
- **Modeled as:** `ExecutionTargetType.CRC_OKD`
- **Status:** NOT_INSTALLED

### MicroShift
- **URL:** https://github.com/openshift/microshift
- **Type:** LOCAL_RUNTIME
- **Platform:** OPENSHIFT_OCP
- **Classification:** Lightweight edge-focused OpenShift
- **Modeled as:** `ExecutionTargetType.MICROSHIFT`
- **Status:** NOT_INSTALLED

## Private Cloud Targets

### DevStack
- **URL:** https://docs.openstack.org/devstack/
- **Type:** LOCAL_PRIVATE_CLOUD (NOT lightweight API mock)
- **Classification:** Real private-cloud stack locally
- **Modeled as:** `ExecutionTargetType.DEVSTACK`
- **Status:** NOT_INSTALLED

## Virtualization Targets

### vcsim (govmomi)
- **URL:** https://github.com/vmware/govmomi/tree/main/vcsim
- **Type:** SIMULATOR (VMware API simulator)
- **Modeled as:** `ExecutionTargetType.VCSIM`
- **Status:** NOT_INSTALLED
- **Note:** Does NOT prove real VMware provisioning

## Future On-Prem Adapters (Architecture Only)
- KVM / libvirt
- Proxmox
- Bare Metal

## Supporting Local Infrastructure
- **MinIO** — S3-compatible object storage (separate from provider identity)
- **Vault dev** — Secrets management for local testing
- **PostgreSQL** — Local database runtime
- **Docker/Podman** — Container runtime

## Execution Fidelity Classification

| Mode | Fidelity | Blast Radius | Safety |
|---|---|---|---|
| PLAN_ONLY | No mutation | Zero | AUTO |
| SIMULATED | API simulation | Zero | AUTO |
| LOCAL_RUNTIME | Real software, local | Local machine | AUTO |
| LOCAL_PRIVATE_CLOUD | Real stack, local | Local machine | AUTO |
| SANDBOX | Real provider, isolated | Sandbox account | ASK |
| CONTROLLED_REAL | Real provider, non-prod | Controlled env | ASK |
| PRODUCTION | Real provider, production | Full blast radius | BLOCK |
