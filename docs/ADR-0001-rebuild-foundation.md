# ADR-0001 — Rebuild foundation decisions

Status: accepted
Date: 2026-08-01

## Context

QA-Again's first build targeted Cloudflare Workers/Next.js/D1/R2. Per
`QA_AGAIN_REBUILD_PROMPT_FASTAPI_REACT.md`, this rebuild replaces that
foundation with PM-Again's actual architecture (FastAPI + SQLite on
Fly.io, React + Vite, deployed to Cloudflare Pages instead of Vercel for
the frontend only). Three points were left as explicit decisions rather
than assumptions; this ADR records them.

## Decisions

### 1. Evidence file storage: filesystem on the Fly.io volume (Option A)

Screenshot/evidence originals and annotation-revision JSON are stored
under the same persistent volume as the per-project SQLite files:

```
data/projects/{slug}/evidence/{evidenceId}/original.{ext}
data/projects/{slug}/evidence/{evidenceId}/annotations/rev-000N.json
```

Served through an authenticated FastAPI route (`StreamingResponse`/
`FileResponse`) that checks project membership before reading — never a
static file mount, so authorization can't be bypassed by guessing a path.

Rejected: Option B (R2/S3-compatible object storage) — no known volume-size
or CDN-delivery constraint exists yet to justify a second cloud dependency.
Revisit if the Fly volume approaches its size ceiling.

### 2. Roles: global role per user, not per-project membership

`users.role` is a single column (`ADMIN` | `TESTER` | `VIEWER`), exactly
PM-Again's model — no per-project role table. This deviates from the
original QA-Again spec's per-project-role assumption, but matching
PM-Again's pattern is this rebuild's explicit point (see section 0 of the
rebuild prompt). Revisit only if multi-project role variance becomes a
hard, concrete requirement — that would be a deliberate, documented
deviation at that point, not a default.

### 3. Excel/ZIP export: server-side (pandas/openpyxl)

Matches PM-Again's `excel_utils.py` pattern exactly
(`make_excel_response`/`make_template_response`/`read_import_excel`,
strict header validation on import). The original spec's "avoid server
CPU" guardrail was Cloudflare Workers-specific (CPU-time billing); Fly.io
has no equivalent constraint, so the constraint that motivated
client-side ExcelJS no longer applies.

### 4. Automated/robot ("hybrid") test execution — superseded by ADR-HYB-001

Originally recorded here (2026-08-01) as deferred-not-rejected: the
rebuild prompt's "no Playwright E2E automation platform" non-goal stayed
in force for Phases 0–7, with automation only planned for later.

That has since changed. The user approved
`QA_AGAIN_HYBRID_AI_QA_MVP_EXPANSION.md` as the product direction, and
**[[ADR-HYB-001]](adr/ADR-HYB-001-playwright-hybrid-execution.md)**
formally supersedes — precisely and only — that one non-goal. Every other
decision in this ADR (evidence storage, roles, export) and every other
non-goal from the rebuild prompt remain unchanged; see ADR-HYB-001 for
the exact scope of what changed and what didn't. `docs/ROADMAP.md`'s
Phase 8 now tracks the approved Track B (HYB-0…HYB-5) delivery plan
instead of a deferred placeholder.

## Consequences

- Backend stays 100% FastAPI on Fly.io; no new cloud service to
  provision for storage.
- Auth/roles code can copy PM-Again's `auth.py`/`require_roles` pattern
  near-verbatim, just with QA-Again's own role names and its own
  `users` table/JWT secret (no shared session with PM-Again).
- Export code can copy PM-Again's `excel_utils.py` near-verbatim.
