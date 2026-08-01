# ADR-HYB-001 — Supersede the "no Playwright automation platform" non-goal

Status: accepted
Date: 2026-08-01
Companion documents: `QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md`,
`QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md`

## Context

The rebuild prompt (`QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md`, section 7,
carried forward from the original master prompt's section 25) lists as an
explicit non-goal:

> No Playwright E2E automation platform.

`docs/ADR-0001-rebuild-foundation.md` decision 4 and `docs/ROADMAP.md`
recorded this as a *deferred* future requirement based on an earlier user
request, not yet an approved architectural direction.

The user has now approved `QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md` as the
product-direction proposal that supersedes that deferral. Per that
document's section 2 ("Important change to the existing specification"),
exactly one prior decision must change — nothing else in the rebuild
prompt is affected.

## Decision

**Supersede, precisely and only, the "no Playwright E2E automation
platform" non-goal.**

Replacing it:

> QA-Again may orchestrate Playwright-based browser workflows through a
> controlled runner, including hybrid pauses for manual verification.

Everything else in `QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md` remains the
baseline, unchanged by this ADR:

- FastAPI + SQLAlchemy backend, per-project SQLite on Fly.io, matching
  PM-Again's conventions (auth, database, routers, Excel patterns).
- React + Vite + Tailwind frontend on Cloudflare Pages.
- Evidence-first execution model: immutable evidence originals,
  append-only annotation revisions, authenticated evidence routes.
- Immutable script revisions: a suite's published revision is never
  edited in place; corrections clone into a new DRAFT revision. This ADR
  extends the same immutability discipline to the new
  `workflow_revisions` entity — see ADR-HYB-002 (domain model, to be
  written before HYB-1) for how workflow revisions plug into the existing
  `ScriptRevision`/`TestCase` model from ADR-0001.
- The other non-goals carried forward alongside the Playwright one are
  **not** touched by this ADR and remain in force: no continuous video
  recording, no shared database/session with PM-Again, no two-way
  PM-Again sync, no silent mutation of published revisions, no
  replacement of evidence originals, no automatic acceptance based only
  on an AI statement, no uncontrolled browser automation running inside
  the public API process (hence: a separate QA Runner process, not
  Playwright embedded in the FastAPI web process).

## Consequences

- Track A (the current rebuild: Phases 0–7 in `docs/ROADMAP.md`) remains
  the baseline and is not abandoned or rewritten — the hybrid expansion
  is additive (Track B), not a replacement.
- A new component, the **QA Runner** (Node.js + Playwright, per section
  4.2 of the hybrid expansion doc), is introduced outside the FastAPI
  process. It communicates outbound-only (runner → backend), matching the
  "no uncontrolled browser automation inside the public API process"
  constraint above.
- `docs/ADR-0001-rebuild-foundation.md` decision 4 is updated to point
  here instead of describing automation as merely "deferred."
- `docs/ROADMAP.md`'s Phase 8 placeholder is replaced with the Track B
  (HYB-0 … HYB-5) delivery plan from the hybrid expansion doc.
- A fresh threat model (`docs/HYBRID_RUNNER_THREAT_MODEL.md`) is required
  before any production rollout of the runner — not written by this ADR,
  tracked as a HYB-5 deliverable.
- No implementation code is authorized by this ADR alone. Per the hybrid
  expansion doc's section 20, next steps are: a gap analysis against its
  sections 4–13, then the smallest possible HYB-0 spike (local runner
  opens a visible browser, executes 3 recorded steps, pauses for a human
  decision, resumes, uploads one screenshot, stores an auditable run
  record) — not the full feature set — before any broader Track B build.
