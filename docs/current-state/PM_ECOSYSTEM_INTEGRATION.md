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

## Known limitation: golden flow is not a live three-process run

Only Account Again was confirmed running locally during this session (port 8001). PM Again and Conductor Main were not started as live servers together, and provisioning real RS256 service credentials against the already-running Account Again instance without user-provided credentials was out of scope for this session (see security hygiene requirements in the integration task). The golden flow above proves every real code path — contract validation, idempotency, tenant enforcement, PMStatus derivation from genuine state changes — but not the literal live HTTP round-trip between three separately-running processes. `docs/architecture/PM_CONDUCTOR_BOUNDARY.md` documents exactly what a live run would additionally require.
