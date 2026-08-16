# INFRA-AGAIN Phase 3.1 — Freeze + Runner Architecture

**Date:** 2026-08-10  
**Baseline:** `3135e69` → `(current)`

## Architecture: Control Plane / Execution Plane

```
Cloudflare Frontend (React + Vite)
        │
        ▼ HTTPS
Fly.io Control Plane (FastAPI)
  ├── Intent, Plan, Policy, Approval
  ├── Run State, Evidence Index
  ├── Capability Registry
  ├── Architecture Graph
  └── Runner API
        │
        │ outbound HTTPS (runner → control)
        ▼
Execution Plane (Infra Again Runner)
  ├── OpenTofu, kubectl, kind, minikube, CRC
  ├── Provider APIs
  └── Local infrastructure
```

Control Plane ≠ Execution Plane. Fly.io does NOT run local tools.

## Phase 3 Freeze Gates

| Gate | Result |
|---|---|
| Phase 0/1 regression | PASS |
| Phase 2A regression | PASS |
| Phase 2B regression (OpenTofu + SHA-256) | PASS |
| fakecloud Golden E2E | PASS |
| kind Golden E2E | PASS |
| kind failure truth | PASS |
| Kubernetes observe/validate | PASS |
| Capability Registry truth | PASS |
| API acceptance | PASS |
| UI build | PASS |
| Deterministic runner | PASS |
| Runner domain models | PASS |
| Runner capability detection | PASS |
| Runner registration | PASS |
| Runner heartbeat | PASS |
| Task queue/lease | PASS |
| Lease idempotency | PASS |
| Control/Execution separation | PASS |
| Runner visibility in UI | PASS |
| Required failures | 0 |
| Required skips | 0 |

## Status

```
INFRA-AGAIN Phase 0/1  ACCEPTED
INFRA-AGAIN Phase 2A   FROZEN
INFRA-AGAIN Phase 2B   FROZEN
INFRA-AGAIN Phase 3    FROZEN

Runner Architecture    ACCEPTED
Fly Backend            BUILD_READY / AUTH_REQUIRED
Cloudflare Frontend    BUILD_READY / AUTH_REQUIRED

minikube               NOT_INSTALLED
CRC                    NOT_INSTALLED
GCP                    NOT_IMPLEMENTED
Real AWS               NOT_TESTED
```
