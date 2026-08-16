# Operations Runbook (Release Candidate)

## Run (local dev)

```
cd backend && .venv/bin/alembic upgrade head
AUTH_MODE=local .venv/bin/uvicorn app.main:app --port 8000
cd frontend && npm run dev
```

## Run (production mode)

```
export AUTH_MODE=account_again
export ACCOUNT_AGAIN_URL=https://...            # Account Again origin
export DOCUMENT_AGAIN_CLIENT_SECRET=...         # AA service secret for DOCUMENT_AGAIN
export CONDUCTOR_MAIN_URL=https://.../api       # Conductor Main relay
export DATABASE_URL=postgresql+psycopg://...    # production DB (SQLite fallback otherwise)
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Health / readiness / metrics

- `GET /api/health` — process alive.
- `GET /api/readiness` — DB + Account Again (when in account_again mode).
  PM/QA deliberately do NOT gate readiness.
- `GET /api/metrics` — in-process counters (outbox pending/failed, handoff
  sent/ack, auth denied, confirmation completed, export generated).
- `GET /api/rc-readiness` — config, migration head, dependency reachability,
  outbox state (operator evidence).

## Failure / replay

- `GET /api/outbox/{id}` — inspect a failed delivery + its immutable payload.
- `POST /api/outbox/{id}/retry` — safely re-enqueue a FAILED event (payload is
  never mutated; replay is audited).

## PNG export dependency

PNG exports (ERD/flow/architecture) use CairoSVG and require the cairo native
library (`brew install cairo` on macOS; `libcairo2` on Debian/Ubuntu).

## Logs

Structured JSON on stdout; every request carries `X-Request-Id`; no secrets are
ever logged.

## Known limitations

See `docs/KNOWN_LIMITATIONS.md`.
