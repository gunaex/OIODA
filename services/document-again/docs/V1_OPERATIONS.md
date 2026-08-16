# Document Again v1.0 — Operations

## Run (local dev)

```
cd backend && .venv/bin/alembic upgrade head
AUTH_MODE=local .venv/bin/uvicorn app.main:app --port 8000
cd frontend && npm run dev
```

## Run (production)

```
export AUTH_MODE=account_again
export ACCOUNT_AGAIN_URL=https://...          # Account Again origin
export DOCUMENT_AGAIN_CLIENT_SECRET=...       # AA service secret for DOCUMENT_AGAIN
export CONDUCTOR_MAIN_URL=https://.../api     # Conductor Main relay
export DATABASE_URL=postgresql+psycopg://...  # production DB
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `/api/health` — liveness. `/api/readiness` — DB + Account Again (when in
  account_again mode). `/api/metrics` — counters. `/api/rc-readiness` — operator
  evidence (config, migration head, dependency reachability, outbox state).

## Failure / replay

- `GET /api/outbox/{id}` inspect; `POST /api/outbox/{id}/retry` safe re-enqueue
  (payload immutable, audited).

## PNG export

Requires cairo native library (`brew install cairo` / `libcairo2`).

## Logs

Structured JSON on stdout; `X-Request-Id` correlation; no secrets logged.
