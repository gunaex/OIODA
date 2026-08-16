# INFRA-AGAIN Platform Model

## Platform Identity

**Platform = HOW infrastructure runs (runtime layer)**

| Platform | Description |
|---|---|
| NATIVE_VM | Virtual machines / bare metal |
| KUBERNETES | Container orchestration (K8s) |
| OPENSHIFT_OCP | Red Hat OpenShift Container Platform |
| BARE_METAL | Physical hardware |

## OCP is a Platform, NOT a Provider

Critical distinction:
- OCP runs ON providers (AWS, GCP, On-Prem)
- OCP provides the runtime layer
- OCP is NOT an alternative to AWS/GCP

## Platform Adapter Interface

Every platform implements:
```
probeStatus()      → Truthful platform availability
getCapabilities()  → Platform runtime capabilities
deploy()           → Deploy workload
observe()          → Observe platform state
validate()         → Desired vs observed
destroy()          → Remove workload (GATED)
```

## Local Platform Targets

| Platform | Local Target | Mode |
|---|---|---|
| KUBERNETES | kind, minikube | LOCAL_RUNTIME |
| OPENSHIFT_OCP | CRC, OKD, MicroShift | LOCAL_RUNTIME |
| NATIVE_VM | Docker, Podman | LOCAL_RUNTIME |
