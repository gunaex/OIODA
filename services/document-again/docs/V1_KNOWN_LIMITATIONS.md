# Document Again v1.0 — Known Limitations

1. **Live PM/QA dispatch** requires PM Again and QA Again running with seeded
   `PM_AGAIN`/`QA_AGAIN` service identities; the Document → Conductor relay is
   live-verified, the final hop is mapped and unit-tested but not live-run.
2. **PostgreSQL**: full migration chain + smoke verified on real PostgreSQL 16;
   the automated suite is not run on it, and 2 reflection nits remain
   (`POSTGRESQL_READINESS.md`).
3. **PNG export** requires the cairo native library (`cairosvg`) at runtime.
4. **Account Again session expiry/revocation** has no validation endpoint today;
   validation is account-level entitlement (fail-closed).
5. **Conductor Main** has 7 pre-existing live-service integration test failures
   (outside Document Again's boundary, verified unchanged).
6. Local development uses SQLite; production uses `DATABASE_URL`.
