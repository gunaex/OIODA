# HYB-0 Spike Results

Status: passed
Date: 2026-08-01
Prerequisite: `docs/hybrid/HYB-0-GAP-ANALYSIS.md`

## What ran

A real local session: FastAPI backend (`uvicorn`, SQLite), the actual
QA-Again React frontend (`vite` dev server), and the Node.js/TypeScript
runner in `runner/` (`npm run spike`), driving a real headed Chromium
browser via Playwright against QA-Again's own `/login` page.

Sequence actually observed (run id 1, project `checkout-flow-qa`):

```text
runner: POST /hybrid/runs                       -> run 1, status=RUNNING
runner: NAVIGATE /login                          -> STEP_STARTED / STEP_COMPLETED
runner: FILL email (getByLabel("Email"))         -> STEP_STARTED / STEP_COMPLETED
runner: FILL password (getByLabel("Password"))   -> STEP_STARTED / STEP_COMPLETED
runner: POST /events {CHECKPOINT_WAITING}        -> run status=WAITING_FOR_HUMAN
runner: polling GET /runs/1 every 2s...
human:  POST /checkpoint-decision {"decision":"PASS"}   (curl, admin@example.com session cookie)
runner: (next poll) sees status=RESUMING, proceeds
runner: CLICK "Sign in" (getByRole("button", {name:"Sign in"}))
runner: waits for h1:has-text("Projects")
runner: captures 1 screenshot, POST /evidence (multipart)
runner: POST /finish                             -> run status=PASSED
```

Full final run record (`GET /runs/1`) showed 13 events in order:
`RUN_CLAIMED`(RUNNER) → 3×`STEP_STARTED`/`STEP_COMPLETED` pairs(RUNNER) →
`CHECKPOINT_WAITING`(RUNNER) → `CHECKPOINT_RELEASED`(HUMAN) →
`STEP_STARTED`/`STEP_COMPLETED`(RUNNER) → `EVIDENCE_UPLOADED`(RUNNER) →
`RUN_COMPLETED`(SYSTEM), plus one `HybridCheckpointDecision` row
(`decision=PASS`, `decided_by=admin@example.com`, real server timestamp).

A negative-path check was also run separately (curl-driven, not through
the browser scenario): a `FAIL` decision with a reason correctly set the
run to `FAILED` and a subsequent `POST /finish` from the runner was
rejected with *"Run 2 is not in RESUMING (status: FAILED) — refusing to
auto-finalize"* — the runner cannot override a human's non-PASS decision.

## Gate criteria — evidence

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Browser opens headed and is actually visible | **Pass** | `chromium.launch({ headless: false })` in `runner/src/browser/spike.ts`. Confirmed live via `Get-Process chrome \| Where MainWindowTitle` during the run — window titled *"QA-Again - Google Chrome for Testing"* was present on-screen while the run was `WAITING_FOR_HUMAN`. |
| 2 | Locators are semantic, not raw x/y | **Pass** | `page.getByLabel("Email")`, `page.getByLabel("Password")`, `page.getByRole("button", { name: "Sign in" })` — no coordinates anywhere in `spike.ts`. Worked with zero markup changes to `LoginPage.jsx` because it already used `<label htmlFor>` and real button text. |
| 3 | Runner→backend communication is outbound-only | **Pass** | The runner process starts no server and opens no listening port — `runner/src/api/client.ts` only issues outbound `fetch()` calls. Reviewed the full runner source: no inbound-accepting code exists. |
| 4 | Pause does not lose the browser/session | **Pass** | The Playwright `browser`/`page` objects live in the same long-running `npm run spike` Node process for the entire pause; `waitForHumanDecision()` polls in a loop inside that process rather than exiting and relaunching. The same page that had the email/password already filled was the one that got the `Sign in` click after resume. |
| 5 | Human decision recorded with user identity and timestamp | **Pass** | `HybridCheckpointDecision` row: `decided_by="admin@example.com"` (from the authenticated session, not client-supplied), `decided_at` server-generated. |
| 6 | Resume continues the same session, not a fresh restart | **Pass** | No new `chromium.launch()` or `newPage()` call after the checkpoint — `runSpike()` is one continuous `try` block; the click happens on the same `page` variable created before step 1. |
| 7 | Screenshot stored via an authenticated backend route | **Pass** | `POST /api/{slug}/hybrid/runs/{id}/evidence` requires `X-Runner-Token`; `GET .../evidence/{id}` requires a user session (`get_current_user`). Downloaded the stored file after the run and confirmed it's the real final-state screenshot (Projects page, admin@example.com logged in) — not a placeholder. |
| 8 | Run history separates automation, human, and system actions | **Pass** | Every `hybrid_run_events` row and the one `hybrid_checkpoint_decisions` row carries `actor_type` ∈ `{RUNNER, HUMAN, SYSTEM}` — visible directly in the `GET /runs/1` response captured above. |
| 9 | No mock or fake backend | **Pass** | Real `uvicorn` process, real SQLite file (`backend/data/projects/checkout-flow-qa.db`), real HTTP round trips over `127.0.0.1:8000` — no stub server, no recorded/replayed fixtures. |
| 10 | Failure is never auto-summarized as PASS | **Pass** | Separate negative-path run: `FAIL` decision → run status `FAILED` → runner's `POST /finish` explicitly rejected (400) rather than silently finalizing as `PASSED`. See `_DECISION_TO_RUN_STATUS` mapping and the `RESUMING`-only guard in `routers/hybrid.py::finish_run`. |

## Bugs found and fixed during the spike

The spike caught one real bug before it ever reached a human tester: the
checkpoint-decision endpoint set `run.status = payload.decision` directly,
so a `FAIL` decision produced run status `"FAIL"` (not in
`HYBRID_RUN_STATUSES`, which uses `"FAILED"`), and `NOT_APPLICABLE` had no
corresponding run status at all. Fixed with an explicit
`_DECISION_TO_RUN_STATUS` mapping table and added `"NOT_APPLICABLE"` to
`HYBRID_RUN_STATUSES`/`TERMINAL_STATUSES`. This is exactly the kind of
gap a spike is supposed to surface early.

## Conclusion

The hybrid manual+automation architecture works as designed at small
scale: a real headed browser, controlled by a real outbound-only Node.js
runner, pauses for a real human decision recorded with identity and
timestamp, resumes the same session, and produces an auditable,
provenance-tagged run record with real uploaded evidence — all against
the real FastAPI control plane, no mocks.

**Recommendation: proceed to Track A Phases 4–7**, carrying forward the
extension points identified in `docs/ROADMAP.md` (`execution_mode`,
`result_source`/`actor_type`, `runner_run_id`, `step_kind`,
`checkpoint_status`, `evidence_source`, append-only run events) so the
Phase 4 cycle/execution model and Phase 5 evidence model don't have to be
reworked when HYB-1 links them to real workflow revisions. Do not start
HYB-1 (workflow model/editor) until Track A's execution and evidence
foundation exists to link against.
