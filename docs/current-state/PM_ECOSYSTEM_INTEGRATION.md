# PM Again — Ecosystem Integration Status

**Status:** `ECOSYSTEM_INTEGRATION_READY` (local integration, not production-verified)
**Date:** 2026-08-12
**Predecessor:** [`PM_RUNTIME_DISCOVERY.md`](PM_RUNTIME_DISCOVERY.md) (`FUNCTIONAL_STANDALONE`, commit `ef0698e`)

## What changed

PM Again gained a canonical-contract-bound integration surface on top of its existing, preserved project-management product. Nothing described in the discovery doc's feature list was rebuilt, redesigned, or migrated.

| Area | What was added |
|---|---|
| Test foundation | pytest + isolated temp `DATA_DIR`, 38 tests, zero prior test files |
| Canonical contracts | All 11 AGAIN-ECOSYSTEM v1 schemas vendored (`app/contracts/vendored/`, pinned to commit `bf1237d`), `CanonicalContractValidator`, Pydantic bindings for `DeliveryWorkPackage`/`PMStatus` |
| Correlation/idempotency | `ExternalWorkReference` + `EvidenceReference` models, idempotent intake with payload-hash conflict detection |
| PMStatus | `pm_status_service.build_pm_status()` derives a real canonical `PMStatus` from `Task`/`BoardItem`/`GanttItem` state — never fabricates `estimatedCompletion`/`dependencies` |
| Conductor intake | `POST /api/ecosystem/delivery-work-packages` — service-token-authenticated, schema-validated, idempotent, maps to a PM `Project` + seed `Task` |
| Conductor status pull | `GET /api/ecosystem/pm-status?workPackageId=...` — service-authenticated lookup by the id Conductor actually holds |
| Account Again | `ecosystem_auth.py` — Account Again is entitlement-authoritative when `ECOSYSTEM_MODE=true`; local JWT auth never overrides it |
| Tenant isolation | `Project.tenant_id` / `User.tenant_id` (additive, nullable), `require_project_tenant_match` layered onto project/task/pm-status routes |
| Operator UI | `EcosystemSourceBadge` (dashboard, shown only for Conductor-originated projects), `EcosystemStatusIndicator` (header, real reachability probe) |
| Conductor-side | `pm_adapter.py` flipped `UNAVAILABLE` → `REAL_RUNTIME`; PM surfaced as a non-blocking, informational readiness input only |

## What did NOT change

- SQLite persistence, per-project DB isolation, Thai Business Day Engine, Function Point effort calculator, Progress Matrix, Gantt, reports, Excel import/export, draw.io whiteboards — all untouched.
- No AI provider execution was added (`NO_NEW_PM_AI_RUNTIME`).
- No LACC integration (no genuine PM AI requirement was found — none was invented).
- No database technology migration (still SQLite).
- No frontend rewrite — three small, additive components/functions only.

## PMStatus field mapping

See the docstring at the top of `backend/app/pm_status_service.py` for the exact canonical-field → PM-source mapping, including which fields are deliberately left unset (`estimatedCompletion`, `dependencies`) because PM Again has no real source for them today.

## Verification performed

- PM Again backend: 38/38 pytest passing, isolated temp DB, real `backend/data/` never touched by tests (confirmed via directory listing / mtime).
- PM Again frontend: `npm run build` and `npm run lint` clean (pre-existing warnings only).
- Conductor: full suite 129/130 passing at PM-E5 checkpoint (1 failure was an unrelated, pre-existing Ollama-availability flake in `test_e81_golden_deliberation.py`, confirmed to pass in isolation); focused regression subset (`test_dispatch_adapters.py`, `test_orchestration_domain.py`, `test_contracts.py`) 38 passed / 1 skipped (live PM Again not running) at the PM-E9 checkpoint.
- Golden flow (`backend/tests/test_golden_flow.py`): intake → real task state changes (Todo→InProgress→Done) → PMStatus reflects each change → blocker flow → idempotent replay → cross-tenant deny → invalid/missing token rejection → evidence chain, all exercised through PM Again's real code paths in one process, with Conductor's identity simulated via FastAPI dependency override (the same technique used throughout the PM-E4/E6 test suites) rather than a live three-process run.

## PM-E8 in-process golden = PARTIAL; PM-E10 live cross-process golden = PASS

The PM-E8 golden flow (above) proved every real code path but simulated Conductor's identity via a FastAPI dependency override rather than a live HTTP round-trip. PM-E10 closed that gap: **three real local processes** — Account Again (already running, port 8001), PM Again (started fresh, port 8000), Conductor Main (started fresh, port 8010) — all with `ECOSYSTEM_MODE=true`, exchanging real signed RS256 service JWTs verified against Account Again's live JWKS, driving a real `BusinessIntent → DeliveryRun → DeliveryWorkPackage → dispatch-pm → PMStatus → refresh-pm-status → readiness` flow through Conductor's own real orchestration API — no in-process overrides, no mocks.

**Status: `PM_LIVE_CROSS_PROCESS_STATUS=VERIFIED`.**

Live evidence chain (see the full PM-E10 report for exact HTTP transcripts):

- `businessIntentId=bi-9b5b916cbf14`, `correlationId=corr-2c580c91d5da`, `runId=run-c98a2c886c1c`, `workPackageId=wp-5b8df921e97e`
- Real Conductor → PM Again dispatch (`dispatchStatus: SENT`) created a real PM `Project` (`minimal-local-service-with-a-health-endpoint-and-tests`) + seed `Task`
- A real human task-state change (Todo → InProgress → Done) via PM Again's normal API was reflected in `PMStatus.projectStatus` on the very next live fetch, retrieved by Conductor through its own real `refresh-pm-status` endpoint
- A real `BoardItem` issue made `PMStatus.projectStatus = BLOCKED`; Conductor's real readiness computation still returned `READY_FOR_DELIVERY` (no engineering/infra/qa assigned in this run), proving PM's status is genuinely non-blocking/informational
- Idempotent replay (same `Idempotency-Key`, same payload) returned the existing mapping (`created: false`, same `externalWorkReferenceId`); a mismatched-payload replay under the same key returned `409`
- Three live negative tests: missing service token → 401; invalid service token → 403; a spoofed identity header alongside a valid token was ignored (only the signed JWT's `systemId` claim governs identity)
- Three live cross-tenant denials: a second real tenant reading the first tenant's project (404), reading its PMStatus (404), and Conductor attempting to dispatch the same `businessIntentId` under the second tenant (403) — all via real Account-Again-authorized requests, not overrides
- A tenant with no `PM_AGAIN` product entitlement was denied by Account Again's real entitlement engine (`PRODUCT_NOT_ENTITLED`)

Two genuine defects were found and fixed during this closure (both were real code paths that had never been exercised live before): (1) `DeliveryWorkPackage` intake used only the service token's own (often-null) registered tenant instead of the per-request `DeliveryRun` tenant — Conductor now forwards `X-Tenant-Id` per its own existing pattern; (2) `PMAgainClient` didn't fail closed on an Account-Again token-issuance failure (only on PM Again transport errors), which would have crashed instead of returning `None`/raising `PMAgainUnavailableError`. Both are fixed and regression-tested (PM Again 38/38, Conductor 130/130 full suite, 0 skipped).

Live-only test tenants (`pm-e10-golden-tenant`, `pm-e10-tenant-b`, `pm-e10-no-entitlement`) and their product entitlements remain in Account Again's live local DB, left in place as clearly-named test fixtures at the operator's direction — they touch no real tenant or project data. The PM Again and Conductor Main processes started for this closure were stopped afterward; their scratch data directories were temporary and are gone. Account Again itself was already running before this session and was left running.
