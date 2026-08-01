# Roadmap

Phases 0–7 below are the current rebuild scope, per
`QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md` section 9. Phase 8 is
deliberately **out of scope for this rebuild** but is a confirmed future
requirement (user decision, 2026-08-01) — recorded here so it isn't lost.

0. Repository audit + ADR-0001 (evidence storage, roles, export — done).
1. Backend/frontend scaffold matching PM-Again's shape, health check +
   login working end-to-end.
2. Identity/projects/roles.
3. Test suites, immutable revisions, Excel/CSV import (strict header
   validation).
4. Test cycles and execution.
5. Evidence capture/annotation/storage.
6. Dashboard, reports, Excel/ZIP export.
7. Hardening, threat model, capacity doc, user guides, handover.

## Phase 8 (future, not started): automated / "hybrid" test execution

Today a test case's result (PASS/NG/BLOCKED/NOT RUN/N/A) is entered by a
human tester. The user wants a path to also let a case's result be
produced by an automated script, alongside — not instead of — manual
execution ("hybrid").

Not designed yet. Open questions to resolve before starting this phase:

- **Trigger model**: does QA-Again run the automation itself (spawning a
  Playwright/other runner as a job), or does an external CI pipeline run
  it and push a result back into QA-Again via an API/webhook? The latter
  keeps QA-Again's own deploy (single small Fly.io machine, scale-to-zero)
  simple and avoids it needing a browser-automation runtime; the former is
  more "one app does everything" but is a much bigger infrastructure
  lift (headless browser, job queue, log/artifact storage) on a
  low-traffic internal tool's hosting budget.
- **Result provenance**: a cycle result needs a `source` field
  (`manual` | `automated`) so reports/dashboards can distinguish them, and
  an automated result likely needs its own evidence shape (log output,
  a CI run URL) rather than a manually-captured/annotated screenshot.
- **Which cases are eligible**: not every manual case maps to a scriptable
  check — this needs a per-case flag or a separate "automated case" type
  linked to the manual one it corresponds to, not a blanket assumption
  that all cases become automatable.
- **Auth for the callback**: if external CI pushes results in, that's a
  new unauthenticated-by-a-human API surface — needs its own
  service-token auth distinct from the cookie-based user auth in
  `auth.py`, scoped narrowly (can only post a result to one project/cycle
  it holds a token for).

Revisit this phase once 0–7 are stable and deployed; write a proper spec
document at that point rather than deciding architecture from this note
alone.
