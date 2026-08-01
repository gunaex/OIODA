# Roadmap

This roadmap now has two tracks, per
`QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md` section 15:

- **Track A** (Phases 0–7 below): the manual, evidence-first QA rebuild
  per `QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md` section 9. This remains
  the baseline — Track B is additive, not a replacement.
- **Track B** (HYB-0…HYB-5, formerly "Phase 8"): the approved hybrid
  manual+automation expansion. See
  [ADR-HYB-001](adr/ADR-HYB-001-playwright-hybrid-execution.md) for the
  one specification change this required (superseding the "no Playwright
  automation platform" non-goal — nothing else about Track A changed).

0. Repository audit + ADR-0001 (evidence storage, roles, export — done).
1. Backend/frontend scaffold matching PM-Again's shape, health check +
   login working end-to-end.
2. Identity/projects/roles.
3. Test suites, immutable revisions, Excel/CSV import (strict header
   validation) — **done** (suites, DRAFT/PUBLISHED/SUPERSEDED revisions,
   clone-for-correction, publish-supersedes-prior, strict-header Excel/CSV
   import+export, verified end-to-end via Playwright screenshots).
   **Not yet done**: the Markdown (`.md`) importer for the SATL-style
   source document (rebuild prompt section 11) — deferred because the
   required fixture file
   (`SATL_REGRESSION_CHECKPOINT_SCRIPT_PRE_GOLIVE_2026AUG01.md`) isn't in
   this workspace yet and the spec explicitly says "do not invent missing
   source content." Revisit once that fixture is available; until then,
   manual entry + Excel/CSV import cover suite/revision/case creation.
4. Test cycles and execution — **done**. `TestCycle` (snapshots one exact
   PUBLISHED revision's cases as `NOT_RUN` results at creation; a later
   publish never touches an existing cycle), `CycleTestResult`
   (PASS/FAIL/BLOCKED/NOT_APPLICABLE with FAIL/BLOCKED/N-A validation,
   N-A admin review/approval), `CycleResultHistory` (append-only, one row
   per mutation, `result_revision_no` increments, never overwritten).
   Cycle lifecycle DRAFT|READY|IN_PROGRESS|REVIEW|COMPLETED|LOCKED|
   CANCELLED; locking blocks all result mutation, admin-only reopen
   requires a reason and is audit-logged. Evidence-first execution UI
   (case list + filters, detail panel, actual-result editor, sticky
   PASS/NG/BLOCKED/N-A actions, unsaved/saving/saved/error states,
   per-result draft isolation, history panel). Verified end-to-end via
   curl (full lifecycle incl. lock/reopen/validation rejections) and
   Playwright screenshots of the actual execution UI.

   Hybrid extension points included per HYB-0's findings, not enabled:
   `execution_mode` (MANUAL|AUTOMATED|HYBRID, default MANUAL),
   `result_source` (HUMAN|RUNNER|SYSTEM, default HUMAN) on both
   `CycleTestResult` and `CycleResultHistory` (as `change_source`), and a
   reserved nullable `runner_run_id` (unused until HYB-2's real runner
   registration exists). `step_kind`/`checkpoint_status`/
   `evidence_source` were deliberately **not** added — they only mean
   something once `workflow_steps` (HYB-1) exists; adding them now would
   be meaningless nullable columns, not a real hook.

   **Documented gap, not silently dropped**: the rebuild prompt requires
   blocking PASS when the project/cycle evidence policy requires evidence
   and none exists. Not enforced yet — there is no evidence model until
   Phase 5. Tracked as a Phase 5 follow-up gate below.
5. Evidence capture/annotation/storage — **done**, storage backend
   **updated 2026-08-01 per [ADR-0002](ADR-0002-evidence-storage-r2.md)**:
   evidence binaries now live in a private Cloudflare R2 bucket (Standard
   storage class) behind a swappable `EvidenceStorage` abstraction
   (`backend/app/storage/`) — filesystem remains the zero-config local
   dev default, R2 is what production uses. All metadata (checksums,
   sizes, MIME types, actor provenance, archive state) stays in the
   project SQLite DB regardless of which storage backend is active; only
   binary payloads move. Non-guessable UUID-based object keys, upload is
   content-addressed/idempotent (a retried identical upload returns the
   existing row instead of duplicating it), and a DB-write failure after
   a successful storage write triggers a compensating delete (logged
   loudly if that itself fails — see
   [EVIDENCE_STORAGE_LIFECYCLE.md](EVIDENCE_STORAGE_LIFECYCLE.md) for
   reconciliation). Per-project storage quota
   (`GET`/`PUT /api/projects/{slug}/storage-quota`, configurable
   70/85/95/100% thresholds, blocks upload past 100%) is now built —
   this closes the gap this section used to list as "not built." Deploy
   details and required env vars in
   [DEPLOYMENT.md](DEPLOYMENT.md). Verified via 11 automated pytest
   tests (idempotency, quota enforcement, archive/quota interaction,
   compensating cleanup on a simulated DB failure, and the R2 backend
   itself against a local mock S3 server) plus a full curl re-verification
   of the upload/download/PASS-gate flow after the refactor — a real bug
   (a doubled `evidence/evidence/...` path segment) was caught and fixed
   before the automated tests even ran, during test-fixture setup.
   `EvidenceItem.object_key` replaced the earlier `original_path` field
   name once it stopped being literally a filesystem path.

   `EvidenceItem` (immutable original, `{sha256}.{ext}`-independent
   UUID-based key naming so the client-supplied filename never touches a
   storage key, MIME-signature sniffing that rejects a mismatched/spoofed
   content-type, 8MB size cap) + `EvidenceRevision`
   (append-only annotation history, design-state JSON not a rendered
   image per revision, matching the spec's own "unless proven necessary"
   guidance). Three capture paths funnel into the same authenticated
   upload endpoint: file upload, clipboard paste, and the Screen Capture
   API. A custom lightweight HTML5 Canvas annotator (arrow, rectangle,
   highlight, freehand, text, numbered callout, blur/redaction, orange
   default, undo/redo) — **decision**: built instead of react-konva/
   Filerobot (the rebuild doc asked to re-run that compatibility spike;
   a dependency-free canvas tool sidesteps the React-19-compatibility
   question entirely). **Closes the Phase 4 gap**: `TestCycle.
   require_evidence_for_pass` (default true) now actually blocks PASS
   with no active evidence attached, enforced in
   `cycle_results.py::update_result`. Upload/annotate/archive all reuse
   the same LOCKED-cycle guard as results; reopening re-enables them.
   Every evidence/annotation row carries a real `captured_by`/
   `created_by` and server timestamp. `EvidenceItem.evidence_source`
   (`HUMAN|RUNNER|SYSTEM`, default `HUMAN`) is the hybrid extension
   point, unused. Verified via a full curl lifecycle (sniff rejects a
   spoofed non-image file, PASS blocked then allowed, lock/reopen,
   archive) and a Playwright run through the real UI including drawing
   and saving real arrow/rectangle annotation shapes (confirmed via the
   stored `annotation_json`, not just a UI screenshot).

   **Documented gaps, not silently dropped**:
   - Screen Capture API and clipboard-paste upload paths are
     implemented for real use but not exercised by the Playwright
     verification — `getDisplayMedia` needs a user gesture + OS picker
     that isn't automatable headless, and paste requires a synthetic
     `ClipboardEvent` with real image bytes. Both share the exact same
     upload code path as the file-input flow, which *was* verified, so
     the marginal risk is in the two browser-API call sites themselves,
     not the upload/storage logic.
   - No thumbnails or stored image width/height — deliberately no
     Pillow/image-processing dependency added for Phase 5; the original
     master spec listed these as optional MVP fields.
6. Dashboard, reports, Excel/ZIP export — **done**, 2026-08-01. Before
   this phase, four retrofits to Phase 5's R2 evidence storage were
   carried forward per explicit user requirement (all pytest-verified):
   presigned downloads now override Content-Disposition/Content-Type so
   a browser save-as shows the evidence's real filename, not its opaque
   object key; a concurrent-upload quota race is closed (post-commit
   re-check + deterministic self-evict — SQLite serializes commits, so
   whichever request commits last detects and undoes an over-quota
   race, never both); `EvidenceStorage.list_keys()` + a safe, idempotent
   `app/reconciliation.py` (re-verifies "not referenced by a committed
   row" immediately before every delete, dry-run by default) plus an ops
   CLI (`scripts/reconcile_evidence.py`); and a real (uncommitted-secrets)
   R2 staging smoke test (`scripts/r2_staging_smoke_test.py`) — **written
   but not run in this environment**, no real Cloudflare credentials are
   available here; must be run by whoever holds the staging R2
   credentials before production release (see `docs/DEPLOYMENT.md`).

   Added `Defect` and `SignOff` (minimal — original domain model
   entities the spec required but no earlier phase built) so dashboard's
   "open defects by severity" and Excel's `03_NG_Defects`/`06_Sign_Off`
   sheets have real data instead of being faked or left empty.

   Dashboard: total/PASS/FAIL/BLOCKED/NOT_RUN/N-A counts, pass rate,
   evidence completeness, go-live readiness (with a blocker list),
   open defects by severity, pending N/A reviews, storage usage, recent
   activity — for the project's "active cycle" (most recently created
   non-CANCELLED cycle; spec doesn't define "active", documented choice).
   **Formulas the spec left genuinely undefined, resolved and
   documented** (surfaced explicitly, not silently chosen):
   pass rate = `PASS / (total − approved NOT_APPLICABLE)`, NOT_RUN stays
   in the denominator so an incomplete cycle can't show a misleadingly
   high rate; evidence completeness = `executed results with >=1 ACTIVE
   evidence / executed results`; go-live readiness = no P0 case
   FAIL/BLOCKED/NOT_RUN, no P0 N/A case unapproved, no open P0/P1 defect
   linked to the cycle.

   All 10 named reports (§16) exist as real backend endpoints
   (`/api/{slug}/reports/*`); the frontend consolidates them into **one**
   Reports page with a report-type selector rather than 10 near-duplicate
   screens — a deliberate scope call (the Excel export already surfaces
   the same data structurally), not a silent cut.

   Excel export: exact 7 sheets/columns from §17 (`00_Cover` …
   `06_Sign_Off`), no embedded thumbnails (same no-Pillow decision as
   Phase 5 — evidence referenced by ID/hash/caption, full images live in
   the ZIP). ZIP export: server-side, in-memory (`io.BytesIO`, no temp
   files to clean up), every evidence file read via
   `EvidenceStorage.get()` — **never** a presigned URL substituted into
   the archive, per explicit requirement. A missing storage object is
   recorded in `manifest.json` as `"missing": true` and skipped, not a
   hard failure of the whole export. Archived evidence is **included**
   in exports (marked `"status": "ARCHIVED"`) and still counts toward
   storage quota — exports are historical records, archiving only hides
   from the live execution UI, it doesn't delete.

   Verified: 20 automated pytest tests (dashboard formulas, Excel sheet
   names/columns/rows via openpyxl, ZIP extraction with manifest-to-file
   sha256 consistency, archived-evidence inclusion, missing-object
   graceful handling, concurrent-upload quota race, reconciliation
   safety) plus a full Playwright run through the real UI — dashboard
   tiles, the Reports page across multiple report types, and **actual
   file downloads** (not just HTTP 200s) of both the Excel workbook and
   ZIP package, both opened/inspected afterward to confirm they're real,
   non-corrupt files.
7. Hardening, threat model, capacity doc, user guides, handover.

## Track B — Hybrid manual+automation expansion (approved, not started)

Full detail lives in `QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md`; this is
the index. QA-Again gains a separate **QA Runner** (Node.js + Playwright,
outbound-only communication to the FastAPI control plane — never
Playwright embedded in the public API process) that can execute
repeatable browser steps and pause at manual checkpoints for a human
tester to verify, capture evidence, and decide PASS/FAIL/BLOCKED/N/A.
Machine assertions and human decisions are always recorded with distinct
provenance; AI may draft content but never finalizes a result.

Per the hybrid doc's section 20 ("first instruction for the
implementation team"), before any feature build:

1. Gap analysis against the hybrid doc's sections 4–13, against what
   Track A actually has at the time (currently: suites/revisions/cases
   done; cycles/execution/evidence/annotation/reports/export not yet
   built).
2. Smallest possible **HYB-0 spike** — not the full feature set. Exit
   gate (hybrid doc section 15, HYB-0): a local runner opens a visible
   browser, executes 3 recorded steps, pauses for a human decision,
   resumes, uploads one screenshot, stores an auditable run record. No
   mocked runner output accepted as satisfying this gate.

Delivery sequence after the spike:

- **HYB-0** — architecture spike. **Done, 2026-08-01** — see
  [HYB-0-GAP-ANALYSIS.md](hybrid/HYB-0-GAP-ANALYSIS.md) (decisions made)
  and [HYB-0-SPIKE-RESULTS.md](hybrid/HYB-0-SPIKE-RESULTS.md) (all 10
  gate criteria passed with recorded evidence — real headed browser,
  semantic locators, outbound-only runner, pause/resume in the same
  session, human decision with identity+timestamp, authenticated
  evidence upload/download, actor-tagged run history, real backend
  throughout, no auto-PASS on failure). Runner code lives in `runner/`
  (Node.js + TypeScript + Playwright). **Per the user's explicit
  instruction, HYB-1 does not start next — return to Track A Phases
  4–7 first**, carrying the extension points above into that work.
- **HYB-1** — workflow model and editor (`workflow_definitions`,
  `workflow_revisions`, `workflow_steps`, draft/publish/clone, test-case
  links, manual checkpoint editor).
- **HYB-2** — runner registration and execution (registration/revocation,
  heartbeat, job claim protocol, execution state machine, Chromium
  execution, structured step results, failure categories).
- **HYB-3** — recorder (record session, semantic locator capture,
  sensitive-input handling, draft workflow generation, locator warnings,
  tester review before publish).
- **HYB-4** — hybrid checkpoint and evidence (pause/resume UI, manual
  decisions, screenshot capture/upload, annotation linkage, defect
  linkage, lost-runner handling).
- **HYB-5** — timing, reports, hardening (per-step timing history,
  hybrid execution report, machine-vs-human provenance, export updates,
  `docs/HYBRID_RUNNER_THREAT_MODEL.md`, recovery/retry rules, operator
  and tester guides).

Explicit non-goals for the hybrid MVP (hybrid doc section 13): full
load/stress/soak testing, mobile/desktop app automation, continuous
video, AI autonomous sign-off or final pass/fail decisions, automatic
Git-diff impact analysis, IDE integration, autonomous locator repair,
pixel-diff as final authority, arbitrary scripting, branching/loops,
cloud-scale parallel browser farms, shared auth or two-way sync with
PM-Again, and replacing manual execution as a mode.
