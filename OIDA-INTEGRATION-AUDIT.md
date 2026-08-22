# OIDA Independent Integration Audit & Recovery Pass

Audit date: 2026-08-22 (Asia/Bangkok)
Accepted baseline: `3e7aa05fcbe0ddb576354f4cec9dbc20479ebc2d`
Audited OIODA HEAD: `a08438ae2b49a75924136820b3979f5f265e2d7e` (`main`, clean before this pass)
Scope: PM Again, QA Again, Infra Again, OIDA gateway/web projection, and Document Again generation precheck.

This report is based on owning-service source, route registration, schemas/models, frontend source, gateway configuration, tests, and locally executable validation. It does not treat a rendered card or README claim as proof. The full machine-readable coverage matrix is [OIDA-INTEGRATION-AUDIT.csv](OIDA-INTEGRATION-AUDIT.csv).

## 1. Repository and runtime inventory

| Repository | Branch / HEAD | State at audit start | Remote | Runtime | Deployment target / discovered URL |
|---|---|---|---|---|---|
| OIODA | `main` / `a08438a` | clean | `github.com/gunaex/OIODA.git` | React/Vite shell; Python FastAPI gateway and vendored services | Cloudflare/Vercel-style web config; Fly `oida-gateway`, `sin`; production API default referenced as `api-oida.kanphong.com` |
| PM-AGAIN | `main` / `ec16f34` | clean | `github.com/gunaex/PM-Again` | FastAPI/SQLAlchemy + React/Vite | Fly `pmo-platform-backend`; OIDA vendored target `oida-pm.internal:8000` |
| QA-AGAIN | `main` / `23760b1` | clean | `github.com/gunaex/PM-QA-Again` | FastAPI/SQLAlchemy + React/Vite + TypeScript runner | Fly `qa-again-backend`; OIDA vendored target `oida-qa.internal:8000` |
| INFRA-AGAIN | `main` / `f2318b8` | clean | `github.com/gunaex/INFRA-AGAIN.git` | FastAPI + React/TypeScript; SQLite persistence; IaC/runner modules | Fly `infra-again`; OIDA vendored target `oida-infra.internal:8080` |
| DOCUMENT-AGAIN | `main` / `bed7196` | dirty (unrelated deleted Office temp files and untracked UX images) | no remote printed | FastAPI + React/Vite | OIDA vendored Fly `oida-document` |
| ACCOUNT-AGAIN | `master` / `90f3e0f` | clean | no remote printed | FastAPI | OIDA vendored Fly `oida-account` |
| CONDUCTOR-AGAIN | `master` / `1f0c46a` | clean | `github.com/gunaex/Conductor_Again.git` | FastAPI + React/Vite | OIDA vendored Fly `oida-conductor` |
| AGAIN-ECOSYSTEM | `main` / `0b48455` | dirty (two unrelated untracked governance files) | `github.com/gunaex/AGAIN-ECOSYSTEM.git` | documentation/contracts | no runtime |

Unrelated dirty files were not modified. OIODA vendors snapshots of all bounded services. The external repositories are the capability-discovery authorities for this audit; deployed OIODA uses its vendored snapshots.

## 2. Capability inventories

### PM_CAPABILITY_INVENTORY — PASS (source inventory)

The owning service supports substantially more than OIDA projects today:

- READ/WRITE/ACTION: projects, functions/workstreams, tasks, Gantt items, annotations, plan dates, actual overrides, board items, quick notes, linked note pages, resources, allocations, effort configuration/estimates, PM documents, whiteboards, and PM change requests.
- WORKFLOW/GOVERNANCE: task/board promotion, document review/sign-off, CR impact and approval submission, project archive, ecosystem delivery-work-package intake.
- ANALYTICS: dashboard, PM status, progress matrix/calendar, slippage, utilization, effort budget/summary, daily/weekly/monthly/phase-closure reports.
- EXPORT/INTEGRATION: XLSX import/export for core planning entities, ecosystem intake/status, PM/QA handoffs from implementation plans.

Evidence: `services/pm-again/backend/app/routers/*`, `models.py`, `schemas.py`, and standalone PM frontend. There is no single first-class “milestone” model; schedule truth is expressed through functions/tasks/Gantt/plan dates.

### QA_CAPABILITY_INVENTORY — PASS (source inventory)

- READ/WRITE/ACTION: projects, suites, revisions, cases/steps, cycles, results, evidence, annotations, defects, sign-offs, and quotas.
- WORKFLOW/GOVERNANCE: revision publish/clone, cycle lock/reopen, result review/history, evidence archive, cycle sign-off, ecosystem QA request/rerun/result.
- AUTOMATION: hybrid run lifecycle, provenance, runner events, manual checkpoint decisions, run evidence, finish; runner-token issue and standalone runner.
- ANALYTICS/EXPORT: dashboard, execution/detail/defect/evidence/revision/cycle/tester/readiness/signoff/storage reports; Excel and evidence ZIP exports.

Evidence: `services/qa-again/backend/app/routers/*`, `models.py`, `schemas.py`, and `runner/src/main.ts`. Variables/secrets are runner environment configuration, not a user-facing QA secrets vault.

### INFRA_CAPABILITY_INVENTORY — PASS (source inventory)

- READ/WRITE/ACTION: architecture design baselines, flow graph nodes/edges, simulation, feasibility, implementation plans, work packages/dependencies, execution packages/runs/evidence, environments, promotions, UAT, rollback, production readiness, and workspaces.
- WORKFLOW/GOVERNANCE: accept/freeze/request-change, plan approval, immutable approval gates, preflight, execution verification, promotion approval/reject/consume/verify, UAT sign-off, readiness evaluation.
- INTEGRATION/ANALYTICS: PM/QA implementation-plan handoffs, provider intelligence and capability comparison, provider catalog sync/snapshots, remote runner/task API.
- AI: AgainPilot and provider-assisted design/review exist, with deterministic gates around acceptance/execution.

Evidence: `services/infra-again/src/infra_again/{api,flow,implementation,execution,intelligence,visualization}`. The graph is a real node/edge flow model. Some generated design content explicitly uses `create_demo_flow()` when a user invokes generate; OIDA never invokes that action or uses it as an outage fallback.

## 3. Full capability coverage matrix

The 53-row matrix (22 PM, 15 QA, 16 Infra) is in `OIDA-INTEGRATION-AUDIT.csv` with every required column:

`Service, Domain, Capability, Owning Service Supports?, Owning API/Route, Owning UI, OIDA Backend Integration, OIDA Frontend Projection, OIDA Action Available, Real Data or Mock, Read Coverage, Write Coverage, Error Handling, Permission Handling, Status, Evidence, Required Fix`.

Human-readable coverage summary:

| Service | Complete | Partial | Missing | Unreachable / N/A | Principal gap |
|---|---:|---:|---:|---:|---|
| PM Again | 1 | 16 | 5 | 0 | Progress/schedule/effort details and several owner workflows are invisible; most read errors become empty data. |
| QA Again | 1 | 11 | 4 | 1 | Evidence, hybrid runner, sign-off, and exports are absent/unreachable; read errors frequently become empty data. |
| Infra Again | 2 | 5 | 5 | 4 | Only design/environment graph is projected; implementation/execution/governance surfaces are mostly invisible. |

Classification: project health, schedule, effort, QA status/evidence/defects, architecture, execution, and readiness are category **A** (must project). Task/result/link actions are selective **B**. Full editors/import/export/admin workflows are generally **C** (deep-link/delegate). Runner internals are **D**. A formal cross-service dependency snapshot contract is **E** until agreed.

## 4. End-to-end integration traces

### PM read/write

`PlanningPage/TasksPage → pmApi → /api/pm/{slug}/... → gateway /api prefix → PM router → SQLAlchemy models → JSON → React state`.

Task creates/updates/deletes persist in PM Again, then the page reloads PM truth. Board creates/promotions and note creates follow the same owner-persistence pattern. No inspected PM write stores PM truth in Document Again or an OIDA database.

### QA read/write

`QaSuites/QaCycles/QaDefects → qaApi → /api/qa/{slug}/... → gateway → QA router → QA database/evidence storage → JSON → React state`.

Suite/revision/case/cycle/result/defect actions persist in QA Again and refresh. OIDA does not write QA evidence into Document Again. Evidence and sign-off owner routes exist but are not projected.

### Infra read/binding

`InfraAgainPage → infraApi → /api/infra/... → gateway /api/v1 → Infra design/environment stores → JSON → React Flow`.

The selected Infra design ID is stored as a correlation pointer in Document Again project metadata. Architecture nodes/edges remain Infra truth. Before this pass, health incorrectly traced to `/api/v1/health` (404); fixed to `/health` in production and local proxy.

### Broken/half paths

- QA fallback resolution previously returned a manufactured `wp-<handoff>` slug even when no QA project existed. Pages then called a nonexistent project and often displayed an empty dataset. This pass retains the string only as a lookup hint and exposes no usable slug unless QA confirms it.
- Infra feasibility, execution runs, promotions, UAT, and readiness have API-client methods but no reachable UI projection.
- QA export URL methods exist but no clear reachable controls; direct URL navigation also requires attaching the ecosystem bearer token, so a plain anchor is insufficient.
- Document precheck stops at locally built `source_indicators`; it does not traverse gateway/adapters to PM/QA/Infra.

## 5. Mock, fallback, and duplicated-truth findings

`MOCK_DATA_IN_PRODUCTION = PARTIAL`.

- No OIDA PM/QA/Infra page was found substituting static project fixtures after a fetch failure.
- The more serious production masking pattern was `.catch(() => [])` / `.catch(() => null)` across many pages. That is not mock data, but it falsely presents outages/authorization failures as empty truth.
- Infra's owner-side explicit design generation calls `create_demo_flow()`. It is a real persisted generation operation, not an OIDA outage fallback, but the capability name should be made clearer by Infra Again.
- Document `services.py` contains a `demo_reference` flag for the known TCM seed; this is metadata, not a data fallback.

`DUPLICATED_BOUNDED_TRUTH = PARTIAL`.

- OIDA does not own a PM/QA/Infra database. PM/QA writes inspected go to the owning services.
- Document Again owns project correlation pointers (`pm_project_slug`, `qa_project_slugs`, `infra_design_id`), which is architecture-consistent.
- Infra Again also owns workspace current-design/plan/package pointers. Without a formal mapping between a Document project and an Infra workspace, there are two competing correlation mechanisms, though not two copies of architecture truth.
- PM Again contains a document workflow and PM change-request domain while Document Again is the ecosystem authority for governed documents and commercial CRs. OIDA correctly avoids exposing PM document sign-off as Document acceptance, but naming/ownership must remain explicit.

## 6. API contract drift and silent data loss

`API_CONTRACT_ALIGNMENT = PARTIAL`.

- Fixed: Infra health route root mismatch in both Fly gateway and Vite proxy.
- PM and QA client route paths match current router prefixes for the exposed capabilities.
- Infra business client routes match registered `/api/v1` endpoints and response envelopes (`designs`, `environments`).
- Infra graph projection consumes nodes/edges but drops checksums, revision provenance, feasibility, architecture status details, and most execution/governance metadata.
- PM pages drop dependencies implicit in Gantt/plan structures, detailed estimates/drivers, actual overrides, slippage and pagination/filter affordances.
- QA pages drop evidence metadata/annotations/history, defect linkage details, cycle history, hybrid provenance and runner state.
- The JavaScript client is untyped, so enum/field drift has no compile-time guard. The repair should use explicit runtime mappers or generated contract types rather than `any`.

## 7. Read/write parity and permissions

Displaying data was not counted as write coverage. The detailed matrix marks most owner CRUD/import/export operations partial or missing. Native OIDA actions are justified for high-frequency task, result, defect and binding work. Full suite editors, schedule import, provider catalog maintenance, runner-token issue, and Infra execution controls should be delegated unless a cross-service workflow requires orchestration.

Gateway authorization is deny-by-default. It strips spoofable identity headers, verifies the Account Again RS256 token, derives actor/tenant context and forwards it. Owner services retain their own permission dependencies. The UI still lacks consistent 401/403 presentation; `IntegrationState` now distinguishes those states for Infra, and the same pattern remains to be rolled through PM/QA reads.

## 8. Cross-service dependency and workload findings

`CROSS_SERVICE_PRECHECK = FAIL`.

`human.precheck()` calls `build_source_indicators(db, project)` against Document Again's database. For non-Document standards it reports `NO_SOURCE` when the local indicator is absent. It does not call PM schedule/wave ownership, QA readiness/evidence, or Infra design/source inventory. Therefore Migration Strategy and similar prechecks cannot prove authoritative dependency readiness. This pass intentionally does not mark them ready or copy bounded truth into Document Again.

Recommended contract: a read-only, versioned dependency snapshot assembled by OIDA/Conductor at request time, carrying authority, object ID, revision/checksum, retrieved-at, status and explicit unavailable/unauthorized states. Document Again should consume that snapshot as evidence without persisting a second business truth.

Current repeated-workload risks:

- users must open PM Again for progress matrix, slippage, detailed estimates and schedule editing;
- users must open QA Again for evidence, sign-off, hybrid runner and exports;
- users must open Infra Again for feasibility, implementation readiness, execution evidence and production readiness;
- document precheck cannot consume those facts, encouraging manual copy/paste into generation notes.

## 9. Remediation list

### P0

- No confirmed OIDA-owned bounded truth or fake CUSTOMER acceptance was found.
- The widespread empty-on-error pattern is capable of hiding auth/outage failures; treat any customer decision based on those empty states as unsafe until the P1 rollout is complete.

### P1

- **Fixed:** Infra health route contract.
- **Fixed:** Infra list/detail failures are visibly classified instead of replaced by empty counts.
- **Fixed:** unconfirmed derived QA slugs are no longer treated as real bindings.
- **Open:** roll honest error state through all PM/QA critical reads and project context probes.
- **Open:** project PM progress/schedule/effort and QA evidence/sign-off/hybrid status.
- **Open:** project Infra feasibility/implementation/execution/readiness.
- **Open:** implement the authoritative cross-service precheck snapshot contract.

### P2

- Make QA exports reachable using authenticated `fetch`/blob download.
- Project QA revision/result/evidence history and PM actual overrides.
- Add owner-service deep links from delegated capabilities.
- Add generated/runtime contract validation for JS adapters.

### P3

- Convenience import/export controls and secondary authoring actions.
- Cross-service trend views after the core truth/status contracts are stable.

## 10. Fixes implemented

1. Production gateway maps Infra `/api/infra/health` to owner `/health`, retaining `/api/v1` for business routes.
2. Local Vite proxy applies the same contract.
3. Added route-contract unit coverage for health, Infra business routes and PM routes.
4. Added reusable UI classification for `UNAUTHORIZED`, `FORBIDDEN`, `UNAVAILABLE`, `NOT_SUPPORTED`, and `ERROR`.
5. Infra workspace now displays owner failures and offers retry instead of converting them to zero environments/designs.
6. QA project discovery no longer promotes a guessed slug to a usable binding when QA Again did not return that project.

## 11. Tests and validation

Executed results:

- OIDA web lint: **PASS**, exit 0. The previously missing `oxlint` dev dependency was added; 47 pre-existing warnings remain (unused imports/variables, one duplicate object key and two unused expressions).
- OIDA production web build: **PASS**, Vite 8.2.1, 1,783 modules transformed. One non-blocking chunk-size warning remains.
- Gateway route contract: **PASS**, 3/3 tests.
- Gateway Python compile and `git diff --check`: **PASS**.
- PM Again vendored backend: **PASS**, 38/38 tests.
- QA Again vendored backend: **PASS**, 101 passed, 5 skipped.
- Infra Again vendored service: **PARTIAL**, 343 passed, 8 skipped, 18 failed. Every failure explicitly requires the external fakecloud/OpenTofu test environment and fails at `_require_fakecloud()`; no functional assertion ran in those 18 cases. Initial collection also required the documented `PYTHONPATH=src` layout.

Required interpretations:

- A build proves only compilation/bundling, not integration completeness.
- Browser and production validation remain `BLOCKED` unless executed with a real Account Again credential and live service data.
- No acceptance/sign-off will be created by this audit.

## 12. Final acceptance matrix

| Acceptance item | Result | Evidence |
|---|---|---|
| PM_CAPABILITY_INVENTORY | PASS | Owning backend routes/models/frontend inspected; matrix contains 22 PM rows. |
| PM_OIDA_READ_COVERAGE | PARTIAL | Tasks/planning/dashboard/board/notes/resources/effort/reports read; progress matrix/slippage/annotations/CR absent. |
| PM_OIDA_ACTION_COVERAGE | PARTIAL | Task CRUD, board create/promote and note create exist; broader owner actions delegated or absent. |
| QA_CAPABILITY_INVENTORY | PASS | Owning routes/models/runner/frontend inspected; matrix contains 15 QA rows. |
| QA_OIDA_READ_COVERAGE | PARTIAL | Suites/revisions/cases/cycles/results/defects/reports read; evidence/sign-off/hybrid absent. |
| QA_OIDA_ACTION_COVERAGE | PARTIAL | Core design/execution/defect actions exist; lifecycle/evidence/hybrid/export actions incomplete. |
| INFRA_CAPABILITY_INVENTORY | PASS | Registered flow/implementation/execution/promotion/provider/runner APIs inspected; matrix contains 15 Infra rows. |
| INFRA_OIDA_READ_COVERAGE | PARTIAL | Environments/design graph read; feasibility and implementation/execution/governance mostly not projected. |
| INFRA_OIDA_ACTION_COVERAGE | PARTIAL | Binding action only; owner authoring/execution appropriately delegated but deep links are absent. |
| MOCK_DATA_IN_PRODUCTION | PARTIAL | No OIDA static fallback found; silent empty fallback remains in PM/QA; owner generate uses explicit demo flow. |
| DUPLICATED_BOUNDED_TRUTH | PARTIAL | No OIDA domain DB; dual Document/Infra correlation pointers and overlapping PM document/CR concepts require boundary clarification. |
| API_CONTRACT_ALIGNMENT | PARTIAL | Exposed PM/QA routes align; Infra health fixed; extensive owner fields/capabilities remain unmapped. |
| CROSS_SERVICE_PRECHECK | FAIL | Document precheck reads local indicators only; no live PM/QA/Infra calls. |
| ERROR_STATE_INTEGRITY | PARTIAL | Gateway honest; Infra UI fixed; many PM/QA `.catch(() => [])` remain. |
| BUILD | PASS | Production Vite build completed; 1,783 modules transformed. |
| TESTS | PARTIAL | Gateway 3/3, PM 38/38, QA 101 pass/5 skip; Infra 343 pass/8 skip/18 fakecloud-blocked failures. |
| BROWSER_VALIDATION | BLOCKED | No browser automation tool/credentialed session available in this audit environment. |
| PRODUCTION_VALIDATION | BLOCKED | Real Account Again credentials and authorization to exercise production were not available. |

## 13. Remaining limitations and recommended next step

The system is not integration-complete. The highest-value next increment is an R17-compatible integration-hardening change (not R18): define a versioned OIDA/Conductor project-truth snapshot for PM schedule/effort, QA readiness/evidence/defects, and Infra architecture/implementation readiness; use it in Document precheck; and standardize typed unavailable/unauthorized/error envelopes. In parallel, finish the mechanical PM/QA error-state rollout and add contract tests against owner OpenAPI schemas.
