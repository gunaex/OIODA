# Document Again — P0 Acceptance

Acceptance is defined by the P0 handover (preserved in
`PRODUCT_HANDOVER.md`). This file maps each criterion to where it is
implemented and how it is verified.

| Criterion | Where | Evidence |
|-----------|-------|----------|
| Project can be created | `svc.create_project` + `/api/projects` | dogfood step 1 |
| Requirement can be created | `svc.create_requirement` + `/api/requirements` | dogfood step 2 |
| Artifact can have multiple revisions | `svc.create_revision` | `test_clone_preserves_ancestry` |
| Confirmed revision is immutable | `require_editable` (409) | `test_confirmed_revision_is_immutable`, `test_api_rejects_edit_of_confirmed_revision` |
| Confirmed baseline freezes revision bindings | `create_baseline` / `resolve_baseline` | `test_baseline_retains_bound_child_revision` |
| New revision does not mutate old baseline | baseline bindings are stored rows | `test_new_child_revision_does_not_mutate_old_baseline`, dogfood step 14 |
| Requirement can trace to DR/design objects | `TraceLink` on semantic IDs | `test_trace_links_use_semantic_ids_only` |
| Annotation can bind to semantic object | `create_annotation` anchor check | `test_annotation_semantic_anchor` |
| DB table/field can exist as structured design objects | `DatabaseSchema/Table/Field/Relation` | `test_db_design_structured_model` |
| Change Request can link to affected objects | `change_request_links` | `test_change_request_revision_flow` |
| Minimal ecosystem-consistent workspace loads | `frontend/src/App.jsx` + pages | `npm run build` succeeds |
| First dogfood flow works | `scripts/dogfood.py` | 17/17 steps PASS |
| Critical invariant tests pass | `backend/tests/test_invariants.py` | 18/18 tests PASS |
| Documentation exists | `docs/` | this file + siblings |

## Verification commands

```bash
cd backend
.venv/bin/alembic check                # models == migration
.venv/bin/python -m pytest tests/ -q   # 18 passed
.venv/bin/python ../scripts/dogfood.py # 17/17 (fresh migrated DB)

cd ../frontend
npm run build                          # builds cleanly
```

## Non-goals confirmed not-built

Realtime collaboration, BPMN engine, enterprise DMS, complex ACL,
digital signatures, database migration execution, autonomous AI
approval, large workflow engine, service mesh, full ERD editor, full
architecture designer, full whiteboard, autonomous AI trace
generation. These are represented as explicit placeholders and model
reservations, not implemented behavior.
