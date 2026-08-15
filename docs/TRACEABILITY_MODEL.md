# Document Again — Traceability Model

Traceability and annotation survive visual/document changes because
they bind to **stable semantic IDs**, never to pixel coordinates or
document text positions.

## SemanticObject

`semantic_objects` registers a canonical identity per project:

```text
REQ-0042
tbl_approval_history
fld_approval_history_approver_id
flow_purchase_approval
flow_step_finance_review
api_order_approve
```

Each row has:

- `semantic_id` — the canonical ID (unique per project)
- `object_type` — one of the `SemanticObjectType` enum values
- `display_name` — may change freely
- `entity_ref` — opaque row ID of the owning entity (e.g. a
  `DatabaseField.id`), when the object backs a structured row

Service helpers register these automatically: `create_requirement`,
`create_schema`, `create_table`, `create_field`, `create_relation` all
call `ensure_semantic_object`, so structured design data is
traceable and annotatable the moment it exists.

## TraceLink

`trace_links` is a directed, typed edge:

```text
(source_semantic_id) --relation_type--> (target_semantic_id)
```

Both endpoints must already be registered semantic objects —
`create_trace_link` rejects unknown IDs with a 422. Duplicate
(project, source, target, relation) links are rejected.

### Relation types

`DERIVED_FROM`, `IMPLEMENTS`, `DESIGNED_BY`, `VALIDATED_BY`, `AFFECTS`,
`REFERENCES`, `SUPERSEDES`, `GENERATED_FROM`, `CONFIRMED_BY`.

## Example graph (P0 side)

```text
Requirement ↔ UR ↔ DR ↔ DB ↔ API ↔ Flow
             ↘ ChangeRequest
```

P0 implements the Document Again side only. Task (PM) and Test (QA)
edges are future contract integrations, not faked.

## Impact lookup

`impact_of(project_id, semantic_id)` returns one-hop upstream
(sources) and downstream (targets) neighbors using trace links only.

## Invariant tests

- `test_trace_links_use_semantic_ids_only` — renaming the requirement
  title does not break the trace.
- `test_trace_rejects_unknown_semantic_ids` — no phantom edges.
- `test_change_request_revision_flow` — a CR traces to the revision it
  spawned via `GENERATED_FROM`.
