# INFRA-AGAIN Acceptance Tests V2B.1 — HARDENED / FROZEN

**Version:** 2B.1
**Date:** 2026-08-10
**Phase:** 2B.1 — OpenTofu Hardening + Integrity + Final Freeze

## Acceptance Matrix

| # | Gate | Required | Result |
|---|---|---|---|
| 1 | Phase 0/1 regression | PASS | PASS |
| 2 | Phase 2A regression | PASS | PASS |
| 3 | Phase 2B regression | PASS | PASS |
| 4 | OpenTofu detected | PASS | v1.12.5 |
| 5 | OpenTofu exact version recorded | PASS | 1.12.5 |
| 6 | AWS provider exact version recorded | PASS | v5.100.0 |
| 7 | Lock file produced | PASS | `.terraform.lock.hcl` |
| 8 | Lock file checksum recorded | PASS | HCL checksum |
| 9 | Reproducible provider selection | PASS | `~> 5.0` + lock file |
| 10 | Configuration checksum | PASS | SHA-256 |
| 11 | Plan full SHA-256 checksum | PASS | Full 64-char hex |
| 12 | Approved plan checksum persisted | PASS | `iac_approved_plan_sha256` |
| 13 | Applied plan checksum persisted | PASS | `iac_applied_plan_sha256` |
| 14 | Approved == Applied checksum | PASS | Before-apply verification |
| 15 | Tampered plan blocked | PASS | Checksum mismatch → BLOCK |
| 16 | Cross-run plan blocked | PASS | Path containment enforced |
| 17 | Saved-plan-only apply | PASS | `tofu apply <saved-plan>` |
| 18 | Real tofu apply against fakecloud | PASS | S3 bucket created |
| 19 | Provider observe after apply | PASS | `list_buckets()` confirms |
| 20 | Apply success + observe mismatch → FAILED | PASS | Bucket deleted before observe |
| 21 | FAILED InfrastructureResult | PASS | `status = FAILED` |
| 22 | FAILED run state | PASS | `ExecutionState.FAILED` |
| 23 | Visualization planned graph | PASS | `architecture-planned.json` |
| 24 | Visualization observed graph | PASS | `architecture-observed.json` |
| 25 | Missing resource shown as MISSING | PASS | Diff shows MISSING |
| 26 | AFTER view based on provider observation | PASS | Not on tfstate |
| 27 | Architecture diff truthful | PASS | MATCH/MISSING/UNEXPECTED |
| 28 | Restart during apply reconciliation | PASS | `REQUIRES_RECONCILIATION` |
| 29 | No duplicate apply | PASS | Idempotency preserved |
| 30 | Ownership safety | PASS | INFRA_AGAIN tags |
| 31 | No real AWS fallback | PASS | All endpoints localhost:4566 |
| 32 | No real AWS credentials required | PASS | Dummy creds only |
| 33 | Evidence complete | PASS | plan-integrity.json + all artifacts |
| 34 | Required failures | 0 | 0 |
| 35 | Required skips | 0 | 0 |
| 36 | Acceptance runner exit | 0 | 0 |

## Environment

| Component | Version |
|---|---|
| OpenTofu | v1.12.5 (darwin_arm64) |
| AWS Provider | v5.100.0 (hashicorp/aws) |
| Provider constraint | `~> 5.0` + `.terraform.lock.hcl` |
| fakecloud | v0.44.9 |
| Python | 3.11.15 |

## Plan Integrity

| Field | Value |
|---|---|
| Checksum algorithm | SHA-256 (full 64-char hex) |
| Plan artifact path | `.ai/infra-runs/<RUN-ID>/iac/tfplan` |
| Path containment | Must be within run's iac/ directory |
| Approved checksum stored | `iac_approved_plan_sha256` |
| Applied checksum verified | Compared before `tofu apply` |
| Mismatch behavior | BLOCKED, no apply |

## Test Count

**123 passed, 0 failed, 0 skipped**

## Verdict

**FROZEN**

All 36 gates PASS. Phase 2B.1 delivers:
- Full SHA-256 plan integrity with approved/applied checksum enforcement
- Tampered plan detection → BLOCK
- Cross-run plan path containment
- Apply-success/observe-mismatch → FAILED E2E proof
- Visualization failure truth (MISSING, UNEXPECTED, MATCH)
- Restart/reconciliation during IAC_APPLYING
- No real AWS fallback — all endpoints routed to localhost:4566

## Phase Status

```
INFRA-AGAIN Phase 0/1     ACCEPTED
INFRA-AGAIN Phase 2A      FROZEN
INFRA-AGAIN Phase 2B      FROZEN

Real AWS                 NOT_TESTED
GCP                      NOT_IMPLEMENTED
Kubernetes               NOT_IMPLEMENTED
OpenShift/OCP            NOT_IMPLEMENTED
Dynamic Catalog          NOT_IMPLEMENTED
```
