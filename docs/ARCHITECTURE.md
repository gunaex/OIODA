# Document Again — Architecture

## Role

Document Again is the AGAIN ecosystem authority for requirement,
technical design, revision, baseline, review, confirmation,
annotation, decision, change request, traceability, impact analysis,
project memory, and reproducible export.

It is a **living design-knowledge system**. Generated files (UR/DR
PDF, data dictionary, diagrams) are outputs. Structured, versioned
objects are the source of truth.

## Independence

Document Again is an independent product. It does not share a
database with PM Again, QA Again, Conductor Again, or Account Again
(AGAIN ADR-001). It does not execute PM work or QA verification.

Future integrations will be contract-based (AGAIN ADR-002/003). P0
does not fake those integrations.

## Selected stack

```text
Frontend    React 19 + Vite 8 + Tailwind 4 + React Router 7
Backend     FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2
Storage     SQLite (single file, project-scoped rows)
IDs         Stable string IDs (opaque for internals, canonical for semantics)
Transport   REST / JSON under /api
```

Rationale: match the PM/QA frontend toolchain so the ecosystem UX
stays consistent, keep a production-friendly local backend with a
real migration path, and avoid infrastructure that P0 does not need.

## Process topology

```text
Browser (Vite :5175)
    └── /api  →  FastAPI (:8002)
                    └── SQLite  backend/data/document-again.db
```

Ports are chosen so Document Again can run beside PM (:8000/:5173)
and QA without collision.

## Layering

```text
UI workspace
    └── HTTP routers  (thin)
            └── Domain services  (invariants live here)
                    └── SQLAlchemy models
                            └── SQLite
```

Critical rules (immutability, baseline binding, clone ancestry,
semantic-only traces) are enforced in the **service layer**, not in
the UI and not as "please don't click this" conventions.

## Data ownership

| Object | Owner | Notes |
|--------|-------|--------|
| Requirement | Document Again | Canonical, independent of generated UR/DR text |
| Artifact + Revision | Document Again | Revision is the unit of confirmation |
| Baseline | Document Again | Frozen revision bindings, not a status flag |
| SemanticObject | Document Again | Stable identity for trace + annotation |
| DatabaseSchema/Table/Field/Relation | Document Again | Structured design model; diagram is a view |
| Annotation / Review / Confirmation | Document Again | Confirmation makes a revision immutable |
| ChangeRequest | Document Again | Must spawn new revisions; never mutates a baseline |
| Task / schedule | PM Again | Out of scope |
| Test result / evidence verdict | QA Again | Out of scope |
| Identity / tenant | Account Again | P0 uses a local actor header only |

## Source-of-truth rules

```text
Canonical model
    ↓
Artifact revision snapshot  (document view at a point in time)
    ↓
Baseline bindings           (which revisions belonged together)
    ↓
Export / diagram / file     (reproducible output)
```

- Live structured objects (tables, fields, requirements) are the
  **working** design.
- A DRAFT revision snapshot may be synced from the working model.
- Leaving DRAFT freezes that snapshot.
- A baseline stores exact `artifact_id → artifact_revision_id` pairs
  and never re-resolves to "latest".

## Identity

Two ID families:

1. **Opaque entity IDs** — `prj_…`, `art_…`, `rev_…`, `bsl_…`.
   Stable, never reused, not display names.
2. **Canonical semantic IDs** — `REQ-0042`, `tbl_approval_history`,
   `fld_approval_history_approver_id`, `flow_purchase_approval`,
   `api_order_approve`. These are the IDs used by TraceLink and
   Annotation anchors.

Display titles may change. IDs must not.

## Actor model (P0)

P0 does not implement Account Again, ACL, or digital signatures.

Every mutating request accepts `X-Actor` (default `local-user`).
That string is stored as `created_by` / `confirmed_by`. This is
enough to make confirmation attributable. It is not authentication.

## AI boundary

No AI is wired in P0. Future AI may draft, summarize, or suggest.
It must never confirm, approve, invent traces as fact, overwrite a
confirmed baseline, or silently change schema.

## Growth without redesign

The P0 schema already separates:

- working objects vs frozen revision snapshots
- semantic identity vs document layout
- baseline bindings vs current draft pointers
- annotation anchors vs optional canvas coordinates

Those separations are the reason P0 exists. Features (ERD engine,
whiteboard, BPMN, export, Account Again) plug in later without
replacing these tables.
