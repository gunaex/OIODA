# Deployment

Covers the backend (Fly.io) and its Cloudflare R2 evidence storage
dependency (ADR-0002). Frontend deploy (Cloudflare Pages) is unchanged
from the rebuild prompt's section 2 "Deploy" subsection — not repeated
here.

## Backend environment variables

None of these are committed anywhere — set them via `fly secrets set`
(production) or a local `.env` file, never in git. `backend/.env.example`
lists every variable with placeholder values.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATA_DIR` | prod only | `backend/data` | Fly volume mount path in production. |
| `ALLOWED_ORIGINS` | prod only | `http://localhost:5173` | Comma-separated CORS origins. |
| `JWT_SECRET_KEY` | prod only | ephemeral random | Session signing key — set before deploying or every restart logs everyone out. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | first boot | random | Bootstrap admin account. |
| `COOKIE_SECURE` | prod only | `false` | Must be `true` in production. |
| `STORAGE_BACKEND` | prod only | `filesystem` | `filesystem` (local dev) or `r2` (production). |
| `R2_ACCOUNT_ID` | if `STORAGE_BACKEND=r2` | — | Cloudflare account ID (from the R2 dashboard). |
| `R2_BUCKET_NAME` | if `STORAGE_BACKEND=r2` | — | The private bucket created below. |
| `R2_ACCESS_KEY_ID` | if `STORAGE_BACKEND=r2` | — | R2 API token access key. |
| `R2_SECRET_ACCESS_KEY` | if `STORAGE_BACKEND=r2` | — | R2 API token secret. |

## Setting up the R2 bucket

1. In the Cloudflare dashboard, go to **R2 Object Storage** → **Create
   bucket**. Name it something like `qa-again-evidence`. Location: Automatic.
2. Leave the bucket **private** — do not enable public access or attach a
   custom domain to it. This app never links directly to R2; every
   download goes through the authenticated backend route, which either
   streams bytes or issues a short-lived presigned URL after its own
   authorization check (ADR-0002).
3. Storage class: **Standard** (the default). Do not select Infrequent
   Access — this app's `R2EvidenceStorage` always writes with
   `StorageClass=STANDARD` regardless, but the bucket-level default
   should match so any tooling that inspects the bucket isn't surprised.
4. Go to **R2** → **Manage API tokens** → **Create API token**. Scope it
   to **Object Read & Write**, restricted to the one bucket created
   above (not "all buckets"). Copy the Access Key ID and Secret Access
   Key immediately — the secret is shown once.
5. The R2 Account ID is shown on the main R2 dashboard page (also visible
   in any bucket's **S3 API** connection details panel).

## Setting the secrets on Fly

```bash
fly secrets set \
  STORAGE_BACKEND=r2 \
  R2_ACCOUNT_ID=<account-id> \
  R2_BUCKET_NAME=qa-again-evidence \
  R2_ACCESS_KEY_ID=<access-key-id> \
  R2_SECRET_ACCESS_KEY=<secret-access-key> \
  --app qa-again-backend
```

(Alongside the existing `JWT_SECRET_KEY`, `ADMIN_EMAIL`,
`ADMIN_PASSWORD`, `ALLOWED_ORIGINS`, `COOKIE_SECURE` secrets from the
rebuild prompt's original deploy setup.)

## Local development

Leave `STORAGE_BACKEND` unset (or `filesystem`) — evidence is stored
under `backend/data/evidence/` exactly as before, zero configuration
required, matching every other local-dev default in this app. Point it
at a real (or moto-mocked, for testing) R2 bucket only when you
specifically need to exercise the R2 path locally.

## R2 staging smoke test — required before first production release

`tests/test_r2_storage.py` (moto-mocked) proves `R2EvidenceStorage`'s
boto3 calls are wired up correctly against *an* S3-compatible API. It
does not prove the real endpoint, real credentials, or real bucket
permissions work — only a live run against real R2 can. Run this once
against the staging bucket before the first production release, and
again after any credential/bucket change:

```bash
cd backend
R2_ACCOUNT_ID=... R2_BUCKET_NAME=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... \
  ./.venv/Scripts/python scripts/r2_staging_smoke_test.py
```

It exercises, against the real bucket: `put` → `head`(exists) → `get`
(byte-for-byte + checksum roundtrip) → an actual HTTP fetch of a
presigned URL (proving real endpoint/signing, not just that a URL
string was generated, and that the `Content-Disposition` filename
override applies) → `delete` (cleanup). Exits non-zero naming the
specific failed step. **This script has not been run in this
environment** — no real Cloudflare credentials are available here; it
must be run by whoever holds the staging R2 credentials before relying
on this in production.

## Verifying the R2 path after deploy (quick manual check)

```bash
curl -b cookies.txt -X POST https://api.qaagain.<yourdomain>/api/<slug>/cycles/<id>/results/<id>/evidence \
  -F "file=@screenshot.png"
```

A successful response with a real `id`/`original_sha256` confirms R2
connectivity, credentials, and bucket permissions are all correct. If
`STORAGE_BACKEND=r2` but any of the four `R2_*` variables is missing,
the backend returns a `500` naming the specific missing variable
(`app/storage/__init__.py::_required_env`) rather than a generic boto3
connection error — check that first.
