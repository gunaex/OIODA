# HYB-0 Gap Analysis

Status: accepted (pre-spike)
Date: 2026-08-01
Scope: compares the current implementation (Track A, through the Phase 3
commit) against `QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md` sections 4–13.
This document does not change any feature. It exists to make the HYB-0
spike's decisions explicit before writing runner or backend code.

---

## 1. What's already ready to use as-is

| Item | Where | Why it transfers directly |
|---|---|---|
| Cookie/JWT user auth (`get_current_user`, `require_roles`) | `backend/app/auth.py` | The human checkpoint-decision endpoint is a normal authenticated write — no new auth model needed for the *human* side. |
| Per-project SQLite provisioning (`get_project_db`, `ProjectBase`) | `backend/app/database.py` | New hybrid tables (runs, events, checkpoint decisions, spike evidence) are project-scoped exactly like `TestSuite`/`ScriptRevision`/`TestCase` — same file-per-project boundary, no `project_id` column needed. |
| Filesystem evidence storage decision | ADR-0001 §1 | The spike's "capture 1 screenshot → upload to backend" step reuses this directly: `data/projects/{slug}/...`, served through an authenticated route, never a static mount. |
| Router prefix convention (`/api/{slug}/<resource>`) | `backend/app/routers/*.py` | `/api/{slug}/hybrid/runs...` follows the exact same pattern as `/api/{slug}/suites`. |
| CORS / security headers | `backend/app/main.py` | Runner→backend calls are server-to-server (Node process calling an HTTP API), not a browser fetch — CORS/CSP don't apply to that leg. Checked explicitly; not a conflict. |
| Immutable-revision + clone-for-correction pattern | `ScriptRevision`/`TestCase`, Phase 3 | Not needed by the spike itself, but is the proven pattern `workflow_revisions` (HYB-1) will copy — confirms the approach scales to a second immutable-revision entity. |
| QA-Again's own login page as a target app | `frontend/src/pages/LoginPage.jsx` | Inputs already use `<label htmlFor>` and the button has real text — Playwright's `getByLabel()`/`getByRole()` work today with **zero markup changes**. Using our own login flow as the spike's "3 semantic steps" avoids standing up a separate demo app. |

## 2. What's usable but needs extension

| Item | Gap | Extension needed |
|---|---|---|
| `activity.py` (`log_changes`) | It's a *field-diff* logger (old value → new value per field), not an *event-stream* logger. Section 8.9 of the hybrid doc explicitly warns: "do not use runner events as a substitute for normalized business result tables" — the inverse is also true here: a diff log is the wrong shape for `RUN_CLAIMED`/`STEP_STARTED`/`CHECKPOINT_WAITING`-style events. | Keep `ActivityLog` as-is for suite/revision/case field edits. Add a **separate** `hybrid_run_events` table (append-only, typed `event_type`, not a diff). Do not try to force one table to do both jobs. |
| `auth.py` | Only knows user cookie/JWT auth. | Add a second, parallel dependency `get_current_runner` — a **runner token**, not a user session (see §4 decision 2). |
| Router pattern | Assumes every request is either public or user-authenticated. | Hybrid routes are the first case where *some* endpoints on the same router need runner-token auth (create run, post event, upload evidence) and *others* need user auth (checkpoint decision, evidence download). Each endpoint declares its own dependency rather than one router-level `dependencies=[...]`, unlike `suites.py`/`cases.py`. |

## 3. What conflicts

**None found that require reworking Phase 0–3.** One real sequencing
dependency, not a conflict but worth stating precisely so it isn't
missed:

- The hybrid doc's full `execution_runs` model (§8.6) references
  `cycle_id` and `cycle_test_result_id` — tables that don't exist yet
  (`test_cycles`/`cycle_test_results` are Track A Phase 4, not built).
  **The HYB-0 spike must not hard-require those foreign keys.** The
  spike's run table omits `cycle_id`/`cycle_test_result_id` entirely
  (nullable would invite half-wired code that looks connected but isn't
  — omitting is more honest for a spike). HYB-1/HYB-2, once Phase 4
  exists, is where those links get added for real.

## 4. What's not built yet (in scope for later Track B phases, not HYB-0)

Per the hybrid doc's own explicit HYB-0 scope lock, these are confirmed
**out of scope for HYB-0** and are not built by this spike:

- `workflow_definitions` / `workflow_revisions` / `workflow_steps`
  (§8.1–8.3) — HYB-1.
- `test_case_workflow_links` (§8.4) — HYB-1, and depends on Track A's
  `TestCase` (ready) plus `workflow_revisions` (not yet built).
- Full `runners` registration table with capabilities/heartbeat/platform
  metadata (§8.5) — HYB-2. The spike uses one pre-shared runner token,
  not a registration flow.
- Recorder (§5.4, §9) — HYB-3.
- Annotation, response-time history, reports/export integration (§5.6,
  §5.8, §5.9) — HYB-4/HYB-5, and also depend on Track A Phase 5/6
  (evidence, reports) which aren't built yet either.
- AI assistance (§7) — not started anywhere in the app yet; no conflict,
  just not present.
- Result-provenance enum (§6) at the *cycle_test_results* level — can't
  exist yet because `cycle_test_results` doesn't exist yet (Phase 4).
  The spike's own run/event/decision tables **do** carry an
  `actor_type` (`SYSTEM` | `RUNNER` | `HUMAN`) from day one — see §5 —
  so the provenance discipline the doc requires is proven at small scale
  now, ready to generalize once Phase 4 exists.

## 5. Decisions made before HYB-0

These are the concrete calls this gap analysis makes so implementation
can start unambiguously. Each is deliberately the *smallest* choice that
still proves the architecture, per the user's HYB-0 scope lock.

1. **Communication shape: plain REST polling, not WebSockets/SSE.**
   The runner polls `GET /runs/{id}` on a short interval while
   `WAITING_FOR_HUMAN`. Simpler to build and to prove for a spike; a
   push-based channel is a HYB-2+ optimization, not an architecture
   question the spike needs to answer.

2. **Runner auth: a minimal `runner_tokens` table, not the full
   `runners` registration model.** One row: `id`, `token_hash` (sha256,
   same pattern as `RefreshToken`), `label`, `revoked`, `created_at`.
   Lives in the **master DB** (a token is a credential, not
   project-scoped data — same reasoning as `User`/`RefreshToken`). No
   heartbeat, no capabilities JSON, no platform metadata yet — those are
   HYB-2. This still proves the "runner talks outbound-only using a
   revocable, scoped-by-possession token" requirement from the hybrid
   doc's §10 security minimums.

3. **New tables are project-scoped (`ProjectBase`), matching every
   existing QA-Again entity.** `hybrid_runs`, `hybrid_run_events`,
   `hybrid_checkpoint_decisions`, `hybrid_run_evidence` all live in the
   per-project SQLite file. `runner_tokens` is the one exception (master
   DB, per decision 2).

4. **Spike evidence gets its own minimal table, not a premature full
   `evidence_items`/`evidence_revisions` build-out.** Building the real
   Phase-5 evidence model now would violate the "don't build ahead of
   Track A" instruction. `hybrid_run_evidence` carries the same core
   fields the real model will need (`original_path`, `original_filename`,
   `original_content_type`, `original_size_bytes`, `original_sha256`,
   `captured_at`) so Phase 5 can fold hybrid evidence into the general
   model later without a field-shape rewrite — but it is explicitly a
   spike-scoped table, not presented as the final evidence schema.

5. **Target app for the spike's 3 steps: QA-Again's own `/login` page**,
   not a separate demo application. Zero markup changes needed (see §1).
   Steps: `NAVIGATE` to `/login`, `FILL` email, `FILL` password — then a
   `MANUAL_CHECKPOINT` before the actual sign-in click, matching the
   hybrid doc's principle that automation repeats and humans judge.

6. **Runner tech: Node.js + TypeScript + Playwright**, per hybrid doc
   §16's suggested repo shape (`runner/src/main.ts`). TypeScript from
   the start, not JS-then-rewrite — HYB-1+ builds directly on this
   spike's code rather than replacing it.

7. **Pause/resume implementation: the Playwright browser/page object
   stays alive in the same Node process's memory** across the pause —
   the runner is a long-running local process that polls, not a
   short-lived script that exits and relaunches. This is what makes
   "pause does not lose the browser/session" (a HYB-0 gate criterion)
   true by construction rather than by luck.

## 6. Minimum contract between control plane and runner

All endpoints below are new, under `/api/{slug}/hybrid/`. Auth column
says which credential each requires.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /runs` | runner token | Create a run record, status `QUEUED` → immediately `RUNNING` (no separate claim step at HYB-0 scale — one spike, one runner). Returns `run_id`. |
| `POST /runs/{id}/events` | runner token | Append one `hybrid_run_events` row. `event_type` one of the §8.9 enum values actually used at HYB-0: `RUN_CLAIMED`, `STEP_STARTED`, `STEP_COMPLETED`, `CHECKPOINT_WAITING`, `CHECKPOINT_RELEASED`, `EVIDENCE_UPLOADED`, `RUN_COMPLETED`. |
| `GET /runs/{id}` | runner token **or** user session | Current run status + latest pending checkpoint (if any). The runner polls this while `WAITING_FOR_HUMAN`; a human-facing page (not built at HYB-0 — curl/Playwright-driven browser check is enough for the spike) could use the same endpoint. |
| `POST /runs/{id}/checkpoint-decision` | **user session** (`get_current_user`, any authenticated role — same as manual execution elsewhere) | Records `decision` (`PASS`\|`FAIL`\|`BLOCKED`\|`NOT_APPLICABLE`), optional `reason`, `decided_by` (from the session, not client-supplied), `decided_at` (server clock). Moves run from `WAITING_FOR_HUMAN` to `RESUMING`. Never edited in place — one row per decision. |
| `POST /runs/{id}/evidence` | runner token | Multipart upload. Validates size, computes SHA-256, stores under `data/projects/{slug}/hybrid-evidence/{run_id}/`, records the `hybrid_run_evidence` row. |
| `GET /runs/{id}/evidence/{evidence_id}` | user session | Authenticated download/preview — never a static file mount. |

Run status enum for HYB-0 (subset of §5.3 — full set arrives with
HYB-2's execution state machine): `RUNNING`, `WAITING_FOR_HUMAN`,
`RESUMING`, `PASSED`, `FAILED`, `BLOCKED`, `CANCELLED`. `QUEUED`/
`CLAIMED`/`STARTING`/`RUNNER_LOST` are meaningful once there's a real
claim protocol and multiple runners (HYB-2) — the spike collapses
straight to `RUNNING` since there is exactly one runner and no queue.

## 7. What HYB-0 explicitly does not build

Per the user's instruction, restated here so it isn't lost during
implementation: no recorder UI, no workflow designer, no AI generation,
no regression library, no scheduling, no parallel execution, no retry
intelligence, no performance dashboard, no production runner deployment,
no RBAC refinement beyond "any authenticated user can decide a
checkpoint" (the same as today's manual execution model would allow).

## 8. Gate criteria this spike must satisfy

Restated from the user's instruction, as the acceptance checklist for
`docs/hybrid/HYB-0-SPIKE-RESULTS.md` (written after the spike runs):

1. Browser opens headed and is actually visible (not headless).
2. Locators are semantic (`getByLabel`/`getByRole`), not raw x/y.
3. Runner→backend communication is outbound-only.
4. Pause does not lose the browser/session.
5. Human decision is recorded with user identity and timestamp.
6. Resume continues the same session, not a fresh restart.
7. Screenshot is stored via an authenticated backend route.
8. Run history separates automation actions, human actions, and system
   events (`actor_type` on every event/decision row).
9. No mock or fake backend — a real FastAPI process, a real SQLite file,
   a real HTTP round trip.
10. A failure is never auto-summarized as PASS.
