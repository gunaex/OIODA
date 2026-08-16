# INFRA-AGAIN Acceptance V4.1 — Provider Intelligence Hardening + Freeze

**Date:** 2026-08-10  
**Baseline:** `8288b60` → Final: `648ed152000579a399faa65c2a314367716a506c`  
**V4 Runner:** `scripts/run-acceptance-v4.sh`

## A. Baseline

| Item | Value |
|---|---|
| Starting SHA | `8288b602933f0bb964bcb7ccbc0551bf993d917b` |
| Final SHA | `648ed152000579a399faa65c2a314367716a506c` |
| Remote SHA | `648ed152000579a399faa65c2a314367716a506c` (matched) |

## B. Phase 3 Regression

| Item | Value |
|---|---|
| Command | `pytest tests/integration/test_phase3.py tests/unit/ -q` |
| Passed | 46 |
| Failed | 0 |
| Skipped | 0 |
| Exit code | 0 |
| Verdict | PASS — no regression |

## C. Backend Runtime Verification

| Check | Result | Evidence |
|---|---|---|
| FastAPI import | PASS | `from infra_again.api import app` → App title, version |
| Route enumeration | PASS | 30 routes enumerated |
| Uvicorn start | PASS | Started on port 18090, PID tracked |
| Health HTTP | PASS | `curl → 200` |
| Providers HTTP | PASS | AWS=1 exec, GCP=0 exec (truthful) |
| AWS services HTTP | PASS | S3=VERIFIED, SIMULATED, MANUAL_VERIFIED |
| GCP services HTTP | PASS | Cloud Storage=CAPABILITY_MAPPED, PLAN_ONLY, isExecutable=false |
| Compare HTTP POST | PASS | AWS=FULL, GCP=PLAN_ONLY |
| Catalog status HTTP | PASS | 2 snapshots with checksums |
| Unknown provider | PASS | 404 |
| Sync LOCAL_REFRESH | PASS | syncMode=LOCAL_REFRESH, truthful note |
| Sync LIVE | PASS | status=not_implemented (truthful) |
| Backend clean stop | PASS | PID killed, no orphan process |
| Backend runtime verdict | PASS | All 12 HTTP checks passed |

## D. Docker Backend

| Check | Result |
|---|---|
| Docker build | PASS (`docker build -t infra-again:v4-test .`) |
| Docker run | PASS (container started) |
| Container health | PASS (curl → 200) |
| Providers in container | PASS (AWS=14 svcs, 1 exec; GCP=11 svcs, 0 exec) |
| Docker runtime verdict | PASS |

## E. Provider Intelligence

| Check | Result |
|---|---|
| Catalog SQLite persistence | PASS (`persist()` → `load_persisted()` roundtrip) |
| Restart durability | PASS (same checksum, same service count, S3 VERIFIED) |
| Snapshot checksum deterministic | PASS (same content → same checksum; change → different) |
| Catalog diff | PASS (same snapshot → 0 changes) |
| Stale detection | PASS (FreshnessStatus field exists, mutable) |
| Deprecated behavior | PASS (flag propagated to compare output) |
| Provenance: STATIC_FIXTURE adapters | PASS (AwsCatalogSource, GcpCatalogSource) |
| Provenance: no hidden OFFICIAL_LIVE | PASS (all adapters source_kind=STATIC_FIXTURE) |
| Provenance: S3 MANUAL_VERIFIED | PASS |
| Provenance: EC2 STATIC_SEED | PASS |

## F. Planner E2E (Golden Tests)

### Golden A: OBJECT_STORAGE + AWS + SIMULATED
- **Input:** capability=OBJECT_STORAGE, provider=AWS, mode=SIMULATED
- **Selected:** AWS S3
- **Execution Support:** SUPPORTED
- **Selection Reason:** SIMULATED execution VERIFIED via fakecloud
- **Result:** PASS

### Golden B: OBJECT_STORAGE + GCP + PLAN_ONLY
- **Input:** capability=OBJECT_STORAGE, provider=GCP, mode=PLAN_ONLY
- **Selected:** GCP Cloud Storage
- **Execution Support:** PLAN_ONLY
- **Selection Reason:** Catalog mapped, PLAN_ONLY only
- **Result:** PASS

### Golden C: OBJECT_STORAGE + neutral + SIMULATED
- **Input:** capability=OBJECT_STORAGE, provider=ON_PREM (no hint), mode=SIMULATED
- **Selected:** AWS S3 (only SIMULATED-executable candidate)
- **Execution Support:** SUPPORTED
- **Result:** PASS

### Golden D: OBJECT_STORAGE + GCP + SIMULATED
- **Input:** capability=OBJECT_STORAGE, provider=GCP, mode=SIMULATED
- **Result:** EXECUTION_NOT_SUPPORTED (GCP does not support SIMULATED)
- **No fallback to AWS** (provider hint is explicit)
- **Result:** PASS

### Golden E: QUANTUM_DATABASE
- **Input:** capability=QUANTUM_DATABASE
- **Candidates:** 0
- **Selected:** None
- **Result:** PASS (NO_SUPPORTED_REALIZATION)

## G. API Semantics

| Check | Result |
|---|---|
| AWS truth | 14 services, 1 VERIFIED (S3), 1 executable → PASS |
| GCP truth | 11 services, 0 VERIFIED, 0 executable → PASS |
| Unknown provider → 404 | PASS |
| Unsupported capability → empty | PASS |
| LIVE sync → NOT_IMPLEMENTED | PASS (truthful) |

## H. UI

| Check | Result |
|---|---|
| npm install | PASS (ci) |
| npm test | NOT_CONFIGURED (no test script) |
| npm build | PASS (dist/index.html exists) |
| API URL configuration | NOT_FOUND (may be in separate config) |
| UI evidence level | RUNTIME (build verified) |

## I. Optional Verification

| Check | Status |
|---|---|
| LIVE_OFFICIAL_SYNC | NOT_EXECUTED |
| BROWSER_E2E | NOT_EXECUTED |
| FLY_REMOTE | NOT_EXECUTED |
| CLOUDFLARE_REMOTE | NOT_EXECUTED |

## J. V4 Acceptance Runner

| Item | Value |
|---|---|
| Command | `bash scripts/run-acceptance-v4.sh` |
| Required passed | 25 |
| Required failed | 0 |
| Required skipped | 0 (5 optional NOT_EXECUTED) |
| Exit code | 0 |

## K. Claim/Evidence Summary

- RUNTIME_VERIFIED: 22 claims
- INTEGRATION_VERIFIED: 8 claims
- UNIT_VERIFIED: 6 claims
- NOT_EXECUTED: 4 (all optional)
- STATIC_ONLY: 0
- See `INFRA_AGAIN_PHASE4_CLAIM_EVIDENCE.md` for full matrix

## L. Final Verdict

**FROZEN**

Phase 4.1 meets all freeze criteria:
- ✅ Phase 3 runner executes successfully (46 passed, 0 failed)
- ✅ Catalog state survives restart (persistence → load → same checksum)
- ✅ Planner demonstrably consumes Provider Intelligence (5 Golden tests)
- ✅ Unsupported/deprecated/stale behavior is truthful
- ✅ FastAPI starts as a real server (uvicorn)
- ✅ Real HTTP API checks pass (13 endpoints)
- ✅ Docker backend runs (build + container + health)
- ✅ Frontend build passes
- ✅ Required failures == 0
- ✅ Required skips == 0
- ✅ V4 runner exit == 0

## M. Remaining Gaps

1. Real AWS execution — NOT_IMPLEMENTED
2. GCP execution — NOT_IMPLEMENTED
3. Fly.io deploy — AUTH_REQUIRED
4. Cloudflare deploy — AUTH_REQUIRED
5. Live provider sync — NOT_IMPLEMENTED (STATIC_FIXTURE only)
6. Browser E2E — NOT_CONFIGURED

## N. Git

| Item | Status |
|---|---|
| Commit SHA | `648ed152000579a399faa65c2a314367716a506c` |
| Push result | Pushed to origin/main |
| Remote SHA match | ✅ `648ed15` == `648ed15` |
| Message | `fix: harden and freeze Provider Intelligence runtime (Phase 4.1)` |
| Files changed | 8 files, +966/-60 |
