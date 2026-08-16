# OIDA WORKSPACE — Architecture Decision (R0)

Date: 2026-08-16
Program: OIDA OS (Oops!...I Did It Again) — Unified Project Delivery Workspace
Internal architecture: AGAIN Ecosystem (unchanged service boundaries)

---

## 1. Decision

**OPTION B — a dedicated `OIDA-WORKSPACE` frontend shell** that composes the
existing AGAIN services over HTTP.

It is a **stateless presentation layer**. It owns no domain truth, no shared
database, and no orchestration logic. Every fact it shows is read from, and
every action it performs is delegated to, the authoritative backend service.

```
                    ┌──────────────────────────────┐
                    │   OIDA OS  (OIDA-WORKSPACE)   │  human-facing product
                    │  React 19 · Vite · React Router│
                    └──────┬───────┬────────┬───────┘
              /api/da/*    │       │        │        /api/account/*
   ┌──────────────┐  /api/pm/* │   /api/qa/* │  /api/conductor/*
   ▼              ▼            ▼            ▼            ▼
 Document Again  PM Again   QA Again   Conductor    Account Again
 (design truth) (exec truth)(verif truth)(orchestration)(identity truth)
```

## 2. Why Option B (and not Option A)

| Criterion | Option A: evolve DOCUMENT-AGAIN frontend | Option B: dedicated shell |
|---|---|---|
| Code coupling | High — its pages are coupled to a single `/api` and one backend | Low — shell is a proxy/composition layer |
| Routing | HashRouter, single-backend, no login page | BrowserRouter, `/projects/:id/...`, built for multi-backend |
| Authentication | local `X-Actor` header only (no login) | One login screen that federates to each service's own session |
| Component reuse | Would drag PM/QA UIs into the document authority UI | Thin pages over each service's real API; zero reuse risk |
| Deployment | Risky to the working document authority | New static build + path-based reverse proxy |
| Migration risk | High (touches the production document workflow) | Minimal (services untouched) |
| Maintainability | One big app spanning 5 domains | Shell stays thin; each service UI remains standalone for admin |

**Conclusion:** Option B is the smallest safe architecture. Document Again stays
the document/design authority with its own UI intact for deep editing. OIDA is
the owner's entry point.

## 3. Service boundaries preserved (non-negotiable)

| Service | Authority | Port (local) | Base path in shell |
|---|---|---|---|
| Account Again | identity, tenant, role, entitlement, trust | 8001 | `/api/account/*` |
| Document Again | customer source, requirement, UR/DR, traceability, change, baseline | 8003 | `/api/da/*` |
| Conductor | orchestration, distribution, synchronization | 8010 | `/api/conductor/*` |
| PM Again | execution planning, function, task, timeline, progress | 8000 | `/api/pm/*` |
| QA Again | validation scope, test case/run, evidence, defect | 8002 | `/api/qa/*` |

The shell **never** writes to more than one domain truth for a single logical
action. "Confirm Baseline" remains `Document → Conductor → {PM, QA}`.

## 4. Authentication

There is no cross-service human SSO today. Each service issues its own session:

- PM Again, QA Again, Conductor: email+password → httpOnly JWT cookie (own user DB).
- Document Again: local mode, `X-Actor` header (no password).
- Account Again: service-to-service RS256 JWTs only (no human login).

The OIDA login screen federates best-effort: it attempts login against every
human-auth service with the entered credentials and reports which succeeded.
Sessions ride on the shell's single-origin cookies via the Vite proxy, so the
owner logs in once from their point of view. (Full SSO is backlog — see §10.)

## 5. Project identity propagation

Document Again is the project master. `prj_02884ef10cdc459889f1` ("True Cloud
Migration", tenant `t-truecloud`) is the canonical project id used in OIDA URLs.

Cross-service resolution (verified against live data):

| Service | Human identity | Technical identity | Link to Document |
|---|---|---|---|
| Document | True Cloud Migration | `prj_02884ef10cdc459889f1` | — |
| PM | True Cloud Migration | slug `design-baseline-bsl-1d8584f6c27f46738c9b` | `ExternalWorkReference` businessIntentId = `prj_02884…` |
| QA (V1) | Work Package `qah_844…` | slug `wp-qah-844fcb2bde6d4eac9648` | `ExternalQAProjectLink` workPackageId = handoff id |
| QA (V2) | Work Package `qah_878…` | slug `wp-qah-878171fa5b9948119e54` | same |
| Conductor | — (invisible) | `document_handoffs` by `handoff_id` | `project_id` + `baseline_id` |

The shell resolves PM/QA projects by matching the Document project name and the
Document QA-handoff ids. **Technical IDs are never shown as primary titles.**

## 6. What the shell reuses (no new engine, no new DB)

- Document Again: `/projects`, `/projects/{id}/home`, `/requirements`,
  `/revisions/{id}/document`, `/baselines`, `/traces`, `/trace-graph`,
  `/semantic-context`, `/flows`, `/architecture-diagrams`, `/timeline`,
  `/audit-events`, `/change-requests`, `/handoffs/*`, `/ecosystem-trace`.
- PM Again: `/projects`, `/{slug}/functions`, `/{slug}/tasks`, `/{slug}/gantt`,
  `/{slug}/dashboard`, `/{slug}/activity`, `/{slug}/pm-status`.
- QA Again: `/projects`, `/{slug}/dashboard`, `/{slug}/suites`,
  `/{slug}/cycles`, evidence/defects routers.
- Conductor: `document_handoffs` (read-only status for the "Synchronized" line).
- Account Again: `/api/v1/tenants`, `/api/v1/accounts`, `/api/v1/roles`,
  `/api/v1/product-entitlements` (Administration section).

## 7. Backend materialization fixes (required, minimal)

Verified gaps this program must close:

1. **PM execution materialization** — PM intake creates one flat seed task per
   DeliveryWorkPackage ("Design baseline bsl_xxx"). Fix: decompose the enriched
   handoff into Functions (Track 1 / Track 2) and requirement-backed Tasks.
2. **QA validation materialization** — QA intake names the project
   "Work Package qah_xxx" and leaves it `RECEIVED` with no human context. Fix:
   use the human project/baseline title and surface the validation scope from
   the preserved `QARequest`.

Both are additive; neither renames contracts nor merges services.

## 8. Routing (conceptual → implemented)

```
/projects                              → Document Again project list
/projects/:projectId                   → Project Home (composed)
/projects/:projectId/requirements      → Requirement Register
/projects/:projectId/requirements/:code→ Requirement trace view
/projects/:projectId/documents/ur      → UR
/projects/:projectId/documents/dr      → DR
/projects/:projectId/architecture      → Architecture
/projects/:projectId/trace             → Traceability
/projects/:projectId/planning          → Planning overview
/projects/:projectId/planning/functions→ Functions / Workstreams
/projects/:projectId/planning/timeline → Timeline / Gantt
/projects/:projectId/planning/tasks    → Tasks
/projects/:projectId/qa                → QA validation scope
/projects/:projectId/qa/test-cases     → Test cases
/projects/:projectId/qa/test-runs      → Test runs
/projects/:projectId/qa/evidence       → Evidence
/projects/:projectId/changes           → Change requests + baselines
/projects/:projectId/history           → Activity / audit
/admin                                 → Account Again (Users/Roles/Tenants)
```

## 9. Honest-dogfood data (verified, not synthetic)

- 1 project, 2 baselines (V1 `bsl_1d8584…`, V2 `bsl_41f2e9…`), 11 requirements
  (`REQ-T1-001…006`, `REQ-T2-001…005`), UR rev1 CONFIRMED, DR rev1 SUPERSEDED /
  DR rev2 CONFIRMED, 9 open clarifications, 2 assumptions, 1 decision,
  2 process flows, 2 architecture diagrams, 32 trace links.
- PM: 4 generic seed tasks, 0 functions (the gap to fix).
- QA: 3 `RECEIVED` requests, no published revision → no cycles, no fabricated
  results (honest).

## 10. Backlog (not blocking dogfood) — `OIDA_POST_R1_BACKLOG`

- Full Account-Again SSO / unified human JWT.
- Cross-origin production reverse proxy + cookie `SameSite=None`.
- Conductor sync-failure UI with correlation-id drill-down.
- Live semantic diff viewer; ERD/flow editing inside the shell.
- DOCX/PDF parity (explicitly out of scope per Excel policy).
