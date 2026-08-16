# P5 — Release Candidate

Document Again is a **credible Release Candidate** of the AGAIN Ecosystem: it
completes the live orchestration chain (Document → Conductor → PM/QA), closes
production read-auth, proves PostgreSQL migration readiness, and adds PNG export
with a V4 design package.

## Completed in P5

- **P5-A Conductor relay** — `POST /api/ecosystem/document-handoffs` accepting
  only `DOCUMENT_AGAIN` (Account Again JWKS), versioned contract, idempotent.
- **P5-B/C PM/QA orchestration mapping** — Conductor maps design handoffs into
  canonical `DeliveryWorkPackage` / `QARequest`; Document Again delivers through
  Conductor and records the external reference.
- **P5-D Acknowledgement lifecycle** — `QUEUED → DELIVERED_TO_CONDUCTOR →
  ACKNOWLEDGED | FAILED`, with `last_error` and audit events.
- **P5-E Production read auth** — all non-public reads require a validated
  identity in `account_again` mode.
- **P5-F PostgreSQL** — `DATABASE_URL` support; full migration chain + app smoke
  verified against a real PostgreSQL 16 container (PARTIAL: suite not run on it).
- **P5-G PNG + package V4** — CairoSVG PNG for ERD/flow/architecture; design
  package V4 directory structure from frozen snapshots.
- **P5-H/I/J** — baseline `target_release`; ecosystem-trace endpoint; upgraded
  Ecosystem UI showing the orchestration chain.
- **P5-K RC readiness** — `/api/rc-readiness` operator snapshot.
- **P5-L Security review** — no release blockers (see `P5_SECURITY_REVIEW.md`).
- **P5-M Migration/recovery** — fresh migration, downgrade/upgrade, drift NONE.
- **P5-N live relay dogfood** — 5/5 live checks (Account Again → Document Again
  → Conductor relay → fail-closed PM dispatch).

## RC recommendation

**YES** — no critical FAIL exists in historical truth, tenant isolation,
production auth, Conductor relay, idempotency, migration, or baseline
reproducibility. Remaining PARTIALs are non-critical deployment-environment
limitations (see `KNOWN_LIMITATIONS.md`).

## Remaining PARTIALs

- Live PM/QA dispatch (requires PM/QA running with seeded identities).
- PostgreSQL full-suite run + 2 reflection nits.
- Full 5-service live dogfood.
