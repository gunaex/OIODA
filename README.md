# Document Again

Living requirement + technical-design workspace and the AGAIN ecosystem
authority for **requirement, design, revision, baseline, confirmation,
annotation, traceability and change memory**.

> Files are outputs. Structured, versioned design knowledge is the
> source of truth.

## What exists (P0)

- Canonical **Requirement** model independent of generated documents
- Generic **Artifact / ArtifactRevision** with an explicit lifecycle
  (`DRAFT → IN_REVIEW → CONFIRMED → SUPERSEDED → ARCHIVED`)
- **Immutable confirmed revisions** — editing requires *clone as new
  revision*, ancestry preserved
- **Baselines** that freeze exact artifact→revision bindings and never
  re-resolve to latest
- **SemanticObject** identity layer (`REQ-0042`, `tbl_approval_history`,
  `fld_approval_history_approver_id`, …) with **TraceLink** graph and
  impact lookup
- **Annotations** anchored to semantic objects (coordinates are
  optional placement, never the anchor)
- **Review / Confirmation** records with actor, time, comment, evidence
- **ChangeRequest** as a first-class object that spawns new revisions
  and never mutates an old baseline
- Structured **database design model** (schema/table/field/relation)
  with the data dictionary generated as a pure view
- Ecosystem-consistent three-pane workspace UI

## Stack

FastAPI · SQLAlchemy 2 · Alembic · SQLite · React 19 · Vite · Tailwind 4 · React Router

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run

```bash
# backend  (http://localhost:8002)
cd backend
uv venv .venv --python 3.12 && uv pip install -r requirements.txt --python .venv
.venv/bin/alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --port 8002

# frontend (http://localhost:5175)
cd frontend
npm install
npm run dev
```

## Dogfood + tests

```bash
cd backend
.venv/bin/python ../scripts/dogfood.py     # end-to-end P0 scenario, seeds local db
.venv/bin/python -m pytest tests/ -q       # product invariant suite
```

## Docs

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [DOMAIN_MODEL.md](docs/DOMAIN_MODEL.md)
- [REVISION_BASELINE_MODEL.md](docs/REVISION_BASELINE_MODEL.md)
- [TRACEABILITY_MODEL.md](docs/TRACEABILITY_MODEL.md)
- [ANNOTATION_MODEL.md](docs/ANNOTATION_MODEL.md)
- [UX_FOUNDATION.md](docs/UX_FOUNDATION.md)
- [P0_ACCEPTANCE.md](docs/P0_ACCEPTANCE.md)
- [PRODUCT_HANDOVER.md](docs/PRODUCT_HANDOVER.md) (original handover, reference)
