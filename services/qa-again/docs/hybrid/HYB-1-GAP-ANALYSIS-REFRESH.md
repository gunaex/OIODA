# HYB-1 Gap Analysis Refresh

Status: informational — written to satisfy the "refresh the gap analysis
before HYB-1" requirement from `docs/ROADMAP.md`'s Release Closure
section and `docs/Autonomous hybird prompt.md`'s preflight. **This
document does not authorize starting HYB-1 feature code.** Per
ROADMAP.md's documented delivery sequence, HYB-1 still waits on Release
Closure (the three human-operated checks in `docs/RELEASE_CLOSURE.md`)
and an explicit production-readiness decision — neither has happened.
This refresh exists so that work isn't blocked on gap analysis once
those two things clear.

Date: 2026-08-02
Baseline commit: see `docs/ROADMAP.md`'s Release Closure section /
the `track-a-baseline` tag created alongside this document.
Supersedes nothing — `HYB-0-GAP-ANALYSIS.md` remains the accurate
record of what was true when HYB-0 was written (Phase 3 only). This
document covers everything built since.

---

## 1. What changed since HYB-0-GAP-ANALYSIS.md was written

HYB-0's gap analysis was written when Track A had only suites,
immutable revisions, and cases (Phase 3). Everything below is new since
then and directly relevant to HYB-1's workflow model and HYB-2+'s
execution/checkpoint work.

### Cycle and result domain models (Phase 4)

`TestCycle`, `CycleTestResult`, `CycleResultHistory` now exist
(`backend/app/models.py`). This resolves HYB-0-GAP-ANALYSIS.md §3's one
open sequencing dependency: the hybrid doc's `execution_runs` model can
now reference real `cycle_id`/`cycle_test_result_id` foreign keys
instead of omitting them.

- `CycleTestResult` already carries `execution_mode`
  (`MANUAL|AUTOMATED|HYBRID`), `result_source` (`HUMAN|RUNNER|SYSTEM`),
  and a nullable `runner_run_id` — reserved, unused, exactly as HYB-0
  left them. HYB-2 is where `runner_run_id` first gets a real value.
- `CycleResultHistory.change_source` mirrors `result_source` — every
  append-only history row already has a provenance slot ready.
- Cycle lifecycle (`DRAFT|READY|IN_PROGRESS|REVIEW|COMPLETED|LOCKED|
  CANCELLED`) and the locked-cycle mutation guard
  (`cycle_results.py::update_result`) are real and enforced. **HYB-4's
  checkpoint decision endpoint must reuse this exact guard** — a
  checkpoint decision is a `CycleTestResult` mutation like any other and
  must be rejected the same way if the linked cycle is `LOCKED`.

### Evidence and annotation models (Phase 5)

`EvidenceItem` (immutable original, content-addressed, MIME-sniffed,
UUID object keys) and `EvidenceRevision` (append-only annotation JSON)
are real. `EvidenceItem.evidence_source` (`HUMAN|RUNNER|SYSTEM`) is
already reserved and unused — this is exactly the field HYB-4's runner-
captured screenshots should populate as `RUNNER` (or `SYSTEM` for a
pure machine assertion screenshot with no human involved yet).

HYB-0's spike-scoped `hybrid_run_evidence` table (still in the schema,
untouched) was explicitly documented as *not* the final evidence model
(HYB-0-GAP-ANALYSIS.md §4/decision 4). **Decision needed at HYB-1/HYB-4
kickoff, not resolved here**: does hybrid evidence migrate onto the real
`EvidenceItem`/`EvidenceRevision` tables (recommended — avoids two
parallel evidence systems with two immutability/quota/reconciliation
implementations), or does `hybrid_run_evidence` get extended in place?
Migrating onto `EvidenceItem` means hybrid evidence automatically
inherits quota enforcement, orphan reconciliation, R2/filesystem
backend-agnosticism, and export inclusion for free — the gap analysis's
recommendation is to migrate, but this is a real design decision for a
human to confirm before HYB-4 writes code, not something to silently
decide in this document.

### `EvidenceStorage` abstraction + R2 backend (Phase 5/6, ADR-0002)

`backend/app/storage/` (`EvidenceStorage` interface,
`FilesystemEvidenceStorage`, `R2EvidenceStorage`) is real and is what
Track A's evidence upload/download/archive/export all go through.
**Any HYB-4 runner-captured evidence must go through this same
abstraction** — not a parallel `hybrid-evidence/` filesystem path like
the HYB-0 spike used. This is the concrete form of the migration
decision above.

### Actor/provenance conventions

Established pattern across the codebase: `captured_by`/`created_by`
(free-text email/identity) for human actors, `execution_mode`/
`result_source`/`change_source`/`evidence_source` enums for
human-vs-machine provenance. HYB-1's `WorkflowStep`/`WorkflowRevision`
and HYB-2's `WorkflowRun`/`WorkflowStepRun` should follow this exact
naming/typing convention rather than inventing a new one.

### Authentication, CSRF, CORS, role boundaries (Phase 7)

- `get_current_user`/`require_tester`/`require_admin`
  (`backend/app/auth.py`) — unchanged shape from what HYB-0-GAP-ANALYSIS
  already accounted for.
- `main.py::csrf_origin_check` — Origin-header validation on
  cookie-authenticated state-changing requests, **exempting
  `Authorization: Bearer` requests**. This is directly relevant to
  HYB-2: the runner must authenticate with a Bearer-style credential
  (not a cookie) both because it's a server-to-server caller (no
  browser, no CORS/CSRF exposure) and so it doesn't accidentally trip
  this check. HYB-0-GAP-ANALYSIS.md's `get_current_runner`
  decision (item 2) already anticipated a separate runner-token
  dependency parallel to user auth — Phase 7's CSRF work makes it
  concrete: runner endpoints must authenticate via a header token
  checked by `get_current_runner`, never a cookie.
- `ALLOWED_ORIGINS`/CORS: still only relevant to browser callers (the
  frontend). Runner→backend traffic is server-to-server and untouched
  by this, exactly as HYB-0-GAP-ANALYSIS.md §1 already noted.

### Dashboard, reporting, Excel/ZIP export (Phase 6)

Real, with documented formulas (`backend/app/metrics.py`) — pass rate,
evidence completeness, go-live readiness. HYB-5's requirement to "not
modify existing Track A formulas silently" is achievable because these
formulas are isolated in one module with the denominators already
written down in `docs/ROADMAP.md` Phase 6. Hybrid reporting (HYB-5)
should be additive functions in the same module/pattern, not edits to
`pass_rate`/`evidence_completeness`/`go_live_readiness` themselves.

Excel export (`report_excel.py`, 7 fixed sheets) and ZIP export
(`exports.py`, in-memory, real `EvidenceStorage.get()` reads, never a
presigned URL substituted in) are real. HYB-5's requirement to add
hybrid data to these exports means: new sheets/manifest entries, not
edits to the existing 7 sheets' shape (Phase 6's Excel structure is a
documented contract other tooling may depend on).

### Existing hybrid extension fields — confirmed still correctly unused

`execution_mode`, `result_source`, `change_source`, `evidence_source`,
`runner_run_id` all exist in the schema today, all default to their
manual/human values, and no Track A code path sets them to anything
else. HYB-1 introduces no schema risk here — these fields were added
specifically so this moment wouldn't require a migration.

### Frontend execution UI (`CycleExecution.jsx`)

As of the Performance Fast Pass (2026-08-02, see
`docs/PERFORMANCE_FAST_PASS.md`), this page:

- Fetches a **lightweight** result list up front, and full case detail
  **lazily per selection**, cached for the page session
  (`detailCache`), with a stale-request guard
  (`detailRequestSeq` ref) so rapid selection changes never show wrong
  data.
- This is the pattern HYB-4's pause/resume checkpoint UI should follow,
  not the HYB-0 spike's console-only runner output: a checkpoint's
  detail (screenshot, prior machine assertions, expected result) should
  load lazily when a specific `WAITING_FOR_HUMAN` run is opened, not be
  embedded in whatever list endpoint shows all active runs.
- `EvidenceGallery.jsx` thumbnails now use `loading="lazy"` — HYB-4's
  checkpoint evidence display should do the same rather than reintroduce
  eager-loaded full-resolution images.

### Performance patterns established by the fast pass

Three concrete patterns HYB-1/HYB-2's new endpoints should follow from
day one, rather than needing their own later fast pass:

1. **List endpoints return lightweight shapes; detail endpoints return
   full shapes.** (`CycleTestResultListOut` vs `CycleTestResultOut`.)
   `WorkflowStep` lists and `WorkflowRun`/`WorkflowStepRun` lists should
   follow the same split from the start — e.g. a run list should not
   embed every step's full locator payload and screenshot references.
2. **Additive SQLite indexes via `ensure_indexes()`
   (`backend/app/database.py`)** — any new hot FK/filter column HYB-1+
   introduces (`workflow_steps.revision_id`, `workflow_runs.workflow_id`,
   `runner_events.run_id`, etc.) should be added to `PROJECT_INDEXES`
   at the same time the table is introduced, not retrofitted later.
3. **No N+1 list-building.** `list_cycles`' grouped-query fix
   (`cycles.py`) is the template: batch a per-row aggregate into one
   `GROUP BY` query rather than looping and querying per row.

---

## 2. Open decisions for HYB-1 kickoff (not resolved by this document)

Restated from `docs/Autonomous hybird prompt.md`'s own instruction not
to silently choose a behavior that breaks historical reproducibility:

1. **`WorkflowTestCaseLink` target**: stable test-case identity,
   exact-revision snapshot, or both? Recommendation to weigh at kickoff:
   linking to the exact `TestCase` row (which is itself immutable once
   its parent `ScriptRevision` is published) already gives revision-
   exact reproducibility for free, the same way `TestCycle` snapshots a
   revision today — a separate "snapshot" concept may be redundant. This
   needs an explicit human decision, not an inferred one.
2. **Hybrid evidence migration**: onto real `EvidenceItem`/
   `EvidenceRevision` (recommended above) vs. extending
   `hybrid_run_evidence`. Affects HYB-1 only in that if migrating,
   `WorkflowStep`'s evidence-policy field should reference the real
   model's concepts (`evidence_type`, quota) rather than inventing
   parallel ones.
3. **Runner-token model for HYB-1's own needs**: HYB-1 itself is
   editor-only (no runner execution yet — that's HYB-2), so no new
   runner-auth decision is actually needed until HYB-2. Noted here only
   so HYB-1 doesn't accidentally start building runner auth ahead of
   scope.

---

## 3. What's still correctly not built (unchanged from HYB-0)

`workflow_definitions`/`workflow_revisions`/`workflow_steps`,
`test_case_workflow_links`, full runner registration, the recorder,
timing/reports/hardening — all still HYB-1 through HYB-5 as originally
scoped, none started.

---

## 4. Preflight record (per `docs/Autonomous hybird prompt.md`)

- Performance fast pass: complete, committed (`a345261`), pushed.
- `git status`: clean at time of writing this document.
- Branch: `main`.
- Backend tests: 41 passing (fresh venv, confirmed during the fast
  pass's final gate).
- Frontend build: passing (fresh `node_modules`, confirmed same gate).
- Track A operational: yes — the fast pass's real headed-browser
  Playwright run exercised the full login→cycle→evidence→annotation→
  dashboard→export workflow immediately before this document was
  written.
- Release readiness: **NOT PRODUCTION READY**. Three release blockers
  remain 🔴 BLOCKED (`docs/RELEASE_CHECKLIST.md`): real R2 staging
  smoke test, human-operated Screen Capture acceptance, human-operated
  clipboard-paste acceptance. None of these were touched by this
  document or the performance pass.
- Baseline tag: `track-a-baseline` (created alongside this document) —
  marks a **code-complete Track A state**, explicitly not a
  production-readiness claim.
