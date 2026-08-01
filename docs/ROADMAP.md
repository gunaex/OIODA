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
4. Test cycles and execution.
5. Evidence capture/annotation/storage.
6. Dashboard, reports, Excel/ZIP export.
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

- **HYB-0** — architecture spike (runner comms design, runner-token
  security design, Playwright recording spike, semantic locator
  evaluation, pause/resume browser-context spike, evidence-upload spike,
  Windows/macOS feasibility check).
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
