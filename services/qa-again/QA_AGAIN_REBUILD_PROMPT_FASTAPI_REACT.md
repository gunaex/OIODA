# QA-Again — Rebuild Master Prompt (FastAPI + React, matching PM-Again)

## 0. Why this document exists

The first build of QA-Again (see `QA_AGAIN_CLAUDE_CODE_MASTER_PROMPT_2026AUG01.md`
in this same repo, and the resulting Cloudflare Workers / Next.js / D1 / R2
implementation across phases 00–07) was built to a spec that assumed a
Cloudflare-native stack. It works and is fully tested, but it does **not**
match the real sibling application it's meant to sit next to — **PM-Again**
(`https://github.com/gunaex/PM-Again`) — which is FastAPI + SQLite on
Fly.io, and React + Vite on Vercel. That mismatch is the root cause of both
complaints that triggered this rewrite: the architecture doesn't match
what was actually wanted, and the UI doesn't feel as finished/polished as
PM-Again's does.

This document throws out the Cloudflare-specific technical foundation and
replaces it with PM-Again's actual, working architecture — same backend
framework, same DB pattern, same auth pattern, same frontend stack, same
component/UI conventions. One deliberate deploy difference from PM-Again:
QA-Again's **frontend** targets **Cloudflare Pages** instead of Vercel
(the user's eventual hosting preference — see section 2's Deploy
subsection for what that does and doesn't change). The **backend** still
targets Fly.io, unchanged from PM-Again's pattern — see that section for
why. The **QA domain model**
(test suites, immutable revisions, cycles, execution, evidence capture/
annotation, defects, reports, exports) from the original spec is largely
still correct and is carried forward with adjustments only where the new
stack requires them (e.g. evidence storage can't use R2 anymore).

**Before writing any code**, clone and actually read PM-Again — do not
guess at its conventions from this document alone, this document is a
summary, not a substitute:

```bash
git clone https://github.com/gunaex/PM-Again.git
```

At minimum, read these files in full before starting — they are the
ground truth for every convention section 2 below describes:

```
backend/app/auth.py            JWT + cookie + refresh-token pattern
backend/app/database.py        master DB + per-project SQLite provisioning
backend/app/main.py            app wiring, CORS, security headers, router registration
backend/app/models.py          SQLAlchemy model conventions, role enum
backend/app/excel_utils.py     Excel export/import-template/import pattern
backend/app/routers/tasks.py   representative CRUD + Excel + clone router
backend/app/activity.py        audit/change-log helper
backend/.env.example           required environment variables
backend/fly.toml, Dockerfile   Fly.io deploy config
frontend/src/App.jsx           route tree
frontend/src/components/Layout.jsx    nav shell, role-conditional tabs
frontend/src/auth/AuthContext.jsx     frontend session state
frontend/src/api/client.js     axios client + endpoint conventions
frontend/src/components/StatusBadge.jsx   status-color convention
frontend/vite.config.js        dev proxy + PWA config
frontend/vercel.json           SPA rewrite config
```

Also skim a few PM-Again `ClaudeCode_*_Spec.md` files at the repo root —
they are prior prompts written for PM-Again itself and show the level of
grounding and voice this document is trying to match.

---

## 1. Product goal (unchanged from the original spec)

QA-Again is evidence-first manual QA tooling: test scripts with immutable
revision history, test cycles bound to one exact revision, PASS/NG/
BLOCKED/NOT RUN/N/A execution with screenshot evidence and annotation,
defects, dashboards/reports, and Excel/portable-package export — for
multiple independent projects.

QA-Again remains a **standalone application** — its own repo, its own
deploy, its own database(s), its own auth. It is not a Cloudflare Worker
and does not use D1/R2/Access. It links to a matching PM-Again project by
URL only (see section 8) — no shared database, no shared session, no
two-way sync. This constraint is unchanged from the original spec; only
*how* QA-Again is built has changed.

---

## 2. Technical foundation — match PM-Again exactly

### Backend

- **Python 3.11, FastAPI**, same dependency set as PM-Again's
  `requirements.txt` as a starting point (`fastapi`, `uvicorn[standard]`,
  `sqlalchemy`, `pydantic`, `openpyxl`, `pandas`, `python-multipart`,
  `bcrypt`, `pyjwt`, `slowapi`, `python-dotenv`). Add packages only when a
  real requirement needs them (e.g. an image-processing library for
  server-side thumbnail generation, if that ends up necessary — see
  section 5).
- **SQLAlchemy models + `declarative_base()`, no Alembic.** Follow
  PM-Again's `database.py` pattern exactly:
  - One **master** SQLite DB (`master.db`) holding the project registry,
    users, and any truly global reference data.
  - **One SQLite file per project**, auto-provisioned on first access
    (`data/projects/{slug}.db`), via a `get_project_engine(slug)` /
    `get_project_db(slug)` pair mirroring PM-Again's.
  - Schema evolution via **additive column patches**
    (`ensure_columns()` + a `*_COLUMN_PATCHES` dict), not a migration
    framework — exactly PM-Again's approach. Never remove/rename an
    existing column this way; a genuine breaking change needs its own
    decision, documented, not silently patched.
  - Idempotent value migrations (PM-Again's `migrate_phase_values`
    pattern) for the rare case an enum value needs to change after data
    already exists using the old value.
- **Auth**: copy PM-Again's `auth.py` pattern as closely as the domain
  allows — bcrypt password hashing, short-lived JWT access token (30 min)
  in an httpOnly cookie, opaque refresh token (7 days) stored **hashed**
  in the DB and rotated on every use, `Authorization: Bearer` also
  accepted (for direct API testing), a `get_current_user` FastAPI
  dependency, and a `require_roles(*roles)` dependency factory for
  route-level authorization. **QA-Again's own users/auth are entirely
  separate from PM-Again's** — its own `JWT_SECRET_KEY`, its own `users`
  table in its own master DB. Do not attempt to share sessions or tokens
  between the two apps.
- **Roles**: `ADMIN`, `TESTER`, `VIEWER` (QA-Again's existing role names —
  keep them, they map cleanly to PM-Again's `pmo_admin`/`dev`+`qa`/
  `client_viewer` split). Follow PM-Again's global-role-per-user model
  (a `role` column on `users`, not a per-project membership table) unless
  multi-project role variance turns out to be a hard requirement — if it
  is, that's a deliberate, documented deviation from PM-Again's pattern,
  not an accidental one. (The original QA-Again spec assumed per-project
  roles; decide this explicitly before building auth, and write down why.)
- **Router convention**: `APIRouter(prefix="/api/{slug}/<resource>", ...)`
  for project-scoped resources, `router.dependencies=[Depends(require_...)]`
  at the router level, not repeated per-endpoint. `slug` auto-resolves
  from the path parameter — see PM-Again's `tasks.py`.
- **Excel import/export**: `pandas` + `openpyxl`, following PM-Again's
  `excel_utils.py` exactly — `make_excel_response`, `make_template_response`,
  `read_import_excel`. **Strict column-header validation**: reject an
  import whose headers don't exactly match the template (report missing/
  unexpected columns in the error) rather than auto-mapping/guessing. This
  is a deliberate change from the original QA-Again spec's auto-mapping
  import wizard — PM-Again's approach is stricter and simpler, and
  matching it is part of this rebuild's point.
- **CORS + security headers**: explicit `ALLOWED_ORIGINS` env var (never
  `"*"`, required for credentialed cookies to work), `allow_credentials=True`,
  and the same security-headers middleware PM-Again's `main.py` sets
  (HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a CSP).
- **Rate limiting**: `slowapi`, same pattern as PM-Again's `rate_limit.py`
  + the `RateLimitExceeded` exception handler in `main.py`.
- **Audit/activity log**: an `activity.py`-style `log_changes(db, entity_type,
  entity_id, diffs, changed_by)` helper, called from update endpoints —
  mirrors PM-Again's diff-based activity log.
- **Health check**: `GET /api/health` returning `{"status": "ok"}`, same
  as PM-Again's.

### Frontend

- **React 19 + Vite + Tailwind v4 + `react-router-dom` v7 + axios.** Same
  major versions as PM-Again's `package.json`.
- **Routing**: nested routes under `/:slug` wrapped in a `<Layout>` that
  loads project context once and renders an `<Outlet context={{ project }} />`
  — same shape as PM-Again's `App.jsx`/`Layout.jsx`. A top-level `/login`
  route and a project-list route (`/`) outside the `/:slug` tree.
- **Nav shell**: tab-style `NavLink`s in the header, conditionally hidden
  based on the current user's role (UX-only hiding — the backend RBAC is
  what actually enforces it, exactly PM-Again's stated reasoning in
  `Layout.jsx`). Match PM-Again's actual header layout: back-link + title
  on the left, nav tabs, a user badge on the right.
- **Auth state**: an `AuthContext` + `useAuth()` hook exactly like
  PM-Again's — `getMe()` on mount, `login()`/`logout()`, an axios response
  interceptor that clears the user on an unexpected 401 (but not on the
  login call itself or the initial `/auth/me` probe).
- **API client**: one `axios.create({ baseURL, withCredentials: true })`
  instance in `src/api/client.js`, with one named export function per
  backend endpoint — not a generic fetch-everywhere pattern. Follow
  PM-Again's naming (`listX`, `createX`, `updateX`, `deleteX`, `cloneX`,
  `exportUrl`, `importTemplateUrl`, `importX`).
- **PWA**: `vite-plugin-pwa`, offline-caching only static build assets
  (`globPatterns: ['**/*.{js,css,html,png,svg}']`) — **never** cache API
  responses, exactly PM-Again's stated reasoning (QA execution data
  changes constantly; a stale cached response would silently show wrong
  data).
- **Design tokens**: match PM-Again's actual look — Tailwind's default
  gray/red/green/yellow/blue/indigo palette, no custom CSS variable design
  system layered on top. Status badges follow PM-Again's `StatusBadge.jsx`
  convention exactly: `bg-{color}-100 text-{color}-700`, rounded-full,
  `text-xs`, `px-2 py-0.5`. QA-Again's own accent color (its "green QA
  identity" from the original spec) can still differ from PM-Again's
  indigo-600 — that's a legitimate product-identity choice, not an
  architecture one — but every *component pattern* (badges, buttons, nav
  tabs, modals, empty/error/loading states) should look and feel like it
  belongs to the same design system as PM-Again, not like a different app
  wearing different colors. When in doubt, open the equivalent PM-Again
  page/component side by side and match its spacing, weight, and states.

### Deploy

- **Backend on Fly.io**: same `Dockerfile` shape (`python:3.11-slim`,
  install requirements, `uvicorn app.main:app --host 0.0.0.0 --port 8000`),
  same `fly.toml` shape (a persistent volume mounted at the `DATA_DIR`
  path, `/api/health` as the HTTP check, `auto_stop_machines`/
  `min_machines_running = 0` for cost control on a low-traffic internal
  tool).
- **Frontend on Cloudflare Pages, not Vercel.** This is the one
  deliberate deploy difference from PM-Again. Concretely:
  - Same `vite build` output (`dist/`) — Pages serves a static SPA build
    exactly like Vercel does; nothing about the React/Vite/Tailwind code
    itself changes.
  - Replace `vercel.json`'s SPA rewrite with Pages' own mechanism: a
    `public/_redirects` file containing `/* /index.html 200` (everything
    that isn't a real static asset falls through to the SPA shell, same
    intent as the old `rewrites` rule).
  - Deploy via `wrangler pages deploy dist` (or the Cloudflare Pages
    GitHub integration for automatic deploys on push) — either is fine;
    pick one and document it in `docs/DEPLOYMENT.md`.
  - `VITE_API_BASE_URL` still points at the Fly.io backend's origin,
    exactly as it does pointing at Fly from Vercel today — this is a
    static-hosting swap, not a change to how frontend/backend talk to
    each other.
  - Update the backend's `ALLOWED_ORIGINS` to the Pages domain (and any
    custom domain) instead of a Vercel domain — everything else about the
    CORS/cookie setup in section 2's Backend subsection is unchanged
    (still `allow_credentials=True` + an explicit origin list, still
    `SameSite=None; Secure` in production since frontend and backend
    remain different origins).
  - Cloudflare Pages does **not** pull QA-Again back onto Workers/D1/R2 —
    it's static-asset hosting only here, none of the compute/DB
    architecture concerns from section 0 apply. Don't reach for Pages
    Functions, D1, or R2 for anything in this rebuild; the backend stays
    100% FastAPI on Fly.io.
- **Two independent deployments** — a Fly.io app for the backend and a
  Cloudflare Pages project for the frontend, both separate from PM-Again's
  own Fly app / Vercel project. QA-Again is not a route inside PM-Again's
  deployment. Cross-origin calls from the QA-Again frontend only ever go
  to the QA-Again backend.

### Domain topology (kanphong.com, registered in Cloudflare)

The user owns `kanphong.com` in Cloudflare and wants this exact subdomain
layout. Build to it — these are real target domains, not placeholders:

```
kanphong.com                    Cloudflare Pages — a separate, minimal
                                 "landing" project. Just an image. No nav,
                                 no app list, no links to the apps below.
                                 Not part of the QA-Again or PM-Again
                                 codebase — its own tiny static site.

qaagain.kanphong.com            Cloudflare Pages — QA-Again frontend
                                 (this rebuild). Has its own login;
                                 no session shared with anything else.

api.qaagain.kanphong.com        Fly.io — QA-Again backend, on a custom
                                 domain (not the default *.fly.dev host).
                                 Set up via `fly certs add
                                 api.qaagain.kanphong.com` on the QA-Again
                                 Fly app, then add the DNS records Fly's
                                 CLI reports (a CNAME, or A+AAAA for the
                                 apex-style setup) in Cloudflare DNS.

pmagain.kanphong.com            Today: Vercel (PM-Again's current host) —
                                 Vercel supports a custom domain whose DNS
                                 lives in Cloudflare without moving the
                                 zone itself, just a CNAME record. Later:
                                 swap the CNAME target to a Cloudflare
                                 Pages project once PM-Again's frontend
                                 migrates too (out of scope for *this*
                                 rebuild, but the domain doesn't change
                                 when that happens — only where the CNAME
                                 points).
```

Practical implications for this rebuild:

- `VITE_API_BASE_URL` (frontend build env) = `https://api.qaagain.kanphong.com`.
- Backend `ALLOWED_ORIGINS` = `https://qaagain.kanphong.com` (plus
  `http://localhost:5173` for local dev, per PM-Again's own `.env.example`
  pattern).
- Cookie flags: `COOKIE_SECURE=true` in production, `SameSite=None` — the
  frontend (`qaagain.kanphong.com`) and backend
  (`api.qaagain.kanphong.com`) are different hostnames even though they
  share the same apex domain, so this is still a cross-site cookie
  situation, not same-origin. Don't assume sharing `kanphong.com` as a
  parent domain makes the cookie same-site by itself — it doesn't; Fly.io
  and Cloudflare Pages are still two different hosts.
- The landing page at the bare apex (`kanphong.com`) is out of scope for
  the QA-Again codebase entirely — don't build it as part of this
  rebuild; it's a separate, tiny, unrelated static site/Pages project. If
  it doesn't exist yet when you reach deploy, flag that as a separate
  small task rather than building it inside the QA-Again repo.

---

## 3. What changes because there's no Cloudflare R2

The original spec leaned on R2 for private evidence/source-file storage
with a content-addressed object-key layout. Two real options, pick one
explicitly and document the choice (don't leave it implicit):

**Option A — filesystem storage on the Fly.io volume (recommended,
matches PM-Again's own pattern most closely).** Store evidence files
under the same persistent volume as the per-project SQLite files, e.g.
`data/projects/{slug}/evidence/{evidenceId}/original.{ext}`,
`.../annotations/rev-000N.json`. Serve them through an authenticated
FastAPI route (`StreamingResponse`/`FileResponse`) that checks project
membership before reading the file — never a static file mount, so
there's no way to bypass authorization by guessing a path. This keeps
the entire app on one deploy target family (Fly.io) with no new cloud
service to provision, mirroring how PM-Again already treats its SQLite
files as "just files on the volume."

**Option B — a real object-storage service** (Cloudflare R2 used
API-only via its S3-compatible endpoint, or AWS S3, or Fly's own object
storage offering) if the volume approach turns out to be insufficient
(e.g. volume size limits, needing CDN-backed delivery). If you pick this,
it is an *addition* to the Fly.io/Cloudflare Pages stack, not a reason to
move the whole app onto Cloudflare Workers/D1 — keep FastAPI/React and
only swap the storage backend.

Whichever is chosen, preserve every integrity rule from the original
evidence model: original is immutable once written, annotation state is
append-only revisions (design-state JSON, not a re-rendered image per
revision), real MIME-signature sniffing on upload (not just the claimed
content type), a hard size ceiling, and per-project storage-quota
accounting with the same 70/85/95%/100% warning behavior.

---

## 4. Domain model — carry forward, adapt to SQLAlchemy

Re-implement the same entities as SQLAlchemy models (one set per
per-project SQLite file, following PM-Again's `ProjectBase` convention;
`users`/project registry stay in the master DB following PM-Again's
`MasterBase` convention):

- **Test suites** → published, immutable **script revisions** → **test
  cases** within a revision. A correction to a published revision clones
  into a new draft; a published revision's content is never edited in
  place.
- **Test cycles**, each snapshotting one exact published revision's case
  set at creation time — publishing a later revision must never change an
  existing cycle.
- **Cycle test results**: PASS/FAIL/BLOCKED/NOT_RUN/NOT_APPLICABLE, with
  the same required-field rules as before (FAIL needs an actual result,
  BLOCKED needs a reason, N/A needs a reason + admin approval), append-
  only history on every mutation, and enforcement that a locked cycle
  rejects all mutation.
- **Evidence items + evidence revisions**, per section 3 above.
- **Defects**, sequential per-project `DEF-N` keys, linkable to a result.
- **Sign-offs**, one row per decision (never edited in place).
- **Audit log**, following PM-Again's `activity.py` pattern rather than a
  bespoke table if the shapes converge naturally — evaluate reusing
  activity log semantics instead of inventing a parallel audit system.

Use PM-Again's own `functions`/`tasks`/`gantt_items` tables in
`backend/app/models.py` as the concrete pattern reference for how a
per-project SQLAlchemy model should look (column style, `phase` handling,
etc.) — don't reinvent a different modeling style.

---

## 5. Execution workflow, evidence capture/annotation, reports, export

These sections of the original spec are still the right *product*
requirements — carry them forward as-is, only re-grounding the
*implementation* in React/FastAPI instead of Next.js/Cloudflare:

- Evidence-first execution UI (case list, actual-result editor, evidence
  gallery, defect link, sticky PASS/NG/BLOCKED/N/A actions) — a React
  page/component tree instead of a Next.js Server Component, calling the
  FastAPI backend via the axios client described in section 2.
- Screenshot capture (Screen Capture API single-frame, paste, upload) —
  unchanged, this is all browser API, independent of backend stack.
- Annotation editor — re-run the react-konva vs. Filerobot Image Editor
  compatibility spike against **this repo's actual React version** once
  it's pinned (don't assume the old ADR's conclusion still holds; React
  19 compatibility can change release to release — verify against
  whatever's actually in `package.json` at build time). Write a fresh
  ADR either way.
- Dashboard/reports (pass rate, evidence completeness, defects by
  severity, go-live readiness, etc.) with explicit denominators — same
  formulas as before, computed from SQLAlchemy queries instead of
  Drizzle.
- Excel export (7-sheet workbook) and portable ZIP package — same
  required sheets/columns as the original spec's section 17, but built
  server-side with `pandas`/`openpyxl` (matching PM-Again's
  `excel_utils.py` pattern) rather than client-side ExcelJS, **unless**
  there's a concrete CPU-cost reason on Fly.io to push it back to the
  browser — Fly.io doesn't have Cloudflare Workers' CPU-time billing
  model, so the original "avoid server CPU" guardrail may no longer
  apply; decide explicitly and document which way this went and why.

---

## 6. What to explicitly NOT carry forward

- Anything Cloudflare-specific: Workers, D1, R2, Access, `wrangler.jsonc`,
  `@opennextjs/cloudflare`, the Windows/OpenNext symlink workarounds.
- The Next.js App Router structure (Server Components, Server Actions,
  route handlers under `src/app/api`) — replaced by FastAPI routers +
  React Router pages.
- The free-plan capacity framing tied to Cloudflare Workers/D1/R2's
  specific limits (`docs/FREE_PLAN_CAPACITY.md`) — write a new capacity
  doc grounded in Fly.io's actual free/hobby-tier limits (backend + the
  persistent volume) and Cloudflare Pages' actual limits (frontend static
  hosting — a much simpler limit set than Workers/D1/R2 since Pages here
  is just a static-asset CDN, no compute/DB quotas apply to it).
- The spreadsheet auto-mapping import wizard — replaced by PM-Again's
  strict-header-validation import pattern (section 2).

## 7. What to keep verbatim from the original spec

- Section 13 (screenshot capture modes, no video, ever).
- Section 14's annotation requirements (tools, orange default, numbered
  callouts) — just re-run the library compatibility spike (section 5).
- Section 19's security/threat-model checklist — re-verify each item
  against the new stack (e.g. "Access JWT verification" becomes "this
  app's own JWT verification", "private R2" becomes "authenticated
  filesystem/object-storage route") and write a fresh
  `docs/THREAT_MODEL.md`, don't just copy the old one's code references.
- Section 25's explicit non-goals (no video, no Playwright E2E automation
  platform, no two-way PM-Again sync, no server-side heavy PDF
  generation, etc.) — still correct.

## 8. PM-Again link (unchanged relationship, confirmed independent)

Keep the original one-way-link-only integration: an optional
`external_project_url` field on a QA-Again project shows a "Back to
PM-Again" link when set. No shared database, no shared auth, no data
sync in either direction — confirmed by reading PM-Again's actual repo,
which has zero references to QA-Again anywhere in its codebase. Do not
build anything deeper than this link unless explicitly asked.

---

## 9. Suggested delivery phases

Same phase-by-phase discipline as the original build (small, reviewable
commits, a tag per phase, quality gates before moving on) — but the gate
commands change:

```bash
# Backend
cd backend && ruff check . && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

(No `wrangler dev`/OpenNext preview step for the backend — replace with
actually running `uvicorn` + `vite dev` locally against each other, and a
real deploy to a Fly.io backend + Cloudflare Pages preview deployment
before calling a phase done. `wrangler pages deploy` does apply here, just
for static frontend hosting, not for Workers/D1.)

Rough phase shape (adjust after actually reading PM-Again, per section 0):

0. Repository audit + this document's decisions written down as an ADR
   (evidence storage: A or B; roles: global or per-project; export:
   server or client-side).
1. Backend/frontend scaffold matching PM-Again's shape exactly, deployed
   end-to-end on Fly.io (backend) + Cloudflare Pages (frontend) with
   nothing but a health check and login working — prove the deploy
   pipeline before building features.
2. Identity/projects/roles.
3. Test suites, immutable revisions, Markdown/Excel/CSV import (strict
   header validation).
4. Test cycles and execution.
5. Evidence capture/annotation/storage.
6. Dashboard, reports, Excel/ZIP export.
7. Hardening, threat model, capacity doc, user guides, handover.

---

## 10. First message to send in the fresh session

Paste this whole document as the first message, then add: "Clone
`https://github.com/gunaex/PM-Again` first and actually read the files
listed in section 0 before writing any QA-Again code. Confirm your
understanding of PM-Again's auth/DB/router/Excel/UI conventions back to
me before starting Phase 0."
