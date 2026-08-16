# INFRA-AGAIN Acceptance Tests V2B

**Version:** 2B
**Date:** 2026-08-10
**Phase:** 2B — OpenTofu Execution Integration

## Acceptance Matrix

| # | Gate | Required | Result |
|---|---|---|---|
| 1 | Phase 0/1 regression | PASS | PASS |
| 2 | Phase 2A regression | PASS | PASS |
| 3 | OpenTofu detected | PASS | PASS (v1.12.5) |
| 4 | OpenTofu version captured | PASS | PASS |
| 5 | AWS provider version captured | PASS | v5.100.0 |
| 6 | IaC workspace isolated | PASS | PASS |
| 7 | Deterministic HCL generation | PASS | PASS |
| 8 | No provider-specific leakage into core | PASS | PASS |
| 9 | `tofu fmt` | PASS | PASS |
| 10 | `tofu init` | PASS | PASS |
| 11 | `tofu validate` | PASS | PASS |
| 12 | Real `tofu plan` | PASS | PASS |
| 13 | Saved plan artifact | PASS | PASS |
| 14 | Machine-readable plan evidence | PASS | PASS |
| 15 | Policy gate before apply | PASS | PASS |
| 16 | Plan checksum verified | PASS | PASS |
| 17 | Real `tofu apply` | PASS | PASS |
| 18 | fakecloud actually mutated | PASS | PASS |
| 19 | Observe-after-apply | PASS | PASS |
| 20 | Desired vs observed | PASS | PASS |
| 21 | InfrastructureResult | PASS | PASS |
| 22 | OpenTofu state reference persisted | PASS | PASS |
| 23 | IaC state not duplicated by Infra Again | PASS | PASS |
| 24 | Request identity survives restart | PASS | PASS |
| 25 | Apply restart → reconciliation | PASS | PASS |
| 26 | Idempotency/no duplicate apply | PASS | PASS |
| 27 | Invalid HCL prevents apply | PASS | PASS |
| 28 | Plan failure prevents apply | PASS | PASS |
| 29 | Checksum mismatch blocks apply | PASS | PASS |
| 30 | Apply failure propagates | PASS | PASS |
| 31 | Observation mismatch fails | PASS | PASS |
| 32 | Ownership-safe cleanup | PASS | PASS |
| 33 | No real AWS fallback | PASS | PASS |
| 34 | No real AWS credentials required | PASS | PASS |
| 35 | Evidence complete | PASS | PASS |
| 36 | Proposed architecture generated | PASS | PASS |
| 37 | Planned architecture generated | PASS | PASS |
| 38 | Observed architecture generated | PASS | PASS |
| 39 | Before/After diff generated | PASS | PASS |
| 40 | Structured graph model | PASS | PASS |
| 41 | Mermaid human-readable diagram | PASS | PASS |
| 42 | Planned resource not shown as observed | PASS | PASS |
| 43 | After view based on provider observation | PASS | PASS |
| 44 | Missing resource visible | PASS | PASS |
| 45 | Required skips | 0 | 0 |
| 46 | Required failures | 0 | 0 |
| 47 | Runner exit | 0 | 0 |

## Environment

| Component | Version |
|---|---|
| OpenTofu | v1.12.5 (darwin_arm64) |
| AWS Provider | v5.100.0 |
| fakecloud | v0.44.9 |
| Python | 3.11.15 |
| S3 addressing | Path-style (`s3_use_path_style = true`) |

## Test Count

**110 passed, 0 failed, 0 skipped**

## Architecture Visualization

Generated artifacts per run:
- `architecture-proposed.json` — capability-level PROPOSED graph
- `architecture-planned.json` — provider-resolved PLANNED graph
- `architecture-observed.json` — actual OBSERVED graph
- `architecture-diff.json` — Before/After diff
- `architecture-before-after.md` — Mermaid human-readable diagram

## Verdict

**ACCEPTED**

Phase 2B delivers OpenTofu execution integration with:
- Deterministic HCL generation from InfrastructurePlan
- Full pipeline: fmt → init → validate → plan → apply
- Machine-readable plan evidence
- Architecture visualization (proposed/planned/observed/diff/Mermaid)
- No real AWS fallback
- All existing regression tests pass
