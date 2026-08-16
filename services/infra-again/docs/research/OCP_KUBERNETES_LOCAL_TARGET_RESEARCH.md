# OCP / Kubernetes Local Target Research

**Date:** 2026-08-09

## Kubernetes Local Targets

### kind (Kubernetes in Docker)
- **Type:** LOCAL_RUNTIME
- **Use:** CI/Automated Kubernetes testing
- **Strengths:** Fast startup, ephemeral, scriptable
- **Limitations:** Docker dependency, single-host, simulated multi-node
- **Production parity:** NOT equivalent

### minikube
- **Type:** LOCAL_RUNTIME
- **Use:** Richer local Kubernetes development/acceptance
- **Strengths:** Addons ecosystem, multiple drivers, wider K8s feature support
- **Limitations:** Single-node focus, addons may diverge from production
- **Production parity:** NOT equivalent

### k3s
- **Type:** LOCAL_RUNTIME
- **Use:** Lightweight Kubernetes (edge/IoT)
- **Strengths:** Low resource, single binary
- **Limitations:** Reduced feature set
- **Production parity:** Suitable for edge, not full K8s

## OpenShift Local Targets

### CRC (Red Hat OpenShift Local)
- **Type:** LOCAL_RUNTIME
- **Platform:** OPENSHIFT_OCP
- **Requirements:** 16GB+ RAM, 4+ vCPU, ~35GB disk
- **Strengths:** Real OpenShift API, developer sandbox
- **Limitations:** Single-node, resource-heavy, not production-grade
- **Key distinction:** CRC ≠ production OCP

### OKD (OpenShift Origin via CRC)
- **Type:** LOCAL_RUNTIME
- **Platform:** OPENSHIFT_OCP
- **Strengths:** Community OpenShift, free
- **Limitations:** Community support, not Red Hat supported
- **Key distinction:** OKD ≠ Red Hat OpenShift

### MicroShift
- **Type:** LOCAL_RUNTIME
- **Platform:** OPENSHIFT_OCP
- **Strengths:** Lightweight, edge-focused, low resource
- **Limitations:** Reduced API surface, not full OCP
- **Key distinction:** MicroShift is OCP subset

## Platform ≠ Provider

Critical architectural distinction:
- OCP is a PLATFORM/runtime layer
- OCP is NOT a cloud provider
- OCP runs ON providers (AWS, GCP, On-Prem)
- Valid: AWS + OCP, GCP + OCP, On-Prem + OCP

## For INFRA-AGAIN

Phase 1: Modeled in Local Lab Registry, NOT_INSTALLED
Phase 2+: Implement platform adapters with truthful capability probing
