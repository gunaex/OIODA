# INFRA-AGAIN Acceptance Tests V2A.1 — HARDENED

**Version:** 2A.1
**Date:** 2026-08-09
**Phase:** 2A.1 — Correctness Fix + Deterministic Acceptance + Freeze

## Idempotency Bugs Found & Fixed

| Bug | Severity | Fix |
|---|---|---|
| EXECUTING returned SUCCESS | CRITICAL | Returns PARTIAL + in-progress evidence |
| OBSERVING returned SUCCESS | CRITICAL | Returns PARTIAL + in-progress evidence |
| VALIDATING returned SUCCESS | CRITICAL | Returns PARTIAL + in-progress evidence |
| No persisted result for COMPLETED | MEDIUM | `persist_final_result()` stores exact JSON |
| Rebuilt result on duplicate | MEDIUM | Returns persisted `final_result` from DB |

## Destroy Ownership Bypass Removed

| Bypass | Action |
|---|---|
| `is_isolated_lab` shortcut | REMOVED — destroy is ownership-only |
| `target.mode in (SIMULATED, LOCAL_RUNTIME)` shortcut | REMOVED |
| Missing ownership → AUTO | FIXED → ASK |
| Unknown ownership → infer | FIXED → ASK (never infer) |

Destroy AUTO requires ALL of:
- `managedBy == INFRA_AGAIN`
- `createdByRunId == currentRunId`
- `ephemeral == true`
- `targetScope == ISOLATED`

## Acceptance Matrix

| # | Gate | Expected | Result |
|---|---|---|---|
| 1 | Phase 0/1 regression | PASS | PASS (78 passed, 0 skipped, 0 failed) |
| 2 | Phase 2A regression | PASS | PASS |
| 3 | Build/import | PASS | PASS |
| 4 | Canonical contract conformance | PASS | PASS |
| 5 | Idempotent COMPLETED → persisted result | PASS | PASS |
| 6 | Idempotent EXECUTING → not SUCCESS | PASS | PASS |
| 7 | Idempotent OBSERVING → not SUCCESS | PASS | PASS |
| 8 | Idempotent VALIDATING → not SUCCESS | PASS | PASS |
| 9 | Idempotent FAILED → remains FAILED | PASS | PASS |
| 10 | No duplicate mutation on duplicate key | PASS | PASS |
| 11 | Owned+ephemeral+ISOLATED+same_run → AUTO | PASS | PASS |
| 12 | Different run → ASK | PASS | PASS |
| 13 | managedBy != INFRA_AGAIN → ASK | PASS | PASS |
| 14 | ephemeral=false → ASK | PASS | PASS |
| 15 | SHARED → ASK | PASS | PASS |
| 16 | EXTERNAL → ASK | PASS | PASS |
| 17 | UNKNOWN → ASK | PASS | PASS |
| 18 | Missing ownership → ASK | PASS | PASS |
| 19 | SIMULATED non-owned → ASK | PASS | PASS |
| 20 | LOCAL_RUNTIME non-owned → ASK | PASS | PASS |
| 21 | Production owned → BLOCK | PASS | PASS |
| 22 | ASK policy → provider.destroy() NOT called | PASS | PASS |
| 23 | BLOCK policy → provider.destroy() NOT called | PASS | PASS |
| 24 | SQLite persistence | PASS | PASS |
| 25 | Final result persistence & retrieval | PASS | PASS |
| 26 | Full restart context (runId, target, plan, resources) | PASS | PASS |
| 27 | EXECUTING restart → REQUIRES_RECONCILIATION | PASS | PASS |
| 28 | fakecloud startup | PASS | PASS |
| 29 | Real S3 simulated apply | PASS (acceptance) | PASS |
| 30 | Observe actual fakecloud state | PASS | PASS |
| 31 | Desired vs observed validate | PASS | PASS |
| 32 | Validation failure → non-SUCCESS | PASS | PASS |
| 33 | Owned cleanup (AUTO destroy) | PASS | PASS |
| 34 | Evidence persistence (.ai/infra-runs/) | PASS | PASS |
| 35 | Simulation fidelity truthful | PASS | PASS |
| 36 | Acceptance runner ZERO skips | PASS | PASS |
| 37 | Acceptance runner ZERO failures | PASS | PASS |

## fakecloud Runtime

| Attribute | Value |
|---|---|
| Version | 0.44.9 |
| Install | Homebrew (`brew install fakecloud`) |
| License | AGPL-3.0 |
| Endpoint | `http://localhost:4566` |
| Service used | S3 |
| Fidelity | AWS API simulated: VERIFIED; Real AWS: NOT_TESTED; Production: NOT_VERIFIED |

## Schema

RunStore has **5 tables** (corrected from previous report of 6):
1. `runs` — execution runs (includes `final_result` column)
2. `state_transitions` — transition history
3. `resources` — owned resource metadata
4. `evidence_items` — evidence references
5. `apply_log` — apply/destroy operation log

## Verdict

**FROZEN**

All 37 gates PASS. Phase 2A.1 delivers:

- Truthful idempotency: active runs never return false SUCCESS
- Exact persisted result retrieval for COMPLETED runs
- Ownership-only destroy: AUTO only with all 4 ownership conditions
- Missing/unknown ownership → ASK (never AUTO)
- Restart from EXECUTING → REQUIRES_RECONCILIATION
- Full context survival on restart
- Validation failure → FAILED run state
- Deterministic acceptance runner with zero required skips
- No Homebrew dependency in core code

## Phase Status

```
INFRA-AGAIN Phase 0/1    ACCEPTED
INFRA-AGAIN Phase 2A     FROZEN
```

Persistent Safe SIMULATED AWS Execution Baseline: **FROZEN**

Real AWS remains: **NOT_TESTED**

## Next Build

**Phase 2B — OpenTofu Integration**
