# ADR-0002 — Evidence object storage moves to Cloudflare R2 (Standard)

Status: accepted
Date: 2026-08-01
Supersedes: ADR-0001 decision 1 (filesystem-on-Fly-volume)

## Context

ADR-0001 decision 1 chose filesystem storage on the Fly.io persistent
volume for evidence originals and annotation data, explicitly rejecting
R2/S3-compatible object storage at the time ("no known volume-size or
CDN-delivery constraint exists yet to justify a second cloud
dependency"). Phase 5 built evidence/annotation storage against that
decision (`backend/app/database.py::project_evidence_dir`, direct
filesystem writes in `routers/evidence.py`).

The user has now made a deliberate, proactive infrastructure decision —
not triggered by hitting the volume's size ceiling, but as the intended
long-term shape of the system.

## Decision

**Evidence binary objects move to a private Cloudflare R2 bucket
(Standard storage class), accessed through R2's S3-compatible API.**
Everything else about the architecture is unchanged:

- React frontend on Cloudflare Pages.
- FastAPI + SQLAlchemy backend on Fly.io — **still 100% FastAPI**, not
  moved to Workers/D1/Pages Functions/any other Cloudflare compute
  platform. R2 is used purely as an S3-compatible object store the
  Fly-hosted backend talks to over HTTPS, exactly as it would talk to
  AWS S3.
- Per-project SQLite on the Fly volume — **unchanged**. Only evidence
  *binary payloads* (the original screenshot bytes and, if ever needed,
  a rendered annotation export) move to R2. All evidence *metadata*
  stays in SQLite: `EvidenceItem`/`EvidenceRevision` rows, checksums
  (`original_sha256`), exact sizes (`original_size_bytes`), MIME types,
  actor provenance (`captured_by`/`created_by`), timestamps, status
  (`ACTIVE`/`ARCHIVED`), and the object key that locates the binary in
  R2. The database remains the single source of truth for "what
  evidence exists and who touched it"; R2 only holds bytes.

### Why R2 over continuing with the Fly volume

Not a reversal driven by a technical problem with the volume — a
deliberate choice to decouple evidence storage growth from the backend's
compute instance, keep the Fly volume small (SQLite files only), and put
evidence behind Cloudflare's edge network (same provider already hosting
the frontend and DNS), while keeping the compute/API surface unchanged.

### Storage abstraction (requirement 1)

`backend/app/storage/` defines an `EvidenceStorage` interface
(`put`/`get`/`delete`/`exists`/`presigned_get_url`) with two
implementations: `FilesystemEvidenceStorage` (ADR-0001's original
approach, kept as the zero-config **local dev default**) and
`R2EvidenceStorage` (boto3 S3-compatible client, used in production via
`STORAGE_BACKEND=r2`). `routers/evidence.py` depends only on the
interface — swapping backends never touches router/model code.

### Non-guessable keys (requirement 5)

Object keys are `evidence/{slug}/{cycle_test_result_id}/{uuid4hex}.{ext}`
— a random UUID, not derived solely from content hash (a predictable
low-entropy file, e.g. a mostly-blank screenshot, would otherwise be
easier to guess by hash alone). `original_sha256` is still stored and
verified separately for integrity, decoupled from the key's
unguessability.

### Private objects, authenticated access (requirements 2, 3)

The R2 bucket is private — no public bucket policy, no direct object
URLs handed to the frontend. R2 credentials never leave the backend
process; they are read from environment variables server-side only. The
existing authenticated, project-scoped download route
(`GET /api/{slug}/cycles/{cycle_id}/results/{result_id}/evidence/{id}/original`)
is unchanged as the frontend-facing contract. Internally, after the
existing auth/authorization checks pass, the backend asks the storage
backend for the bytes (filesystem) or a **short-lived presigned GET URL**
(R2, 5-minute expiry) and redirects the already-authorized request to it.
No R2 credential or long-lived URL is ever returned to the browser.

### Idempotent uploads — safe retries (requirement 6)

Upload is content-addressed per result: before writing anything, the
handler checks for an existing `ACTIVE` `EvidenceItem` with the same
`(cycle_test_result_id, original_sha256)`. If found, that row is
returned as-is — no new DB row, no new R2 object, no duplicate storage
cost. A client that retries an upload after a dropped response (network
timeout, etc.) converges on the same evidence item instead of creating a
duplicate.

### Partial-failure handling (requirement 7)

Upload order is deliberately: **validate → check quota → check
idempotency → write to R2 → insert DB row**. Failure at each step has a
distinct, explicit outcome:

| Failure point | Outcome |
|---|---|
| Validation (size/MIME sniff) fails | 400, nothing written anywhere. Retry-safe. |
| Quota check fails | 400, nothing written anywhere. Retry-safe (after quota is addressed). |
| R2 `put` fails (network/auth/bucket error) | 502, no DB row created — nothing to clean up. Safe to retry. |
| R2 `put` succeeds, DB insert fails | The handler makes a **compensating delete** call against the object it just wrote, inside its own try/except (a failure to clean up is logged, not silently swallowed, and surfaces as a 500 with a distinct message: "evidence file was stored but its record could not be saved — do not assume it exists, retry the upload"). This is the one case that can produce a genuinely orphaned object if the compensating delete itself fails (rare: would require R2 to accept the write but then reject the delete) — covered by the reconciliation process in `docs/EVIDENCE_STORAGE_LIFECYCLE.md`. |

### Deletion and archive (requirement 8)

Unchanged from Phase 5's deliberate design: the API only ever exposes
**archive** (`status = ARCHIVED`), never a delete endpoint. The R2 object
is never removed by ordinary application use — archiving hides an item
from the default view without touching its stored bytes or its DB row.
A real retention/purge capability (permanently removing old archived
evidence and its R2 object together) is out of scope for this ADR — it
would be a separate, deliberate, audited admin feature, not an
incidental side effect of this storage migration.

### Per-project quota accounting (requirement 9)

`Project.storage_quota_bytes` (master DB, default 5 GiB) and
`Project.storage_warning_thresholds` (JSON array, default
`[70, 85, 95, 100]`, admin-configurable per project) drive a quota
endpoint (`GET /api/projects/{slug}/storage-quota`) that sums
`original_size_bytes` across **all** evidence for the project (`ACTIVE`
and `ARCHIVED` — archived evidence still occupies real storage) and
reports which threshold band current usage falls into. Upload is
rejected once usage would exceed 100% of quota.

### R2 Standard, not Infrequent Access (requirement 11)

`R2EvidenceStorage` never sets a `StorageClass` other than the default
Standard tier — evidence is accessed on-demand during active QA cycles,
not archival-pattern data, so Infrequent Access's retrieval-fee model is
the wrong fit.

### Environment variables (requirement 12)

New variables, documented in `backend/.env.example` and
`docs/DEPLOYMENT.md`, no secrets committed:

```
STORAGE_BACKEND=filesystem|r2   # default: filesystem (local dev)
R2_ACCOUNT_ID=
R2_BUCKET_NAME=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
```

`R2EvidenceStorage` derives the S3-compatible endpoint from
`R2_ACCOUNT_ID` (`https://{account_id}.r2.cloudflarestorage.com`) —
no separate endpoint variable needed.

## Migration of previously stored evidence

**Explicitly accepted pre-production reset — there is no data to
migrate.** This application has not been deployed anywhere; every
evidence file created so far exists only in local development/
verification runs, and this project's own convention (established since
Phase 1) has been to delete `backend/data/` after every local
verification pass before committing. No filesystem evidence has ever
existed outside a throwaway local session.

If a real migration were needed after a production deploy, the storage
abstraction makes it mechanical: for each `EvidenceItem`, read bytes via
`FilesystemEvidenceStorage.get(old_path)`, write via
`R2EvidenceStorage.put(new_key, bytes, content_type)`, update
`original_path` to the new key, verify `sha256(bytes)` still matches
`original_sha256` before deleting the old file. This is documented as a
future capability in `docs/EVIDENCE_STORAGE_LIFECYCLE.md`, not built now
— there is nothing for it to migrate yet.

## Consequences

- `backend/requirements.txt` gains `boto3`.
- Local development continues to work with zero configuration
  (`STORAGE_BACKEND` unset → filesystem), matching every other
  zero-config local-dev default in this codebase (DATA_DIR,
  JWT_SECRET_KEY, ADMIN_PASSWORD).
- Production Fly deploy must set the four `R2_*` secrets and
  `STORAGE_BACKEND=r2` via `fly secrets set` before evidence upload will
  work against real R2 (documented in `docs/DEPLOYMENT.md`).
- A reconciliation process becomes necessary in production (objects
  without matching DB rows, DB rows without matching objects) — see
  `docs/EVIDENCE_STORAGE_LIFECYCLE.md`. Not a new burden created by
  moving to R2 specifically — the same class of risk existed with the Fly
  volume, just now spans two systems instead of one, hence writing it
  down explicitly here.
