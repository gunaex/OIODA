# INFRA-AGAIN Provider Model

## Provider Identity

**Provider = WHERE infrastructure runs**

| Provider | Description |
|---|---|
| AWS | Amazon Web Services |
| GCP | Google Cloud Platform |
| ON_PREM | On-premises infrastructure |
| PRIVATE_CLOUD | Private cloud (OpenStack, etc.) |

## Provider ≠ Platform

Provider and Platform are orthogonal:
```
Provider (WHERE) × Platform (HOW)
```

Valid combinations:
| Provider | Native VM | Kubernetes | OpenShift OCP |
|---|---|---|---|
| AWS | EC2 | EKS | AWS + OCP |
| GCP | Compute Engine | GKE | GCP + OCP |
| ON_PREM | VMware/KVM | K8s | OCP |
| PRIVATE_CLOUD | OpenStack | K8s on OpenStack | — |

## Provider Adapter Interface

Every provider implements:
```
discover()     → Current infrastructure state
plan()         → Provider-specific plan from neutral requirements
validatePlan() → Plan validation against provider constraints
apply()        → Execute plan (GATED by policy)
observe()      → Post-execution state observation
validate()     → Desired vs observed comparison
destroy()      → Resource destruction (GATED by policy)
probeStatus()  → Truthful connection status
```

## AWS is NOT the Architecture

- AWS is the first provider adapter
- Core domain model is provider-agnostic
- No AWS service names in provider-neutral types
- AWS adapter is a conforming implementation, not the architecture
