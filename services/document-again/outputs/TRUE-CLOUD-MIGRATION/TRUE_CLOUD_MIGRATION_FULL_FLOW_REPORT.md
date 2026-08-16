# AGAIN OS — TRUE CLOUD MIGRATION FULL-FLOW REPORT

**Date:** 2026-08-16
**Scope:** Full Loop execution of the TRUE CLOUD MIGRATION project across the
real AGAIN service repositories, under the Excel-only working-document policy
(`ADR-006` + `docs/governance/EXCEL_WORKING_DOCUMENT_POLICY.md`).

---

## 1. Summary verdict

```
EXCEL_WORKING_PACKAGE=PASS
DOCX_GENERATION=NOT_REQUIRED
PDF_GENERATION=NOT_REQUIRED
```

The complete working project package was produced and is inspectable in XLSX.
Baseline V1 and V2 were both pushed downstream through Conductor Main into
PM Again and QA Again and persisted, without V2 overwriting V1.

---

## 2. Project identity (real IDs)

| Item | Value |
|---|---|
| Project | `prj_02884ef10cdc459889f1` (key `TCM`, tenant `t-truecloud`) |
| Baseline V1 | `bsl_1d8584f6c27f46738c9b` — "True Cloud Migration v1.0" |
| Baseline V2 | `bsl_41f2e9a552ad49c1bfc9` — "True Cloud Migration v2.0" |
| UR v1 | `rev_a89db68095244b2a80a2` (CONFIRMED, rev 1) |
| DR v1 | `rev_d3a41614a56a40f1a9e4` (rev 1, SUPERSEDED) |
| DR v2 | `rev_86f214d247024520a5c1` (rev 2, CONFIRMED, based on DR v1) |
| Change request | `cr_946b8f9020414b3b8b04` (CR-0001, TRIAL_CHANGE) |
| Requirements | 11 (100% traced, `trace_coverage=100`) |

---

## 3. Answering the 10 required questions

### Q1. Was the complete working project package produced in XLSX?
**Yes.** Nine XLSX workbooks exist under `DOCUMENT-AGAIN/outputs/TRUE-CLOUD-MIGRATION/`:

- `01_REQUIREMENTS_REGISTER.xlsx` (11 requirements + header)
- `12_TRACEABILITY_MATRIX.xlsx` (Metadata / Document / Traceability)
- `13_CLARIFICATION_REGISTER.xlsx` (7)
- `14_ASSUMPTION_REGISTER.xlsx` (2)
- `15_DECISION_REGISTER.xlsx` (1)
- `16_UR_v1.xlsx`, `17_DR_v1.xlsx`, `22_DR_v2.xlsx` (generated this loop via the
  existing `GET /revisions/{id}/export?format=xlsx`)

No DOCX or PDF was generated during this loop.

### Q2. Can UR and DR be reviewed comfortably in Excel?
**Partially comfortable, improvable.** `export_revision_v2(xlsx)` renders each
UR/DR as a workbook with `Metadata`, `Document` (one row per section), and
`Traceability` sheets. UR v1 = 17 sections, DR v1 = 31 sections, DR v2 = 32
sections. This is a flat section list; grouping/indentation/freeze-panes/hyperlinks
are not yet applied — recorded in `POST_V1_BACKLOG` (item 8).

### Q3. Can requirements and designs be traced across worksheets?
**Yes.** `12_TRACEABILITY_MATRIX.xlsx` carries 32 trace links; each UR/DR XLSX
also embeds a `Traceability` sheet (33 rows). Example: `REQ-T2-005` →
`DERIVED_FROM dr_waves`, `dr_handover`, `f2_closure`; `REQ-T2-004` →
`DERIVED_FROM dr_pilot`, `f1_pilot`, and `ASM-0001 REFERENCES REQ-T2-004`.

### Q4. Can clarification / assumption / decision records be reviewed from the workbook?
**Yes.** `13_CLARIFICATION_REGISTER.xlsx` (7 open clarifications),
`14_ASSUMPTION_REGISTER.xlsx` (2 labelled assumptions, incl. private-path
replication), `15_DECISION_REGISTER.xlsx` (1 decision: documentation deliverables,
not deployment implementation).

### Q5. Can V1 and V2 be distinguished clearly?
**Yes.** Baseline bindings are immutable and never re-resolved:

- V1 binds UR rev 1 + DR rev 1 (`rev_d3a41614a56a40f1a9e4`, SUPERSEDED).
- V2 binds UR rev 1 (unchanged) + DR rev 2 (`rev_86f214d247024520a5c1`, CONFIRMED).
- DR snapshot size differs (19,618 vs 20,045 chars); `change_set
  "Private-only connectivity"` records `REQ-T2-003` and `REQ-T1-006` as MODIFIED;
  `CR-0001` AFFECTS the same two requirements. V2 never overwrote V1.

### Q6. Are PM and QA references visible against the correct baseline?
**Yes, per-baseline.** Persisted in PM/QA:

| Baseline | PM workPackageId (external_work_references) | QA qa_request_id (external_qa_requests) |
|---|---|---|
| V1 | `pmh_acf23d42585044b580b9` (MAPPED) | `qah_844fcb2bde6d4eac9648` (RECEIVED) |
| V2 | `pmh_10e67890a87d4a8ca5cb` (MAPPED) | `qah_878171fa5b9948119e54` (RECEIVED) |

PM `pm-status` returns distinct status per baseline (`correlationId`
`pm:…:bsl_1d8584f6…` vs `pm:…:bsl_41f2e9a5…`). The correlation IDs encode the
baseline id, so the PM/QA references are unambiguously against the correct baseline.

### Q7. Can reviewers add comments or review notes without changing semantic truth?
**Yes.** Document Again keeps review/comment state in dedicated tables
(`reviews`, `comment_threads`, `confirmations`, `annotations`) separate from
immutable `artifact_revisions` snapshots. Adding a comment never mutates a
confirmed revision (editing requires clone-as-new-revision). The handoff
delivery path carries only immutable references (`baseline_id`,
`artifact_revision_ids`), never mutable review state.

### Q8. Are architecture and process-flow views accessible from the Excel package?
**Yes, as supporting renders.** `06/07_ARCHITECTURE_TRACK1.svg/png`,
`08/09_ARCHITECTURE_TRACK2.svg/png`, `10/11_MIGRATION_FLOW.svg/png` exist, and
the traceability sheets reference the architecture diagrams (`arch_track1`,
`arch_track2`) and process flows (`flow_migration_factory`, `flow_wave_ops`).
XLSX is the primary artifact; SVG/PNG remain supporting renders only.

### Q9. Is any important information still only accessible through backend APIs?
**Yes, partially — the review/change audit trail.** Registers, UR/DR, trace, and
baseline truth are in XLSX. But the live review/comment threads, confirmation
evidence, and change-request semantic diff (`change_sets`/`change_items`) are
currently queryable only via Document Again's API or the SQLite store — they are
not yet rendered into a workbook. Backlog item: emit review/comments + change-log
sheets into the master workbook.

### Q10. What Excel UX improvements belong in POST_V1_BACKLOG?
1. Consolidate 9 workbooks into one master `TRUE_CLOUD_MIGRATION_AGAIN.xlsx`.
2. UR/DR `Document` sheet grouping, indentation, freeze panes, filters.
3. Cross-sheet hyperlinks for traceability navigation (SOW → REQ → UR → DR →
   Arch/Flow → Baseline → Conductor → PM/QA).
4. Add review/comment + change-log + revision-history sheets.
5. External-reference normalisation (see below).

---

## 4. Defects found and fixed (classified)

| # | Defect | Class | Fix |
|---|---|---|---|
| 1 | Conductor `_map_execution` sent `engineeringContext.requirements` as `[]` (array) but canonical `DeliveryWorkPackage` requires a string → PM rejected 422. | BLOCKING, Conductor mapping | Joined requirement ids into a string. |
| 2 | Conductor `_map_qa` sent `releaseCandidate` without required `repo`/`branch`/`commit` → QA rejected 422. | BLOCKING, Conductor mapping | Mapped project→repo, baseline→branch, bound design revision→commit (honest design identifiers). |
| 3 | Local Account Again (`:8001`) was a stale process serving an unlinked SQLite inode (no `DOCUMENT_AGAIN` identity, 500 on `/auth/service-token`). | BLOCKING, stale runtime | Started a fresh canonical Account Again on `:8011` with a fresh bootstrapped DB; configured the loop services against it. Non-destructive to the running process. |

## 5. External-reference semantics (not blocking, → backlog)

Document Again stores Conductor's `externalReferenceId` verbatim. PM returns its
internal `ExternalWorkReference.id` (e.g. `7`/`9`) and QA's response uses
`externalQARequestId`, while Conductor's QA branch reads `externalReferenceId`
and falls back to the correlation id. The loop is complete and traceable via the
correlation id + handoff id, but the stored reference should be normalised to the
canonical `workPackageId` / `qaRequestId` (backlog item 9).

## 6. Honest QA state

QA intakes both requests but leaves them `RECEIVED` (unmapped, no TestCycle)
because the QA project has no published revision to validate against — QA did not
fabricate a result. This is contract/handoff verification, not real customer
infrastructure validation (which the SOW does not request — Database/API remain
`NOT_APPLICABLE`).

---

## 7. Runtime topology used for this loop

| Service | URL | Note |
|---|---|---|
| Account Again (fresh) | `http://127.0.0.1:8011` | fresh bootstrapped DB, tenant `t-truecloud`, DOCUMENT_AGAIN + CONDUCTOR_MAIN secrets |
| Conductor Main | `http://127.0.0.1:8010` | relay `/api/ecosystem/document-handoffs` |
| PM Again | `http://127.0.0.1:8000` | intake `/api/ecosystem/delivery-work-packages` |
| QA Again | `http://127.0.0.1:8002` | intake `/api/ecosystem/qa-requests` |
| Document Again | in-process (TestClient), account_again auth | real delivery client → real Conductor |
