# INFRA-AGAIN Local Lab Model

## Overview

The Local Lab enables safe infrastructure testing before real provider execution.
No target is automatically installed. Support is claimed only after truthful verification.

## Target Catalog

### AWS
| Target | Type | Mode | Status |
|---|---|---|---|
| fakecloud | SIMULATOR | SIMULATED | NOT_INSTALLED |
| LocalStack | EMULATOR | SIMULATED | NOT_INSTALLED |

### GCP
| Target | Type | Mode | Status |
|---|---|---|---|
| GCP Emulators | EMULATOR | SIMULATED | NOT_INSTALLED |
| fake-gcs-server | EMULATOR | SIMULATED | NOT_INSTALLED |

### Kubernetes
| Target | Type | Mode | Status |
|---|---|---|---|
| kind | LOCAL_RUNTIME | LOCAL_RUNTIME | NOT_INSTALLED |
| minikube | LOCAL_RUNTIME | LOCAL_RUNTIME | NOT_INSTALLED |

### OpenShift/OCP
| Target | Type | Mode | Status |
|---|---|---|---|
| CRC OpenShift | LOCAL_RUNTIME | LOCAL_RUNTIME | NOT_INSTALLED |
| CRC OKD | LOCAL_RUNTIME | LOCAL_RUNTIME | NOT_INSTALLED |
| MicroShift | LOCAL_RUNTIME | LOCAL_RUNTIME | NOT_INSTALLED |

### Private Cloud
| Target | Type | Mode | Status |
|---|---|---|---|
| DevStack | LOCAL_PRIVATE_CLOUD | LOCAL_PRIVATE_CLOUD | NOT_INSTALLED |

### Virtualization
| Target | Type | Mode | Status |
|---|---|---|---|
| vcsim | SIMULATOR | SIMULATED | NOT_INSTALLED |

## Fidelity Rules

- fakecloud does NOT prove AWS production readiness
- CRC does NOT prove production OCP readiness
- vcsim does NOT prove real VMware provisioning
- DevStack is NOT a lightweight API mock
- GCP emulators are NOT the full GCP environment

## Testing Ladder

```
PLAN_ONLY → SIMULATED → LOCAL_RUNTIME → SANDBOX → CONTROLLED_REAL → PRODUCTION
```
