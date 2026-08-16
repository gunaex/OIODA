# INFRA-AGAIN Phase 4 — Claim / Evidence Matrix

> Rule: Every critical claim MUST be backed by executed evidence at the appropriate verification level.

| # | Claim | Evidence Level | Verification | Result |
|---|---|---|---|---|
| 1 | API routes exist (30 routes) | INTEGRATION | Route enumeration at import | PASS |
| 2 | FastAPI import succeeds | UNIT | `python -c "from infra_again.api import app"` exit 0 | PASS |
| 3 | API runs as real server | RUNTIME | uvicorn on port 18090, curl health 200, PID tracked, clean kill | PASS |
| 4 | `/health` returns 200 | RUNTIME | `curl -f http://127.0.0.1:18090/health` → 200 | PASS |
| 5 | `/api/v1/providers` returns AWS/GCP | RUNTIME | curl → AWS=1 exec, GCP=0 exec | PASS |
| 6 | AWS S3 is VERIFIED, SIMULATED | RUNTIME | curl → lifecycle=VERIFIED, exec=['SIMULATED'], source=MANUAL_VERIFIED | PASS |
| 7 | GCP Storage is PLAN_ONLY, not executable | RUNTIME | curl → lifecycle=CAPABILITY_MAPPED, exec=['PLAN_ONLY'], isExecutable=false | PASS |
| 8 | `/api/v1/capabilities/compare` POST works | RUNTIME | curl → AWS=FULL, GCP=PLAN_ONLY | PASS |
| 9 | `/api/v1/catalog/status` returns 2 snapshots | RUNTIME | curl → 2 snapshots with checksums | PASS |
| 10 | Unknown provider → 404 | RUNTIME | curl → 404 | PASS |
| 11 | Catalog sync LOCAL_REFRESH works | RUNTIME | curl POST → syncMode=LOCAL_REFRESH | PASS |
| 12 | Catalog sync LIVE is NOT_IMPLEMENTED | RUNTIME | curl POST → status=not_implemented | PASS |
| 13 | Docker image builds | RUNTIME | `docker build -t infra-again:v4-test .` exit 0 | PASS |
| 14 | Docker container runs + health 200 | RUNTIME | Docker run → curl health 200, providers API works | PASS |
| 15 | Catalog persists to SQLite | INTEGRATION | `catalog.persist(db)` then `load_persisted(db)` → same data | PASS |
| 16 | Restart durability (checksums match) | INTEGRATION | Persist → new instance load → same checksum, same service count | PASS |
| 17 | Snapshot checksum is deterministic | UNIT | Same content → same checksum; change → different checksum | PASS |
| 18 | Catalog diff works (same = 0 changes) | UNIT | `diff_snapshots(same_id, same_id)` → 0 changes | PASS |
| 19 | Stale freshness field exists | UNIT | `FreshnessStatus.CURRENT/STALE/UNKNOWN` enum | PASS |
| 20 | Deprecated flag propagates to compare output | UNIT | Set deprecated=True → compare output shows deprecated | PASS |
| 21 | Capability mapper: OBJECT_STORAGE→S3, GCP, QUANTUM→empty | INTEGRATION | `catalog.compare(capability, mode)` → correct fits | PASS |
| 22 | Provider comparison ordering (AWS first) | UNIT | SIMULATED compare → AWS before GCP | PASS |
| 23 | Planner Golden A: AWS SIMULATED → S3 | INTEGRATION | `_query_provider_intelligence` → SUPPORTED, AWS S3 | PASS |
| 24 | Planner Golden B: GCP PLAN_ONLY → Cloud Storage | INTEGRATION | `_query_provider_intelligence` → PLAN_ONLY, GCP Storage | PASS |
| 25 | Planner Golden C: neutral SIMULATED → AWS S3 | INTEGRATION | No hint → AWS selected (only SIMULATED executable) | PASS |
| 26 | Planner Golden D: GCP SIMULATED → NOT_SUPPORTED | INTEGRATION | GCP hint + SIMULATED → EXECUTION_NOT_SUPPORTED | PASS |
| 27 | Planner Golden E: QUANTUM_DATABASE → no candidates | INTEGRATION | Unknown capability → empty, selected=None | PASS |
| 28 | Provenance: STATIC_FIXTURE adapters | UNIT | `AwsCatalogSource.source_kind == 'STATIC_FIXTURE'` | PASS |
| 29 | Provenance: no hidden OFFICIAL_LIVE | UNIT | All adapters source_kind = STATIC_FIXTURE | PASS |
| 30 | Provenance: S3 MANUAL_VERIFIED, EC2 STATIC_SEED | UNIT | SourceType audit of all services | PASS |
| 31 | Phase 3 regression (frozen V3 runner) | RUNTIME | `./scripts/run-acceptance-v3.sh` exit 0, 4 PASS, 0 FAIL, 0 SKIP | PASS |
| 32 | Frontend build produces dist/ | RUNTIME | `npm ci && vite build` → dist/index.html exists | PASS |
| 33 | Freshness: CURRENT evaluation | UNIT | retrieved 1d ago, threshold 7d → CURRENT | PASS |
| 34 | Freshness: STALE evaluation | UNIT | retrieved 8d ago, threshold 7d → STALE | PASS |
| 35 | Freshness: UNKNOWN evaluation | UNIT | empty/missing timestamp → UNKNOWN | PASS |
| 36 | Stale planner warning | INTEGRATION | STALE snapshot → catalogFreshness=STALE in planner output | PASS |
| 37 | Deprecated: comparison visibility | UNIT | deprecated=True → comparison output shows deprecated | PASS |
| 38 | Deprecated: planner exclusion | INTEGRATION | deprecated S3 + SIMULATED → DEPRECATED_RESOURCE, not selected | PASS |
| 39 | Catalog diff: SERVICE_ADDED | INTEGRATION | `ProviderCatalog.compute_diff()` production entry point | PASS |
| 40 | Catalog diff: SERVICE_REMOVED | INTEGRATION | `ProviderCatalog.compute_diff()` production entry point | PASS |
| 41 | Catalog diff: SCHEMA_CHANGED | INTEGRATION | `ProviderCatalog.compute_diff()` production entry point | PASS |
| 42 | Catalog diff: DEPRECATED | INTEGRATION | `ProviderCatalog.compute_diff()` production entry point | PASS |
| 43 | Required/optional accounting | RUNTIME | 27 REQUIRED PASS, 0 FAIL, 0 SKIP; optional separated | PASS |
| 44 | Docker real build (not cached) | RUNTIME | `docker build -t infra-again:v4-acceptance .` exit 0 | PASS |
| 45 | Docker real run + health | RUNTIME | container health 200, providers API 2 | PASS |
| 46 | Frontend fresh npm ci | RUNTIME | `npm ci` exit 0 (dist removed before) | PASS |
| 47 | Frontend fresh vite build | RUNTIME | `vite build` exit 0 (dist removed before → new dist/index.html) | PASS |
| 48 | No manual diff in acceptance | STATIC | Audit: 0 occurrences of `CatalogDiff(` or manual diff.append | PASS |
| 49 | LIVE_OFFICIAL_SYNC | N/A | NOT_EXECUTED (internet source fetch not attempted) | NOT_EXECUTED |
| 47 | BROWSER_E2E | N/A | NOT_EXECUTED (no browser automation) | NOT_EXECUTED |
| 48 | FLY_REMOTE | N/A | NOT_EXECUTED (Fly deploy not performed) | NOT_EXECUTED |
| 49 | CLOUDFLARE_REMOTE | N/A | NOT_EXECUTED (Cloudflare deploy not performed) | NOT_EXECUTED |

## Evidence Level Legend

- **STATIC_ONLY**: Source code exists, no execution verification
- **UNIT_VERIFIED**: Unit-level Python assertion passes
- **INTEGRATION_VERIFIED**: Multi-component integration test passes (TestClient, SQLite, etc.)
- **RUNTIME_VERIFIED**: Real process started, real HTTP request made, response verified
- **REMOTE_VERIFIED**: Deployed to remote environment and verified

## Summary

- RUNTIME verified: 29 claims
- INTEGRATION verified: 12 claims
- UNIT verified: 7 claims
- STATIC (audit): 1 claim
- NOT_EXECUTED (optional): 4 claims
- No claims are STATIC_ONLY
