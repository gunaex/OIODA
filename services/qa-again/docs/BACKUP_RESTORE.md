# SQLite Backup, Restore, and Corruption Recovery

Covers the master DB and every per-project DB on the Fly volume.
Evidence binaries in R2 are a separate concern — see
`docs/EVIDENCE_STORAGE_LIFECYCLE.md`.

## Why per-project files matter here

Every project is its own SQLite file
(`data/projects/{slug}.db`) — the same property that gives project data
isolation (ADR-0001/rebuild prompt section 2) also means backup/restore
is naturally per-project: you never have to restore *all* projects to
fix *one*, and a corrupt project DB can't take down another project's
data.

## Backing up

```bash
cd backend
./.venv/Scripts/python scripts/backup_databases.py [optional/backup/dir]
```

Uses SQLite's **online backup API** (`sqlite3.Connection.backup()`), not
a raw file copy — it produces a transactionally consistent snapshot even
while the app is actively writing. A raw `cp` of a live SQLite file can
catch a mid-write/mid-transaction state and copy something the SQLite
library itself would refuse to open.

Default destination: `$DATA_DIR/backups/{UTC timestamp}/`, containing
`master.db` and `projects/{slug}.db` for every project that exists at
backup time. Verified working against real data during Phase 7 (backed
up, then confirmed with `PRAGMA integrity_check` and a direct row query
on the copy — both passed).

**Schedule**: not automated in this repository (no cron/scheduled-job
infrastructure exists yet). Recommended: a Fly.io scheduled machine or
an external cron hitting a small trigger, running this script daily at
minimum, before any schema-affecting deploy, and before any bulk/risky
admin operation (project delete, quota changes at scale). Copy the
resulting `backups/` directory off the Fly volume regularly (`fly sftp`
or a scripted `flyctl ssh` pull) — a backup that lives on the same
volume as the data it protects doesn't protect against volume loss.

## Restoring

**Full restore (disaster recovery)**:

1. Stop the backend (`fly scale count 0` or equivalent, so nothing
   writes during restore).
2. Replace `$DATA_DIR/master.db` and the relevant `$DATA_DIR/projects/
   *.db` files with the backup copies.
3. Restart the backend.
4. Sanity-check: `GET /api/health`, log in, confirm a known project is
   visible with expected data.

**Per-project restore** (the common case — one project's data needs to
roll back, the rest of the app keeps running):

1. Stop the backend (per-project restore while the app is live risks the
   in-memory `_project_engines` cache in `database.py` holding a stale
   connection to the file you're about to replace).
2. Replace only `$DATA_DIR/projects/{slug}.db` with its backup.
3. Restart the backend (clears the engine cache).
4. Sanity-check that project specifically.

## Corruption recovery

1. Detect: `sqlite3 path/to/file.db "PRAGMA integrity_check;"` — anything
   other than a single `ok` row means corruption.
2. First choice: restore from the most recent known-good backup (above)
   — simplest, and evidence-first discipline means you'd rather lose a
   little recent data than ship a subtly-corrupt DB.
3. If no recent backup exists: attempt `sqlite3 corrupt.db ".recover"`
   (modern SQLite CLI) piped into a fresh DB file, e.g.:
   ```bash
   sqlite3 corrupt.db ".recover" | sqlite3 recovered.db
   ```
   This rebuilds what it can from the page data directly, salvaging rows
   `.dump`/`.recover` are able to parse even from a damaged file. Treat
   the recovered file as suspect — re-run `PRAGMA integrity_check`
   against it, and manually spot-check a few tables (especially
   `evidence_items.original_sha256` values against R2, since a corrupted
   metadata row pointing at a real object is recoverable, but a
   corrupted row whose data can't be trusted should be flagged, not
   silently kept).
4. After recovery, run the app's own schema patch step (`ensure_columns`,
   automatic on next startup) to confirm the recovered file's schema is
   still compatible.

## What backup does *not* cover

- **R2 evidence binaries** — not touched by this script. See
  `docs/EVIDENCE_STORAGE_LIFECYCLE.md`'s reconciliation section; consider
  enabling R2 bucket versioning (a Cloudflare R2 feature, not something
  this app's code manages) as an additional, independent safety net for
  the binaries themselves.
- **Secrets** (`JWT_SECRET_KEY`, R2 credentials, `ADMIN_PASSWORD`) — live
  in Fly secrets, not in the SQLite files; back those up via your secrets
  manager / password manager, not this script.
