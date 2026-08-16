# Capacity Documentation

Grounded in the actual Fly.io + Cloudflare R2 architecture (ADR-0002) —
supersedes the original spec's Cloudflare Workers/D1/R2 free-plan
guardrails (`docs/FREE_PLAN_CAPACITY.md` was never written for this
rebuild and should not be resurrected; it assumed a different platform).

## SQLite databases (Fly volume)

- One `master.db` (users, project registry, runner tokens, quota
  config) + one file per project (`data/projects/{slug}.db`).
- SQLite handles single-digit-GB files comfortably; this app's per-
  project data volume (suites/revisions/cases/cycles/results/defects/
  sign-offs/evidence *metadata* — not the binaries) is text/small-int
  heavy, not binary — expect low tens of MB per active project even with
  hundreds of cases and dozens of cycles.
- **Concurrency**: SQLite serializes writers (one write transaction at a
  time per file). `database.py`'s project engines use `timeout=30`
  (Phase 7) so a concurrent write waits up to 30s for the current writer
  rather than failing immediately — verified under real concurrent load
  by `test_evidence_concurrency.py`. This is fine for this app's expected
  usage (a QA team, not a public multi-tenant SaaS with thousands of
  concurrent writers per project) — if a project ever needs many
  concurrent testers hammering the same cycle simultaneously, SQLite's
  single-writer model becomes the limiting factor before disk space does.
- **Fly volume sizing**: `fly.toml`'s `initial_size = '1gb'` is a
  starting point. Grow via `fly volumes extend` as project count/size
  grows — cheap and non-disruptive, no code change needed.

## R2 object storage

- Each evidence object: capped at 8MB (`MAX_EVIDENCE_SIZE_BYTES`), a
  screenshot in practice is typically 100KB–2MB.
- Default per-project quota: 5 GiB (`Project.storage_quota_bytes`,
  admin-adjustable per project — `PUT /api/projects/{slug}/storage-quota`).
  At ~500KB/screenshot average, that's roughly 10,000 evidence items
  before a project needs its quota raised.
- R2 Standard pricing model (as of this writing): storage + Class A
  (writes) + Class B (reads) operations, **no egress fee** — unlike S3,
  R2 doesn't charge for bandwidth out, which matters because every
  evidence download/export reads through it. Confirm current Cloudflare
  R2 pricing before committing to a specific per-project cost estimate;
  don't hardcode a price into application behavior.
- Bucket-level: no lifecycle rules are configured or assumed by this
  app's code (`put()` never sets an expiry) — if a lifecycle rule is
  added directly in the Cloudflare dashboard for cost control, it MUST
  exclude anything under `evidence/` or it will silently delete evidence
  outside this app's own archive/audit discipline. Document any such
  rule here if one is ever added.

## Request limits

- Fly.io `fly.toml` config: `shared-cpu-1x`, 256MB RAM,
  `auto_stop_machines`/`min_machines_running = 0` (scale-to-zero for a
  low-traffic internal tool) — a cold start adds latency to the first
  request after idle; acceptable for this app's usage pattern, would need
  revisiting (`min_machines_running = 1`) if idle-start latency becomes a
  real user complaint.
- Login rate limit: 5/minute per IP (slowapi). No other endpoint is
  rate-limited (see `docs/THREAT_MODEL.md` §9's accepted risk).

## Export memory usage

- Excel/ZIP export is generated **entirely in memory**
  (`io.BytesIO`, `report_zip.py`/`report_excel.py`) — no temp files, no
  streaming to disk. For a cycle with N cases and M evidence items
  averaging ~500KB each, peak memory during export is roughly
  `(workbook size) + M × 500KB` held simultaneously (each evidence file
  is read fully into memory, written into the ZIP, then the next is
  read) plus the assembled ZIP buffer itself.
- **Documented threshold**: comfortable up to a few hundred evidence
  items per export (~100–200MB working set) on the 256MB Fly machine
  configured in `fly.toml`. A cycle with evidence-heavy cases numbering
  in the thousands could approach or exceed that machine's memory and
  should either scale the machine (`fly scale memory`) or (a future,
  not-yet-built change) move to streaming ZIP generation
  (`zipfile.ZipFile` with a streaming writer + chunked reads from
  storage) rather than fully-buffered generation. Not built now because
  no real cycle at this project's current scale approaches that
  threshold — don't build ahead of a real requirement.
- Verified (not just estimated): `test_export_security.py::
  test_export_of_a_larger_cycle_completes_and_produces_a_consistent_manifest`
  exercises a 25-case export end-to-end; this is a sanity check, not a
  load test at the documented threshold above.

## Expected operating thresholds (summary table)

| Resource | Comfortable | Needs attention | Action |
|---|---|---|---|
| SQLite file size | < 500 MB | > 1 GB | Check for unbounded activity-log growth; `fly volumes extend` regardless |
| Fly volume free space | > 20% free | < 10% free | `fly volumes extend` |
| Project evidence quota | < 70% (informational threshold) | > 95% | Admin raises quota or archives; see `docs/EVIDENCE_STORAGE_LIFECYCLE.md` |
| Evidence items per export | < 200 | > 500 | Consider streaming export (not yet built) or splitting the cycle |
| Fly machine memory | steady-state well under 256MB | repeated OOM kills in logs | `fly scale memory` |

## What this app does NOT claim

Per the original spec's own discipline ("do not claim unlimited"): this
document describes *expected* comfortable ranges based on the
architecture's design, not load-tested hard limits at production scale.
No load/stress testing has been performed against a production-scale R2
bucket or SQLite file (see `docs/RELEASE_CHECKLIST.md` for what has and
hasn't been verified before release).
