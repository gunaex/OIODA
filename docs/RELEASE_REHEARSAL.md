# Release Rehearsal Record

Executed 2026-08-01, in this Phase 7 session, in a genuinely clean
environment (not the accumulated development database from earlier
phases). Recorded here as the evidence for `docs/RELEASE_CHECKLIST.md`.

## Environment reset

```
rm -rf backend/.venv backend/data backend/tests/_tmp_data backend/.pytest_cache
rm -rf frontend/node_modules frontend/dist
```

Fresh Python venv, fresh `pip install -r requirements-dev.txt`, fresh
`npm install` — no cached dependency state carried over from any earlier
phase's work.

## 1. Backend automated tests (fresh venv)

```
41 passed in 9.19s
```

All 41 tests across `test_evidence_concurrency.py`,
`test_evidence_security.py`, `test_evidence_storage.py`,
`test_export_security.py`, `test_r2_storage.py`, `test_reconciliation.py`,
`test_reports_and_exports.py`, `test_security_boundaries.py` — the full
suite built across Phases 5–7, run cold.

## 2. Frontend build (fresh node_modules)

```
✓ 96 modules transformed
dist/assets/index-*.js   346.77 kB │ gzip: 105.18 kB
✓ built in 360ms
PWA v1.3.0 — files generated
```

Clean build, no errors, no new dependency-resolution issues.

## 3. Full-stack, real-browser, end-to-end flow

Fresh `data/` directory (no carried-over projects/users), backend +
frontend started clean, driven with Playwright through an **actual
rendered Chromium browser** — not a script hitting the API directly —
specifically to prove Phase 7's CSRF Origin-check fix does not break
normal browser usage (a real browser sends `Origin` automatically; this
was the first real-browser exercise of that code path, the earlier CSRF
tests used `TestClient` with a manually-set header).

Sequence exercised, each step screenshotted
(`docs/../` — see session artifacts, not committed to the repo):

1. Login → forced password change (bootstrap admin) → Projects page.
2. Create project "Rehearsal Project".
3. Create suite → draft revision → add one case → **Publish**
   (`window.confirm()` dialog handled) → revision shows `PUBLISHED`.
4. Create cycle against the published revision → execution screen shows
   the case as `NOT_RUN`.
5. Upload evidence via file input → thumbnail appears → fill actual
   result → click **PASS** → "Saved" confirmation, cycle auto-transitions
   to `IN_PROGRESS`.
6. Dashboard: **100% pass rate**, **100% evidence completeness**,
   **Go-Live Readiness: READY** (correct — the one P0-less case passed
   with evidence, no open defects) — confirmed via an explicit assertion
   in the driver script (`if (!dashboardText.includes('100%')) throw`),
   not just eyeballing a screenshot.
7. Reports page → real **Export Excel** and **Export ZIP Package**
   downloads (actual browser download events captured via
   `page.waitForEvent('download')`, not just an HTTP 200 assumption).

Console errors during the entire run: two `401`s, both the expected
initial `/auth/me` probe before login (the app's own documented,
intentional behavior) — no unexpected errors.

## 4. Downloaded file verification

```
Sheets: ['00_Cover', '01_Execution_Summary', '02_Test_Results',
         '03_NG_Defects', '04_Evidence_Index', '05_Revision_History',
         '06_Sign_Off']
Zip entries: ['rehearsal-project_Rehearsal-Cycle.xlsx', 'report.html',
              'evidence/REH-001_EVID-1.png', 'manifest.json']
testzip: None   (zip integrity check passed)
Manifest evidence: [{'evidence_id': 1, 'test_id': 'REH-001',
  'filename': 'evidence/REH-001_EVID-1.png',
  'sha256': 'f61eb2ac...11865', 'size_bytes': 74, 'status': 'ACTIVE',
  'missing': False}]
```

Both files opened and inspected with real tooling (`openpyxl`,
`zipfile`), not just checked for existence.

## 5. What this rehearsal did NOT cover (by design — see checklist)

- **Real Cloudflare R2** — this rehearsal ran with `STORAGE_BACKEND`
  unset (filesystem, the local-dev default). It does not substitute for
  `scripts/r2_staging_smoke_test.py` against the real bucket — that
  remains 🔴 BLOCKED, unexecuted, no credentials available here.
- **Screen Capture API / clipboard-paste** — evidence was captured via
  file upload (deterministic, automatable). The other two capture paths
  remain 🔴 BLOCKED per the checklist, same reasoning as before this
  rehearsal — a rehearsal in a headless-capable browser cannot supply
  what those specifically need (a real OS screen-share picker and a
  synthetic system clipboard with real image bytes).
- **Concurrent multi-user load** — this rehearsal was single-session;
  concurrency correctness is covered separately by
  `test_evidence_concurrency.py`'s real-threading test, not repeated here.

## Conclusion

Everything within this rehearsal's scope passed, cold, in a clean
environment, with real assertions (not just "it didn't crash"). This
satisfies requirement 12. It does **not**, by itself, clear the three
🔴 BLOCKED items in `docs/RELEASE_CHECKLIST.md` — those require
resources (real R2 credentials, a human at a real browser) that don't
exist in this development environment.
