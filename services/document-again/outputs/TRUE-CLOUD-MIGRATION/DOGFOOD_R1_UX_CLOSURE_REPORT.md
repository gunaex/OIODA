# AGAIN Dogfood R1 — P1 Owner UX Gap Closure Report

**Date:** 2026-08-16
**Pass:** P1 UX / materialization closure (no new feature families).

---

## Root cause found (critical)

The Document Again frontend rendered a **blank page** because every workspace
page uses a named export (`export function Requirements()`) while React 19's
`lazy()` requires a default export. The dynamic import resolved, React logged
`"lazy: … Instead received: %s"` with the module namespace object, and the
`%s` formatting threw `Cannot convert object to primitive value` — blank UI.

This is why the owner had to browse repository output folders: the app never
rendered. Fixed in `frontend/src/App.jsx` with a `lazyPage(loader, name)`
wrapper that surfaces the named component as the default export.

Also fixed: `frontend/vite.config.js` proxied `/api` to `:8002` (QA Again's
canonical port) instead of Document Again's backend — corrected to `:8003`.

---

## Changes made

### Document Again (`DOCUMENT-AGAIN`)
- `frontend/src/App.jsx` — `lazyPage()` wrapper; `ProjectHome` route at `/`;
  "Project Home" nav entry (fixes blank page).
- `frontend/src/pages/ProjectHome.jsx` — new Project Home (project identity,
  current baseline, last updated, open clarifications, PM/QA status with
  links, document hub with Open/Excel/History, requirements+trace,
  latest activity).
- `frontend/vite.config.js` — API proxy `:8002` → `:8003`.
- `backend/app/services.py` — `project_home()` aggregate endpoint; human
  trace resolution; `_render_xlsx()` formatting (freeze panes, column widths,
  wrap, section fills); `build_handoff_payload()` adds `title`,
  `baseline_name`, `requirement_refs` (human requirement code+title).
- `backend/app/routers/api.py` — `GET /projects/{id}/home` route.
- GAP-010 — two clarifications recorded (CLR-0008 DR scope wording,
  CLR-0009 UR acceptance wording) as CLARIFICATION_REQUIRED.

### Conductor Again (`CONDUCTOR-AGAIN`)
- `backend/app/routers/document_handoff.py` — `_map_execution` uses the
  project title + human description; `_map_qa` carries `title`/`baselineName`
  in `releaseCandidate` and human `acceptanceCriteria.business` strings.

### PM Again (`PM-AGAIN`)
- `backend/app/ecosystem/mapping_service.py` — `_find_or_create_project` now
  updates the materialized project **name** to the authoritative Document
  Again project name (slug stays stable as DB identity).

### QA Again (`QA-AGAIN`)
- No code change; the QARequest now arrives with human context (project
  title, baseline name, `acceptanceCriteria.business` = "REQ-… — title").
  QA UI rendering of these fields remains in backlog.

---

## Acceptance matrix

| Criterion | Result |
|---|---|
| PROJECT_HOME | **PASS** |
| DOCUMENT_DISCOVERABILITY | **PASS** |
| DOCUMENT_OPEN_IN_2_CLICKS | **PASS** |
| LATEST_REVISION_VISIBLE | **PASS** |
| REQUIREMENT_TRACE_NAVIGATION | **PASS** |
| TRACE_HUMAN_READABILITY | **PASS** |
| PM_HUMAN_NAMING | **PASS** |
| PM_EXECUTION_MATERIALIZATION | **PARTIAL** (name fixed; per-requirement work structure not yet decomposed) |
| PM_DISCOVERABILITY | **PARTIAL** |
| QA_HUMAN_NAMING | **PARTIAL** (data carries human context; QA UI not updated) |
| QA_VALIDATION_MATERIALIZATION | **PARTIAL** |
| QA_DISCOVERABILITY | **PARTIAL** |
| CROSS_SERVICE_STATUS | **PASS** |
| RECENT_ACTIVITY | **PASS** |
| UR_XLSX_READABILITY | **PASS** |
| DR_XLSX_READABILITY | **PASS** |
| TECHNICAL_ID_LEAKAGE | **PARTIAL** (home is clean; PM slug + Ecosystem page still expose raw IDs as metadata) |
| OWNER_NO_BACKEND_REQUIRED | **PASS** |
| OWNER_DOGFOOD_R1 | **PARTIAL** |

---

## Verified in-browser (owner path)

- Open `http://localhost:5175/` → **True Cloud Migration** project home:
  current baseline `True Cloud Migration v2.0`, 7 open clarifications,
  11 requirements, PM/QA status, 11 documents with Open/Excel/History.
- Click `REQ-T2-004` → "Designed in — 24. Pilot Migration Flow" and
  "Covered by flow step — Pilot verification" (human labels, no semantic IDs).
- UR/DR re-exported as XLSX with freeze panes + column widths + wrap.

## Remaining (POST_V1_BACKLOG, not done)

1. PM per-requirement/track work-structure materialization.
2. QA frontend renders project title + validation scope + requirement list.
3. Master single-workbook consolidation + cross-sheet hyperlinks.
4. Normalise `externalReferenceId` to canonical `workPackageId`/`qaRequestId`.
5. Ecosystem page + PM slug still show raw IDs as primary labels.
