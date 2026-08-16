# P5 — PostgreSQL Readiness

## Status: PARTIAL (validated, not full-suite tested)

- **Target:** `postgresql+psycopg://…` via `DATABASE_URL` env (SQLite remains the
  local-dev fallback). `app/db.py` and `alembic/env.py` both honor `DATABASE_URL`.
- **Validated against a real PostgreSQL 16 container:**
  - `alembic upgrade head` — full migration chain (P0→P5) succeeds.
  - Application insert/read smoke via `SessionLocal` succeeds.
- **Full pytest suite was NOT run against PostgreSQL** (suite is SQLite-oriented;
  running it on postgres is a P5 follow-up). Report as PARTIAL, not PASS.

## Known postgres reflection nits (2, pre-existing)

`alembic check` against postgres reports two autogenerate comparison artifacts
that are NOT present on SQLite (SQLite drift is NONE):

1. `architecture_nodes` unnamed `UniqueConstraint("diagram_id","semantic_id")` —
   the metadata-declared unnamed constraint reflects under a different
   auto-generated name on postgres.
2. `artifacts.current_draft_revision_id` `use_alter=True` FK — the metadata's
   `use_alter` declaration is not recognized by postgres reflection comparison.

Neither affects runtime correctness (the constraints exist in the DB). To close
them, give both an explicit name in the model and add a matching migration.

## Types audit

- JSON columns → `JSON` (works on postgres `JSONB`-compatible; sqlite `JSON`).
- Enums (`Enum(RevisionStatus)` etc.) → SQLAlchemy `Enum` creates native postgres
  enums; no `create_type=False` is used, which is acceptable for a single-schema
  deployment.
- `DateTime(timezone=True)` → `TIMESTAMPTZ` on postgres.
- Unique constraints, indexes, and FKs are declared explicitly.
- Concurrency: confirmation uniqueness is enforced by a DB unique constraint
  (works on both sqlite and postgres).

## Recommendation

Adopt PostgreSQL for production deployment; keep SQLite for local dev. Before
GA, run the full pytest suite once against PostgreSQL and resolve the 2
reflection nits above.
