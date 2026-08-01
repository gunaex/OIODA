# Release Readiness Checklist

Status as of Release Closure procedure preparation (2026-08-02),
originally established at Phase 7 completion (2026-08-01). 🟢 done and
verified · 🟡 done, minor caveat noted · 🔴 **BLOCKED — must resolve
before production release**.

The project is currently in **Release Closure**: no new features are in
progress, the only open work is executing the three items below.
`docs/RELEASE_CLOSURE.md` is the exact, step-by-step procedure a human
operator follows to close each one (prerequisites, commands, expected
results, evidence to capture, cleanup, failure diagnosis) — this table
will be updated with real outcomes once that procedure has been run.

## Release-blocking items

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Real Cloudflare R2 staging smoke test executed successfully | 🔴 **BLOCKED** | `scripts/r2_staging_smoke_test.py` exists and is correct (put/head/get/presigned-fetch/delete against a real bucket), but **has not been run** — no real Cloudflare credentials exist in this development environment. Procedure to run it: `docs/RELEASE_CLOSURE.md` §1. Record output in `docs/RELEASE_REHEARSAL.md` when done. |
| 2 | Screen Capture API real-browser acceptance | 🔴 **BLOCKED** | `getDisplayMedia` cannot be exercised in a headless test browser. Needs a human tester, in a real browser, confirming screen capture → upload works. Shares the upload code path already verified via file input (lower residual risk, but not zero). Procedure: `docs/RELEASE_CLOSURE.md` §2. |
| 3 | Clipboard-paste real-browser acceptance | 🔴 **BLOCKED** | Same category as #2 — needs a synthetic `ClipboardEvent` with real image bytes that headless automation can't reliably produce; needs human verification. Procedure: `docs/RELEASE_CLOSURE.md` §3. |

**Do not describe this application as production-ready while any of the
above three remain BLOCKED**, per explicit instruction. Everything below
this line is done and verified, but does not override the three items
above.

## Automated test coverage (all passing — see `docs/RELEASE_REHEARSAL.md` for the exact run)

- 41 backend pytest tests across: evidence storage lifecycle (Phase 5),
  R2 backend behavior via moto (Phase 5/6), evidence-storage
  concurrency/reconciliation (Phase 6), reports/dashboard/export
  correctness (Phase 6), and Phase 7's new security-boundary/evidence-
  abuse/export-security suites.
- Frontend: `npm run build` succeeds; every phase's UI has been
  Playwright-verified against a real headed/rendered browser at the time
  it was built (Phases 1, 3, 4, 5, 6) — no new frontend code was added in
  Phase 7 (backend-only + documentation), so no new Playwright run was
  required for this phase specifically.

## Security checks (Phase 7 — see `docs/THREAT_MODEL.md` for full detail)

| Check | Status |
|---|---|
| Password hashing (bcrypt), no plaintext storage | 🟢 |
| JWT access token (30 min, httpOnly), refresh token (7 day, hashed at rest, rotated) | 🟢 |
| Login rate limiting (5/min) | 🟢 verified live |
| Role boundaries (ADMIN/TESTER/VIEWER) enforced server-side | 🟢 verified live |
| Cross-project data isolation | 🟢 verified live |
| CORS explicit-origin-only | 🟢 verified live |
| CSRF (Origin-header check on cookie-authenticated writes) | 🟢 **new this phase** — real gap found and closed, verified live |
| Evidence: oversized-file rejection | 🟢 verified live |
| Evidence: MIME-signature spoofing rejection | 🟢 verified (Phase 5) |
| Evidence: malicious-filename handling | 🟢 **hardened this phase** — `..` sequences now stripped, verified live |
| Evidence: cross-project access denial | 🟢 verified live |
| Evidence: presigned URL short expiry + safe filename | 🟢 verified live |
| Export: ZIP path traversal / filename injection | 🟢 verified live |
| Export: openpyxl illegal-character crash | 🟢 **real bug found and fixed this phase** — verified live |
| Export: temp-file cleanup | 🟢 verified live (in-memory generation, nothing written to disk) |
| Export: authorization/leakage on missing or cross-project data | 🟢 verified live |
| Export: memory behavior at scale | 🟡 sanity-tested at 25 cases; documented (not load-tested) ceiling in `docs/CAPACITY.md` |

## Operational readiness

| Item | Status |
|---|---|
| SQLite backup script | 🟢 written and tested against real data |
| Backup restore procedure documented | 🟢 `docs/BACKUP_RESTORE.md` |
| Corruption recovery procedure documented | 🟢 `docs/BACKUP_RESTORE.md` |
| R2 orphan reconciliation | 🟢 script + tests (Phase 6), lifecycle doc extended this phase |
| R2 credential rotation procedure | 🟢 documented, not yet exercised for real (needs real credentials — same blocker as #1) |
| Capacity documentation | 🟢 `docs/CAPACITY.md` |
| Deployment docs (local/staging/prod, rollback, secrets) | 🟢 `docs/DEPLOYMENT.md` |
| Threat model | 🟢 `docs/THREAT_MODEL.md` |
| User guides (Admin/Tester/Viewer) | 🟢 `docs/guides/` |
| Technical handover | 🟢 `docs/HANDOVER.md` |
| Backups scheduled/automated | 🔴 not blocking release, but **not done** — script exists, no cron/scheduled job wired up. Recommended before real production data accumulates. |

## Accepted limitations (not release blockers, explicitly carried forward)

- Hybrid execution beyond HYB-0 remains disabled (scope boundary, not a
  defect).
- No hard-delete/purge for evidence (deliberate; no retention policy was
  requested this phase).
- No UI for user management, defect creation, or sign-off recording
  (API-only).
- No per-endpoint rate limiting beyond login (accepted risk at current
  scale — see `docs/THREAT_MODEL.md` §9).
- Markdown (SATL-style) test-script importer deferred (no fixture
  document available).

## Sign-off

This checklist itself does not constitute production-readiness approval
— the three 🔴 items above must move to 🟢 with recorded evidence
(`docs/RELEASE_REHEARSAL.md` and this file, updated) before that claim
can be made.
