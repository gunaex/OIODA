import os
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .account_client import AUTH_MODE, ACCOUNT_AGAIN_URL
from .db import Base, DATABASE_URL, engine
from . import models  # noqa: F401 — register ORM tables with Base.metadata
from .observability import configure_logging, log, metrics, set_request_id, started_at
from .routers.api import router
from .routers.deps import tenant_scope
from .services import DomainError

configure_logging()

# Local schema bootstrap: create any missing tables (idempotent — never alters
# existing tables). Production migrations remain Alembic's job; this only
# ensures newly-introduced tables exist on existing development databases.
Base.metadata.create_all(bind=engine)


def _ensure_dev_columns() -> None:
    """Idempotent additive-column bootstrap for existing SQLite dev databases.

    ``create_all`` never ALTERs existing tables, so columns introduced after a
    table first existed are added here (guarded by PRAGMA table_info). This runs
    only for SQLite dev databases; production (Postgres) uses Alembic."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    additions = {
        "change_requests": {
            "title": "VARCHAR(200)",
            "requested_date": "DATE",
            "source_reference": "VARCHAR(300)",
            "notes": "TEXT",
            "updated_at": "DATETIME",
        },
        "projects": {
            "metadata": "JSON",
            "lifecycle_state": "VARCHAR(20)",
            "cloned_from_project_id": "VARCHAR(40)",
            "cloned_at": "DATETIME",
            "cloned_by": "VARCHAR(100)",
            "clone_policy_version": "VARCHAR(20)",
        },
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            existing = {
                row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))
            }
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
        # Backfill: SQLite ADD COLUMN leaves NULL on pre-existing rows; the
        # ORM default only applies to new inserts.
        conn.execute(text("UPDATE projects SET lifecycle_state = 'ACTIVE' WHERE lifecycle_state IS NULL"))


_ensure_dev_columns()

app = FastAPI(title="Document Again", version="0.1.0", dependencies=[Depends(tenant_scope)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    set_request_id(rid)
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    response.headers["X-Request-Id"] = rid
    log.info("request", extra={"method": request.method, "path": request.url.path,
                               "status": response.status_code, "duration_ms": duration_ms})
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(router)


@app.get("/api/health")
def health():
    """Liveness: the process is alive. Does not imply dependencies are ready."""
    return {"status": "ok", "service": "document-again"}


@app.get("/api/readiness")
def readiness():
    """Readiness: dependencies required for production mode are usable.

    - database: always required
    - Account Again connectivity: required only in AUTH_MODE=account_again
    PM/QA availability deliberately does NOT gate readiness — Document Again
    remains a usable design workspace while those are down (their delivery is
    durable + retried via the outbox).
    """
    checks = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    checks["authMode"] = AUTH_MODE
    if AUTH_MODE == "account_again":
        try:
            import httpx
            r = httpx.get(f"{ACCOUNT_AGAIN_URL}/api/v1/health", timeout=3.0)
            checks["accountAgain"] = "ok" if r.status_code == 200 else f"status {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            checks["accountAgain"] = f"unreachable: {exc}"
            return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    else:
        checks["accountAgain"] = "not required in local mode"

    ready = checks.get("database") == "ok"
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/api/metrics")
def get_metrics():
    """In-process operational counters (no heavyweight monitoring infra)."""
    return {
        "uptime_seconds": round(time.monotonic() - started_at(), 1),
        "counters": metrics.snapshot(),
    }


@app.get("/api/rc-readiness")
def rc_readiness():
    """Release-candidate readiness snapshot (configuration, migration head,
    dependency reachability, outbox state). Operator evidence, not a full
    admin console."""
    from sqlalchemy import text
    head = None
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            head = row[0] if row else None
    except Exception:  # noqa: BLE001
        head = "unknown"

    import httpx
    conductor = "unchecked"
    try:
        r = httpx.get(f"{os.environ.get('CONDUCTOR_MAIN_URL', 'http://localhost:8010/api').rstrip('/')}/health", timeout=3.0)
        conductor = "reachable" if r.status_code == 200 else f"status {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        conductor = f"unreachable: {exc}"

    counters = metrics.snapshot()
    return {
        "service": "document-again",
        "version": "0.1.0",
        "auth_mode": AUTH_MODE,
        "database": (DATABASE_URL or "sqlite").split("://")[0],
        "migration_head": head,
        "account_again": ACCOUNT_AGAIN_URL or "not configured",
        "conductor_main": conductor,
        "outbox_pending": max(counters.get("outbox_pending", 0) - counters.get("outbox_delivered", 0) - counters.get("outbox_failed", 0), 0),
        "outbox_failed": counters.get("outbox_failed", 0),
        "confirmation_completed": counters.get("confirmation_completed", 0),
        "auth_denied": counters.get("auth_denied", 0),
    }
