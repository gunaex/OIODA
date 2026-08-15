# Document Again — Annotation, Review & Confirmation Model

## Annotation

`annotations` binds a comment / question / decision to a **semantic
anchor**, not to a layout position.

```text
Annotation
  project_id
  artifact_revision_id   (optional — which revision was open)
  anchor_object_type     DOCUMENT_SECTION | DB_TABLE | DB_FIELD | …
  anchor_semantic_id     the stable semantic ID (REQUIRED)
  canvas_x / canvas_y    optional visual placement only
  type                   COMMENT | QUESTION | … | CHANGE_REQUEST
  content
  drawing_payload        optional drawing JSON
  status                 OPEN | REPLIED | RESOLVED | REOPENED
  thread_id              optional grouping into a CommentThread
```

### Anchor types

`DOCUMENT_SECTION`, `DB_TABLE`, `DB_FIELD`, `FLOW_STEP`,
`API_ENDPOINT`, `DIAGRAM_NODE`, `SCREEN_REGION`.

### Annotation types

`COMMENT`, `QUESTION`, `CLARIFICATION`, `DECISION`, `ASSUMPTION`,
`ISSUE`, `CHANGE_REQUEST`.

### Anchor rule

`create_annotation` verifies the anchor semantic object exists and
rejects unknown anchors with a 422. Coordinates are stored for visual
placement but are **never** the anchor — deleting a canvas or
reflowing a document never orphans an annotation.

### Lifecycle

`OPEN → REPLIED → RESOLVED`, plus `REOPENED`. `set_annotation_status`
validates the target status.

## CommentThread

`comment_threads` groups annotations into a resolvable discussion.
P0 persists threads and the `thread_id` reference; a full threaded
inbox is a P1 surface.

## Review

`reviews` records a verdict on a revision:

- `artifact_revision_id`, `reviewer`, `verdict`
  (`APPROVE` / `CHANGES_REQUESTED`), `comment`.

## Confirmation

`confirmations` records the authoritative freeze:

```text
Confirmed By    (actor)
Confirmed At
Revision        (artifact_revision_id)
Comment
Evidence        (JSON — e.g. review walkthrough)
```

A confirmed revision becomes immutable (see
[REVISION_BASELINE_MODEL.md](REVISION_BASELINE_MODEL.md)). P0 stores
the confirmation record and enforces immutability; enterprise digital
signatures are explicitly out of scope.

## Invariant tests

- `test_annotation_semantic_anchor` — annotation stays bound to
  `REQ-0001` after status change.
- `test_annotation_rejects_unknown_anchor` — no phantom anchors.
- `test_db_design_structured_model` — a DB field is annotatable the
  moment it is created.
