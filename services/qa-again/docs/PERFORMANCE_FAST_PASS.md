# Performance Fast Pass — 2026-08-02

A focused, measurement-first performance pass on Track A, run because the
application felt too slow for practical same-morning use. Scope was
explicitly limited to demonstrated bottlenecks in the existing
architecture — no HYB-1 work, no UI redesign, no new features, no
weakened security/validation/audit/immutability behavior.

**This does not change release status.** The project remains
**NOT PRODUCTION READY** — the same three blockers in
`docs/RELEASE_CHECKLIST.md` (real R2 staging smoke test, human-operated
Screen Capture acceptance, human-operated clipboard-paste acceptance)
are still unresolved and untouched by this pass.

## Test environment

- Local Windows dev machine, backend on `127.0.0.1:8000` (uvicorn,
  filesystem evidence storage), frontend on `localhost:5173` (Vite dev
  server).
- Real headed Chromium via Playwright for browser-level verification —
  not a script hitting the API directly.
- Backend: fresh `.venv`, `requirements-dev.txt`. Frontend: fresh
  `node_modules`, `npm run build`.

## Dataset (seeded directly via SQLAlchemy for speed, not committed)

One project (`perf-project`), 5 suites, 440 test cases total. One large
cycle ("Perf Cycle (large)") snapshotting 200 cases with a realistic mix
of PASS/FAIL/BLOCKED/NOT_APPLICABLE/NOT_RUN results, 383 result-history
rows, 94 evidence items (23 annotated), 12 defects, 300 activity-log
rows, plus 6 smaller cycles for the cycle-list endpoint. This is inside
the 100–300 result range asked for and large enough to expose payload-
and query-scaling problems an empty dev database never shows.

## Method

1. Measured backend response times and payload sizes directly via `curl
   -w time_total/size_download` against the real running backend, before
   any code change (see "Before" below).
2. Read the actual endpoint/query code (not guessed) to find the
   mechanism behind each slow/heavy response.
3. Applied only fixes tied to something actually measured or read in
   code.
4. Re-measured the same endpoints via curl (after, cold and warm).
5. Ran a real headed-browser Playwright script through the full
   login→...→export workflow, timing each step with wall-clock
   `Date.now()` brackets around real user actions (clicks, waits for the
   resulting DOM state) — not developer estimates.

## Measured bottlenecks

### 1. Cycle-results list payload was 3.5x larger than necessary

**Symptom**: opening Cycle Execution on the 200-case cycle was the
single heaviest request in the whole app.
**Measured (before)**: `GET /cycles/1/results` → **136 ms, 354,669
bytes**.
**Root cause**: `backend/app/routers/cycle_results.py::list_results`
returned the *full* `CycleTestResultOut` shape for every row, including
`case_action_md`, `case_expected_result_md`, `case_setup_md`,
`case_validation_md` — the full case markdown text, duplicated across
all 200 rows, even though the sidebar list only renders
`checkpoint_code`, `case_title`, and a status badge.
**Fix**: added `CycleTestResultListOut` (schemas.py) — the same shape
minus those four markdown fields. `list_results` now returns that;
`get_result`/`update_result`/`review` still return the full
`CycleTestResultOut` (which now simply subclasses the list shape and
adds the four fields back). `frontend/src/pages/CycleExecution.jsx` was
changed to fetch full case detail lazily, once, only for whichever
result is currently selected (see fix 4 below) — this is what actually
lets the backend stop sending that data in the list response at all.
**Measured (after, warm)**: **24–38 ms, 161,869 bytes** — **54% smaller
payload**, mostly query/serialization time now rather than data volume.

### 2. `list_cycles` was N+1

**Symptom**: cycle list endpoint issued one extra query per cycle.
**Measured (before)**: 7 cycles → **29 ms** (curl, warm).
**Root cause**: `backend/app/routers/cycles.py::list_cycles` called
`_to_out()` per cycle, and `_to_out` ran a fresh
`SELECT status, id FROM cycle_test_results WHERE cycle_id = ?` per
cycle — 7 cycles = 7 separate result-count queries (would scale linearly
with cycle count).
**Fix**: `list_cycles` now issues one grouped query
(`GROUP BY cycle_id, status`) across all cycles' results and builds each
cycle's `ResultCounts` from an in-memory dict, instead of querying per
cycle. `_to_out` itself (still used by `create_cycle`/`get_cycle`/
`lock`/`reopen`, which only ever handle one cycle) is unchanged.
**Measured (after, warm)**: **14 ms** for the same 7 cycles.

### 3. Dashboard/report metrics recomputed the same query twice

**Symptom**: `pass_rate()` silently recalculated `result_counts()`
internally, even though the caller (`dashboard.py`, `reports.py`) had
already computed the exact same counts one line earlier.
**Fix**: `metrics.py::pass_rate` now takes an optional `counts` param;
`dashboard.py` and `reports.py::execution_summary` pass their
already-computed counts through instead of triggering a second query.
Formulas themselves are byte-for-byte unchanged (pass-rate denominator,
NOT_RUN treatment, approved-NOT_APPLICABLE exclusion, evidence-
completeness denominator, go-live blockers — none of this was touched).
**Measured**: dashboard **40 ms → 20 ms** (curl, warm) on this dataset;
the win grows with cycle size since the eliminated query scans
`cycle_test_results` a second time.

### 4. Cycle Execution loaded and re-rendered every case's full detail up front

**Root cause**: the frontend held the entire 200-row list (previously
including all markdown) in state and rendered detail straight from it —
there was no separate "detail" fetch at all, so the full-detail cost was
baked into initial page load regardless of which case a tester actually
looked at.
**Fix**: `CycleExecution.jsx` now fetches the lightweight list up front
(fast, small), and fetches full case detail
(`GET /cycles/{id}/results/{result_id}`) only for the currently selected
result, once, caching it in a `detailCache` keyed by result id for the
rest of the page session (revisiting an already-opened case is instant,
no network call). A request-sequence guard
(`detailRequestSeq` ref) discards a stale in-flight detail response if
the tester clicks a different case before it returns, so rapid
selection changes never show the wrong case's detail. Unsaved drafts,
save state, and the evidence-first PASS gate are all untouched.
**Measured (real browser, after)**: switching between results averaged
**81 ms** (max 118 ms) including the detail fetch; revisiting an
already-opened case was **45 ms** (cache hit, no network round trip).

### 5. Evidence gallery thumbnails had no lazy loading

**Root cause**: every evidence thumbnail `<img>` in
`EvidenceGallery.jsx` requested the full original image immediately on
render, regardless of whether it was scrolled into view. No server-side
thumbnail subsystem exists (a deliberate Phase-5 decision to avoid a new
Pillow/image-processing dependency — preserved, not revisited here,
since this dataset's evidence is small and the bottleneck wasn't proven
to be image bytes specifically).
**Fix**: added `loading="lazy" decoding="async"` to the thumbnail
`<img>` — zero new dependencies, defers off-screen evidence image
requests until they'd actually be visible. This is browser-native
lazy loading, not a new subsystem.
**Not done, and why**: real server-side thumbnail generation was
considered and deliberately not built — it would require adding Pillow
(a new dependency the project explicitly avoided in Phase 5) and this
dataset didn't demonstrate original-image download time as the actual
bottleneck (seeded evidence is tiny). Documented here per the "don't
introduce risky shortcuts" instruction rather than silently skipped.

### 6. No indexes on hot foreign-key/filter columns

**Root cause**: none of `cycle_test_results.cycle_id`,
`.test_case_id`, `cycle_result_history.cycle_test_result_id`,
`evidence_items.cycle_test_result_id`/`.cycle_id`,
`evidence_revisions.evidence_id`, `test_cases.revision_id`/`.suite_id`,
`script_revisions.suite_id`, `defects.cycle_id`, `sign_offs.cycle_id`,
or `activity_log.changed_at` had an index — every list/filter/join query
against them was a full table scan. Not yet painful at this dataset's
scale (SQLite handles a few hundred rows fine either way), but a real,
demonstrated gap that gets worse linearly as cycles/evidence grow.
**Fix**: `database.py` gained `PROJECT_INDEXES` + `ensure_indexes()`,
following the exact same additive-patch pattern already used for
column patches (`ensure_columns`/`*_COLUMN_PATCHES`) — `CREATE INDEX IF
NOT EXISTS`, applied on every `get_project_engine()` call, safe against
both a brand-new database and an existing one that predates this
change. Verified against both: pytest's fresh per-test databases, and
the existing `perf-project.db` created before this change (restarted
the backend against it, indexes applied without error, existing data
untouched).

## Not changed (measured, but not worth the risk/benefit this morning)

- **Excel/ZIP export generation itself** was not touched — exports were
  already deferred to explicit click (`<a href>`, no eager generation on
  page load; confirmed by reading `ReportsPage.jsx`), and starting a
  download in the real-browser run took 220–349 ms, well inside target.
  No evidence generation is slow enough on this dataset to justify a
  background-job architecture, which the task explicitly said not to
  add unless synchronous exports were genuinely unusable.
- **Reports page** already only fetches the one selected report type on
  "Run Report" — confirmed by reading `ReportsPage.jsx`; the 10 report
  types were never all fetched eagerly, so there was nothing to fix.
- **Layout/project metadata** already only refetches on project (slug)
  change, not on every tab click — `Layout.jsx` is the persistent parent
  route for all `/:slug/*` pages, confirmed by reading `App.jsx`'s route
  tree.
- **Evidence list endpoint** already returns metadata only (no binary,
  no annotation JSON) — confirmed by reading `evidence.py`; annotation
  JSON is only fetched when the annotation editor opens, and only if
  `current_revision_no > 0`.
- **Server-side thumbnails** — see bottleneck 5 above.
- Duplicate request counts observed in the browser run (e.g. `/auth/me`
  called twice, dashboard fetched twice) are **React 19 StrictMode's
  documented dev-only double-invoke behavior** (`main.jsx` wraps the app
  in `<StrictMode>`), not a production duplicate-request defect —
  StrictMode intentionally mounts effects twice in development to
  surface side-effect bugs; this does not happen in the production
  build. Confirmed by reading `main.jsx`, not assumed.

## Before / after — backend (curl, real running server)

| Endpoint | Before | After (warm) | Notes |
|---|---:|---:|---|
| `GET /auth/me` | 10 ms | 10 ms | unchanged, already fast |
| `GET /projects` | 13 ms | 9 ms | unchanged code, noise |
| `GET /{slug}/suites` | 39 ms | 10 ms | first-hit cold-start noise before, not a real fix |
| `GET /{slug}/cycles` (7 cycles) | 29 ms | 14 ms | N+1 → 1 grouped query |
| `GET /{slug}/cycles/1` | 21 ms | 15 ms | unchanged, noise |
| `GET /{slug}/cycles/1/results` (200 rows) | **136 ms / 354,669 B** | **24–38 ms / 161,869 B** | lightweight list schema |
| `GET /{slug}/cycles/1/results/1` | 17 ms | 13 ms | unchanged (still full detail) |
| `GET /{slug}/cycles/1/results/1/evidence` | 20 ms | 14 ms | unchanged, already lean |
| `GET /{slug}/cycles/1/results/1/history` | 26 ms | 13 ms | unchanged, noise |
| `GET /{slug}/dashboard` | 40 ms | 20 ms | de-duplicated metric query |

## After — real headed-browser workflow (Playwright, production-shaped user actions)

| Operation | Measured | Target | Result |
|---|---:|---:|---|
| Login → Projects visible | 641 ms | — | includes bcrypt verify + full page nav |
| Open project → dashboard usable | 123 ms | < 2 s | ✅ |
| Open cycle list | 99 ms | — | ✅ |
| Open Cycle Execution, 200-case list visible | 248 ms | < 2 s | ✅ |
| Switch selected result (avg of 6) | 81 ms | < 500 ms | ✅ |
| Switch selected result (max of 6) | 118 ms | < 500 ms | ✅ |
| Switch to an already-opened result (cached) | 45 ms | < 500 ms | ✅ |
| Paste → local preview shown (no upload yet) | 49 ms | immediate | ✅ |
| Confirm upload → evidence visible | 62 ms | immediate feedback | ✅ |
| Open annotation editor → save revision | 133 ms | < 1 s | ✅ |
| Revisit dashboard | 130 ms | < 2 s | ✅ |
| Reports page shell | 48 ms | < 1 s | ✅ |
| Run a report (Execution Summary) | 112 ms | < 2 s | ✅ |
| Start Excel export (download event fires) | 349 ms | immediate | ✅ |
| Start ZIP export (download event fires) | 220 ms | immediate | ✅ |

Every measured operation is inside its acceptance target on this
dataset. `docs/CAPACITY.md`'s existing documented ceiling (sanity-tested
at 25 cases, not load-tested) is unchanged by this pass — this fast pass
adds a second, larger real data point (200-case cycle) but is not a
substitute for a proper load test.

## Files changed

- `backend/app/main.py` — dev request-timing log (`perf` logger, method
  + path + status + duration only, no secrets/cookies/bodies/query
  strings).
- `backend/app/database.py` — `ensure_indexes()` + `PROJECT_INDEXES`,
  wired into `get_project_engine()`.
- `backend/app/schemas.py` — `CycleTestResultListOut` added;
  `CycleTestResultOut` now extends it.
- `backend/app/routers/cycle_results.py` — `_to_list_out()` added;
  `list_results` uses the lightweight schema.
- `backend/app/routers/cycles.py` — `list_cycles` batches result counts
  in one grouped query instead of one query per cycle.
- `backend/app/metrics.py` — `pass_rate()` accepts precomputed counts.
- `backend/app/routers/dashboard.py`, `routers/reports.py` — pass
  precomputed counts into `pass_rate()`.
- `frontend/src/pages/CycleExecution.jsx` — lazy per-selection detail
  fetch with session cache and stale-request guard.
- `frontend/src/components/EvidenceGallery.jsx` — `loading="lazy"` on
  thumbnails.
- `start.bat`, `start.ps1` (new) — morning quick-start launchers.
- `docs/DEPLOYMENT.md` — "Morning quick start" subsection.

## Verification

- Backend: `pytest` — **41 passed**, same suite as before this pass,
  confirming the schema split and index/query changes didn't change any
  observable API behavior the tests cover.
- Frontend: `npm run build` — clean, no errors.
- Real headed-browser Playwright run covering the full workflow (login →
  project → cycle list → Cycle Execution on the 200-case cycle → rapid
  result switching → clipboard paste preview → confirm upload → open
  annotation editor → draw → save → dashboard → reports → real Excel
  download → real ZIP download), with both exported files re-opened and
  validated (`openpyxl` sheet names, `zipfile.testzip()` integrity)
  afterward — not just checked for existence.
- Confirmed via the same run that cancelling a pending
  screen-capture/paste preview still creates zero evidence rows (see the
  separate preview-before-upload verification in this repo's history);
  this pass did not touch that logic beyond the unrelated lazy-loading
  attribute on the thumbnail `<img>`.

## Remaining risks / honest gaps

- Browser-level "before" timings were not separately captured — the
  primary measured bottleneck (bottleneck 1) was conclusively identified
  and fixed at the backend/payload level via curl, which is what
  actually drove the fix; the after-only browser run verifies the fixed
  system meets targets rather than quantifying browser-side before/after
  delta. Re-running the old frontend against the old backend to get a
  literal browser-side "before" number was judged not worth the time
  this morning given the backend-level evidence was already conclusive
  and unambiguous.
- This dataset (200-case cycle) is larger than the previously-documented
  25-case sanity check but still not a real load test; `docs/CAPACITY.md`
  should eventually get a proper multi-hundred/thousand-row soak test.
- Server-side evidence thumbnails remain unbuilt (see bottleneck 5) —
  fine at current evidence sizes, worth revisiting if real screen
  captures prove to be multi-MB in practice.
- The three real release blockers (R2 staging smoke test, human Screen
  Capture acceptance, human clipboard-paste acceptance) are completely
  unaffected by this pass and remain 🔴 BLOCKED.
