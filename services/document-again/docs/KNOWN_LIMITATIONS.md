# Known Limitations (Release Candidate)

1. **Live PM/QA dispatch is PARTIAL.** Document → Conductor relay is live and
   verified; Conductor → PM/QA dispatch requires PM Again and QA Again running
   with seeded `PM_AGAIN` / `QA_AGAIN` service identities. The mapping is
   implemented and unit-tested; the full 5-service run was not completed in P5.
2. **PostgreSQL: migrations + smoke validated, full test suite not run on
   postgres.** Two reflection nits (`architecture_nodes` unnamed unique
   constraint; `artifacts.current_draft_revision_id` `use_alter` FK) are
   documented in `docs/POSTGRESQL_READINESS.md`.
3. **Conductor Main pre-existing test failures (7)** are live-service
   integration tests unrelated to P5 (verified unchanged by stash); they live in
   the Conductor repository, outside Document Again's boundary.
4. **Account Again session expiry/revocation** has no validation endpoint today;
   Document Again validates account-level entitlement against AA's actual
   contract (fail-closed).
5. **PNG export** requires the cairo native library at runtime.
6. **Local dev** remains SQLite; production uses `DATABASE_URL`.
