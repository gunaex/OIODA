# Document Again — POST_V1_BACKLOG

Enhancements deferred past v1.0 (not started; no new feature work in P6).

1. ~~Live PM/QA end-to-end dispatch~~ — VERIFIED in the TRUE CLOUD MIGRATION Full Loop (2026-08-16): V1+V2 execution→PM and QA handoffs delivered through Conductor Main to real PM/QA and persisted (PM MAPPED, QA RECEIVED).
2. PostgreSQL full-suite CI + resolve the 2 reflection nits.
3. Full 5-service live ecosystem dogfood (AA + DA + Conductor + PM + QA).
4. PNG rasterization on platforms without Homebrew cairo (bundled renderer).
5. Richer design-package contents (change-log/audit files generated directly).
6. Conductor golden-flow integration test drift fixes.

## Full Loop findings (2026-08-16)

7. **Single master workbook** — current True Cloud XLSX output is 9 separate
   workbooks (requirements, trace, 3 registers, UR/DR). Consolidate into one
   navigable `TRUE_CLOUD_MIGRATION_AGAIN.xlsx` per the Excel-only policy.
8. **UR/DR XLSX section hierarchy** — `export_revision_v2(xlsx)` renders a flat
   `Document` sheet (section per row) with no grouping/indentation/freeze-panes
   yet. Add grouping + filters + cross-sheet hyperlinks for human review UX.
9. **External-reference semantics** — Document Again stores Conductor's
   `externalReferenceId` verbatim. PM returns its internal `ExternalWorkReference.id`
   (integer) and QA returns `externalQARequestId` (internal id) while Conductor's
   QA branch reads `externalReferenceId` (never present → falls back to
   correlationId). Normalise so the stored reference is the canonical
   `workPackageId` / `qaRequestId` (which is the handoff id) for round-trip lookup.
10. **QA stays RECEIVED (honest)** — QA intakes the QARequest but leaves it
    unmapped (no TestCycle) because the QA project has no published revision to
    validate. This is correct fail-closed behaviour; document the operator path
    to map a revision and produce a real QAResult.
11. **Stale local Account Again process** — a long-running `uvicorn` on `:8001`
    kept serving an unlinked SQLite inode (7 identities, `DOCUMENT_AGAIN` missing)
    and returned 500 on `/auth/service-token`. Full Loop used a fresh AA on
    `:8011` with a fresh bootstrapped DB instead. Consider a health/liveness
    guard that detects DB-file replacement.
