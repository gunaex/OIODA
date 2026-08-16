# Evidence storage lifecycle and reconciliation

Companion to [ADR-0002](ADR-0002-evidence-storage-r2.md). This document
covers what ADR-0002 deferred: object key layout, how orphaned objects
can arise despite the upload flow's safeguards, how to detect and
resolve them, and the deliberate no-hard-delete policy.

## Object key layout

```
evidence/{project_slug}/{cycle_test_result_id}/{uuid4hex}.{ext}
```

- `{ext}` is derived from the *sniffed* MIME signature, never the
  client-supplied filename or claimed content type.
- The UUID component makes keys non-guessable regardless of content
  (ADR-0002 requirement 5) — do not change this to a purely
  content-hash-derived key without re-reading that requirement.
- The same key string is used verbatim by both storage backends: a
  relative path under `FilesystemEvidenceStorage`'s root, an object key
  under `R2EvidenceStorage`'s bucket.

## Every evidence object's source of truth

A `EvidenceItem.object_key` row in the project's SQLite DB is the only
thing that makes an object "real" from the application's point of view.
An object with no matching DB row is orphaned. A DB row whose object is
missing from storage is corrupt (should not normally happen — see below
for the one case that can produce it).

## How an orphan can occur (and how it's already minimized)

Per ADR-0002's failure-handling table, the upload endpoint writes to
storage *before* inserting the DB row, specifically so that:

- If the storage write fails, no DB row exists — nothing to reconcile.
- If the DB insert fails *after* a successful storage write, the
  endpoint immediately attempts a **compensating delete** of the object
  it just wrote.

The only realistic orphan scenario is the compensating delete itself
failing (e.g., a transient network blip between the backend and R2 right
after a DB error) — logged as `ORPHANED EVIDENCE OBJECT` at `ERROR`
level with the object key, specifically so it's greppable in production
logs without needing a separate alerting system for this MVP.

A process crash between the storage `put` succeeding and the DB
`commit` completing (e.g., the Fly machine is killed mid-request) is the
other realistic path to an orphan — no application code runs the
compensating delete in that case, since nothing catches a SIGKILL.

## Detecting orphans (objects with no DB row)

Not automated yet — a manual/scripted reconciliation, run periodically
or after a suspected incident:

```python
# Sketch, not a shipped script — adapt per environment.
# 1. List all objects under evidence/{slug}/ in R2 for a project.
# 2. Query that project's EvidenceItem.object_key for every row.
# 3. Any listed object key with no matching row is an orphan.
#    Confirm it's not mid-upload (check its LastModified timestamp is
#    older than a few minutes) before deleting — a very recent object
#    may just be a request still in flight.
```

Cost impact of leaving an orphan in place is small (R2 Standard pricing,
one screenshot) — treat this as a periodic hygiene task, not an
emergency.

## Detecting corrupt rows (DB rows with no matching object)

```python
# For each EvidenceItem row: storage.exists(row.object_key).
# A False here (outside of the brief in-flight-upload window) means the
# object was lost or never wrote successfully — should not happen given
# the write-before-insert ordering, but is exactly what this check is
# for. If found: this evidence item cannot be recovered (the original
# bytes are gone) — flag it for manual review, do not silently
# resurrect or fabricate content.
```

## Deletion and archive policy

The API only ever exposes **archive** (`PUT .../evidence/{id}/archive`,
admin-only, blocked while the cycle is locked) — it flips
`EvidenceItem.status` to `ARCHIVED` and touches nothing in storage. This
is deliberate (ADR-0002 requirement 8): evidence integrity depends on
originals never disappearing out from under an audit trail.

**A real purge/retention feature (permanently removing old archived
evidence and its object together) is explicitly out of scope for this
ADR.** If one is ever built, it must be:

- a separate, deliberate, audited admin action (not a side effect of
  archiving, not automatic based on age alone without an explicit
  project-level retention policy setting);
- logged with actor identity and timestamp, same as every other
  consequential action in this app;
- the only place in the codebase that calls `EvidenceStorage.delete()`
  on behalf of a real (non-orphaned, non-failed-upload) evidence item.

## Migration path (for when there is real data to migrate)

See ADR-0002's "Migration of previously stored evidence" section — as of
this writing there is no production data, so this is documented as a
future capability, not implemented:

1. For each `EvidenceItem` with a filesystem-relative `object_key`: read
   via `FilesystemEvidenceStorage.get(key)`.
2. Verify `sha256(bytes) == EvidenceItem.original_sha256` before doing
   anything else — refuse to migrate a file that doesn't match its
   recorded checksum.
3. Write via `R2EvidenceStorage.put(key, bytes, content_type)` — the key
   string is identical between backends, so no `object_key` update is
   even needed in the DB.
4. Verify via `R2EvidenceStorage.exists(key)` before deleting the
   filesystem copy.
5. Run in batches, log progress, and make it safely re-runnable (skip
   any key that already `exists()` in R2).

## R2 credential rotation

1. In the Cloudflare dashboard, create a **new** R2 API token (same
   bucket-scoped Object Read & Write permissions as the original — see
   `docs/DEPLOYMENT.md`'s bucket setup). Do not revoke the old one yet.
2. `fly secrets set R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=...` with
   the new token's values. Fly restarts the app machines automatically on
   a secrets change.
3. Verify: upload one piece of evidence through the running app, confirm
   it succeeds (proves the new credentials work end-to-end, not just
   that `fly secrets set` succeeded).
4. Only after step 3 passes, revoke the old API token in the Cloudflare
   dashboard.
5. No application code or data needs to change — object keys and bucket
   name are unaffected by a credential rotation, only the access
   key/secret pair.

## Quota recovery (a project is stuck over quota)

A project can end up at or over `storage_quota_bytes` in two ways: real
usage growth, or (rare, self-correcting — see ADR-0002's concurrency
handling) a resolved race. Recovery options, in order of preference:

1. **Archive evidence that's no longer needed** — does *not* free quota
   by itself (archived evidence still counts, requirement 3 — it's still
   consuming real storage), but is the correct first step before any
   destructive action, since it's what surfaces which evidence is safe to
   consider for the (currently unbuilt, deliberately out-of-scope) purge
   feature.
2. **Raise the project's quota**: `PUT /api/projects/{slug}/storage-quota`
   (ADMIN) with a larger `storage_quota_bytes`. The simplest fix when the
   growth is legitimate.
3. **Export and offload**: use the ZIP export to produce an authoritative
   copy of a completed cycle's evidence outside the app, as a precondition
   before ever considering a future purge feature for that cycle's
   evidence.

There is currently no automated quota-recovery action beyond raising the
limit — a purge/retention feature remains a deliberate future addition
(see "Deletion and archive policy" above), not built speculatively.

## Inaccessible-object recovery (R2 object exists in the DB but can't be reached)

Symptom: `GET .../evidence/{id}/original` returns 404 "Original file
missing from storage," or a ZIP export marks an entry `"missing": true`
in its manifest.

1. Confirm it's not a credential/connectivity problem first — check
   `GET /api/health` and try any other evidence download; if *everything*
   fails, this is an R2 outage or a credential issue (see rotation
   section above), not a single missing object.
2. If only one object is affected: it has almost certainly been lost
   (deleted out-of-band, e.g. manually in the R2 dashboard, or an
   unresolved orphan-cleanup race — see the reconciliation limitation
   noted above). There is no way to regenerate the original bytes — this
   is exactly why originals are immutable and why the DB row and object
   are written in that specific order (object first) to make loss rare,
   not impossible.
3. Record what happened (who/when/why, if known) via the project's normal
   audit trail conventions — don't silently delete the now-broken
   `EvidenceItem` row; a "missing" evidence record is itself meaningful
   audit information (the case was executed and evidence was captured,
   even if the artifact itself was later lost).
4. If this is discovered to be systemic (many objects, not one), stop and
   treat it as an incident — check R2 bucket lifecycle rules weren't
   accidentally configured to expire objects (this app's `put()` never
   sets an expiry, but a bucket-level lifecycle rule could still exist if
   someone configured one directly in Cloudflare, outside this app's
   control) — see `docs/CAPACITY.md` for the bucket configuration this
   app assumes.
