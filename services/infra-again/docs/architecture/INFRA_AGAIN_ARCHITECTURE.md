# INFRA-AGAIN Architecture

**Version:** 0.1.0
**Date:** 2026-08-09
**Canonical Baseline:** AGAIN-ECOSYSTEM commit `24337c35`

## Position in AGAIN Ecosystem

```
Conductor Main ──► Infrastructure Again ──► InfrastructureResult
                           │
                      HOW / WHERE DOES
                      THE SYSTEM RUN?
```

INFRA-AGAIN is the **Infrastructure / Platform OS** in the AGAIN Ecosystem.

## Core Pipeline

```
InfrastructureRequest
        ↓
Provider-Neutral Requirement Model
        ↓
Provider Intelligence
        ↓
Dynamic Capability Registry
        ↓
Architecture / Change Planner
        ↓
Policy + Safety Gate (AIRLOCK)
        ↓
Approval Gate
        ↓
Execution Orchestrator
        ↓
Provider / Platform Adapter
        ↓
Observe / Validate
        ↓
Evidence
        ↓
InfrastructureResult
```

## Domain Model

### Provider × Platform Separation

**Provider (WHERE):** AWS, GCP, ON_PREM, PRIVATE_CLOUD
**Platform (HOW):** NATIVE_VM, KUBERNETES, OPENSHIFT_OCP, BARE_METAL

These are orthogonal dimensions. Any valid combination is possible:
- AWS + Native VM
- AWS + Kubernetes (EKS)
- AWS + OpenShift/OCP
- GCP + Kubernetes (GKE)
- On-Prem + OpenShift/OCP

OCP is a PLATFORM, not a provider.

### Execution Mode Ladder

```
LEVEL 0: PLAN_ONLY       — No mutation
LEVEL 1: SIMULATED       — API simulation
LEVEL 2: LOCAL_RUNTIME   — Real software locally
LEVEL 3: LOCAL_PRIVATE_CLOUD — Real private cloud locally
LEVEL 4: SANDBOX         — Real provider, isolated
LEVEL 5: CONTROLLED_REAL — Real provider, non-prod
LEVEL 6: PRODUCTION      — Real provider, production
```

### Safety / AIRLOCK

```
AUTO — Safe operations (read, plan, PLAN_ONLY, approved local lab)
ASK  — Requires approval (create resources, apply to sandbox, install deps)
BLOCK — Blocked by default (production mutation, sudo, secret exfiltration, hidden fallback)
```

## Component Architecture

```
src/infra_again/
├── contracts/         # Canonical contract type adapters
├── core/
│   └── domain.py      # Provider-neutral domain model
├── intelligence/
│   └── interface.py   # Provider intelligence interfaces
├── providers/
│   ├── interface.py   # Provider adapter interface
│   ├── aws/           # AWS adapter (PLAN_ONLY)
│   ├── gcp/           # GCP adapter (stub)
│   └── onprem/        # On-Prem adapter (stub)
├── platforms/
│   ├── interface.py   # Platform adapter interface
│   ├── kubernetes/    # K8s adapter (stub)
│   ├── openshift/     # OCP adapter (stub)
│   └── native/        # Native VM adapter (stub)
├── execution/
│   ├── orchestrator.py # Pipeline orchestration
│   └── lab.py         # Local lab registry
├── policy/            # Policy engine (future)
└── evidence/          # Evidence collection (future)
```

## Technology Stack

- **Language:** Python 3.11+
- **Schema/Validation:** Pydantic v2
- **Testing:** pytest + pytest-asyncio
- **IaC Integration:** OpenTofu/Terraform (subprocess, future)
- **Config Management:** Ansible (future)

## Key Design Decisions

1. **Provider-neutral core**: AWS/GCP/On-Prem are adapters, not the core
2. **Dynamic capability discovery**: Official sources → Registry → AI reasoning
3. **PLAN_ONLY first**: Safe execution path without credentials
4. **Explicit state machine**: DRAFT → ... → COMPLETED/FAILED/BLOCKED
5. **Evidence-first**: Every decision produces traceable evidence
6. **No fake success**: TruthStatus enforces honest reporting
