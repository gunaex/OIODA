# INFRA-AGAIN Acceptance Tests V2

**Version:** 2.0  
**Date:** 2026-08-09  
**Phase:** 2A — Persistent Safe Local Execution + fakecloud

## Test Results

| # | Gate | Expected | Result | Evidence |
|---|---|---|---|---|
| 1 | Phase 0/1 regression | PASS | PASS | 55/55 tests pass |
| 2 | Build/import | PASS | PASS | All imports resolve |
| 3 | Unit tests | PASS | PASS | 35 unit tests |
| 4 | Canonical contract conformance | PASS | PASS | 11 tests |
| 5 | Provider-neutral core preserved | PASS | PASS | No AWS SKUs in core |
| 6 | Provider ≠ Platform preserved | PASS | PASS | Tests verify separation |
| 7 | Ownership safety | PASS | PASS | 6 ownership tests |
| 8 | SQLite persistence | PASS | PASS | RunStore CRUD, transitions |
| 9 | Restart survival | PASS | PASS | State+resources survive reload |
| 10 | Illegal transition protection | PASS | PASS | DRAFT→COMPLETED blocked |
| 11 | fakecloud detected/installed | PASS | PASS | v0.44.9, probe READY |
| 12 | Real SIMULATED apply | PASS | PASS | S3 bucket created via boto3 |
| 13 | Observe after apply | PASS | PASS | list_buckets confirms creation |
| 14 | Desired vs observed validation | PASS | PASS | Match detection works |
| 15 | Failure path | PASS | PASS | Validation fails on nonexistent resource |
| 16 | Evidence persistence | PASS | PASS | .ai/infra-runs/ + SQLite evidence |
| 17 | Idempotency | PASS | PASS | idempotency key prevents duplicates |
| 18 | Owned cleanup (AUTO destroy) | PASS | PASS | Owned ephemeral ISOLATED = AUTO |
| 19 | Non-owned destroy prevented | PASS | PASS | Different run/SHARED = ASK |
| 20 | No AWS credentials required | PASS | PASS | fakecloud uses dummy creds |
| 21 | No real AWS fallback | PASS | PASS | SIMULATED stays on fakecloud |
| 22 | Production mutation blocked | PASS | PASS | PRODUCTION apply = BLOCKED |
| 23 | Canonical InfrastructureResult | PASS | PASS | Valid result with evidence |
| 24 | State transition history | PASS | PASS | All transitions logged |
| 25 | Resource ownership metadata | PASS | PASS | managedBy, createdByRunId, ephemeral, targetScope |

## Detailed Results

### 7. Ownership Safety (6 tests)
- `test_auto_destroy_allowed` — owned, ephemeral, ISOLATED, same run → AUTO ✓
- `test_auto_destroy_blocked_different_run` — different run → blocked ✓
- `test_auto_destroy_blocked_shared` — SHARED scope → blocked ✓
- `test_auto_destroy_blocked_not_ephemeral` — non-ephemeral → blocked ✓
- `test_auto_destroy_blocked_not_managed` — different manager → blocked ✓
- `test_store_can_auto_destroy` — store-level enforcement ✓

### 8. SQLite Persistence (7 tests)
- Run creation/retrieval ✓
- State transition valid ✓
- State transition illegal blocked ✓
- Restart survival (state + transitions preserved) ✓
- Idempotency key lookup ✓
- `can_transition()` helper ✓
- Resource registration + ownership query ✓

### 9. Restart Survival
Run store reload preserves:
- runId ✓
- correlationId ✓
- state ✓
- state transition history ✓
- owned resources ✓

### 12. Real SIMULATED Apply
- fakecloud v0.44.9 started
- S3 bucket created via boto3 against `http://localhost:4566`
- ChangeSet records CREATE action with resource ID
- No real AWS used

### 13. Observe After Apply
- `list_buckets()` confirms bucket exists
- Observation data includes endpoint, timestamp, resource count
- Resources registered with ownership metadata

### 14. Desired vs Observed Validation
- ValidationResult.matches = True when resource found
- ValidationResult.matches = False when resource not found
- Drift detection flag set correctly

### 15. Failure Path
- Validating nonexistent resource → matches=False ✓
- Error captured in validation result ✓
- Does not falsely claim success ✓

### 19. Non-Owned Destroy
- Policy returns ASK for non-owned resources
- Policy returns BLOCK for production destroy
- Policy returns AUTO only for owned+ephemeral+ISOLATED+same_run

## Execution Fidelity

```
fakecloud S3 API Compatibility:  PASS
Real AWS Provisioning:           NOT_TESTED
Production Readiness:            NOT_VERIFIED
```

## Verdict

**ACCEPTED**

All 25 gates PASS. Phase 2A delivers:
- Ownership-aware destroy safety
- SQLite persistence with state machine enforcement
- Restart/resume survival
- Real fakecloud SIMULATED execution (apply → observe → validate → destroy)
- Evidence persistence (.ai/infra-runs/ + DB)
- Idempotency
- AIRLOCK policy with ownership context
- No regression (55 existing tests pass)

One honest limitation: SIMULATED tests require fakecloud running (2 tests skip when offline).
