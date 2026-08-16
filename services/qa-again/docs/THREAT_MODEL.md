# Threat Model

Status: current as of Phase 7 (2026-08-01)
Grounded in the actual deployed architecture: React on Cloudflare Pages,
FastAPI + SQLite on Fly.io, evidence binaries in a private Cloudflare R2
bucket (ADR-0002). Supersedes any threat-model language in the original
pre-rebuild spec (which assumed Workers/D1/R2/Access) — see the rebuild
prompt section 7 for that supersession note.

## 1. Architecture and trust boundaries

```
Browser (tester's machine)
   │  HTTPS, cookies (SameSite=None; Secure in prod)
   ▼
Cloudflare Pages (static React build)          — no compute, no secrets
   │  HTTPS, CORS-restricted, credentialed fetch
   ▼
Fly.io — FastAPI backend                        — holds all secrets
   │  SQLite files on the Fly volume (metadata)
   │  HTTPS, S3-compatible API, private bucket
   ▼
Cloudflare R2 — evidence binaries only           — never public
```

Trust boundaries crossed: browser → Pages (public internet), browser →
Fly backend (public internet, credentialed), Fly backend → R2 (backend
credentials only, never exposed to the browser).

## 2. Assets

- User credentials (bcrypt-hashed passwords, JWT signing secret, refresh
  tokens hashed at rest).
- Project/suite/revision/case/cycle/result data (SQLite, per-project
  files — the project boundary *is* the file).
- Evidence binaries (screenshots) — potentially sensitive (internal
  application screens, PII in test data).
- R2 credentials (`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`) — full
  access to the evidence bucket if leaked.
- Runner tokens (HYB-0) — scoped to hybrid run creation, not evidence
  storage credentials.

## 3. Authentication

- bcrypt password hashing, no plaintext ever stored.
- Short-lived (30 min) JWT access token in an httpOnly cookie — not
  readable by page JS, mitigates XSS token theft for the access token
  specifically (refresh token has its own, path-scoped cookie
  `/api/auth`, also httpOnly).
- Opaque refresh token (7 days), stored **hashed** in the DB, rotated on
  every use — a DB leak alone doesn't hand out a working refresh token,
  and a stolen-and-used refresh token is invalidated for its next use
  (limits replay).
- `Authorization: Bearer` also accepted (documented as a testing
  convenience) — a Bearer-authenticated request is **not** subject to
  the CSRF Origin check (see §5), since a browser never auto-attaches an
  Authorization header the way it does a cookie. Operationally: don't
  put a long-lived bearer token in anything a browser would run.
- Login is rate-limited (5/minute, slowapi) — mitigates credential
  stuffing/brute force. Verified: `test_security_boundaries.py::
  test_login_is_rate_limited`.
- Bootstrap admin account is forced through `must_change_password` on
  first login — a leaked/guessed bootstrap password can't be used
  beyond one password-change action.

## 4. Authorization

- Three roles: `ADMIN` > `TESTER` > `VIEWER`, global per user (ADR-0001
  decision 2) — not per-project. `VIEWER` is read-only everywhere;
  `TESTER` can execute/upload/author; `ADMIN`-only for user management,
  project archive/delete, revision publish, cycle lock/reopen, N/A
  review, sign-off, storage quota changes, evidence archive.
- Every project-scoped route resolves `slug` to its own SQLite file —
  there is no cross-project query possible by construction (not a
  `WHERE project_id = ?` filter that could be forgotten on one query;
  the database connection itself is scoped). Verified:
  `test_security_boundaries.py::test_project_data_is_isolated_by_slug`,
  `test_evidence_security.py::
  test_evidence_from_one_project_is_not_reachable_through_another_projects_slug`.
- Role boundaries verified end-to-end (not just code review):
  `test_security_boundaries.py::test_viewer_can_read_but_not_write`,
  `test_tester_cannot_admin_only_actions`,
  `test_evidence_security.py::test_viewer_can_download_evidence_but_not_upload_or_archive`.

## 5. CSRF

**Finding, closed in Phase 7**: cookies are `SameSite=None` in
production (required — Pages and Fly are different origins), so the
cookie is sent on cross-site requests. CORS's `allow_origins` prevents a
malicious page's JS from *reading* our responses but does not by itself
stop a CORS-"simple" request (needs no preflight) from executing
server-side with the victim's cookie attached. Most endpoints require
`Content-Type: application/json`, which forces a preflight that
`allow_origins` blocks — safe. The evidence-upload endpoint accepts
`multipart/form-data`, which is CORS-simple and was exploitable.

**Mitigation**: `main.py::csrf_origin_check` rejects any cookie-
authenticated (not Bearer-authenticated) `POST`/`PUT`/`PATCH`/`DELETE`
whose `Origin` (or `Referer` fallback) header doesn't match
`ALLOWED_ORIGINS`. Verified:
`test_security_boundaries.py::test_cookie_authenticated_write_without_origin_is_rejected`,
`test_cookie_authenticated_write_with_wrong_origin_is_rejected`,
`test_bearer_token_write_is_not_subject_to_origin_check`.

## 6. CORS

`allow_origins` is an explicit list (never `"*"`), required for
`allow_credentials=True` to function at all per the Fetch spec (browsers
refuse `*` + credentialed). Verified:
`test_security_boundaries.py::test_cors_preflight_reflects_only_allowed_origin`
confirms a disallowed origin does not get reflected in
`Access-Control-Allow-Origin`.

## 7. Evidence storage (R2, ADR-0002)

- Bucket is private — no public bucket policy, no direct object URLs
  ever handed to the frontend.
- R2 credentials live only in Fly secrets, read server-side.
- Object keys are UUID-based (non-guessable) — see ADR-0002 requirement 5.
- Uploads are sniffed by magic bytes, not trusted by claimed
  Content-Type — a `.png`-labeled non-image is rejected. Verified in
  Phase 5/6 (`test_evidence_storage.py::test_spoofed_content_type_is_rejected`).
- Downloads: authorization happens in the backend *before* a presigned
  URL is even generated; the presigned URL is short-lived (300s) and
  carries a `ResponseContentDisposition` override so the real filename
  is shown without exposing the object key as a display name. Verified:
  `test_evidence_security.py::test_download_always_requests_a_short_presigned_expiry`.
- Oversized files rejected before any I/O (8MB cap). Verified:
  `test_evidence_security.py::test_oversized_file_is_rejected`.
- Malicious filenames are sanitized for display and never used to
  construct a storage path in the first place (UUID keys). Verified:
  `test_evidence_security.py::test_malicious_filename_never_reaches_the_storage_key_or_disk`.

## 8. Export (Excel/ZIP)

- Every evidence byte in a ZIP export is read server-side via
  `EvidenceStorage.get()` — never a presigned URL substituted in. A
  missing object is recorded in the manifest as `"missing": true`, not a
  crash. Verified in Phase 6.
- ZIP entry names are derived from a slugified checkpoint code
  (`_safe_slug`), which strips path separators and `..` sequences — a
  checkpoint code crafted as a path-traversal payload cannot produce an
  entry outside `evidence/`. Verified:
  `test_export_security.py::test_zip_entries_never_escape_the_evidence_directory_via_checkpoint_code`.
- **Finding, closed in Phase 7**: openpyxl raises `IllegalCharacterError`
  and aborts the *entire* export if any cell contains an XML-illegal
  control character (e.g. a literal NUL byte pasted into an actual-result
  field) — one bad field could crash every export for a cycle. Fixed:
  `report_excel.py::_clean_cell` strips illegal characters before every
  cell write. Verified:
  `test_export_security.py::test_zip_entries_handle_special_characters_without_corrupting_archive_structure`.
- Export generation is fully in-memory (`io.BytesIO`) — no temp files
  written, nothing to clean up, nothing to leak via a predictable temp
  path. Verified: `test_export_security.py::test_export_leaves_no_temp_files_behind`.
- Export endpoints require authentication and are project-scoped the
  same way every other route is. Verified:
  `test_export_security.py::test_export_requires_authentication`,
  `test_export_for_nonexistent_cycle_in_a_different_project_404s_not_leaks`.

## 9. Rate limiting and abuse

- Login: 5/minute (slowapi).
- No other endpoint is currently rate-limited. **Accepted risk for this
  release**: an authenticated user (any role) could issue a large number
  of evidence uploads in a short window; the storage-quota check bounds
  total *storage* impact but not request volume/Fly compute cost. Not
  fixed this phase — flag for a future phase if usage patterns show it's
  a real problem, not built pre-emptively for a threat with no evidence
  yet (matches this project's general "don't build ahead of a real
  requirement" discipline).

## 10. Known limitations carried into this release (explicit, not silently dropped)

- **Real Cloudflare R2 staging smoke test not executed** — no live
  credentials in the development environment. See `docs/RELEASE_CHECKLIST.md`.
- **Screen Capture API / clipboard-paste acquisition** — implemented,
  but `getDisplayMedia` cannot be exercised in a headless browser, and
  clipboard paste needs a synthetic `ClipboardEvent` with real image
  bytes; neither has real-browser acceptance evidence yet. Both share
  the exact upload code path already verified via file input, so the
  residual risk is narrow (the two browser-API call sites themselves),
  but it is not zero.
- **Hybrid execution beyond HYB-0 remains disabled** — Track B stays
  paused per explicit instruction; no new attack surface from HYB-1+ is
  introduced or needs modeling yet.
- **No hard-delete/purge for evidence** — deliberate; see
  `docs/EVIDENCE_STORAGE_LIFECYCLE.md`. Phase 7 does not introduce a
  retention policy (none was requested).
- **No per-endpoint (beyond login) rate limiting** — see §9.

## 11. Out of scope for this threat model

- Cloudflare-platform-level threats (DDoS at the edge, Cloudflare's own
  infrastructure security) — inherited, not this application's
  responsibility to model.
- Physical/OS-level security of the Fly.io host — Fly's responsibility.
- Supply-chain attacks on npm/PyPI dependencies — not audited this
  phase; a `pip-audit`/`npm audit` pass would be a reasonable Phase 8
  addition if this project continues past MVP.
